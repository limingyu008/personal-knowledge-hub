from pathlib import Path
from typing import Dict, List

import chromadb
import requests

from .database import DATA_DIR


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
    except Exception as exc:
        raise VectorStoreError("Embedding API 调用失败：{}".format(exc)) from exc

    data = payload.get("data") or []
    embeddings = [item.get("embedding") for item in data]
    if len(embeddings) != len(texts) or any(not embedding for embedding in embeddings):
        raise VectorStoreError("Embedding API 返回结果数量异常")
    return embeddings


def get_collection(config: Dict[str, object]):
    chroma_path = config.get("chromaPath") or str(DATA_DIR / "chroma")
    collection_name = config.get("chromaCollection") or "personal_knowledge_chunks"
    Path(chroma_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)
    return client.get_or_create_collection(name=collection_name)


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
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def delete_item_vectors(item_id: int, config: Dict[str, object]):
    if not enabled(config):
        return
    collection = get_collection(config)
    try:
        collection.delete(where={"item_id": int(item_id)})
    except Exception:
        pass


def query_chunks(question: str, top_k: int, config: Dict[str, object]):
    collection = get_collection(config)
    query_embedding = embed_texts([question], config)[0]
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    hits = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 1
        score = max(0.0, min(0.99, 1 - float(distance)))
        hits.append({
            "itemId": metadata.get("item_id"),
            "title": metadata.get("title") or "未命名知识",
            "summary": metadata.get("summary") or document[:180],
            "content": document,
            "score": round(score, 4),
            "reason": "Chroma 向量检索命中 chunk，distance={:.4f}".format(float(distance)),
        })
    return hits
