"""Text chunking utilities for RAG indexing."""
from __future__ import annotations

import hashlib


def chunk_text(text: str, *, chunk_size: int = 600, overlap: int = 80) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
        if start >= len(text):
            break
    return chunks


def compute_hash(text: str) -> str:
    """SHA-256 hash for incremental change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
