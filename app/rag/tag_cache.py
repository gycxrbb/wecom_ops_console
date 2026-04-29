"""In-memory cache for RAG tags — loaded from DB, replaces vocabulary.py for runtime lookups."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class _TagEntry:
    name: str
    description: str
    sort_order: int
    aliases: list[str] = field(default_factory=list)


class _TagCache:
    """Process-global tag cache loaded from rag_tags table."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, _TagEntry]] = {}
        self._lookup: dict[str, dict[str, str]] = {}
        self.loaded: bool = False

    def load(self, db) -> None:
        from ..models_rag import RagTag
        self._entries.clear()
        self._lookup.clear()
        for tag in db.query(RagTag).filter(RagTag.enabled == 1).all():
            aliases = json.loads(tag.aliases) if tag.aliases else []
            self._entries.setdefault(tag.dimension, {})[tag.code] = _TagEntry(
                name=tag.name,
                description=tag.description or "",
                sort_order=tag.sort_order,
                aliases=aliases,
            )
            self._lookup.setdefault(tag.dimension, {})[tag.name] = tag.code
            for alias in aliases:
                self._lookup.setdefault(tag.dimension, {})[alias] = tag.code
        self.loaded = True
        dims = {dim: len(entries) for dim, entries in self._entries.items()}
        _log.info("Tag cache loaded: %s", dims)

    def get_valid_codes(self, dimension: str) -> set[str]:
        return set(self._entries.get(dimension, {}).keys())

    def validate_code(self, dimension: str, value: str | None) -> str | None:
        if not value:
            return None
        v = value.strip().lower().replace("-", "_").replace(" ", "_")
        return v if v in self._entries.get(dimension, {}) else None

    def resolve_code(self, dimension: str, raw: str | None) -> str | None:
        if not raw:
            return None
        code = self.validate_code(dimension, raw)
        if code:
            return code
        return self._lookup.get(dimension, {}).get(raw.strip())

    def get_label(self, dimension: str, code: str) -> str:
        entry = self._entries.get(dimension, {}).get(code)
        return entry.name if entry else code

    def get_keywords(self, dimension: str) -> dict[str, str]:
        """All lookup keys (name + aliases) → code, for query_compiler keyword matching."""
        return dict(self._lookup.get(dimension, {}))


_cache: _TagCache | None = None


def _get() -> _TagCache:
    global _cache
    if _cache is None:
        _cache = _TagCache()
    return _cache


def is_loaded() -> bool:
    return _get().loaded


def load_from_db(db) -> None:
    _get().load(db)


def reload_from_db(db) -> None:
    _get().load(db)


def get_valid_codes(dimension: str) -> set[str]:
    return _get().get_valid_codes(dimension)


def validate_code(dimension: str, value: str | None) -> str | None:
    return _get().validate_code(dimension, value)


def resolve_code(dimension: str, raw: str | None) -> str | None:
    return _get().resolve_code(dimension, raw)


def get_label(dimension: str, code: str) -> str:
    return _get().get_label(dimension, code)


def get_keywords(dimension: str) -> dict[str, str]:
    return _get().get_keywords(dimension)


def resolve_tag_values(dimension: str, raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    values: list[str] = []
    for item in re.split(r"[|、,，;；/]+", raw):
        code = resolve_code(dimension, item.strip())
        if code and code not in values:
            values.append(code)
    return values
