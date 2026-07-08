import json
import logging
import re
from typing import Dict, List

import requests


logger = logging.getLogger(__name__)

ENTITY_TYPES = {"Person", "Project", "Company", "Technology", "Concept", "Decision", "Risk", "Resource", "Goal", "Task"}
RELATION_TYPES = {"MENTIONS", "WORKED_ON", "USES", "BELONGS_TO", "RELATED_TO", "SUPPORTS", "CONFLICTS_WITH", "DEPENDS_ON", "DECIDED", "HAS_RISK", "DERIVED_FROM"}


def extract_graph_candidates(item: Dict[str, object], model_config: Dict[str, object]):
    logger.info("开始抽取图谱候选，item_id：%s，title：%s", item.get("id"), item.get("title"))
    if chat_configured(model_config):
        try:
            result = call_llm_extractor(item, model_config)
            logger.info("LLM 图谱候选抽取完成，item_id：%s，entities：%s，relations：%s", item.get("id"), len(result["entities"]), len(result["relations"]))
            return result
        except Exception as exc:
            logger.warning("LLM 图谱候选抽取失败，转本地规则，item_id：%s，原因：%s", item.get("id"), exc)
    return fallback_extract(item)


def chat_configured(config: Dict[str, object]) -> bool:
    return bool(config.get("chatBaseUrl") and config.get("chatApiKey") and config.get("chatModel"))


def call_llm_extractor(item: Dict[str, object], config: Dict[str, object]):
    prompt = build_extract_prompt(item)
    response = requests.post(
        "{}/chat/completions".format(str(config["chatBaseUrl"]).rstrip("/")),
        headers={
            "Authorization": "Bearer {}".format(config["chatApiKey"]),
            "Content-Type": "application/json",
        },
        json={
            "model": config["chatModel"],
            "messages": [
                {"role": "system", "content": "你是个人知识图谱抽取器，只返回合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        },
        timeout=int(config.get("chatTimeoutSeconds") or config.get("timeoutSeconds") or 45),
    )
    response.raise_for_status()
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    payload = parse_json_content(content)
    return normalize_payload(payload, item)


def build_extract_prompt(item: Dict[str, object]) -> str:
    content = (item.get("content") or "")[:12000]
    return """请从知识条目中抽取个人知识图谱候选。

只返回 JSON，不要 Markdown 代码块。格式：
{{
  "entities": [
    {{"name":"...", "type":"Person|Project|Company|Technology|Concept|Decision|Risk|Resource|Goal|Task", "aliases":["..."], "summary":"...", "confidence":0.0}}
  ],
  "relations": [
    {{"source":"...", "sourceType":"Project", "relation":"USES|MENTIONS|WORKED_ON|BELONGS_TO|RELATED_TO|SUPPORTS|CONFLICTS_WITH|DEPENDS_ON|DECIDED|HAS_RISK|DERIVED_FROM", "target":"...", "targetType":"Technology", "evidence":"原文证据", "confidence":0.0}}
  ]
}}

要求：
1. 不要编造原文没有的信息。
2. relation 必须使用上面的枚举。
3. evidence 必须简短引用或概括原文依据。
4. 关系数量控制在 3-12 条。

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


def normalize_payload(payload, item: Dict[str, object]):
    entities = []
    seen = set()
    for entity in payload.get("entities", []) if isinstance(payload, dict) else []:
        name = str(entity.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        entity_type = entity.get("type") if entity.get("type") in ENTITY_TYPES else "Concept"
        entities.append({
            "name": name,
            "type": entity_type,
            "aliases": entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            "summary": str(entity.get("summary") or "")[:500],
            "confidence": normalize_confidence(entity.get("confidence")),
        })

    relations = []
    for relation in payload.get("relations", []) if isinstance(payload, dict) else []:
        source = str(relation.get("source") or "").strip()
        target = str(relation.get("target") or "").strip()
        if not source or not target or source == target:
            continue
        rel_type = relation.get("relation") if relation.get("relation") in RELATION_TYPES else "RELATED_TO"
        relations.append({
            "source": source,
            "sourceType": relation.get("sourceType") if relation.get("sourceType") in ENTITY_TYPES else "Concept",
            "relation": rel_type,
            "target": target,
            "targetType": relation.get("targetType") if relation.get("targetType") in ENTITY_TYPES else "Concept",
            "evidence": str(relation.get("evidence") or item.get("title") or "")[:800],
            "confidence": normalize_confidence(relation.get("confidence")),
        })
    return {"entities": entities[:20], "relations": relations[:20]}


def fallback_extract(item: Dict[str, object]):
    title = item.get("title") or "未命名知识"
    source_name = title
    source_type = infer_entity_type(title, item.get("tags") or [], item.get("content") or "")
    entities = [{
        "name": source_name,
        "type": source_type,
        "aliases": [],
        "summary": item.get("summary") or summarize(item.get("content") or ""),
        "confidence": 0.55,
    }]
    relations = []
    for tag in item.get("tags") or []:
        entities.append({"name": tag, "type": "Concept", "aliases": [], "summary": "由标签生成的概念实体", "confidence": 0.5})
        relations.append({
            "source": source_name,
            "sourceType": source_type,
            "relation": "MENTIONS",
            "target": tag,
            "targetType": "Concept",
            "evidence": "知识条目标签：{}".format(tag),
            "confidence": 0.5,
        })
    logger.info("本地规则图谱候选生成完成，item_id：%s，entities：%s，relations：%s", item.get("id"), len(entities), len(relations))
    return {"entities": entities, "relations": relations}


def infer_entity_type(title: str, tags, content: str):
    joined = " ".join([title or "", " ".join(tags or []), content[:500]])
    if any(word in joined for word in ["公司", "组织", "集团"]):
        return "Company"
    if any(word in joined for word in ["项目", "系统", "产品", "平台"]):
        return "Project"
    if any(word in joined for word in ["风险", "错误", "失败", "问题"]):
        return "Risk"
    if any(word in joined for word in ["决策", "方案", "路线"]):
        return "Decision"
    if any(word in joined for word in ["Python", "Chroma", "Neo4j", "Spring", "Vue", "技术"]):
        return "Technology"
    return "Concept"


def normalize_confidence(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.6


def summarize(text: str, size: int = 260):
    return " ".join((text or "").split())[:size]
