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
from .crm_speech_templates import SCENE_CATEGORY_MAP, invalidate_cache


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

# Base fallback scenes (used when tag_cache is not yet loaded)
_FALLBACK_SCENES = {
    "meal_checkin",
    "meal_review",
    "obstacle_breaking",
    "habit_education",
    "emotional_support",
    "qa_support",
    "period_review",
    "maintenance",
}


def _get_known_scenes() -> set[str]:
    """Load known scene keys from rag_tags (intervention_scene dimension), fallback to hardcoded."""
    try:
        from ..rag.tag_cache import tag_cache
        codes = tag_cache.get_valid_codes("intervention_scene")
        if codes:
            return set(codes)
    except Exception:
        pass
    return _FALLBACK_SCENES

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
    known_scenes = _get_known_scenes()
    candidates = split_tag_values(row.get("intervention_scene"))
    candidates.extend(split_tag_values(row.get("question_type")))
    for code in candidates:
        mapped = SCENE_ALIASES.get(code, code)
        if mapped in known_scenes:
            return mapped

    question_type = normalize_code(row.get("question_type"))
    if question_type:
        return question_type[:64]
    return "rag_import"


def build_content(row: dict[str, str]) -> str:
    content = (row.get("clean_content") or row.get("content") or "").strip()
    summary = (row.get("summary") or "").strip()
    return content or summary


def _build_metadata_json(row: dict[str, str]) -> tuple[str, list[str]]:
    """Serialize CSV annotation fields into JSON for RAG indexing. Returns (json_str, warnings)."""
    meta: dict[str, Any] = {}
    warnings: list[str] = []

    # Multi-value tag fields with unknown-value tracking
    for field in ("customer_goal", "intervention_scene", "question_type"):
        raw = split_tag_values(row.get(field))
        if not raw:
            continue
        resolved = resolve_tag_values(field, "|".join(raw))
        dropped = [v for v in raw if v not in resolved]
        if dropped:
            warnings.append(f"{field}: {', '.join(dropped)} 未命中词表")
        if resolved:
            meta[field] = resolved

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
    json_str = json.dumps(meta, ensure_ascii=False) if meta else ""
    return json_str, warnings


def validate_row(row: dict[str, str], line_no: int) -> list[str]:
    errors = []
    title = (row.get("title") or "").strip()
    if not title:
        errors.append(f"第 {line_no} 行缺少 title")
    elif len(title) > 128:
        errors.append(f"第 {line_no} 行 title 超过 128 字符限制（当前 {len(title)} 字符）")
    if not build_content(row):
        errors.append(f"第 {line_no} 行缺少 clean_content/content")
    source_type = normalize_code(row.get("source_type"))
    if source_type and source_type not in SOURCE_TYPE_ALIASES:
        errors.append(f"第 {line_no} 行 source_type 不支持: {row.get('source_type')}")
    return errors


def _check_safety_rules(row: dict[str, str], line_no: int) -> list[str]:
    """Validate safety-level hard rules. Returns error list."""
    errors = []
    safety = normalize_code(row.get("safety_level"))
    visibility = normalize_code(row.get("visibility"))
    if safety == "contraindicated":
        errors.append(f"第 {line_no} 行 safety_level=contraindicated，禁止进入 RAG 索引")
    if safety in ("medical_sensitive", "doctor_review") and visibility == "customer_visible":
        errors.append(f"第 {line_no} 行 safety_level={safety} 不可设为 customer_visible")
    return errors


def parse_csv_text(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(csv_text))
    return [{k: (v or "") for k, v in row.items() if k is not None} for row in reader]


def import_speech_template_rows(
    db: Session,
    rows: list[dict[str, str]],
    *,
    dry_run: bool = False,
    owner_id: int | None = None,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "warnings": [],
        "rows": [],
    }

    # Pre-load category lookups
    l3_name_to_id: dict[str, int] = dict(
        db.query(models.SpeechCategory.name, models.SpeechCategory.id)
        .filter(
            models.SpeechCategory.level == 3,
            models.SpeechCategory.deleted_at.is_(None),
        ).all()
    )
    l2_name_to_id: dict[str, int] = dict(
        db.query(models.SpeechCategory.name, models.SpeechCategory.id)
        .filter(
            models.SpeechCategory.level == 2,
            models.SpeechCategory.deleted_at.is_(None),
        ).all()
    )
    code_to_id: dict[str, int] = dict(
        db.query(models.SpeechCategory.code, models.SpeechCategory.id)
        .filter(
            models.SpeechCategory.code.isnot(None),
            models.SpeechCategory.deleted_at.is_(None),
        ).all()
    )

    try:
        for index, row in enumerate(rows, start=2):
            row_errors = validate_row(row, index)
            safety_errors = _check_safety_rules(row, index)
            row_errors.extend(safety_errors)
            if row_errors:
                stats["errors"].extend(row_errors)
                stats["skipped"] += 1
                continue

            status = normalize_code(row.get("status") or "approved")
            if status not in {"approved", "active"}:
                stats["skipped"] += 1
                stats["errors"].append(f"第 {index} 行状态为 {status}，跳过")
                continue

            scene_key = normalize_scene_key(row)
            style = normalize_style(row)
            title = (row.get("title") or "").strip()
            content = build_content(row)
            metadata_json, meta_warnings = _build_metadata_json(row)
            if meta_warnings:
                for w in meta_warnings:
                    stats["warnings"].append(f"第 {index} 行 {w}")

            # Resolve category_id: category_code > SCENE_CATEGORY_MAP > None
            category_id: int | None = None
            cat_code_raw = (row.get("category_code") or "").strip()
            if cat_code_raw:
                cat_code = normalize_code(cat_code_raw)
                category_id = code_to_id.get(cat_code)
                if not category_id:
                    stats["errors"].append(f"第 {index} 行 category_code '{cat_code_raw}' 未找到对应分类")
                    stats["skipped"] += 1
                    continue
            else:
                mapping = SCENE_CATEGORY_MAP.get(scene_key)
                if isinstance(mapping, tuple):
                    category_id = l3_name_to_id.get(mapping[1])
                elif mapping:
                    category_id = l2_name_to_id.get(mapping)

            # Dedup by (scene_key, style) for non-builtin templates
            existing = (
                db.query(models.SpeechTemplate)
                .filter(
                    models.SpeechTemplate.scene_key == scene_key,
                    models.SpeechTemplate.style == style,
                    models.SpeechTemplate.is_builtin == 0,
                )
                .first()
            )

            action = "created"
            if existing:
                existing.label = title
                existing.content = content
                existing.metadata_json = metadata_json
                if category_id:
                    existing.category_id = category_id
                action = "updated"
            else:
                db.add(models.SpeechTemplate(
                    scene_key=scene_key,
                    style=style,
                    label=title,
                    content=content,
                    metadata_json=metadata_json,
                    is_builtin=0,
                    owner_id=owner_id,
                    category_id=category_id,
                ))

            stats[action] += 1
            stats["rows"].append({
                "source_id": row.get("source_id", ""),
                "title": title,
                "scene_key": scene_key,
                "style": style,
                "action": action,
                "category_code": cat_code_raw or "",
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
    owner_id: int | None = None,
) -> dict[str, Any]:
    return import_speech_template_rows(db, parse_csv_text(csv_text), dry_run=dry_run, owner_id=owner_id)


def import_speech_templates_csv_file(
    db: Session,
    csv_path: Path,
    *,
    dry_run: bool = False,
    owner_id: int | None = None,
) -> dict[str, Any]:
    return import_speech_templates_csv(db, decode_csv_bytes(csv_path.read_bytes()), dry_run=dry_run, owner_id=owner_id)
