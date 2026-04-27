"""RAG admin endpoints — indexing and status."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..security import get_current_user, require_role
from ..rag import vector_store

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
_log = logging.getLogger(__name__)


@router.post("/reindex")
async def reindex(
    request: Request,
    db: Session = Depends(get_db),
    source: str = "all",
    force: bool = False,
):
    """Re-index speech templates and/or materials into Qdrant.

    Use force=true to clear existing hashes and re-embed everything.
    """
    user = get_current_user(request, db)
    require_role(user, "admin")

    if not settings.rag_enabled:
        return {"status": "disabled", "message": "RAG is not enabled"}

    if force:
        from ..models_rag import RagResource
        db.query(RagResource).update({RagResource.source_hash: ""})
        db.commit()

    from ..rag.resource_indexer import index_speech_templates, index_materials

    results = {}

    index_db = SessionLocal()
    try:
        if source in ("all", "speech"):
            results["speech_templates"] = await index_speech_templates(index_db)
        if source in ("all", "material"):
            results["materials"] = await index_materials(index_db)
    finally:
        index_db.close()

    return {"status": "ok", "results": results}


@router.get("/status")
async def rag_status(
    request: Request,
    db: Session = Depends(get_db),
):
    """Check RAG subsystem status."""
    user = get_current_user(request, db)
    require_role(user, "admin")

    available = vector_store.is_available()
    return {
        "rag_enabled": settings.rag_enabled,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_available": available,
    }
