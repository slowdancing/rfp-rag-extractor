"""벡터 스토어 팩토리."""
from __future__ import annotations

import re

from src.config import Settings

from .base import BaseVectorStore, RetrievedChunk


def _active_embedding_model(settings: Settings) -> str:
    """현재 provider 에 따라 실제 사용 중인 임베딩 모델명을 반환."""
    if settings.embedding_provider.lower() == "huggingface":
        return settings.hf_embedding_model
    return settings.openai_embedding_model


def collection_name(settings: Settings) -> str:
    """임베딩 모델별로 분리된 컬렉션 이름.

    임베딩 모델마다 벡터 차원이 달라(예: OpenAI 1536 vs bge-m3 1024)
    같은 컬렉션에 섞이면 안 된다. 모델명을 접미사로 붙여 자동 분리한다.
    Chroma 컬렉션명 규칙([a-zA-Z0-9._-])에 맞게 정규화한다.
    """
    model = _active_embedding_model(settings)
    suffix = re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-")
    return f"{settings.chroma_collection}_{suffix}"


def build_vector_store(settings: Settings) -> BaseVectorStore:
    store = settings.vector_store.lower()
    if store == "chroma":
        from .chroma_store import ChromaVectorStore

        return ChromaVectorStore(
            persist_dir=settings.chroma_persist_dir,
            collection=collection_name(settings),
        )
    raise ValueError(f"Unknown vector_store: {settings.vector_store}")


__all__ = ["BaseVectorStore", "RetrievedChunk", "build_vector_store", "collection_name"]
