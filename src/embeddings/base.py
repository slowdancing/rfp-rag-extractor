"""임베딩 백엔드 추상 인터페이스.

OpenAI(1단계) / HuggingFace(2단계) 구현체가 이 인터페이스를 따른다.
RAG 파이프라인은 구체 구현이 아니라 이 추상 타입에만 의존한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """텍스트를 벡터로 변환하는 임베더 공통 인터페이스."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """여러 문서(청크)를 임베딩한다."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """단일 질의를 임베딩한다."""
