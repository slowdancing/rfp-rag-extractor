"""벡터 스토어 추상 인터페이스.

Chroma(1단계) / Qdrant 등으로 교체할 수 있도록 추상화한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    """검색 결과 청크 한 건."""

    text: str
    metadata: dict
    score: float


class BaseVectorStore(ABC):
    @abstractmethod
    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """임베딩된 청크들을 저장한다."""

    @abstractmethod
    def query(
        self,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[RetrievedChunk]:
        """질의 임베딩과 유사한 청크를 검색한다. where 로 메타데이터 필터링."""

    @abstractmethod
    def count(self) -> int:
        """저장된 청크 수."""
