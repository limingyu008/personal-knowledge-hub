import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "personal_knowledge.db"


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '手动',
                source_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '已索引',
                status_type TEXT NOT NULL DEFAULT 'success',
                tags_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_item_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_estimate INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                tone TEXT NOT NULL,
                duration TEXT NOT NULL DEFAULT '-',
                error TEXT NOT NULL DEFAULT '',
                steps_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                type_key TEXT NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                id TEXT PRIMARY KEY,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                status TEXT NOT NULL,
                label TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS graph_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                uri TEXT NOT NULL DEFAULT 'bolt://localhost:7687',
                username TEXT NOT NULL DEFAULT 'neo4j',
                password TEXT NOT NULL DEFAULT '',
                database TEXT NOT NULL DEFAULT 'neo4j'
            );

            CREATE TABLE IF NOT EXISTS wiki_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'summary',
                content_md TEXT NOT NULL DEFAULT '',
                source_item_ids_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'published',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS wiki_compile_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_item_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                pages_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS model_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                base_url TEXT NOT NULL DEFAULT '',
                api_key TEXT NOT NULL DEFAULT '',
                chat_base_url TEXT NOT NULL DEFAULT '',
                chat_api_key TEXT NOT NULL DEFAULT '',
                chat_model TEXT NOT NULL DEFAULT '',
                embedding_base_url TEXT NOT NULL DEFAULT '',
                embedding_api_key TEXT NOT NULL DEFAULT '',
                embedding_model TEXT NOT NULL DEFAULT '',
                timeout_seconds INTEGER NOT NULL DEFAULT 45,
                chat_timeout_seconds INTEGER NOT NULL DEFAULT 45,
                embedding_timeout_seconds INTEGER NOT NULL DEFAULT 45,
                enabled INTEGER NOT NULL DEFAULT 0,
                parser_mode TEXT NOT NULL DEFAULT 'local',
                mineru_base_url TEXT NOT NULL DEFAULT '',
                mineru_api_key TEXT NOT NULL DEFAULT '',
                mineru_model TEXT NOT NULL DEFAULT 'mineru-vl',
                mineru_only_md INTEGER NOT NULL DEFAULT 1,
                retrieval_mode TEXT NOT NULL DEFAULT 'keyword',
                chroma_mode TEXT NOT NULL DEFAULT 'local',
                chroma_path TEXT NOT NULL DEFAULT '',
                chroma_host TEXT NOT NULL DEFAULT 'localhost',
                chroma_port INTEGER NOT NULL DEFAULT 8000,
                chroma_ssl INTEGER NOT NULL DEFAULT 0,
                chroma_api_key TEXT NOT NULL DEFAULT '',
                chroma_collection TEXT NOT NULL DEFAULT 'personal_knowledge_chunks'
            );
            """
        )
        ensure_column(conn, "knowledge_items", "source_url", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "api_key", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "chat_base_url", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "chat_api_key", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "embedding_base_url", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "embedding_api_key", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "chat_timeout_seconds", "INTEGER NOT NULL DEFAULT 45")
        ensure_column(conn, "model_config", "embedding_timeout_seconds", "INTEGER NOT NULL DEFAULT 45")
        ensure_column(conn, "model_config", "parser_mode", "TEXT NOT NULL DEFAULT 'local'")
        ensure_column(conn, "model_config", "mineru_base_url", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "mineru_api_key", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "mineru_model", "TEXT NOT NULL DEFAULT 'mineru-vl'")
        ensure_column(conn, "model_config", "mineru_only_md", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "model_config", "retrieval_mode", "TEXT NOT NULL DEFAULT 'keyword'")
        ensure_column(conn, "model_config", "chroma_mode", "TEXT NOT NULL DEFAULT 'local'")
        ensure_column(conn, "model_config", "chroma_path", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "chroma_host", "TEXT NOT NULL DEFAULT 'localhost'")
        ensure_column(conn, "model_config", "chroma_port", "INTEGER NOT NULL DEFAULT 8000")
        ensure_column(conn, "model_config", "chroma_ssl", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "model_config", "chroma_api_key", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "model_config", "chroma_collection", "TEXT NOT NULL DEFAULT 'personal_knowledge_chunks'")
        ensure_column(conn, "wiki_pages", "source_item_ids_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(conn, "wiki_pages", "tags_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(conn, "wiki_pages", "status", "TEXT NOT NULL DEFAULT 'published'")
        ensure_column(conn, "graph_config", "enabled", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "graph_config", "uri", "TEXT NOT NULL DEFAULT 'bolt://localhost:7687'")
        ensure_column(conn, "graph_config", "username", "TEXT NOT NULL DEFAULT 'neo4j'")
        ensure_column(conn, "graph_config", "password", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "graph_config", "database", "TEXT NOT NULL DEFAULT 'neo4j'")
        conn.execute(
            """
            INSERT INTO graph_config (id, enabled, uri, username, password, database)
            VALUES (1, 0, 'bolt://localhost:7687', 'neo4j', '', 'neo4j')
            ON CONFLICT(id) DO NOTHING
            """
        )
        seed_if_empty(conn)


def ensure_column(conn, table, column, definition):
    columns = [row["name"] for row in conn.execute("PRAGMA table_info({})".format(table)).fetchall()]
    if column not in columns:
        conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, definition))


def seed_if_empty(conn):
    count = conn.execute("SELECT COUNT(*) AS total FROM knowledge_items").fetchone()["total"]
    if count > 0:
        return

    items = [
        (
            "个人 AI 记忆层 MVP 决策",
            "第一版采用本地优先架构，浏览器插件作为入口，后端知识中枢负责知识库、图谱、模型调用和上下文生成。",
            "个人知识中枢要解决通用 AI 缺少个人上下文的问题。MVP 以本地优先、可维护知识库、知识图谱、上下文注入为核心。",
            "手动笔记",
            "已索引",
            "success",
            ["AI产品", "MVP", "架构"],
            "2026-06-26",
        ),
        (
            "机会雷达产品化路径",
            "通过 GitHub 高增长开源项目发现可复制机会，以加法/减法形成个人可运营产品。",
            "机会雷达用于发现副业机会，聚焦可复制的已有需求和开源项目，结合 AI 做分析和评分。",
            "Markdown",
            "已索引",
            "success",
            ["副业", "机会雷达"],
            "2026-06-25",
        ),
        (
            "知识图谱抽取策略",
            "实体关系由 AI 初抽，进入待确认区，人工修正后进入正式图谱，所有关系保留来源证据。",
            "图谱维护要保留证据链。AI 抽取不能直接全信，需要待确认、合并、修正和删除能力。",
            "网页",
            "待确认",
            "warning",
            ["知识图谱", "AI"],
            "2026-06-24",
        ),
        (
            "Docker 私有部署记录",
            "机会雷达采用本地编译产物上传服务器，服务器构建镜像并通过 Compose 启动。",
            "部署策略是本地 Maven/NPM 编译，上传产物到服务器，由服务器 Docker 构建镜像并通过 Compose 编排。",
            "Word",
            "解析失败",
            "danger",
            ["部署", "Docker"],
            "2026-06-23",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO knowledge_items
            (title, summary, content, source, status, status_type, tags_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(title, summary, content, source, status, status_type, json.dumps(tags, ensure_ascii=False), updated_at)
         for title, summary, content, source, status, status_type, tags, updated_at in items],
    )

    jobs = [
        (
            "个人 AI 记忆层 PRD.md",
            "Markdown",
            "成功",
            "success",
            "18s",
            "",
            [
                {"name": "抽取", "state": "done"},
                {"name": "切块", "state": "done"},
                {"name": "摘要", "state": "done"},
                {"name": "实体", "state": "done"},
                {"name": "向量", "state": "done"},
            ],
        ),
        (
            "Docker部署记录.docx",
            "Word",
            "失败",
            "danger",
            "6s",
            "Word 解析失败：文件疑似被占用，可重试。",
            [
                {"name": "抽取", "state": "failed"},
                {"name": "切块", "state": "pending"},
                {"name": "摘要", "state": "pending"},
                {"name": "实体", "state": "pending"},
                {"name": "向量", "state": "pending"},
            ],
        ),
        (
            "开源项目商业化文章",
            "网页",
            "待确认",
            "warning",
            "31s",
            "",
            [
                {"name": "抽取", "state": "done"},
                {"name": "切块", "state": "done"},
                {"name": "摘要", "state": "done"},
                {"name": "实体", "state": "warning"},
                {"name": "向量", "state": "done"},
            ],
        ),
    ]
    conn.executemany(
        """
        INSERT INTO processing_jobs
            (title, source, status, tone, duration, error, steps_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [(title, source, status, tone, duration, error, json.dumps(steps, ensure_ascii=False))
         for title, source, status, tone, duration, error, steps in jobs],
    )

    nodes = [
        ("me", "我", "person", 380, 250),
        ("hub", "知识中枢", "project", 210, 150),
        ("radar", "机会雷达", "project", 570, 145),
        ("python", "Python", "tech", 170, 340),
        ("graph", "知识图谱", "concept", 390, 85),
        ("mvp", "MVP决策", "decision", 590, 335),
        ("risk", "维护成本", "risk", 385, 430),
    ]
    conn.executemany(
        "INSERT INTO graph_nodes (id, label, type_key, x, y) VALUES (?, ?, ?, ?, ?)",
        nodes,
    )

    edges = [
        ("e1", "me", "hub", "confirmed", "规划"),
        ("e2", "hub", "python", "confirmed", "使用"),
        ("e3", "hub", "graph", "pending", "包含"),
        ("e4", "me", "radar", "confirmed", "负责"),
        ("e5", "hub", "mvp", "confirmed", "形成"),
        ("e6", "hub", "risk", "pending", "面临"),
    ]
    conn.executemany(
        "INSERT INTO graph_edges (id, from_node, to_node, status, label) VALUES (?, ?, ?, ?, ?)",
        edges,
    )

    conn.execute(
        """
        INSERT INTO model_config
            (id, base_url, api_key, chat_base_url, chat_api_key, chat_model,
             embedding_base_url, embedding_api_key, embedding_model,
             timeout_seconds, chat_timeout_seconds, embedding_timeout_seconds, enabled,
             parser_mode, mineru_base_url, mineru_api_key, mineru_model, mineru_only_md, retrieval_mode, chroma_mode, chroma_path, chroma_host, chroma_port, chroma_ssl, chroma_api_key, chroma_collection)
        VALUES (1, 'https://api.openai.com/v1', '', 'https://api.openai.com/v1', '', 'gpt-4.1-mini',
                'https://api.openai.com/v1', '', 'text-embedding-3-small',
                45, 45, 45, 0,
                'local', '', '', 'mineru-vl', 1, 'keyword', 'local', '', 'localhost', 8000, 0, '', 'personal_knowledge_chunks')
        """
    )


def parse_json(text, default):
    try:
        return json.loads(text or "")
    except json.JSONDecodeError:
        return default
