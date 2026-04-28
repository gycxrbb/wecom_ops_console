"""RAG admin endpoints — indexing, status, and material CSV import."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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


@router.post("/import-material-csv")
async def import_material_rag_csv(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Import material RAG annotations from CSV. Validates, matches materials, indexes into Qdrant."""
    user = get_current_user(request, db)
    require_role(user, "admin", "coach")

    filename = file.filename or ""
    if filename and not filename.lower().endswith(".csv"):
        raise HTTPException(400, "仅支持 CSV 文件")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "CSV 文件为空")

    from ..services.material_rag_import import import_material_rag_rows
    from ..services.speech_template_import import decode_csv_bytes, parse_csv_text

    csv_text = decode_csv_bytes(raw)
    rows = parse_csv_text(csv_text)
    stats = await import_material_rag_rows(db, rows, dry_run=dry_run)
    return stats
