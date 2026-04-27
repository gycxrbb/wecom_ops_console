"""Embedding client — aihubmix /v1/embeddings via httpx."""
from __future__ import annotations

import logging

import httpx

from ..config import settings

_log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
    return _client


def _resolve_api_key() -> str:
    return settings.rag_embedding_api_key or settings.ai_api_key


async def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    dimension: int | None = None,
) -> list[list[float]]:
    """Embed a list of texts. Returns list of float vectors."""
    if not texts:
        return []

    client = await _get_client()
    api_key = _resolve_api_key()
    url = f"{settings.rag_embedding_base_url}/embeddings"

    payload: dict = {
        "model": model or settings.rag_embedding_model,
        "input": texts,
    }
    dim = dimension or settings.rag_embedding_dimension
    if dim:
        payload["dimensions"] = dim

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    embeddings = []
    for item in sorted(data.get("data", []), key=lambda x: x.get("index", 0)):
        embeddings.append(item["embedding"])
    return embeddings


async def embed_texts_batch(
    texts: list[str],
    *,
    batch_size: int = 20,
    model: str | None = None,
) -> list[list[float]]:
    """Embed texts in batches to avoid request size limits."""
    if not texts:
        return []

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_result = await embed_texts(batch, model=model)
        all_embeddings.extend(batch_result)
    return all_embeddings
