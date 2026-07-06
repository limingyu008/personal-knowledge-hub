import json
import logging
from typing import List, Optional

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import DATA_DIR, get_connection, init_db, parse_json
from .document_parser import ParseError, SUPPORTED_SUFFIXES, parse_document, split_chunks
from .logging_config import configure_logging
from .vector_store import VectorStoreError, delete_item_vectors, enabled as vector_enabled, query_chunks, upsert_chunks


log_file = configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Personal Knowledge Hub", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class KnowledgeCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(default="", max_length=20000)
    summary: str = Field(default="", max_length=1000)
    source: str = "手动笔记"
    source_url: str = Field(default="", alias="sourceUrl")
    tags: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class KnowledgeUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(default="", max_length=20000)
    summary: str = Field(default="", max_length=1000)
    source: str = "手动笔记"
    source_url: str = Field(default="", alias="sourceUrl")
    tags: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class WebImportRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    url: str = Field(default="", max_length=1000)
    content: str = Field(default="", max_length=30000)
    summary: str = Field(default="", max_length=1200)
    tags: List[str] = Field(default_factory=list)


class ContextRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = 8
    token_limit: int = Field(default=3200, alias="tokenLimit")

    model_config = {"populate_by_name": True}


class ModelConfigRequest(BaseModel):
    base_url: str = ""
    api_key: str = Field(default="", alias="apiKey")
    chat_base_url: str = Field(default="", alias="chatBaseUrl")
    chat_api_key: str = Field(default="", alias="chatApiKey")
    chat_model: str = ""
    embedding_base_url: str = Field(default="", alias="embeddingBaseUrl")
    embedding_api_key: str = Field(default="", alias="embeddingApiKey")
    embedding_model: str = ""
    timeout_seconds: int = 45
    chat_timeout_seconds: int = Field(default=45, alias="chatTimeoutSeconds")
    embedding_timeout_seconds: int = Field(default=45, alias="embeddingTimeoutSeconds")
    enabled: bool = False
    parser_mode: str = Field(default="local", alias="parserMode")
    mineru_base_url: str = Field(default="", alias="mineruBaseUrl")
    mineru_api_key: str = Field(default="", alias="mineruApiKey")
    mineru_model: str = Field(default="mineru-vl", alias="mineruModel")
    mineru_only_md: bool = Field(default=True, alias="mineruOnlyMd")
    retrieval_mode: str = Field(default="keyword", alias="retrievalMode")
    chroma_mode: str = Field(default="local", alias="chromaMode")
    chroma_path: str = Field(default="", alias="chromaPath")
    chroma_host: str = Field(default="localhost", alias="chromaHost")
    chroma_port: int = Field(default=8000, alias="chromaPort")
    chroma_ssl: bool = Field(default=False, alias="chromaSsl")
    chroma_api_key: str = Field(default="", alias="chromaApiKey")
    chroma_collection: str = Field(default="personal_knowledge_chunks", alias="chromaCollection")

    model_config = {"populate_by_name": True}


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Personal Knowledge Hub 启动完成，日志文件：%s", log_file)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "personal-knowledge-hub"}


@app.get("/api/dashboard")
def dashboard():
    with get_connection() as conn:
        total_items = conn.execute("SELECT COUNT(*) AS total FROM knowledge_items").fetchone()["total"]
        files = conn.execute(
            "SELECT COUNT(*) AS total FROM knowledge_items WHERE source IN ('PDF', 'Word', 'Markdown', 'TXT')"
        ).fetchone()["total"]
        webpages = conn.execute(
            "SELECT COUNT(*) AS total FROM knowledge_items WHERE source = '网页'"
        ).fetchone()["total"]
        entities = conn.execute("SELECT COUNT(*) AS total FROM graph_nodes").fetchone()["total"]
        relations = conn.execute("SELECT COUNT(*) AS total FROM graph_edges").fetchone()["total"]
        failed_jobs = conn.execute(
            "SELECT COUNT(*) AS total FROM processing_jobs WHERE status = '失败'"
        ).fetchone()["total"]

    return {
        "metrics": [
            {"label": "知识条目", "value": str(total_items), "delta": "SQLite live", "tone": "good"},
            {"label": "文件", "value": str(files), "delta": "PDF / Word / MD", "tone": "neutral"},
            {"label": "网页收藏", "value": str(webpages), "delta": "插件入口", "tone": "good"},
            {"label": "实体", "value": str(entities), "delta": "轻量图谱", "tone": "warn"},
            {"label": "关系", "value": str(relations), "delta": "含待确认", "tone": "good"},
            {"label": "失败任务", "value": str(failed_jobs), "delta": "可重试", "tone": "bad" if failed_jobs else "good"},
        ],
        "pipeline": [
            {"name": "文本抽取", "desc": "Markdown / PDF / Word / Web", "status": "success"},
            {"name": "内容切块", "desc": "chunk pipeline ready", "status": "success"},
            {"name": "实体关系", "desc": "待接入模型抽取", "status": "warning"},
            {"name": "向量索引", "desc": "待接入 embedding", "status": "warning"},
        ],
        "activities": [
            {"title": "本地知识库已连接", "desc": "前端正在从 FastAPI + SQLite 读取数据", "time": "Now"},
            {"title": "上下文调试台待接入模型", "desc": "当前返回基于关键词的上下文模拟结果", "time": "MVP"},
        ],
    }


@app.get("/api/knowledge-items")
def list_knowledge_items(keyword: Optional[str] = None):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, content, source, status, status_type, tags_json, updated_at
            FROM knowledge_items
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

    items = [knowledge_row(row) for row in rows]
    if keyword:
        keyword_lower = keyword.lower()
        items = [
            item for item in items
            if keyword_lower in (item["title"] + item["summary"] + "".join(item["tags"])).lower()
        ]
    return items


@app.post("/api/knowledge-items")
def create_knowledge_item(request: KnowledgeCreateRequest):
    return insert_knowledge_item(
        title=request.title,
        content=request.content,
        summary=request.summary,
        source=request.source,
        source_url=request.source_url,
        tags=request.tags,
    )


@app.patch("/api/knowledge-items/{item_id}")
def update_knowledge_item(item_id: int, request: KnowledgeUpdateRequest):
    summary = request.summary or make_summary(request.content)
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM knowledge_items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        conn.execute(
            """
            UPDATE knowledge_items
            SET title = ?, summary = ?, content = ?, source = ?, source_url = ?,
                tags_json = ?, updated_at = date('now')
            WHERE id = ?
            """,
            (request.title, summary, request.content, request.source, request.source_url, to_json(request.tags), item_id),
        )
        row = conn.execute(
            """
            SELECT id, title, summary, content, source, source_url, status, status_type, tags_json, updated_at
            FROM knowledge_items WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
    item = knowledge_row(row)
    chunks = split_chunks(item["content"])
    save_chunks(item["id"], chunks)
    if index_vectors:
        try:
            upsert_chunks(item, chunks, get_model_config())
        except VectorStoreError as exc:
            logger.exception("知识条目向量索引失败，item_id：%s，title：%s", item["id"], item["title"])
            item["vectorError"] = str(exc)
    return item


@app.delete("/api/knowledge-items/{item_id}")
def delete_knowledge_item(item_id: int):
    config = get_model_config()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
    delete_item_vectors(item_id, config)
    return {"ok": True}


@app.get("/api/knowledge-items/{item_id}/chunks")
def list_knowledge_chunks(item_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, chunk_index, content, token_estimate
            FROM knowledge_chunks
            WHERE knowledge_item_id = ?
            ORDER BY chunk_index ASC
            """,
            (item_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "chunkIndex": row["chunk_index"],
            "content": row["content"],
            "tokenEstimate": row["token_estimate"],
        }
        for row in rows
    ]


@app.post("/api/import/manual")
def import_manual(request: KnowledgeCreateRequest):
    return insert_knowledge_item(
        title=request.title,
        content=request.content,
        summary=request.summary,
        source=request.source or "手动笔记",
        source_url=request.source_url,
        tags=request.tags,
    )


@app.post("/api/import/webpage")
def import_webpage(request: WebImportRequest):
    return insert_knowledge_item(
        title=request.title,
        content=request.content or request.url,
        summary=request.summary,
        source="网页",
        source_url=request.url,
        tags=request.tags or ["网页"],
    )


@app.post("/api/import/file")
async def import_file(file: UploadFile = File(...)):
    filename = file.filename or "untitled.txt"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    logger.info("收到文件上传，文件名：%s，后缀：%s", filename, suffix)
    if suffix not in SUPPORTED_SUFFIXES:
        logger.warning("文件类型不支持，文件名：%s，后缀：%s", filename, suffix)
        raise HTTPException(status_code=400, detail="暂只支持 TXT、Markdown、PDF、Word .docx 文件")

    raw = await file.read()
    logger.info("文件读取完成，文件名：%s，大小：%s bytes", filename, len(raw))
    upload_dir = DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    file_path = upload_dir / safe_name
    file_path.write_bytes(raw)

    source = source_from_suffix(suffix)
    parser_config = get_model_config()
    logger.info("开始导入文件，文件名：%s，来源：%s，解析模式：%s，保存路径：%s", filename, source, parser_config.get("parserMode"), file_path)
    try:
        content = parse_document(file_path, parser_config)
        logger.info("文件解析成功，文件名：%s，文本长度：%s", filename, len(content or ""))
    except ParseError as exc:
        logger.exception("文件解析失败，文件名：%s", filename)
        item = insert_knowledge_item(
            title=filename,
            content="",
            summary=str(exc),
            source=source,
            source_url=str(file_path),
            tags=[source, "文件", "解析失败"],
            status="解析失败",
            status_type="danger",
            create_job=False,
            index_vectors=False,
        )
        create_processing_job_for_item(item["id"], filename, source, "失败", "danger", str(exc), failed_step="抽取")
        return item

    item = insert_knowledge_item(
        title=filename,
        content=content,
        summary="",
        source=source,
        source_url=str(file_path),
        tags=[source, "文件"],
        create_job=False,
        index_vectors=False,
    )
    chunks = split_chunks(content)
    save_chunks(item["id"], chunks)
    try:
        upsert_chunks(item, chunks, get_model_config())
        logger.info("文件向量索引处理完成，文件名：%s，chunk 数：%s", filename, len(chunks))
    except VectorStoreError as exc:
        logger.warning("文件已入库但向量索引失败，文件名：%s，原因：%s", filename, exc)
        create_processing_job_for_item(item["id"], filename, source, "失败", "danger", str(exc), failed_step="向量")
        item["chunkCount"] = len(chunks)
        item["vectorError"] = str(exc)
        return item
    create_processing_job_for_item(item["id"], filename, source, "待确认", "warning", "", failed_step="")
    item["chunkCount"] = len(chunks)
    return item


@app.post("/api/extension/save-page")
def extension_save_page(request: WebImportRequest):
    return import_webpage(request)


@app.post("/api/extension/context")
def extension_context(request: ContextRequest):
    return generate_context(request)


@app.get("/api/jobs")
def list_jobs():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, source, status, tone, duration, error, steps_json
            FROM processing_jobs
            ORDER BY id DESC
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "source": row["source"],
            "status": row["status"],
            "tone": row["tone"],
            "duration": row["duration"],
            "error": row["error"],
            "steps": parse_json(row["steps_json"], []),
        }
        for row in rows
    ]


@app.get("/api/graph")
def graph():
    with get_connection() as conn:
        nodes = conn.execute("SELECT id, label, type_key, x, y FROM graph_nodes").fetchall()
        edges = conn.execute("SELECT id, from_node, to_node, status, label FROM graph_edges").fetchall()
    return {
        "nodes": [
            {"id": row["id"], "label": row["label"], "typeKey": row["type_key"], "x": row["x"], "y": row["y"]}
            for row in nodes
        ],
        "edges": [
            {"id": row["id"], "from": row["from_node"], "to": row["to_node"], "status": row["status"], "label": row["label"]}
            for row in edges
        ],
    }


@app.post("/api/context/generate")
def generate_context(request: ContextRequest):
    config = get_model_config()
    token_limit = normalize_token_limit(request.token_limit)
    top_k = normalize_top_k(request.top_k)

    retrieval_mode = "vector" if vector_enabled(config) else "keyword"
    raw_hits = []
    filtered_hits = []
    try:
        if retrieval_mode == "vector":
            raw_hits = query_chunks(request.question, max(top_k * 3, top_k), config)
            context_items, filtered_hits = prepare_vector_context_items(raw_hits, top_k)
        else:
            raw_hits = rank_context_items(request.question)
            context_items = prepare_keyword_context_items(raw_hits[:top_k])
    except VectorStoreError as exc:
        prompt = "# 个人上下文\n向量检索失败：{}。请检查 Embedding API、API Key、Chroma 配置，或切换为关键词检索。".format(exc)
        prompt += "\n\n# 当前问题\n" + request.question
        return {
            "hits": [],
            "prompt": prompt,
            "tokenEstimate": estimate_tokens(prompt),
            "debug": build_retrieval_debug("vector", request.question, top_k, token_limit, [], [], [], [str(exc)]),
        }

    prompt = build_context_prompt(context_items, request.question, token_limit)
    return {
        "hits": format_context_hits(context_items),
        "prompt": prompt,
        "tokenEstimate": estimate_tokens(prompt),
        "debug": build_retrieval_debug(retrieval_mode, request.question, top_k, token_limit, raw_hits, context_items, filtered_hits, []),
    }


@app.get("/api/model-config")
def get_model_config():
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT base_url, api_key, chat_base_url, chat_api_key, chat_model,
                   embedding_base_url, embedding_api_key, embedding_model,
                   timeout_seconds, chat_timeout_seconds, embedding_timeout_seconds, enabled,
                   parser_mode, mineru_base_url, mineru_api_key, mineru_model, mineru_only_md,
                   retrieval_mode, chroma_mode, chroma_path, chroma_host, chroma_port, chroma_ssl, chroma_api_key, chroma_collection
            FROM model_config WHERE id = 1
            """
        ).fetchone()
    legacy_base_url = row["base_url"]
    legacy_api_key = row["api_key"]
    return {
        "baseUrl": legacy_base_url,
        "apiKey": legacy_api_key,
        "chatBaseUrl": row["chat_base_url"] or legacy_base_url,
        "chatApiKey": row["chat_api_key"] or legacy_api_key,
        "chatModel": row["chat_model"],
        "embeddingBaseUrl": row["embedding_base_url"] or legacy_base_url,
        "embeddingApiKey": row["embedding_api_key"] or legacy_api_key,
        "embeddingModel": row["embedding_model"],
        "timeoutSeconds": row["timeout_seconds"],
        "chatTimeoutSeconds": row["chat_timeout_seconds"] or row["timeout_seconds"],
        "embeddingTimeoutSeconds": row["embedding_timeout_seconds"] or row["timeout_seconds"],
        "enabled": bool(row["enabled"]),
        "parserMode": row["parser_mode"],
        "mineruBaseUrl": row["mineru_base_url"],
        "mineruApiKey": row["mineru_api_key"],
        "mineruModel": row["mineru_model"] or "mineru-vl",
        "mineruOnlyMd": bool(row["mineru_only_md"]),
        "retrievalMode": row["retrieval_mode"],
        "chromaMode": row["chroma_mode"] or "local",
        "chromaPath": row["chroma_path"],
        "chromaHost": row["chroma_host"] or "localhost",
        "chromaPort": row["chroma_port"] or 8000,
        "chromaSsl": bool(row["chroma_ssl"]),
        "chromaApiKey": row["chroma_api_key"],
        "chromaCollection": row["chroma_collection"],
    }


@app.post("/api/model-config")
def save_model_config(request: ModelConfigRequest):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO model_config
                (id, base_url, api_key, chat_base_url, chat_api_key, chat_model,
                 embedding_base_url, embedding_api_key, embedding_model,
                 timeout_seconds, chat_timeout_seconds, embedding_timeout_seconds, enabled,
                 parser_mode, mineru_base_url, mineru_api_key, mineru_model, mineru_only_md, retrieval_mode, chroma_mode, chroma_path, chroma_host, chroma_port, chroma_ssl, chroma_api_key, chroma_collection)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                base_url = excluded.base_url,
                api_key = excluded.api_key,
                chat_base_url = excluded.chat_base_url,
                chat_api_key = excluded.chat_api_key,
                chat_model = excluded.chat_model,
                embedding_base_url = excluded.embedding_base_url,
                embedding_api_key = excluded.embedding_api_key,
                embedding_model = excluded.embedding_model,
                timeout_seconds = excluded.timeout_seconds,
                chat_timeout_seconds = excluded.chat_timeout_seconds,
                embedding_timeout_seconds = excluded.embedding_timeout_seconds,
                enabled = excluded.enabled,
                parser_mode = excluded.parser_mode,
                mineru_base_url = excluded.mineru_base_url,
                mineru_api_key = excluded.mineru_api_key,
                mineru_model = excluded.mineru_model,
                mineru_only_md = excluded.mineru_only_md,
                retrieval_mode = excluded.retrieval_mode,
                chroma_mode = excluded.chroma_mode,
                chroma_path = excluded.chroma_path,
                chroma_host = excluded.chroma_host,
                chroma_port = excluded.chroma_port,
                chroma_ssl = excluded.chroma_ssl,
                chroma_api_key = excluded.chroma_api_key,
                chroma_collection = excluded.chroma_collection
            """,
            (
                request.chat_base_url or request.base_url,
                request.chat_api_key or request.api_key,
                request.chat_base_url or request.base_url,
                request.chat_api_key or request.api_key,
                request.chat_model,
                request.embedding_base_url or request.base_url,
                request.embedding_api_key or request.api_key,
                request.embedding_model,
                request.timeout_seconds,
                request.chat_timeout_seconds or request.timeout_seconds,
                request.embedding_timeout_seconds or request.timeout_seconds,
                1 if request.enabled else 0,
                request.parser_mode if request.parser_mode in {"local", "mineru"} else "local",
                request.mineru_base_url,
                request.mineru_api_key,
                request.mineru_model or "mineru-vl",
                1 if request.mineru_only_md else 0,
                request.retrieval_mode if request.retrieval_mode in {"keyword", "vector"} else "keyword",
                request.chroma_mode if request.chroma_mode in {"local", "http"} else "local",
                request.chroma_path,
                request.chroma_host or "localhost",
                request.chroma_port or 8000,
                1 if request.chroma_ssl else 0,
                request.chroma_api_key,
                request.chroma_collection or "personal_knowledge_chunks",
            ),
        )
    return get_model_config()


@app.post("/api/model-config/test-chat")
def test_chat_model():
    config = get_model_config()
    if not config["chatBaseUrl"] or not config["chatApiKey"] or not config["chatModel"]:
        return {"ok": False, "message": "请先配置 Chat Base URL、API Key 和 Chat Model"}
    try:
        response = requests.post(
            "{}/chat/completions".format(config["chatBaseUrl"].rstrip("/")),
            headers={
                "Authorization": "Bearer {}".format(config["chatApiKey"]),
                "Content-Type": "application/json",
            },
            json={
                "model": config["chatModel"],
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 8,
            },
            timeout=int(config["chatTimeoutSeconds"] or config["timeoutSeconds"] or 45),
        )
        response.raise_for_status()
    except Exception as exc:
        return {"ok": False, "message": "Chat API 调用失败：{}".format(exc)}
    return {"ok": True, "message": "Chat API 连通性正常。"}


@app.post("/api/model-config/test-embedding")
def test_embedding_model():
    config = get_model_config()
    if not config["embeddingBaseUrl"] or not config["embeddingApiKey"] or not config["embeddingModel"]:
        return {"ok": False, "message": "请先配置 Embedding Base URL、API Key 和 Embedding Model"}
    try:
        from .vector_store import embed_texts
        embed_texts(["embedding test"], config)
    except VectorStoreError as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": "Embedding API 连通性正常。"}


@app.post("/api/vector/rebuild")
def rebuild_vector_index():
    config = get_model_config()
    if not vector_enabled(config):
        return {"ok": False, "message": "当前检索模式不是向量检索，请先切换后保存配置。"}

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, content, source, source_url, status, status_type, tags_json, updated_at
            FROM knowledge_items
            ORDER BY id ASC
            """
        ).fetchall()

    indexed = 0
    failed = []
    for row in rows:
        item = knowledge_row(row)
        chunks = split_chunks(item["content"])
        save_chunks(item["id"], chunks)
        try:
            upsert_chunks(item, chunks, config)
            indexed += len(chunks)
        except VectorStoreError as exc:
            failed.append({"id": item["id"], "title": item["title"], "error": str(exc)})

    return {"ok": not failed, "indexedChunks": indexed, "failed": failed}


def knowledge_row(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"],
        "content": row["content"],
        "source": row["source"],
        "sourceUrl": row["source_url"] if "source_url" in row.keys() else "",
        "status": row["status"],
        "statusType": row["status_type"],
        "tags": parse_json(row["tags_json"], []),
        "updatedAt": row["updated_at"],
    }


def to_json(value):
    return json.dumps(value, ensure_ascii=False)


def estimate_tokens(text):
    return max(1, int(len(text) / 1.8))


def normalize_top_k(value):
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        top_k = 8
    return max(1, min(top_k, 20))


def normalize_token_limit(value):
    try:
        token_limit = int(value)
    except (TypeError, ValueError):
        token_limit = 3200
    return max(600, min(token_limit, 12000))


def prepare_keyword_context_items(items):
    prepared = []
    for item in items:
        item = dict(item)
        item["chunks"] = []
        item["reference"] = build_reference(item)
        prepared.append(item)
    return prepared


def prepare_vector_context_items(raw_hits, top_k):
    grouped = {}
    filtered = []
    for hit in raw_hits:
        score = float(hit.get("score") or 0)
        if score < 0.15:
            filtered.append(build_filtered_hit(hit, "分数低于阈值 0.15"))
            continue

        item_id = hit.get("itemId")
        group_key = str(item_id or hit.get("title") or len(grouped))
        group = grouped.setdefault(group_key, {
            "id": item_id,
            "title": hit.get("title") or "未命名知识",
            "summary": hit.get("summary") or "",
            "source": hit.get("source") or "",
            "score": score,
            "chunks": [],
            "chunkIndexes": [],
            "distances": [],
        })
        group["score"] = max(group["score"], score)
        chunk_content = (hit.get("content") or "").strip()
        if chunk_content and chunk_content not in [chunk["content"] for chunk in group["chunks"]]:
            group["chunks"].append({
                "content": chunk_content,
                "score": score,
                "chunkIndex": hit.get("chunkIndex"),
            })
        elif chunk_content:
            filtered.append(build_filtered_hit(hit, "同一知识条目内重复 chunk"))
        if hit.get("chunkIndex") is not None:
            group["chunkIndexes"].append(hit.get("chunkIndex"))
        if hit.get("distance") is not None:
            group["distances"].append(hit.get("distance"))

    ranked_items = sorted(grouped.values(), key=lambda item: item["score"], reverse=True)
    items = ranked_items[:top_k]
    for item in ranked_items[top_k:]:
        filtered.append({
            "title": item.get("title") or "未命名知识",
            "score": round(float(item.get("score") or 0), 4),
            "reason": "Top K 聚合后截断",
        })
    enrich_context_items_from_db(items)

    for item in items:
        item["chunks"] = sorted(item["chunks"], key=lambda chunk: chunk["score"], reverse=True)[:2]
        chunk_indexes = sorted({index for index in item.get("chunkIndexes", []) if index is not None})
        item["reason"] = "Chroma 向量召回，命中 chunk：{}，已按知识条目去重聚合。".format(
            ", ".join(str(index) for index in chunk_indexes[:6]) if chunk_indexes else "-"
        )
        item["reference"] = build_reference(item)
    return items, filtered


def build_filtered_hit(hit, reason):
    return {
        "title": hit.get("title") or "未命名知识",
        "itemId": hit.get("itemId"),
        "chunkIndex": hit.get("chunkIndex"),
        "score": round(float(hit.get("score") or 0), 4),
        "distance": hit.get("distance"),
        "reason": reason,
    }


def enrich_context_items_from_db(items):
    item_ids = [int(item["id"]) for item in items if item.get("id") is not None]
    if not item_ids:
        return

    placeholders = ",".join("?" for _ in item_ids)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, source, source_url, status, tags_json, updated_at
            FROM knowledge_items
            WHERE id IN ({})
            """.format(placeholders),
            item_ids,
        ).fetchall()

    by_id = {row["id"]: row for row in rows}
    for item in items:
        row = by_id.get(item.get("id"))
        if not row:
            continue
        item["title"] = row["title"]
        item["summary"] = row["summary"] or item.get("summary") or ""
        item["source"] = row["source"]
        item["sourceUrl"] = row["source_url"]
        item["status"] = row["status"]
        item["tags"] = parse_json(row["tags_json"], [])
        item["updatedAt"] = row["updated_at"]


def build_reference(item):
    parts = []
    if item.get("source"):
        parts.append(str(item["source"]))
    if item.get("sourceUrl"):
        parts.append(str(item["sourceUrl"]))
    if item.get("updatedAt"):
        parts.append("updated {}".format(item["updatedAt"]))
    return " / ".join(parts) or "本地知识库"


def build_retrieval_debug(mode, question, top_k, token_limit, raw_hits, context_items, filtered_hits, errors):
    return {
        "mode": mode,
        "question": question,
        "topK": top_k,
        "tokenLimit": token_limit,
        "rawCount": len(raw_hits),
        "selectedCount": len(context_items),
        "filteredCount": len(filtered_hits),
        "rawHits": [format_debug_raw_hit(hit) for hit in raw_hits[:30]],
        "selectedItems": [format_debug_selected_item(item) for item in context_items],
        "filteredHits": filtered_hits[:30],
        "errors": errors,
    }


def format_debug_raw_hit(hit):
    return {
        "title": hit.get("title") or "未命名知识",
        "itemId": hit.get("itemId") or hit.get("id"),
        "chunkIndex": hit.get("chunkIndex"),
        "score": round(float(hit.get("score") or 0), 4),
        "distance": hit.get("distance"),
        "reason": hit.get("reason") or "",
        "preview": normalize_context_text(hit.get("content") or hit.get("summary") or "")[:240],
    }


def format_debug_selected_item(item):
    chunks = item.get("chunks") or []
    return {
        "title": item.get("title") or "未命名知识",
        "itemId": item.get("id"),
        "score": round(float(item.get("score") or 0), 4),
        "source": item.get("source") or "",
        "reference": item.get("reference") or build_reference(item),
        "reason": item.get("reason") or "",
        "chunkCount": len(chunks),
        "chunks": [
            {
                "chunkIndex": chunk.get("chunkIndex"),
                "score": round(float(chunk.get("score") or 0), 4),
                "preview": normalize_context_text(chunk.get("content") or "")[:260],
            }
            for chunk in chunks
        ],
    }


def format_context_hits(items):
    hits = []
    for item in items:
        reason = item.get("reason") or "命中标题、摘要、标签或切块，已纳入上下文候选。"
        if item.get("reference"):
            reason = "{} 来源：{}".format(reason, item["reference"])
        hits.append({
            "title": item["title"],
            "reason": reason,
            "score": "{:.2f}".format(float(item.get("score") or 0)),
        })
    return hits


def build_context_prompt(items, question, token_limit):
    header = "# 个人上下文\n"
    footer = "\n\n# 当前问题\n{}\n\n# 回答要求\n请优先引用上方已召回知识；当知识不足或冲突时，请明确指出缺口；结合项目目标、风险约束和可执行步骤回答。".format(question)
    budget = max(200, token_limit - estimate_tokens(header + footer))

    if not items:
        return header + "未召回到明确相关的知识。请谨慎回答，并指出需要补充哪些背景。" + footer

    sections = []
    used_tokens = 0
    for index, item in enumerate(items, 1):
        summary = item.get("summary") or "无摘要"
        reference = item.get("reference") or build_reference(item)
        section_head = "## [{}] {}\n- 相关分：{:.2f}\n- 来源：{}\n- 摘要：{}".format(
            index,
            item.get("title") or "未命名知识",
            float(item.get("score") or 0),
            reference,
            summary,
        )
        section_parts = [section_head]
        for chunk_index, chunk in enumerate(item.get("chunks") or [], 1):
            chunk_text = normalize_context_text(chunk.get("content") or "")
            if not chunk_text:
                continue
            section_parts.append("- 命中片段 {}：{}".format(chunk_index, chunk_text))

        section = "\n".join(section_parts)
        section_tokens = estimate_tokens(section)
        if used_tokens + section_tokens > budget:
            remaining = budget - used_tokens - estimate_tokens(section_head) - 20
            if remaining <= 120:
                break
            truncated_parts = [section_head]
            for chunk_index, chunk in enumerate(item.get("chunks") or [], 1):
                chunk_text = truncate_to_tokens(normalize_context_text(chunk.get("content") or ""), remaining)
                if chunk_text:
                    truncated_parts.append("- 命中片段 {}：{}".format(chunk_index, chunk_text))
                    break
            section = "\n".join(truncated_parts)
            sections.append(section)
            used_tokens += estimate_tokens(section)
            break

        sections.append(section)
        used_tokens += section_tokens

    if not sections:
        sections.append("未召回到可放入 token 预算的知识片段。")
    return header + "\n\n".join(sections) + footer


def normalize_context_text(text):
    return " ".join((text or "").split())


def truncate_to_tokens(text, token_limit):
    max_chars = max(80, int(token_limit * 1.8))
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def rank_context_items(question):
    terms = build_query_terms(question)
    if not terms:
        return []

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, content, source, source_url, status, status_type, tags_json, updated_at
            FROM knowledge_items
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        chunk_rows = conn.execute(
            """
            SELECT knowledge_item_id, content
            FROM knowledge_chunks
            ORDER BY chunk_index ASC
            """
        ).fetchall()

    chunks_by_item = {}
    for row in chunk_rows:
        chunks_by_item.setdefault(row["knowledge_item_id"], []).append(row["content"])

    ranked = []
    for row in rows:
        item = knowledge_row(row)
        tags_text = " ".join(item["tags"])
        chunk_text = "\n".join(chunks_by_item.get(item["id"], [])[:6])
        score, matched = score_item(
            terms,
            title=item["title"],
            summary=item["summary"],
            tags=tags_text,
            content=item["content"],
            chunks=chunk_text,
        )
        if score <= 0:
            continue
        item["score"] = normalize_score(score)
        item["reason"] = "命中关键词：{}。匹配位置：{}。".format(
            "、".join(matched["terms"][:6]),
            "、".join(matched["fields"][:4]),
        )
        ranked.append(item)

    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def build_query_terms(question):
    text = (question or "").strip().lower()
    if not text:
        return []

    terms = set()
    for token in text.replace("，", " ").replace("。", " ").replace(",", " ").split():
        if len(token) >= 2:
            terms.add(token)

    compact = "".join(text.split())
    if len(compact) >= 2:
        terms.add(compact)
    if len(compact) > 2:
        for index in range(len(compact) - 1):
            term = compact[index:index + 2]
            if not is_weak_term(term):
                terms.add(term)

    return sorted(terms, key=len, reverse=True)


def is_weak_term(term):
    weak_terms = {"的是", "一个", "这个", "那个", "什么", "怎么", "如何", "以及", "可以"}
    return term in weak_terms


def score_item(terms, title, summary, tags, content, chunks):
    fields = [
        ("标题", title or "", 7),
        ("标签", tags or "", 6),
        ("摘要", summary or "", 4),
        ("切块", chunks or "", 3),
        ("正文", content or "", 1),
    ]
    score = 0
    matched_terms = []
    matched_fields = []

    for term in terms:
        term_score = 0
        for field_name, field_text, weight in fields:
            if term in field_text.lower():
                term_score += weight
                if field_name not in matched_fields:
                    matched_fields.append(field_name)
        if term_score:
            matched_terms.append(term)
            score += term_score * max(1, len(term) / 2)

    return score, {"terms": matched_terms, "fields": matched_fields}


def normalize_score(score):
    return min(0.99, round(0.5 + (score / (score + 18)) * 0.49, 4))


def insert_knowledge_item(
    title,
    content,
    summary,
    source,
    source_url,
    tags,
    status="已入库",
    status_type="success",
    create_job=True,
    index_vectors=True,
):
    summary = summary or make_summary(content)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO knowledge_items
                (title, summary, content, source, source_url, status, status_type, tags_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'))
            """,
            (title, summary, content, source, source_url, status, status_type, to_json(tags)),
        )
        if create_job:
            create_processing_job(conn, title, source)
        row = conn.execute(
            """
            SELECT id, title, summary, content, source, source_url, status, status_type, tags_json, updated_at
            FROM knowledge_items WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    item = knowledge_row(row)
    chunks = split_chunks(item["content"])
    save_chunks(item["id"], chunks)
    if index_vectors:
        try:
            upsert_chunks(item, chunks, get_model_config())
        except VectorStoreError as exc:
            logger.exception("知识条目向量索引失败，item_id：%s，title：%s", item["id"], item["title"])
            item["vectorError"] = str(exc)
    return item


def create_processing_job(conn, title, source):
    steps = [
        {"name": "抽取", "state": "done"},
        {"name": "切块", "state": "done"},
        {"name": "摘要", "state": "done"},
        {"name": "实体", "state": "pending"},
        {"name": "向量", "state": "pending"},
    ]
    conn.execute(
        """
        INSERT INTO processing_jobs
            (title, source, status, tone, duration, error, steps_json)
        VALUES (?, ?, '待确认', 'warning', '1s', '', ?)
        """,
        (title, source, to_json(steps)),
    )


def make_summary(content):
    clean = " ".join((content or "").split())
    return clean[:180] if clean else "待生成摘要"


def source_from_suffix(suffix):
    if suffix in {"md", "markdown"}:
        return "Markdown"
    if suffix == "txt":
        return "TXT"
    if suffix == "pdf":
        return "PDF"
    if suffix == "docx":
        return "Word"
    return suffix.upper()


def save_chunks(item_id, chunks):
    with get_connection() as conn:
        conn.execute("DELETE FROM knowledge_chunks WHERE knowledge_item_id = ?", (item_id,))
        conn.executemany(
            """
            INSERT INTO knowledge_chunks
                (knowledge_item_id, chunk_index, content, token_estimate)
            VALUES (?, ?, ?, ?)
            """,
            [(item_id, index, chunk, estimate_tokens(chunk)) for index, chunk in enumerate(chunks)],
        )


def index_item_vectors(item):
    chunks = split_chunks(item.get("content") or "")
    save_chunks(item["id"], chunks)
    upsert_chunks(item, chunks, get_model_config())


def create_processing_job_for_item(item_id, title, source, status, tone, error, failed_step=""):
    states = []
    for name in ["抽取", "切块", "摘要", "实体", "向量"]:
        if status == "失败":
            state = "failed" if name == failed_step else "pending"
        elif name in {"抽取", "切块", "摘要"}:
            state = "done"
        else:
            state = "pending"
        states.append({"name": name, "state": state})

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO processing_jobs
                (title, source, status, tone, duration, error, steps_json)
            VALUES (?, ?, ?, ?, '1s', ?, ?)
            """,
            (title, source, status, tone, error, to_json(states)),
        )
