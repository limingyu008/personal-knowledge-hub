import json
import logging
from datetime import datetime

from .database import get_connection, parse_json


logger = logging.getLogger(__name__)


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_wiki_pages(keyword: str = "", page_type: str = ""):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, slug, title, type, content_md, source_item_ids_json, tags_json, status, updated_at, created_at
            FROM wiki_pages
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    pages = [wiki_page_row(row) for row in rows]
    keyword_lower = (keyword or "").strip().lower()
    if keyword_lower:
        pages = [page for page in pages if keyword_lower in (page["title"] + page["contentMd"] + "".join(page["tags"])).lower()]
    if page_type:
        pages = [page for page in pages if page["type"] == page_type]
    return pages


def get_wiki_page(page_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, slug, title, type, content_md, source_item_ids_json, tags_json, status, updated_at, created_at
            FROM wiki_pages WHERE id = ?
            """,
            (page_id,),
        ).fetchone()
    return wiki_page_row(row) if row else None


def upsert_wiki_page(page):
    slug = page["slug"]
    logger.info("写入 Wiki 页面，slug：%s，title：%s，type：%s", slug, page.get("title"), page.get("type"))
    with get_connection() as conn:
        existing = conn.execute("SELECT id, source_item_ids_json FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
        source_ids = merge_source_ids(
            parse_json(existing["source_item_ids_json"], []) if existing else [],
            page.get("sourceItemIds") or [],
        )
        conn.execute(
            """
            INSERT INTO wiki_pages
                (slug, title, type, content_md, source_item_ids_json, tags_json, status, updated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                type = excluded.type,
                content_md = excluded.content_md,
                source_item_ids_json = excluded.source_item_ids_json,
                tags_json = excluded.tags_json,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                slug,
                page.get("title") or slug,
                page.get("type") or "summary",
                page.get("contentMd") or "",
                json.dumps(source_ids, ensure_ascii=False),
                json.dumps(page.get("tags") or [], ensure_ascii=False),
                page.get("status") or "published",
                now_text(),
                now_text(),
            ),
        )
        row = conn.execute(
            """
            SELECT id, slug, title, type, content_md, source_item_ids_json, tags_json, status, updated_at, created_at
            FROM wiki_pages WHERE slug = ?
            """,
            (slug,),
        ).fetchone()
    return wiki_page_row(row)


def record_compile_log(item_id: int, title: str, status: str, message: str, pages):
    logger.info("记录 Wiki 编译日志，item_id：%s，status：%s，pages：%s", item_id, status, len(pages or []))
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO wiki_compile_logs
                (knowledge_item_id, title, status, message, pages_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, title, status, message or "", json.dumps(pages or [], ensure_ascii=False), now_text()),
        )


def list_compile_logs(limit: int = 20):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, knowledge_item_id, title, status, message, pages_json, created_at
            FROM wiki_compile_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [compile_log_row(row) for row in rows]


def wiki_page_row(row):
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "type": row["type"],
        "contentMd": row["content_md"],
        "sourceItemIds": parse_json(row["source_item_ids_json"], []),
        "tags": parse_json(row["tags_json"], []),
        "status": row["status"],
        "updatedAt": row["updated_at"],
        "createdAt": row["created_at"],
    }


def compile_log_row(row):
    return {
        "id": row["id"],
        "knowledgeItemId": row["knowledge_item_id"],
        "title": row["title"],
        "status": row["status"],
        "message": row["message"],
        "pages": parse_json(row["pages_json"], []),
        "createdAt": row["created_at"],
    }


def merge_source_ids(existing, incoming):
    merged = []
    for value in list(existing or []) + list(incoming or []):
        if value not in merged:
            merged.append(value)
    return merged
