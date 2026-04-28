"""Reranker — embed-based re-ranking of retrieval candidates."""
from __future__ import annotations

import logging

from ..config import settings
from .embedding_client import embed_texts_batch

_log = logging.getLogger(__name__)


async def rerank_hits(
    query_vector: list[float],
    hits: list[dict],
    *,
    top_n: int = 6,
) -> list[dict]:
    """Re-rank hits using resource-level embedding similarity.

    Each hit dict should have a "semantic_text" field with the full text.
    Adds "rerank_score" to each hit dict.
    """
    if not settings.rag_rerank_enabled:
        return hits[:top_n]

    if not hits:
        return []

    texts = [h.get("semantic_text", "")[:500] for h in hits]
    if not any(texts):
        return hits[:top_n]

    try:
        vectors = await embed_texts_batch(texts)
    except Exception:
        _log.warning("Rerank embedding failed, returning original order")
        return hits[:top_n]

    if len(vectors) != len(hits):
        return hits[:top_n]

    for hit, vec in zip(hits, vectors):
        hit["rerank_score"] = round(_cosine_similarity(query_vector, vec), 4)

    hits.sort(key=lambda h: h.get("rerank_score", 0), reverse=True)
    return hits[:top_n]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
