import json
import logging
import math
import re
from datetime import datetime
from typing import Dict, List

from .database import get_connection, parse_json


logger = logging.getLogger(__name__)

ENTITY_COLORS = {
    "Person": "person",
    "Project": "project",
    "Company": "company",
    "Technology": "tech",
    "Concept": "concept",
    "Decision": "decision",
    "Risk": "risk",
    "Resource": "resource",
    "Goal": "goal",
    "Task": "task",
}


class GraphStoreError(Exception):
    pass


def get_graph_config():
    with get_connection() as conn:
        row = conn.execute("SELECT id, enabled, uri, username, password, database FROM graph_config WHERE id = 1").fetchone()
    if not row:
        return {"enabled": False, "uri": "bolt://localhost:7687", "username": "neo4j", "password": "", "database": "neo4j"}
    return {
        "enabled": bool(row["enabled"]),
        "uri": row["uri"],
        "username": row["username"],
        "password": row["password"],
        "database": row["database"] or "neo4j",
    }


def save_graph_config(config: Dict[str, object]):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO graph_config (id, enabled, uri, username, password, database)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                enabled = excluded.enabled,
                uri = excluded.uri,
                username = excluded.username,
                password = excluded.password,
                database = excluded.database
            """,
            (
                1 if config.get("enabled") else 0,
                config.get("uri") or "bolt://localhost:7687",
                config.get("username") or "neo4j",
                config.get("password") or "",
                config.get("database") or "neo4j",
            ),
        )
    logger.info("Neo4j 图谱配置已保存，uri：%s，database：%s，enabled：%s", config.get("uri"), config.get("database"), bool(config.get("enabled")))
    return get_graph_config()


def test_graph_connection(config=None):
    config = config or get_graph_config()
    try:
        with neo4j_driver(config) as driver:
            with driver.session(database=config.get("database") or "neo4j") as session:
                value = session.run("RETURN 1 AS ok").single()["ok"]
        return {"ok": value == 1, "message": "Neo4j 连接正常"}
    except Exception as exc:
        logger.exception("Neo4j 连接测试失败")
        return {"ok": False, "message": "Neo4j 连接失败：{}".format(exc)}


def upsert_candidates(candidates: Dict[str, List[Dict[str, object]]], item: Dict[str, object], config=None):
    config = config or get_graph_config()
    if not config.get("enabled"):
        raise GraphStoreError("Neo4j 图谱未启用")
    logger.info("开始写入 Neo4j 图谱候选，item_id：%s", item.get("id"))
    relation_count = 0
    entity_count = 0
    with neo4j_driver(config) as driver:
        with driver.session(database=config.get("database") or "neo4j") as session:
            for entity in candidates.get("entities", []):
                session.execute_write(upsert_entity_tx, entity)
                entity_count += 1
            for relation in candidates.get("relations", []):
                session.execute_write(upsert_relation_tx, relation, item)
                relation_count += 1
    mirror_candidates_to_sqlite(candidates, item)
    logger.info("Neo4j 图谱候选写入完成，item_id：%s，entities：%s，relations：%s", item.get("id"), entity_count, relation_count)
    return {"entities": entity_count, "relations": relation_count}


def list_graph(config=None):
    config = config or get_graph_config()
    if not config.get("enabled"):
        return list_sqlite_graph()
    try:
        with neo4j_driver(config) as driver:
            with driver.session(database=config.get("database") or "neo4j") as session:
                records = session.run(
                    """
                    MATCH (a:Entity)-[r]->(b:Entity)
                    RETURN a.key AS sourceKey, a.name AS sourceName, a.type AS sourceType,
                           b.key AS targetKey, b.name AS targetName, b.type AS targetType,
                           type(r) AS relation, r.status AS status, r.evidence AS evidence, r.confidence AS confidence, elementId(r) AS edgeId
                    ORDER BY r.updatedAt DESC
                    LIMIT 160
                    """
                ).data()
        return graph_records_to_view(records)
    except Exception as exc:
        logger.exception("Neo4j 图谱查询失败，回退 SQLite 图谱")
        fallback = list_sqlite_graph()
        fallback["error"] = str(exc)
        return fallback


def confirm_relation(edge_id: str, config=None):
    return update_relation_status(edge_id, "confirmed", config)


def delete_relation(edge_id: str, config=None):
    config = config or get_graph_config()
    with neo4j_driver(config) as driver:
        with driver.session(database=config.get("database") or "neo4j") as session:
            session.run("MATCH ()-[r]->() WHERE elementId(r) = $edgeId DELETE r", edgeId=edge_id)
    logger.info("Neo4j 关系已删除，edge_id：%s", edge_id)
    return {"ok": True}


def update_relation_status(edge_id: str, status: str, config=None):
    config = config or get_graph_config()
    with neo4j_driver(config) as driver:
        with driver.session(database=config.get("database") or "neo4j") as session:
            session.run(
                "MATCH ()-[r]->() WHERE elementId(r) = $edgeId SET r.status = $status, r.updatedAt = datetime()",
                edgeId=edge_id,
                status=status,
            )
    logger.info("Neo4j 关系状态已更新，edge_id：%s，status：%s", edge_id, status)
    return {"ok": True}


def neo4j_driver(config):
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise GraphStoreError("未安装 neo4j Python 依赖，请执行 pip install neo4j") from exc
    return GraphDatabase.driver(
        config.get("uri") or "bolt://localhost:7687",
        auth=(config.get("username") or "neo4j", config.get("password") or ""),
    )


def upsert_entity_tx(tx, entity):
    key = entity_key(entity.get("type"), entity.get("name"))
    tx.run(
        """
        MERGE (e:Entity {key: $key})
        SET e.name = $name, e.type = $type, e.aliases = $aliases, e.summary = $summary,
            e.confidence = $confidence, e.updatedAt = datetime()
        SET e.createdAt = coalesce(e.createdAt, datetime())
        """,
        key=key,
        name=entity.get("name"),
        type=entity.get("type") or "Concept",
        aliases=entity.get("aliases") or [],
        summary=entity.get("summary") or "",
        confidence=float(entity.get("confidence") or 0.6),
    )


def upsert_relation_tx(tx, relation, item):
    source = {"name": relation.get("source"), "type": relation.get("sourceType") or "Concept"}
    target = {"name": relation.get("target"), "type": relation.get("targetType") or "Concept"}
    source_key = entity_key(source["type"], source["name"])
    target_key = entity_key(target["type"], target["name"])
    rel_type = safe_relation_type(relation.get("relation"))
    query = """
        MERGE (a:Entity {key: $sourceKey})
        SET a.name = $sourceName, a.type = $sourceType, a.updatedAt = datetime()
        SET a.createdAt = coalesce(a.createdAt, datetime())
        MERGE (b:Entity {key: $targetKey})
        SET b.name = $targetName, b.type = $targetType, b.updatedAt = datetime()
        SET b.createdAt = coalesce(b.createdAt, datetime())
        MERGE (a)-[r:%s {sourceItemId: $sourceItemId}]->(b)
        SET r.status = coalesce(r.status, 'pending'), r.evidence = $evidence, r.confidence = $confidence,
            r.sourceTitle = $sourceTitle, r.updatedAt = datetime()
        SET r.createdAt = coalesce(r.createdAt, datetime())
    """ % rel_type
    tx.run(
        query,
        sourceKey=source_key,
        sourceName=source["name"],
        sourceType=source["type"],
        targetKey=target_key,
        targetName=target["name"],
        targetType=target["type"],
        sourceItemId=int(item.get("id")),
        sourceTitle=item.get("title") or "",
        evidence=relation.get("evidence") or "",
        confidence=float(relation.get("confidence") or 0.6),
    )


def graph_records_to_view(records):
    nodes = {}
    edges = []
    for record in records:
        for key_name, label_name, type_name in [("sourceKey", "sourceName", "sourceType"), ("targetKey", "targetName", "targetType")]:
            key = record[key_name]
            if key not in nodes:
                nodes[key] = {"id": key, "label": record[label_name], "typeKey": ENTITY_COLORS.get(record[type_name], "concept"), "entityType": record[type_name]}
        edges.append({
            "id": record["edgeId"],
            "from": record["sourceKey"],
            "to": record["targetKey"],
            "status": record.get("status") or "pending",
            "label": record.get("relation") or "RELATED_TO",
            "evidence": record.get("evidence") or "",
            "confidence": record.get("confidence") or 0,
        })
    positioned = position_nodes(list(nodes.values()))
    return {"nodes": positioned, "edges": edges, "source": "neo4j"}


def position_nodes(nodes):
    if not nodes:
        return []
    center_x, center_y = 380, 260
    radius = 190 if len(nodes) > 4 else 140
    for index, node in enumerate(nodes):
        angle = 2 * math.pi * index / max(1, len(nodes))
        node["x"] = int(center_x + math.cos(angle) * radius)
        node["y"] = int(center_y + math.sin(angle) * radius)
    return nodes


def list_sqlite_graph():
    with get_connection() as conn:
        nodes = conn.execute("SELECT id, label, type_key, x, y FROM graph_nodes").fetchall()
        edges = conn.execute("SELECT id, from_node, to_node, status, label FROM graph_edges").fetchall()
    return {
        "nodes": [{"id": row["id"], "label": row["label"], "typeKey": row["type_key"], "x": row["x"], "y": row["y"]} for row in nodes],
        "edges": [{"id": row["id"], "from": row["from_node"], "to": row["to_node"], "status": row["status"], "label": row["label"]} for row in edges],
        "source": "sqlite",
    }


def mirror_candidates_to_sqlite(candidates, item):
    with get_connection() as conn:
        for entity in candidates.get("entities", []):
            key = entity_key(entity.get("type"), entity.get("name"))
            conn.execute(
                "INSERT OR REPLACE INTO graph_nodes (id, label, type_key, x, y) VALUES (?, ?, ?, ?, ?)",
                (key, entity.get("name"), ENTITY_COLORS.get(entity.get("type"), "concept"), 380, 260),
            )
        for relation in candidates.get("relations", []):
            source_key = entity_key(relation.get("sourceType"), relation.get("source"))
            target_key = entity_key(relation.get("targetType"), relation.get("target"))
            edge_id = "{}:{}:{}".format(source_key, safe_relation_type(relation.get("relation")), target_key)
            conn.execute(
                "INSERT OR REPLACE INTO graph_edges (id, from_node, to_node, status, label) VALUES (?, ?, ?, ?, ?)",
                (edge_id, source_key, target_key, "pending", safe_relation_type(relation.get("relation"))),
            )


def entity_key(entity_type, name):
    safe_type = str(entity_type or "Concept").lower()
    safe_name = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", str(name or "unknown").strip().lower()).strip("-")
    return "{}:{}".format(safe_type, safe_name or "unknown")


def safe_relation_type(value):
    relation = re.sub(r"[^A-Z_]+", "", str(value or "RELATED_TO").upper())
    return relation or "RELATED_TO"
