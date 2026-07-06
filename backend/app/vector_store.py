import logging
from pathlib import Path
from typing import Dict, List

import chromadb
import requests
from chromadb.config import Settings

from .database import DATA_DIR


logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    pass


def enabled(config: Dict[str, object]) -> bool:
    return (config.get("retrievalMode") or "keyword") == "vector"


def embed_texts(texts: List[str], config: Dict[str, object]) -> List[List[float]]:
    base_url = (config.get("embeddingBaseUrl") or config.get("baseUrl") or "").rstrip("/")
    api_key = config.get("embeddingApiKey") or config.get("apiKey") or ""
    model = config.get("embeddingModel") or ""
    timeout = int(config.get("embeddingTimeoutSeconds") or config.get("timeoutSeconds") or 45)

    if not base_url or not api_key or not model:
        raise VectorStoreError("向量检索需要配置 Embedding Base URL、Embedding API Key 和 Embedding Model")

    logger.info("开始调用 Embedding API，文本数量：%s，模型：%s，Base URL：%s", len(texts), model, base_url)
    try:
        response = requests.post(
            "{}/embeddings".format(base_url),
            headers={
                "Authorization": "Bearer {}".format(api_key),
                "Content-Type": "application/json",
            },
            json={"model": model, "input": texts},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        logger.info("Embedding API 调用成功，返回条数：%s", len(payload.get("data") or []))
    except Exception as exc:
        logger.exception("Embedding API 调用失败")
        raise VectorStoreError("Embedding API 调用失败：{}".format(exc)) from exc

    data = payload.get("data") or []
    embeddings = [item.get("embedding") for item in data]
    if len(embeddings) != len(texts) or any(not embedding for embedding in embeddings):
        raise VectorStoreError("Embedding API 返回结果数量异常")
    return embeddings


def get_collection(config: Dict[str, object]):
    collection_name = config.get("chromaCollection") or "personal_knowledge_chunks"
    try:
        client = create_chroma_client(config)
        return client.get_or_create_collection(name=collection_name)
    except Exception as exc:
        message = build_chroma_error_message(exc)
        if is_chroma_configuration_type_error(exc):
            logger.warning("获取 Chroma Collection 失败，collection：%s，原因：%s", collection_name, message)
        else:
            logger.exception("获取 Chroma Collection 失败，collection：%s", collection_name)
        raise VectorStoreError(message) from exc


def create_chroma_client(config: Dict[str, object]):
    mode = (config.get("chromaMode") or "local").lower()
    if mode == "http":
        host, port = normalize_chroma_endpoint(
            config.get("chromaHost") or "localhost",
            config.get("chromaPort") or 8000,
        )
        ssl = bool(config.get("chromaSsl"))
        settings = build_chroma_settings(config)
        logger.info("连接 Chroma HTTP 服务，host：%s，port：%s，ssl：%s，auth：%s", host, port, ssl, bool(settings))
        return chromadb.HttpClient(
            host=host,
            port=port,
            ssl=ssl,
            settings=settings,
            tenant="default_tenant",
            database="default_database",
        )

    chroma_path = config.get("chromaPath") or str(DATA_DIR / "chroma")
    Path(chroma_path).mkdir(parents=True, exist_ok=True)
    logger.info("连接 Chroma 本地持久化存储，path：%s", chroma_path)
    return chromadb.PersistentClient(path=chroma_path)


def normalize_chroma_endpoint(host_value: object, port_value: object):
    host = str(host_value or "localhost").strip()
    port = int(port_value or 8000)
    for scheme in ("http://", "https://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
    host = host.split("/", 1)[0]
    if ":" in host:
        possible_host, possible_port = host.rsplit(":", 1)
        if possible_port.isdigit():
            host = possible_host
            port = int(possible_port)
    return host or "localhost", port


def build_chroma_settings(config: Dict[str, object]):
    api_key = config.get("chromaApiKey") or ""
    if not api_key:
        return None
    return Settings(
        chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
        chroma_client_auth_credentials=api_key,
    )


def is_chroma_configuration_type_error(exc: Exception) -> bool:
    return isinstance(exc, KeyError) and str(exc).strip("'\"") == "_type"


def chroma_client_version() -> str:
    return getattr(chromadb, "__version__", "unknown")


def build_chroma_error_message(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    if is_chroma_configuration_type_error(exc):
        return (
            "Chroma HTTP 服务响应结构与当前 chromadb 客户端不兼容，缺少 _type 字段。"
            "当前客户端版本：{}。请确认 Chroma Server 与 Python chromadb 客户端版本一致；"
            "如果服务端为 1.4.x，请优先执行 pip install -U chromadb==1.4.1 后重启后端，"
            "或临时切换为本地持久化模式。"
        ).format(chroma_client_version())
    return "Chroma 操作失败：{}".format(message)


def upsert_chunks(item: Dict[str, object], chunks: List[str], config: Dict[str, object]):
    if not enabled(config) or not chunks:
        return

    collection = get_collection(config)
    embeddings = embed_texts(chunks, config)
    item_id = int(item["id"])
    ids = ["chunk-{}-{}".format(item_id, index) for index in range(len(chunks))]
    metadatas = [
        {
            "item_id": item_id,
            "chunk_index": index,
            "title": item.get("title") or "",
            "summary": item.get("summary") or "",
            "source": item.get("source") or "",
        }
        for index in range(len(chunks))
    ]
    delete_item_vectors(item_id, config)
    try:
        collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
    except Exception as exc:
        logger.exception("Chroma 写入失败，item_id：%s，chunk 数：%s", item_id, len(chunks))
        raise VectorStoreError(build_chroma_error_message(exc)) from exc
    logger.info("Chroma 写入完成，item_id：%s，chunk 数：%s", item_id, len(chunks))


def delete_item_vectors(item_id: int, config: Dict[str, object]):
    if not enabled(config):
        return
    try:
        collection = get_collection(config)
        collection.delete(where={"item_id": int(item_id)})
    except VectorStoreError:
        logger.warning("删除 Chroma 向量失败，item_id：%s", item_id, exc_info=True)
    except Exception:
        logger.warning("删除 Chroma 向量失败，item_id：%s", item_id, exc_info=True)


def query_chunks(question: str, top_k: int, config: Dict[str, object]):
    collection = get_collection(config)
    query_embedding = embed_texts([question], config)[0]
    try:
        result = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    except Exception as exc:
        logger.exception("Chroma 查询失败，top_k：%s", top_k)
        raise VectorStoreError(build_chroma_error_message(exc)) from exc
    logger.info("Chroma 查询完成，top_k：%s，返回文档组数：%s", top_k, len(result.get("documents", [])))

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    hits = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = float(distances[index] if index < len(distances) else 1)
        score = max(0.0, min(0.99, 1 / (1 + distance)))
        hits.append({
            "itemId": metadata.get("item_id"),
            "chunkIndex": metadata.get("chunk_index"),
            "title": metadata.get("title") or "未命名知识",
            "summary": metadata.get("summary") or document[:180],
            "source": metadata.get("source") or "",
            "content": document,
            "score": round(score, 4),
            "distance": round(distance, 6),
            "reason": "Chroma 向量检索命中 chunk，distance={:.4f}".format(distance),
        })
    return hits
