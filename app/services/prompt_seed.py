# -*- coding: utf-8 -*-
"""Seed prompt_templates and prompt_template_versions from .md files and git history."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from ..models_prompt import (
    PromptTemplate, PromptTemplateVersion,
    PromptSnapshot, PromptSnapshotItem,
)

_log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "crm_profile" / "prompts"
_V1_COMMIT = "e3d4270"


def _read_current(rel_path: str) -> str:
    fp = _PROMPTS_DIR / rel_path
    if not fp.exists():
        return ""
    return fp.read_text(encoding="utf-8").strip()


def _read_v1(rel_path: str) -> str:
    try:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["git", "show", f"{_V1_COMMIT}:app/crm_profile/prompts/{rel_path}"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(repo_root), timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        _log.warning("Failed to read v1.0 from git for %s: %s", rel_path, e)
    return ""


# (layer, key, label, has_v1, v2_md_path)
_TEMPLATE_DEFS = [
    ("base", "platform_guardrails", "平台底线", True, "base/platform_guardrails.md"),
    ("base", "health_coach_core", "核心角色", True, "base/health_coach_core.md"),
    ("base", "visible_thinking_core", "可见思考", True, "base/visible_thinking_core.md"),
    ("base", "context_header", "上下文 Header", False, "base/context_header.md"),
    ("base", "rag_header", "RAG Header", False, "base/rag_header.md"),
    ("base", "scene_hint_header", "场景偏好提示", False, "base/scene_hint_header.md"),
    ("scene", "meal_review", "餐评", True, "scenes/meal_review.md"),
    ("scene", "data_monitoring", "数据监测", True, "scenes/data_monitoring.md"),
    ("scene", "abnormal_intervention", "异常干预", True, "scenes/abnormal_intervention.md"),
    ("scene", "qa_support", "问题答疑", True, "scenes/qa_support.md"),
    ("scene", "period_review", "周月复盘", True, "scenes/period_review.md"),
    ("scene", "long_term_maintenance", "长期维护", True, "scenes/long_term_maintenance.md"),
    ("style", "coach_brief", "教练简报", False, "styles/coach_brief.md"),
    ("style", "customer_reply", "客户话术", False, "styles/customer_reply.md"),
    ("style", "handoff_note", "交接备注", False, "styles/handoff_note.md"),
    ("style", "bullet_list", "要点列表", False, "styles/bullet_list.md"),
    ("style", "detailed_report", "详细报告", False, "styles/detailed_report.md"),
]


def _seed_templates(db: Session) -> list[tuple[str, str, str]]:
    """Seed prompt templates if table is empty. Returns v1 snapshot items."""
    if db.query(PromptTemplate).first() is not None:
        _log.info("prompt_templates already seeded, skipping template creation")
        return []

    _log.info("Seeding prompt_templates from .md files and git v1.0 history ...")
    v1_snapshot_items: list[tuple[str, str, str]] = []

    for layer, key, label, has_v1, v2_path in _TEMPLATE_DEFS:
        v2_content = _read_current(v2_path)
        if not v2_content:
            _log.warning("Skipping %s/%s: no content found", layer, key)
            continue

        tpl = PromptTemplate(
            layer=layer, key=key, label=label,
            content=v2_content, version="v2.1",
            is_active=True, updated_by="system",
        )
        db.add(tpl)
        db.flush()

        db.add(PromptTemplateVersion(
            template_id=tpl.id, content=v2_content, version="v2.1",
            change_note="v2.1 提示词优化（含话术规范、称呼规则、Few-shot）",
            created_by="system",
        ))

        if has_v1:
            v1_content = _read_v1(v2_path)
            if v1_content:
                db.add(PromptTemplateVersion(
                    template_id=tpl.id, content=v1_content, version="v1.0",
                    change_note="v1.0 初始版本", created_by="system",
                ))
                v1_snapshot_items.append((key, "v1.0", v1_content))

    db.commit()
    return v1_snapshot_items


def _seed_snapshots(db: Session, v1_snapshot_items: list[tuple[str, str, str]]) -> None:
    """Create v1.0 and v2.1 snapshots if they don't exist."""
    if db.query(PromptSnapshot).first() is not None:
        _log.info("prompt_snapshots already exist, skipping snapshot creation")
        return

    _log.info("Creating prompt snapshots ...")

    # v1.0 snapshot — only templates that existed in v1.0
    if v1_snapshot_items:
        snap_v1 = PromptSnapshot(
            name="v1.0",
            description="初始版本（9 条模板，无风格模板和 Header）",
            created_by="system",
        )
        db.add(snap_v1)
        db.flush()
        for key, ver, content in v1_snapshot_items:
            db.add(PromptSnapshotItem(
                snapshot_id=snap_v1.id,
                template_key=key, version=ver, content=content,
            ))
    else:
        # Templates existed before snapshots were added — rebuild v1.0 from git
        _log.info("Rebuilding v1.0 snapshot from git history ...")
        snap_v1 = PromptSnapshot(
            name="v1.0",
            description="初始版本（9 条模板，无风格模板和 Header）",
            created_by="system",
        )
        db.add(snap_v1)
        db.flush()
        for layer, key, label, has_v1, v2_path in _TEMPLATE_DEFS:
            if not has_v1:
                continue
            v1_content = _read_v1(v2_path)
            if v1_content:
                db.add(PromptSnapshotItem(
                    snapshot_id=snap_v1.id,
                    template_key=key, version="v1.0", content=v1_content,
                ))

    # v2.1 snapshot — all current templates
    snap_v2 = PromptSnapshot(
        name="v2.1",
        description="v2.1 优化版（含话术规范、称呼规则、Few-shot、风格模板、Header）",
        created_by="system",
    )
    db.add(snap_v2)
    db.flush()
    for layer, key, label, has_v1, v2_path in _TEMPLATE_DEFS:
        v2_content = _read_current(v2_path)
        if v2_content:
            db.add(PromptSnapshotItem(
                snapshot_id=snap_v2.id,
                template_key=key, version="v2.1", content=v2_content,
            ))

    db.commit()
    _log.info("prompt snapshots created (v1.0 + v2.1)")


def seed_prompt_templates(db: Session) -> None:
    """Seed prompt templates and snapshots if missing."""
    v1_items = _seed_templates(db)
    _seed_snapshots(db, v1_items)
