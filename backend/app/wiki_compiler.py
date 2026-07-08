import json
import logging
import re
from typing import Dict, List

import requests

from .wiki_repository import record_compile_log, upsert_wiki_page


logger = logging.getLogger(__name__)

PAGE_TYPES = {"person", "project", "concept", "decision", "risk", "summary", "index", "log"}


class WikiCompileError(Exception):
    pass


def compile_knowledge_item_to_wiki(item: Dict[str, object], config: Dict[str, object]):
    logger.info("开始 Wiki 编译，item_id：%s，title：%s", item.get("id"), item.get("title"))
    try:
        pages, mode = build_pages(item, config)
        saved_pages = [upsert_wiki_page(normalize_page(page, item)) for page in pages]
        record_compile_log(item["id"], item.get("title") or "未命名知识", "成功", "{} 编译完成".format(mode), saved_pages)
        logger.info("Wiki 编译完成，item_id：%s，页面数：%s，mode：%s", item.get("id"), len(saved_pages), mode)
        return {"ok": True, "mode": mode, "pages": saved_pages}
    except Exception as exc:
        logger.exception("Wiki 编译失败，item_id：%s", item.get("id"))
        record_compile_log(item.get("id") or 0, item.get("title") or "未命名知识", "失败", str(exc), [])
        raise WikiCompileError(str(exc)) from exc


def build_pages(item: Dict[str, object], config: Dict[str, object]):
    if chat_configured(config):
        try:
            return call_llm_compiler(item, config), "LLM"
        except Exception as exc:
            logger.warning("LLM Wiki 编译失败，转为本地规则编译，item_id：%s，原因：%s", item.get("id"), exc)
    return fallback_pages(item), "local-fallback"


def chat_configured(config: Dict[str, object]) -> bool:
    return bool(config.get("chatBaseUrl") and config.get("chatApiKey") and config.get("chatModel"))


def call_llm_compiler(item: Dict[str, object], config: Dict[str, object]) -> List[Dict[str, object]]:
    prompt = build_compile_prompt(item)
    response = requests.post(
        "{}/chat/completions".format(str(config["chatBaseUrl"]).rstrip("/")),
        headers={
            "Authorization": "Bearer {}".format(config["chatApiKey"]),
            "Content-Type": "application/json",
        },
        json={
            "model": config["chatModel"],
            "messages": [
                {"role": "system", "content": "你是个人知识中枢的 Wiki 编译器，只返回合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=int(config.get("chatTimeoutSeconds") or config.get("timeoutSeconds") or 45),
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    data = parse_json_content(content)
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list) or not pages:
        raise WikiCompileError("模型未返回 pages 数组")
    return pages[:6]


def build_compile_prompt(item: Dict[str, object]) -> str:
    content = (item.get("content") or "")[:12000]
    return """请把下面的知识条目编译成个人 Markdown Wiki 页面。

要求：
1. 只返回 JSON，不要 Markdown 代码块。
2. JSON 格式：{{"pages":[{{"title":"...","type":"summary|person|project|concept|decision|risk|index|log","contentMd":"...","tags":["..."]}}]}}。
3. 每个 contentMd 使用 Markdown，保留事实、结论、证据和待确认点。
4. 页面之间可以使用 [[页面标题]] 双链。
5. 不要编造原文没有的信息。

知识条目：
ID：{id}
标题：{title}
摘要：{summary}
来源：{source}
标签：{tags}
正文：
{content}
""".format(
        id=item.get("id"),
        title=item.get("title"),
        summary=item.get("summary"),
        source=item.get("source"),
        tags=", ".join(item.get("tags") or []),
        content=content,
    )


def parse_json_content(content: str):
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def fallback_pages(item: Dict[str, object]):
    title = item.get("title") or "未命名知识"
    summary = item.get("summary") or summarize(item.get("content") or "")
    tags = item.get("tags") or []
    content = item.get("content") or ""
    page_type = infer_page_type(title, tags, content)
    content_md = """# {title}

## 摘要
{summary}

## 关键事实
- 来源：{source}
- 原始知识条目：#{item_id}
- 标签：{tags}

## 原文摘录
{excerpt}

## 待确认
- 是否需要拆分为人物、项目、技术、决策或风险等更细页面。
- 是否需要补充与其他 Wiki 页面的双链关系。
""".format(
        title=title,
        summary=summary or "待补充",
        source=item.get("source") or "",
        item_id=item.get("id"),
        tags="、".join(tags) if tags else "无",
        excerpt=summarize(content, 1600) or "暂无正文",
    )
    return [{"title": title, "type": page_type, "contentMd": content_md, "tags": tags}]


def normalize_page(page: Dict[str, object], item: Dict[str, object]):
    title = str(page.get("title") or item.get("title") or "未命名知识").strip()
    page_type = str(page.get("type") or "summary").strip()
    if page_type not in PAGE_TYPES:
        page_type = "summary"
    return {
        "slug": build_slug(page_type, title),
        "title": title,
        "type": page_type,
        "contentMd": str(page.get("contentMd") or page.get("content_md") or "").strip(),
        "sourceItemIds": [item["id"]],
        "tags": normalize_tags(page.get("tags") or item.get("tags") or []),
        "status": "published",
    }


def build_slug(page_type: str, title: str) -> str:
    safe = re.sub(r"[\s/\\:#?]+", "-", title.strip()).strip("-")
    return "{}/{}".format(page_type, safe or "untitled")


def normalize_tags(tags):
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    return [str(tag).strip() for tag in tags if str(tag).strip()][:8]


def infer_page_type(title: str, tags, content: str) -> str:
    joined = " ".join([title or "", " ".join(tags or []), content[:500]])
    if any(word in joined for word in ["风险", "问题", "失败", "错误"]):
        return "risk"
    if any(word in joined for word in ["决策", "方案", "路线", "MVP"]):
        return "decision"
    if any(word in joined for word in ["项目", "系统", "产品", "平台"]):
        return "project"
    if any(word in joined for word in ["Python", "Chroma", "Spring", "Vue", "技术"]):
        return "concept"
    return "summary"


def summarize(text: str, size: int = 420) -> str:
    clean = " ".join((text or "").split())
    return clean[:size]
