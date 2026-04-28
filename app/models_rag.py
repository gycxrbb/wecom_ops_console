"""RAG models — tag dictionary, resource index, chunks, retrieval logs."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class RagTag(Base):
    __tablename__ = "rag_tags"
    __table_args__ = (UniqueConstraint("dimension", "code", name="uq_rag_tags_dim_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagResource(Base):
    __tablename__ = "rag_resources"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_rag_res_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_quality: Mapped[str] = mapped_column(String(16), default="ok")
    content_kind: Mapped[str] = mapped_column(String(32), default="text")
    visibility: Mapped[str] = mapped_column(String(32), default="coach_internal")
    safety_level: Mapped[str] = mapped_column(String(32), default="general")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagResourceTag(Base):
    __tablename__ = "rag_resource_tags"

    resource_id: Mapped[int] = mapped_column(Integer, ForeignKey("rag_resources.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("rag_tags.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RagChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("resource_id", "chunk_index", "embedding_model", name="uq_rag_chunk_res_idx_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(Integer, ForeignKey("rag_resources.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector_point_id: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagRetrievalLog(Base):
    __tablename__ = "rag_retrieval_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    hit_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    intent_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_intent_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rerank_scores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
