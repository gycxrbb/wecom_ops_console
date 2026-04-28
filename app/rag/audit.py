"""RAG retrieval audit — log each retrieval call."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from ..database import SessionLocal
from ..models_rag import RagRetrievalLog

_log = logging.getLogger(__name__)


def write_retrieval_log(
    *,
    session_id: str | None = None,
    message_id: str | None = None,
    customer_id: int | None = None,
    query_text: str | None = None,
    filter_json: str | None = None,
    hit_json: str | None = None,
    latency_ms: int = 0,
    intent_json: str | None = None,
    query_intent_json: str | None = None,
    rerank_scores_json: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(RagRetrievalLog(
            session_id=session_id,
            message_id=message_id,
            customer_id=customer_id,
            query_text=query_text,
            filter_json=filter_json,
            hit_json=hit_json,
            latency_ms=latency_ms,
            intent_json=intent_json,
            query_intent_json=query_intent_json,
            rerank_scores_json=rerank_scores_json,
            created_at=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write RAG retrieval log")
        db.rollback()
    finally:
        db.close()
