"""Qdrant vector store — collection management, upsert, search."""
from __future__ import annotations

import atexit
import logging
import uuid
from pathlib import Path
from typing import Any

from ..config import settings

_log = logging.getLogger(__name__)

_qdrant_client = None
_collection_ready = False


def _cleanup_qdrant():
    global _qdrant_client
    if _qdrant_client is not None:
        try:
            _qdrant_client.close()
        except Exception:
            pass
        _qdrant_client = None


atexit.register(_cleanup_qdrant)


def _get_qdrant_client():
    """Lazy-init Qdrant client. Supports local file mode and remote server mode."""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client

    try:
        from qdrant_client import QdrantClient

        if settings.qdrant_mode == "local":
            db_path = Path(settings.qdrant_local_path)
            db_path.mkdir(parents=True, exist_ok=True)
            _qdrant_client = QdrantClient(path=str(db_path))
            _log.info("Qdrant using local mode: %s", db_path)
        else:
            _qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=5.0,
            )
            _log.info("Qdrant using remote mode: %s:%s", settings.qdrant_host, settings.qdrant_port)
        return _qdrant_client
    except Exception as exc:
        _log.warning("Qdrant client init failed: %s", exc)
        return None


async def ensure_collection() -> bool:
    """Create collection if not exists. Returns True on success."""
    global _collection_ready
    if _collection_ready:
        return True

    client = _get_qdrant_client()
    if client is None:
        return False

    try:
        from qdrant_client.models import Distance, VectorParams

        collections = client.get_collections().collections
        names = [c.name for c in collections]
        if settings.qdrant_collection not in names:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.rag_embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )
            _log.info("Created Qdrant collection: %s", settings.qdrant_collection)
        # Local Qdrant warns that payload indexes are ignored; only create them for server mode.
        if settings.qdrant_mode != "local":
            try:
                from qdrant_client.models import PayloadSchemaType
                for field in [
                    "status", "source_type", "content_kind", "visibility", "safety_level",
                    "semantic_quality", "customer_goal", "intervention_scene", "question_type",
                ]:
                    try:
                        client.create_payload_index(
                            collection_name=settings.qdrant_collection,
                            field_name=field,
                            field_schema=PayloadSchemaType.KEYWORD,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        _collection_ready = True
        return True
    except Exception as exc:
        _log.warning("ensure_collection failed: %s", exc)
        return False


async def upsert_chunks(points: list[dict]) -> bool:
    """Upsert points. Each point: {id, vector, payload}. Returns True on success."""
    client = _get_qdrant_client()
    if client is None:
        return False

    ok = await ensure_collection()
    if not ok:
        return False

    try:
        from qdrant_client.models import PointStruct

        qdrant_points = []
        for p in points:
            qdrant_points.append(
                PointStruct(
                    id=p.get("id", str(uuid.uuid4())),
                    vector=p["vector"],
                    payload=p.get("payload", {}),
                )
            )
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=qdrant_points,
        )
        return True
    except Exception as exc:
        _log.warning("upsert_chunks failed: %s", exc)
        return False


async def search(
    query_vector: list[float],
    *,
    top_k: int = 30,
    filters: dict | None = None,
    must_not: dict | None = None,
) -> list[dict]:
    """Vector search with optional payload filter. Returns list of {id, score, payload}.

    filters: {"field": value_or_list} → must match
    must_not: {"field": value_or_list} → must NOT match
    """
    client = _get_qdrant_client()
    if client is None:
        return []

    ok = await ensure_collection()
    if not ok:
        return []

    try:
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        must_conditions = [FieldCondition(key="status", match=MatchValue(value="active"))]
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    values = [v for v in value if v not in (None, "")]
                    if not values:
                        continue
                    must_conditions.append(FieldCondition(key=key, match=MatchAny(any=values)))
                else:
                    must_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        must_not_conditions = []
        if must_not:
            for key, value in must_not.items():
                if isinstance(value, list):
                    values = [v for v in value if v not in (None, "")]
                    if not values:
                        continue
                    must_not_conditions.append(FieldCondition(key=key, match=MatchAny(any=values)))
                else:
                    must_not_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        results = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=top_k,
            query_filter=Filter(
                must=must_conditions if must_conditions else None,
                must_not=must_not_conditions if must_not_conditions else None,
            ),
        )

        return [
            {"id": str(r.id), "score": r.score, "payload": r.payload or {}}
            for r in results.points
        ]
    except Exception as exc:
        _log.warning("search failed: %s", exc)
        return []


def is_available() -> bool:
    """Check if Qdrant is reachable."""
    client = _get_qdrant_client()
    if client is None:
        return False
    try:
        client.get_collections()
        return True
    except Exception:
        return False


def get_collection_info() -> dict | None:
    """Return collection stats: vector count, status, config. None if unavailable."""
    client = _get_qdrant_client()
    if client is None:
        return None
    try:
        info = client.get_collection(settings.qdrant_collection)
        points_count = getattr(info, "points_count", None)
        return {
            "collection": settings.qdrant_collection,
            "status": info.status.value if hasattr(info.status, 'value') else str(info.status),
            "vectors_count": getattr(info, "vectors_count", None) or points_count,
            "points_count": points_count,
            "indexed_vectors_count": getattr(info, 'indexed_vectors_count', None),
            "segments_count": getattr(info, "segments_count", None),
            "disk_data_size": getattr(info, "disk_data_size", None),
            "ram_data_size": getattr(info, "ram_data_size", None),
            "vector_dim": settings.rag_embedding_dimension,
        }
    except Exception:
        return None


def delete_points(point_ids: list[str]) -> bool:
    """Delete vectors by point IDs. Returns True on success."""
    client = _get_qdrant_client()
    if client is None or not point_ids:
        return False
    try:
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=point_ids,
        )
        _log.info("Deleted %d points from Qdrant", len(point_ids))
        return True
    except Exception as exc:
        _log.warning("delete_points failed: %s", exc)
        return False


def scroll_points(
    limit: int = 20,
    offset: str | None = None,
    filters: dict | None = None,
) -> tuple[list[dict], str | None]:
    """Scroll through collection points for debugging. Returns (points, next_offset)."""
    client = _get_qdrant_client()
    if client is None:
        return [], None
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        qdrant_filter = None
        if filters:
            must = []
            for key, value in filters.items():
                if isinstance(value, list):
                    must.append(FieldCondition(key=key, match=MatchAny(any=value)))
                else:
                    must.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=must) if must else None

        records, next_offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=limit,
            offset=offset,
            scroll_filter=qdrant_filter,
            with_payload=True,
            with_vectors=False,
        )
        points = [
            {"id": str(r.id), "payload": r.payload or {}}
            for r in records
        ]
        return points, next_offset
    except Exception as exc:
        _log.warning("scroll_points failed: %s", exc)
        return [], None
