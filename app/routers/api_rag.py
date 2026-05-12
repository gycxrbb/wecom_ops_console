"""RAG admin endpoints — indexing, status, and material CSV import."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..security import get_current_user, require_role
from ..rag import vector_store

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
_log = logging.getLogger(__name__)


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    require_role(user, "admin")
    return user


@router.post("/reindex")
async def reindex(
    request: Request,
    db: Session = Depends(get_db),
    source: str = "all",
    force: bool = False,
):
    _require_admin(request, db)
    if not settings.rag_enabled:
        return {"status": "disabled", "message": "RAG is not enabled"}
    if force:
        from ..models_rag import RagResource
        db.query(RagResource).update({RagResource.source_hash: ""})
        db.commit()

    from ..rag.resource_indexer import index_speech_templates, index_materials, index_single_speech_template
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
async def rag_status(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    available = vector_store.is_available()
    result = {
        "rag_enabled": settings.rag_enabled,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_available": available,
    }
    if available:
        info = vector_store.get_collection_info()
        if info:
            result["collection"] = info
    from ..models_rag import RagResource
    from sqlalchemy import func as sa_func
    from collections import Counter
    total = db.query(RagResource).count()
    by_type_rows = db.query(RagResource.source_type).all()
    type_counts = Counter(r[0] for r in by_type_rows)
    by_quality_rows = db.query(RagResource.semantic_quality).all()
    quality_counts = Counter(r[0] for r in by_quality_rows)
    result["indexed_resources"] = {"total": total, "by_type": dict(type_counts), "by_quality": dict(quality_counts)}
    return result


@router.post("/import-material-csv")
async def import_material_rag_csv(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
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


@router.get("/tags")
async def list_tags(request: Request, db: Session = Depends(get_db), dimension: str | None = None):
    user = get_current_user(request, db)
    require_role(user, "admin", "coach")
    from ..rag.tag_service import get_tags_by_dimension
    return {"tags": get_tags_by_dimension(db, dimension)}


@router.post("/tags/refresh")
async def refresh_tags(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..rag.tag_service import refresh_tags_from_vocabulary
    stats = refresh_tags_from_vocabulary(db)
    return {"status": "ok", "stats": stats}


@router.post("/tags")
async def create_tag(request: Request, body: dict, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..schemas.tag import TagCreate
    from ..rag.tag_service import create_tag as svc_create
    data = TagCreate(**body)
    try:
        tag = svc_create(db, dimension=data.dimension, code=data.code, name=data.name,
                         description=data.description, sort_order=data.sort_order, aliases=data.aliases)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"status": "ok", "tag": {"id": tag.id, "dimension": tag.dimension, "code": tag.code, "name": tag.name}}


@router.put("/tags/{tag_id}")
async def update_tag(tag_id: int, request: Request, body: dict, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..schemas.tag import TagUpdate
    from ..rag.tag_service import update_tag as svc_update
    data = TagUpdate(**body)
    kwargs = {k: v for k, v in data.model_dump().items() if v is not None}
    try:
        tag = svc_update(db, tag_id, **kwargs)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"status": "ok", "tag": {"id": tag.id, "dimension": tag.dimension, "code": tag.code, "name": tag.name}}


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..rag.tag_service import disable_tag
    try:
        disable_tag(db, tag_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"status": "ok"}


# ── Resource Management ──

def _count_hits(hit_json) -> dict:
    """从 hit_json 中统计实际命中条数，兼容 dict 和 list 结构。"""
    if not hit_json:
        return {"reference": 0, "material": 0, "total": 0}
    if isinstance(hit_json, list):
        return {"reference": len(hit_json), "material": 0, "total": len(hit_json)}
    ref = len(hit_json.get("phase1", []) or [])
    mat = len(hit_json.get("material", []) or [])
    return {"reference": ref, "material": mat, "total": ref + mat}


@router.get("/resources")
def list_resources(
    request: Request, db: Session = Depends(get_db),
    page: int = 1, page_size: int = 20,
    source_type: str | None = None, content_kind: str | None = None,
    quality: str | None = None, rag_status: str | None = None,
    safety_level: str | None = None, visibility: str | None = None,
    q: str | None = None,
):
    _require_admin(request, db)
    from ..models_rag import RagResource, RagChunk
    from sqlalchemy import func as sa_func
    query = db.query(RagResource)
    if source_type:
        query = query.filter(RagResource.source_type == source_type)
    if content_kind:
        query = query.filter(RagResource.content_kind == content_kind)
    if quality:
        query = query.filter(RagResource.semantic_quality == quality)
    if rag_status:
        query = query.filter(RagResource.status == rag_status)
    if safety_level:
        query = query.filter(RagResource.safety_level == safety_level)
    if visibility:
        query = query.filter(RagResource.visibility == visibility)
    if q:
        query = query.filter(RagResource.title.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(RagResource.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    chunk_count_map: dict[int, int] = {}
    if items:
        rows = db.query(RagChunk.resource_id, sa_func.count(RagChunk.id)).filter(
            RagChunk.resource_id.in_([r.id for r in items])
        ).group_by(RagChunk.resource_id).all()
        chunk_count_map = {r[0]: r[1] for r in rows}
    return {
        "items": [{
            "id": r.id, "source_type": r.source_type, "source_id": r.source_id,
            "title": r.title, "content_kind": r.content_kind,
            "semantic_quality": r.semantic_quality, "status": r.status,
            "safety_level": r.safety_level, "visibility": r.visibility,
            "summary": (r.summary or "")[:120], "chunk_count": chunk_count_map.get(r.id, 0),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        } for r in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/resources/{resource_id}")
def get_resource_detail(resource_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagResource, RagChunk, RagResourceTag, RagTag
    r = db.query(RagResource).filter(RagResource.id == resource_id).first()
    if not r:
        raise HTTPException(404, "资源不存在")
    chunks = db.query(RagChunk).filter(RagChunk.resource_id == r.id).order_by(RagChunk.chunk_index).all()
    tag_rows = (
        db.query(RagTag).join(RagResourceTag, RagResourceTag.tag_id == RagTag.id)
        .filter(RagResourceTag.resource_id == r.id).all()
    )
    # Load source metadata for editing
    source_meta = {}
    if r.source_type == "speech_template":
        import json as _json
        from ..models import SpeechTemplate
        tpl = db.query(SpeechTemplate).filter(SpeechTemplate.id == r.source_id).first()
        if tpl and tpl.metadata_json:
            try:
                source_meta = _json.loads(tpl.metadata_json)
            except Exception:
                pass
    elif r.source_type == "material":
        import json as _json
        from ..models import Material
        mat = db.query(Material).filter(Material.id == r.source_id).first()
        if mat and getattr(mat, "rag_meta_json", None):
            try:
                source_meta = _json.loads(mat.rag_meta_json)
            except Exception:
                pass

    return {
        "id": r.id, "source_type": r.source_type, "source_id": r.source_id,
        "title": r.title, "summary": r.summary,
        "semantic_text": r.semantic_text, "semantic_quality": r.semantic_quality,
        "content_kind": r.content_kind, "visibility": r.visibility,
        "safety_level": r.safety_level, "status": r.status, "source_hash": r.source_hash,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "chunks": [{"id": c.id, "chunk_index": c.chunk_index,
                     "text_preview": (c.chunk_text or "")[:200],
                     "embedding_model": c.embedding_model, "status": c.status} for c in chunks],
        "tags": [{"id": t.id, "dimension": t.dimension, "code": t.code, "name": t.name} for t in tag_rows],
        "metadata": source_meta,
    }


def _delete_resource_inner(r, db: Session) -> dict:
    """先删 Qdrant 再删 DB，Qdrant 失败时降级为 disabled。"""
    from ..models_rag import RagChunk, RagResourceTag
    chunks = db.query(RagChunk).filter(RagChunk.resource_id == r.id).all()
    point_ids = [c.vector_point_id for c in chunks if c.vector_point_id]
    qdrant_ok = True
    if point_ids:
        qdrant_ok = vector_store.delete_points(point_ids)
    if qdrant_ok:
        db.query(RagResourceTag).filter(RagResourceTag.resource_id == r.id).delete()
        db.query(RagChunk).filter(RagChunk.resource_id == r.id).delete()
        db.delete(r)
        db.commit()
        return {"status": "deleted", "qdrant_deleted": True, "db_deleted": True}
    else:
        r.status = "disabled"
        for c in chunks:
            c.status = "disabled"
        db.commit()
        return {"status": "fallback_disabled", "qdrant_deleted": False, "db_deleted": False,
                "message": "Qdrant 删除失败，资源已降级为 disabled，请稍后重试"}


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagResource
    r = db.query(RagResource).filter(RagResource.id == resource_id).first()
    if not r:
        raise HTTPException(404, "资源不存在")
    return _delete_resource_inner(r, db)


@router.post("/resources/batch-delete")
def batch_delete_resources(request: Request, body: dict, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagResource
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "请提供要删除的资源 ID")
    resources = db.query(RagResource).filter(RagResource.id.in_(ids)).all()
    results = []
    for r in resources:
        results.append({"id": r.id, **_delete_resource_inner(r, db)})
    return {"status": "ok", "results": results}


@router.post("/resources/{resource_id}/disable")
def disable_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagResource, RagChunk
    r = db.query(RagResource).filter(RagResource.id == resource_id).first()
    if not r:
        raise HTTPException(404, "资源不存在")
    r.status = "disabled"
    db.query(RagChunk).filter(RagChunk.resource_id == r.id).update({"status": "disabled"})
    db.commit()
    return {"status": "ok"}


@router.post("/resources/{resource_id}/enable")
def enable_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagResource, RagChunk
    r = db.query(RagResource).filter(RagResource.id == resource_id).first()
    if not r:
        raise HTTPException(404, "资源不存在")
    r.status = "active"
    db.query(RagChunk).filter(RagChunk.resource_id == r.id).update({"status": "active"})
    db.commit()
    return {"status": "ok"}


class RagMetaUpdateReq(BaseModel):
    safety_level: str | None = None
    visibility: str | None = None
    summary: str | None = None
    customer_goal: list[str] | None = None
    intervention_scene: list[str] | None = None
    question_type: list[str] | None = None
    tags: list[str] | None = None
    usage_note: str | None = None


@router.patch("/resources/{resource_id}/metadata")
async def update_resource_metadata(
    resource_id: int, req: RagMetaUpdateReq, request: Request, db: Session = Depends(get_db)
):
    _require_admin(request, db)
    from ..models_rag import RagResource
    r = db.query(RagResource).filter(RagResource.id == resource_id).first()
    if not r:
        raise HTTPException(404, "资源不存在")

    if req.safety_level is not None:
        r.safety_level = req.safety_level
    if req.visibility is not None:
        r.visibility = req.visibility
    if req.summary is not None:
        r.summary = req.summary

    # Update source metadata if speech_template
    if r.source_type == "speech_template":
        import json as _json
        from ..models import SpeechTemplate
        tpl = db.query(SpeechTemplate).filter(SpeechTemplate.id == r.source_id).first()
        if tpl:
            meta = _json.loads(tpl.metadata_json) if tpl.metadata_json else {}
            _TAG_FIELDS = ("customer_goal", "intervention_scene", "question_type", "tags")
            changed = False
            for field in ("safety_level", "visibility", "summary", "usage_note"):
                val = getattr(req, field, None)
                if val is not None and meta.get(field) != val:
                    meta[field] = val
                    changed = True
            for field in _TAG_FIELDS:
                val = getattr(req, field, None)
                if val is not None:
                    meta[field] = val
                    changed = True
            if changed:
                tpl.metadata_json = _json.dumps(meta, ensure_ascii=False)

    db.commit()

    # Auto-reindex
    r.source_hash = ""
    db.commit()
    index_db = SessionLocal()
    try:
        if r.source_type == "speech_template":
            from ..rag.resource_indexer import index_single_speech_template
            result = await index_single_speech_template(index_db, r.source_id)
        else:
            from ..rag.resource_indexer import index_single_material
            result = await index_single_material(index_db, r.source_id)
    finally:
        index_db.close()

    return {"status": "ok", "result": result}


@router.post("/resources/{resource_id}/reindex")
async def reindex_single_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagResource
    r = db.query(RagResource).filter(RagResource.id == resource_id).first()
    if not r:
        raise HTTPException(404, "资源不存在")
    r.source_hash = ""
    db.commit()
    index_db = SessionLocal()
    try:
        if r.source_type == "speech_template":
            from ..rag.resource_indexer import index_single_speech_template
            result = await index_single_speech_template(index_db, r.source_id)
        else:
            from ..rag.resource_indexer import index_single_material
            result = await index_single_material(index_db, r.source_id)
    except ImportError:
        # fallback: full type reindex
        from ..rag.resource_indexer import index_speech_templates, index_materials
        if r.source_type == "speech_template":
            result = await index_speech_templates(index_db)
        else:
            result = await index_materials(index_db)
    finally:
        index_db.close()
    return {"status": "ok", "result": result}


# ── Retrieval Logs ──

@router.get("/retrieval-logs")
def list_retrieval_logs(
    request: Request, db: Session = Depends(get_db),
    page: int = 1, page_size: int = 20,
    customer_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    _require_admin(request, db)
    from ..models_rag import RagRetrievalLog
    from ..security import json_loads as _jl
    query = db.query(RagRetrievalLog)
    if customer_id:
        query = query.filter(RagRetrievalLog.customer_id == customer_id)
    if start_date:
        from datetime import datetime as _dt
        try:
            sd = _dt.fromisoformat(start_date)
            query = query.filter(RagRetrievalLog.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        from datetime import datetime as _dt
        try:
            ed = _dt.fromisoformat(end_date)
            query = query.filter(RagRetrievalLog.created_at <= ed)
        except ValueError:
            pass
    total = query.count()
    logs = query.order_by(RagRetrievalLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [{"id": l.id, "customer_id": l.customer_id,
                    "query_text": (l.query_text or "")[:100],
                    "latency_ms": l.latency_ms,
                    "hits": _count_hits(_jl(l.hit_json, None)),
                    "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/retrieval-logs/{log_id}")
def get_retrieval_log(log_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    from ..models_rag import RagRetrievalLog
    from ..security import json_loads as _jl
    l = db.query(RagRetrievalLog).filter(RagRetrievalLog.id == log_id).first()
    if not l:
        raise HTTPException(404, "日志不存在")
    return {
        "id": l.id, "session_id": l.session_id, "message_id": l.message_id,
        "customer_id": l.customer_id, "query_text": l.query_text,
        "filter_json": _jl(l.filter_json, None), "hit_json": _jl(l.hit_json, None),
        "hits": _count_hits(_jl(l.hit_json, None)),
        "intent_json": _jl(l.intent_json, None), "query_intent_json": _jl(l.query_intent_json, None),
        "rerank_scores_json": _jl(l.rerank_scores_json, None),
        "latency_ms": l.latency_ms,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }
