"""CSV import helpers for speech templates."""
from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..rag.vocabulary import resolve_code, resolve_tag_values
from .crm_speech_templates import invalidate_cache


MULTI_VALUE_RE = re.compile(r"[|、,，;；/]+")

STYLE_ALIASES = {
    "专业温和": "professional",
    "客观专业": "professional",
    "实用落地": "professional",
    "温柔安抚": "encouraging",
    "鼓励共情": "encouraging",
    "鼓励": "encouraging",
    "共情": "encouraging",
    "专业": "professional",
    "竞争": "competitive",
    "冲刺": "competitive",
}

SCENE_ALIASES = {
    "craving": "obstacle_breaking",
    "dining_out": "qa_support",
    "outside_dining": "qa_support",
    "follow_up_review": "period_review",
}

KNOWN_SCENES = {
    "meal_checkin",
    "meal_review",
    "obstacle_breaking",
    "habit_education",
    "emotional_support",
    "qa_support",
    "period_review",
    "maintenance",
}

SOURCE_TYPE_ALIASES = {
    "speech": "speech_template",
    "speech_template": "speech_template",
    "template": "speech_template",
}


def decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "_", text)
    text = text.replace("-", "_")
    return text.lower()


def split_tag_values(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    values: list[str] = []
    for item in MULTI_VALUE_RE.split(text):
        code = normalize_code(item)
        if code and code not in values:
            values.append(code)
    return values


def normalize_style(row: dict[str, str]) -> str:
    raw = (row.get("style") or row.get("tone") or "").strip()
    code = normalize_code(raw)
    if code in {"professional", "encouraging", "competitive"}:
        return code
    return STYLE_ALIASES.get(raw, "professional")


def normalize_scene_key(row: dict[str, str]) -> str:
    candidates = split_tag_values(row.get("intervention_scene"))
    candidates.extend(split_tag_values(row.get("question_type")))
    for code in candidates:
        mapped = SCENE_ALIASES.get(code, code)
        if mapped in KNOWN_SCENES:
            return mapped

    question_type = normalize_code(row.get("question_type"))
    if question_type:
        return question_type[:64]
    return "rag_import"


def build_content(row: dict[str, str]) -> str:
    content = (row.get("clean_content") or row.get("content") or "").strip()
    summary = (row.get("summary") or "").strip()
    return content or summary


def _build_metadata_json(row: dict[str, str]) -> str:
    """Serialize CSV annotation fields into JSON for RAG indexing."""
    meta: dict[str, Any] = {}
    customer_goal = resolve_tag_values("customer_goal", row.get("customer_goal"))
    if customer_goal:
        meta["customer_goal"] = customer_goal
    intervention_scene = resolve_tag_values("intervention_scene", row.get("intervention_scene"))
    if intervention_scene:
        meta["intervention_scene"] = intervention_scene
    question_type = resolve_tag_values("question_type", row.get("question_type"))
    if question_type:
        meta["question_type"] = question_type
    safety_level = resolve_code("safety_level", normalize_code(row.get("safety_level")))
    if safety_level:
        meta["safety_level"] = safety_level
    visibility = resolve_code("visibility", normalize_code(row.get("visibility")))
    if visibility:
        meta["visibility"] = visibility
    summary = (row.get("summary") or "").strip()
    if summary:
        meta["summary"] = summary
    tags = split_tag_values(row.get("tags"))
    if tags:
        meta["tags"] = tags
    usage_note = (row.get("usage_note") or "").strip()
    if usage_note:
        meta["usage_note"] = usage_note
    return json.dumps(meta, ensure_ascii=False) if meta else ""


def validate_row(row: dict[str, str], line_no: int) -> list[str]:
    errors = []
    if not (row.get("title") or "").strip():
        errors.append(f"第 {line_no} 行缺少 title")
    if not build_content(row):
        errors.append(f"第 {line_no} 行缺少 clean_content/content")
    source_type = normalize_code(row.get("source_type"))
    if source_type and source_type not in SOURCE_TYPE_ALIASES:
        errors.append(f"第 {line_no} 行 source_type 不支持: {row.get('source_type')}")
    return errors


def parse_csv_text(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(csv_text))
    return [{k: (v or "") for k, v in row.items() if k is not None} for row in reader]


def import_speech_template_rows(
    db: Session,
    rows: list[dict[str, str]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "rows": [],
    }
    try:
        for index, row in enumerate(rows, start=2):
            row_errors = validate_row(row, index)
            if row_errors:
                stats["errors"].extend(row_errors)
                stats["skipped"] += 1
                continue

            status = normalize_code(row.get("status") or "approved")
            if status not in {"approved", "active"}:
                stats["skipped"] += 1
                continue

            scene_key = normalize_scene_key(row)
            style = normalize_style(row)
            title = (row.get("title") or "").strip()
            content = build_content(row)
            metadata_json = _build_metadata_json(row)

            existing = (
                db.query(models.SpeechTemplate)
                .filter(
                    models.SpeechTemplate.label == title,
                    models.SpeechTemplate.is_builtin == 0,
                )
                .first()
            )

            action = "created"
            if existing:
                existing.scene_key = scene_key
                existing.style = style
                existing.content = content
                existing.metadata_json = metadata_json
                action = "updated"
            else:
                db.add(models.SpeechTemplate(
                    scene_key=scene_key,
                    style=style,
                    label=title,
                    content=content,
                    metadata_json=metadata_json,
                    is_builtin=0,
                ))

            stats[action] += 1
            stats["rows"].append({
                "source_id": row.get("source_id", ""),
                "title": title,
                "scene_key": scene_key,
                "style": style,
                "action": action,
            })

        if dry_run:
            db.rollback()
        else:
            db.commit()
            invalidate_cache()
    except Exception:
        db.rollback()
        raise
    return stats


def import_speech_templates_csv(
    db: Session,
    csv_text: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    return import_speech_template_rows(db, parse_csv_text(csv_text), dry_run=dry_run)


def import_speech_templates_csv_file(
    db: Session,
    csv_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    return import_speech_templates_csv(db, decode_csv_bytes(csv_path.read_bytes()), dry_run=dry_run)
