"""ChromaDB 벡터 스토어 구현 (1단계).

임베딩은 외부(BaseEmbedder)에서 계산해 넘겨주므로, Chroma 자체의
임베딩 함수는 사용하지 않는다(embedding_function=None).
"""
from __future__ import annotations

import chromadb

from .base import BaseVectorStore, RetrievedChunk


class ChromaVectorStore(BaseVectorStore):
    def __init__(self, persist_dir: str, collection: str):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[RetrievedChunk]:
        res = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
        )
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        # cosine distance -> similarity (1 - distance)
        return [
            RetrievedChunk(text=d, metadata=m or {}, score=1.0 - dist)
            for d, m, dist in zip(docs, metas, dists)
        ]

    def count(self) -> int:
        return self._collection.count()
