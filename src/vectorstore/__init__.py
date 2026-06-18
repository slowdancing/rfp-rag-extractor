"""벡터 스토어 팩토리."""
from __future__ import annotations

from src.config import Settings

from .base import BaseVectorStore, RetrievedChunk


def build_vector_store(settings: Settings) -> BaseVectorStore:
    store = settings.vector_store.lower()
    if store == "chroma":
        from .chroma_store import ChromaVectorStore

        return ChromaVectorStore(
            persist_dir=settings.chroma_persist_dir,
            collection=settings.chroma_collection,
        )
    raise ValueError(f"Unknown vector_store: {settings.vector_store}")


__all__ = ["BaseVectorStore", "RetrievedChunk", "build_vector_store"]
