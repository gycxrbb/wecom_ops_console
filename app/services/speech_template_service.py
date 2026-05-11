"""Unified service for speech template writes — single point of truth for all 3 entry points.

Three entry points (manual create, RAG meta patch, CSV import) all route through
`upsert_speech_template` so that category resolution, vocabulary validation,
builtin protection, and RAG indexing happen consistently.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from ..models import SpeechCategory, SpeechTemplate
from ..rag.vocabulary import resolve_code, resolve_tag_values
from ..schemas.speech_template import SpeechMetadata
from ..services.crm_speech_templates import SCENE_CATEGORY_MAP, invalidate_cache

_log = logging.getLogger(__name__)

_VALID_SAFETY = {'general', 'nutrition_education', 'medical_sensitive', 'doctor_review', 'contraindicated'}
_VALID_VISIBILITY = {'coach_internal', 'customer_visible'}


def validate_metadata_vocabulary(meta: SpeechMetadata) -> tuple[SpeechMetadata, dict[str, list[str]]]:
    """Validate RAG metadata against vocabulary, return (cleaned_meta, dropped_values)."""
    dropped: dict[str, list[str]] = {}

    # Validate scalar enums
    if meta.safety_level and meta.safety_level not in _VALID_SAFETY:
        resolved = resolve_code('safety_level', meta.safety_level)
        if resolved:
            meta.safety_level = resolved
        else:
            dropped.setdefault('safety_level', []).append(meta.safety_level)
            meta.safety_level = None

    if meta.visibility and meta.visibility not in _VALID_VISIBILITY:
        resolved = resolve_code('visibility', meta.visibility)
        if resolved:
            meta.visibility = resolved
        else:
            dropped.setdefault('visibility', []).append(meta.visibility)
            meta.visibility = None

    # Validate multi-value tags
    for field in ('customer_goal', 'intervention_scene', 'question_type'):
        raw = getattr(meta, field, None)
        if not raw:
            continue
        raw_str = '|'.join(raw) if isinstance(raw, list) else str(raw)
        resolved_list = resolve_tag_values(field, raw_str)
        if len(resolved_list) != len(raw):
            invalid = [v for v in raw if v not in resolved_list]
            if invalid:
                dropped[field] = invalid
        setattr(meta, field, resolved_list)

    return meta, dropped


def validate_safety_rules(meta: SpeechMetadata) -> list[str]:
    """Return list of safety rule violations."""
    errors = []
    if meta.safety_level in ('medical_sensitive', 'doctor_review'):
        if meta.visibility == 'customer_visible':
            errors.append(f'{meta.safety_level} 内容不可设为客户可见')
    if meta.safety_level == 'contraindicated':
        errors.append('contraindicated 内容禁止进入 RAG 索引')
    return errors


def resolve_category_id(
    db: Session,
    *,
    category_id: int | None = None,
    scene_key: str | None = None,
) -> int | None:
    """Resolve category_id: explicit id > SCENE_CATEGORY_MAP fallback > None."""
    if category_id:
        cat = db.query(SpeechCategory).get(category_id)
        if cat and cat.deleted_at is None and cat.level == 3:
            return category_id
        # Accept L2 for backward compat
        if cat and cat.deleted_at is None and cat.level == 2:
            return category_id
        return category_id  # trust caller

    # Fallback: scene_key → SCENE_CATEGORY_MAP
    if not scene_key or scene_key not in SCENE_CATEGORY_MAP:
        return None

    mapping = SCENE_CATEGORY_MAP[scene_key]
    l3_name = mapping[1] if isinstance(mapping, tuple) else mapping
    if not l3_name:
        return None

    row = db.query(SpeechCategory).filter_by(
        name=l3_name, level=3, deleted_at=None,
    ).first()
    return row.id if row else None


def upsert_speech_template(
    db: Session,
    *,
    # Layer 1: business identity
    scene_key: str,
    style: str,
    # Layer 2: content
    label: str = '',
    content: str = '',
    # Layer 3: category
    category_id: int | None = None,
    # Layer 4: RAG metadata
    metadata: SpeechMetadata | None = None,
    # Ownership
    owner_id: int | None = None,
    # For updates
    template_id: int | None = None,
    # Control
    index_rag: bool = True,
    allow_builtin_override: bool = False,
) -> SpeechTemplate:
    """Create or update a speech template. Returns the saved row.

    This is the ONLY function that should write to `speech_templates`.
    """
    # Resolve category
    resolved_cat_id = resolve_category_id(
        db, category_id=category_id, scene_key=scene_key,
    )

    if template_id:
        # Update existing
        row = db.query(SpeechTemplate).get(template_id)
        if not row:
            raise ValueError(f'Template {template_id} not found')
        if row.is_builtin == 1 and not allow_builtin_override:
            raise PermissionError('内置模板不可修改')
    else:
        # Create new
        row = SpeechTemplate(
            scene_key=scene_key,
            style=style,
            label=label,
            content=content,
            is_builtin=0,
            owner_id=owner_id,
            category_id=resolved_cat_id,
        )
        db.add(row)
        db.flush()

    # Update content fields
    if label:
        row.label = label
    if content:
        row.content = content
    if resolved_cat_id is not None:
        row.category_id = resolved_cat_id

    # Update metadata_json if provided
    if metadata is not None:
        existing_meta: dict = {}
        if row.metadata_json:
            try:
                existing_meta = json.loads(row.metadata_json)
            except (json.JSONDecodeError, TypeError):
                existing_meta = {}

        update = metadata.model_dump(exclude_none=True)
        # Replace list fields entirely, merge scalar fields
        for k, v in update.items():
            existing_meta[k] = v

        row.metadata_json = json.dumps(existing_meta, ensure_ascii=False) if existing_meta else ""

    db.commit()
    db.refresh(row)
    invalidate_cache()
    return row
