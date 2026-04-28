"""RAG Pydantic schemas — data structures for retrieval results."""
from __future__ import annotations

from pydantic import BaseModel


class RagSource(BaseModel):
    resource_id: int
    source_type: str
    title: str
    snippet: str
    score: float
    content_kind: str
    tags: list[dict] = []
    safety_level: str = "general"
    filter_reason: str | None = None


class RagRecommendedAsset(BaseModel):
    material_id: int
    title: str
    material_type: str
    source_filename: str = ""
    preview_url: str | None = None
    download_url: str | None = None
    public_url: str | None = None
    reason: str = ""
    visibility: str = "coach_internal"
    safety_level: str = "general"
    customer_sendable: bool = False
    resource_id: int = 0


class RagBundle(BaseModel):
    sources: list[RagSource] = []
    recommended_assets: list[RagRecommendedAsset] = []
    rag_status: str = "ok"
    context_text: str = ""
