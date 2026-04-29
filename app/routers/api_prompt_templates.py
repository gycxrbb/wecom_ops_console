# -*- coding: utf-8 -*-
"""Admin CRUD API for prompt template management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_prompt import (
    PromptTemplate, PromptTemplateVersion,
    PromptSnapshot, PromptSnapshotItem,
)
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user, require_role
from ..crm_profile.prompts.registry import reload_prompt, reload_all

router = APIRouter(
    prefix="/api/v1/admin/prompt-templates",
    tags=["prompt-templates"],
    route_class=UnifiedResponseRoute,
)


class PromptUpdateReq(BaseModel):
    content: str
    change_note: str = ""


class RollbackReq(BaseModel):
    version_id: int


class SnapshotSwitchReq(BaseModel):
    snapshot_id: int


# ── Template CRUD ────────────────────────────────────────────────────────────

@router.get("")
def list_templates(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    rows = db.query(PromptTemplate).order_by(
        PromptTemplate.layer, PromptTemplate.key
    ).all()
    return [
        {
            "id": r.id,
            "layer": r.layer,
            "key": r.key,
            "label": r.label,
            "version": r.version,
            "is_active": r.is_active,
            "content_length": len(r.content) if r.content else 0,
            "updated_by": r.updated_by,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.get("/tree")
def get_template_tree(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    rows = db.query(PromptTemplate).order_by(
        PromptTemplate.layer, PromptTemplate.key
    ).all()
    tree: dict[str, list] = {}
    for r in rows:
        layer_label = {
            "base": "基础层 (L1/L2)",
            "scene": "场景策略 (L3)",
            "style": "风格模板",
        }.get(r.layer, r.layer)
        tree.setdefault(layer_label, []).append({
            "id": r.id,
            "key": r.key,
            "label": r.label,
            "version": r.version,
        })
    return tree


@router.get("/{template_id}")
def get_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    row = db.query(PromptTemplate).get(template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    return {
        "id": row.id,
        "layer": row.layer,
        "key": row.key,
        "label": row.label,
        "content": row.content,
        "version": row.version,
        "is_active": row.is_active,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.put("/{template_id}")
def update_template(
    template_id: int,
    req: PromptUpdateReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, "admin")
    row = db.query(PromptTemplate).get(template_id)
    if not row:
        raise HTTPException(404, "Template not found")

    old_ver = row.version
    parts = old_ver.lstrip("v").split(".")
    new_minor = int(parts[1]) + 1 if len(parts) > 1 else 1
    new_ver = f"v{parts[0]}.{new_minor}"

    row.content = req.content
    row.version = new_ver
    row.updated_by = user.username

    db.add(PromptTemplateVersion(
        template_id=row.id, content=req.content, version=new_ver,
        change_note=req.change_note or f"Update from {old_ver} to {new_ver}",
        created_by=user.username,
    ))
    db.commit()
    db.refresh(row)
    reload_prompt(row.key)

    return {
        "id": row.id, "key": row.key, "version": new_ver,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── Per-template version history ─────────────────────────────────────────────

@router.get("/{template_id}/versions")
def list_versions(template_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    row = db.query(PromptTemplate).get(template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    versions = db.query(PromptTemplateVersion).filter_by(
        template_id=template_id
    ).order_by(PromptTemplateVersion.id.desc()).limit(20).all()
    return [
        {
            "id": v.id, "version": v.version, "change_note": v.change_note,
            "content_length": len(v.content) if v.content else 0,
            "created_by": v.created_by,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/{template_id}/versions/{version_id}")
def get_version_detail(
    template_id: int, version_id: int,
    request: Request, db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, "admin")
    v = db.query(PromptTemplateVersion).filter_by(
        template_id=template_id, id=version_id
    ).first()
    if not v:
        raise HTTPException(404, "Version not found")
    return {
        "id": v.id, "template_id": v.template_id, "version": v.version,
        "content": v.content, "change_note": v.change_note,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/{template_id}/rollback")
def rollback_template(
    template_id: int, req: RollbackReq,
    request: Request, db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, "admin")
    row = db.query(PromptTemplate).get(template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    ver = db.query(PromptTemplateVersion).filter_by(
        template_id=template_id, id=req.version_id
    ).first()
    if not ver:
        raise HTTPException(404, "Version not found")

    old_ver = row.version
    row.content = ver.content
    row.version = ver.version
    row.updated_by = user.username

    db.add(PromptTemplateVersion(
        template_id=row.id, content=ver.content, version=ver.version,
        change_note=f"Rollback from {old_ver} to {ver.version}",
        created_by=user.username,
    ))
    db.commit()
    reload_prompt(row.key)
    return {"ok": True, "version": ver.version}


# ── Global snapshots ─────────────────────────────────────────────────────────

@router.get("/snapshots/list")
def list_snapshots(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    snaps = db.query(PromptSnapshot).order_by(PromptSnapshot.id).all()
    result = []
    for s in snaps:
        item_count = db.query(PromptSnapshotItem).filter_by(snapshot_id=s.id).count()
        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "template_count": item_count,
            "created_by": s.created_by,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    snap = db.query(PromptSnapshot).get(snapshot_id)
    if not snap:
        raise HTTPException(404, "Snapshot not found")
    items = db.query(PromptSnapshotItem).filter_by(snapshot_id=snapshot_id).all()
    return {
        "id": snap.id,
        "name": snap.name,
        "description": snap.description,
        "created_by": snap.created_by,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
        "items": [
            {"template_key": i.template_key, "version": i.version}
            for i in items
        ],
    }


@router.post("/snapshots/switch")
def switch_snapshot(
    req: SnapshotSwitchReq,
    request: Request,
    db: Session = Depends(get_db),
):
    """Switch all templates to a snapshot version.

    For templates present in the snapshot: restore their content.
    For templates NOT in the snapshot (e.g. new in v2.1 but absent in v1.0):
    keep current content but log a warning.
    """
    user = get_current_user(request, db)
    require_role(user, "admin")
    snap = db.query(PromptSnapshot).get(req.snapshot_id)
    if not snap:
        raise HTTPException(404, "Snapshot not found")

    items = db.query(PromptSnapshotItem).filter_by(snapshot_id=req.snapshot_id).all()
    item_map = {i.template_key: i for i in items}

    all_templates = db.query(PromptTemplate).all()
    switched = []
    skipped = []

    for tpl in all_templates:
        if tpl.key in item_map:
            item = item_map[tpl.key]
            old_ver = tpl.version
            tpl.content = item.content
            tpl.version = item.version
            tpl.updated_by = f"snapshot:{snap.name}"

            db.add(PromptTemplateVersion(
                template_id=tpl.id, content=item.content, version=item.version,
                change_note=f"全局切换到快照「{snap.name}」（从 {old_ver} 到 {item.version}）",
                created_by=user.username,
            ))
            switched.append(tpl.key)
        else:
            skipped.append(tpl.key)

    db.commit()
    reload_all()

    return {
        "ok": True,
        "snapshot": snap.name,
        "switched": switched,
        "skipped": skipped,
        "message": (
            f"已切换 {len(switched)} 个模板到快照「{snap.name}」"
            + (f"，{len(skipped)} 个模板在该快照中不存在，保持当前内容" if skipped else "")
        ),
    }


@router.post("/snapshots/create")
def create_current_snapshot(request: Request, db: Session = Depends(get_db)):
    """Create a snapshot from all current active templates."""
    user = get_current_user(request, db)
    require_role(user, "admin")

    all_templates = db.query(PromptTemplate).all()
    if not all_templates:
        raise HTTPException(400, "No templates found")

    # Determine snapshot name
    existing_count = db.query(PromptSnapshot).count()
    name = f"manual_{existing_count + 1}"

    snap = PromptSnapshot(
        name=name,
        description=f"手动创建的快照，包含当前所有 {len(all_templates)} 个模板",
        created_by=user.username,
    )
    db.add(snap)
    db.flush()

    for tpl in all_templates:
        db.add(PromptSnapshotItem(
            snapshot_id=snap.id,
            template_key=tpl.key,
            version=tpl.version,
            content=tpl.content,
        ))

    db.commit()
    return {"ok": True, "snapshot_id": snap.id, "name": name, "template_count": len(all_templates)}


# ── Reseed ───────────────────────────────────────────────────────────────────

@router.post("/seed")
def reseed_templates(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, "admin")
    db.query(PromptSnapshotItem).delete()
    db.query(PromptSnapshot).delete()
    db.query(PromptTemplateVersion).delete()
    db.query(PromptTemplate).delete()
    db.commit()

    from ..services.prompt_seed import seed_prompt_templates
    seed_prompt_templates(db)

    reload_all()
    return {"ok": True, "message": "Reseeded from .md files"}
