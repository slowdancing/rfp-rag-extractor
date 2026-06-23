"""하이브리드 검색 (BM25 키워드 + dense 임베딩).

자연어 질문은 dense 임베딩만으로는 변별력이 떨어진다(흔한 일반어가 핵심어를 희석).
키워드 정확 매칭에 강한 BM25 를 결합해 검색 품질을 높인다.

- BM25: 한국어 조사 부착 문제를 피하려고 **문자 바이그램** 토크나이저 사용.
- 결합: 점수 스케일이 다른 두 검색을 **RRF(Reciprocal Rank Fusion)** 로 융합.
"""
from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd
from rank_bm25 import BM25Okapi

from src.embeddings.base import BaseEmbedder
from src.vectorstore.base import BaseVectorStore, RetrievedChunk

_TOKEN = re.compile(r"[가-힣]+|[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    """검색용 토큰화.

    - 한글 토큰(길이>=2): 문자 바이그램으로 분해 (조사 부착에 강함)
    - 영문/숫자: 그대로 (소문자)
    """
    tokens: list[str] = []
    for m in _TOKEN.findall(str(text).lower()):
        if "가" <= m[0] <= "힣":  # 한글
            if len(m) >= 2:
                tokens.extend(m[i : i + 2] for i in range(len(m) - 1))  # 바이그램
            else:
                tokens.append(m)
        else:
            tokens.append(m)
    return tokens


class HybridRetriever:
    """BM25 + dense 를 RRF 로 결합하는 검색기."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        chunks_csv: str = "data/processed/chunks.csv",
        candidates: int = 50,
        k_rrf: int = 60,
    ):
        self._embedder = embedder
        self._store = vector_store
        self._candidates = candidates
        self._k_rrf = k_rrf

        # BM25 인덱스 구축 (chunks.csv 의 text 기준)
        self._df = pd.read_csv(chunks_csv)
        self._df["text"] = self._df["text"].astype(str)
        self._bm25 = BM25Okapi([tokenize(t) for t in self._df["text"]])
        # chunk_id -> 행 인덱스 (결과 조립용)
        self._meta_cols = [c for c in self._df.columns if c != "text"]

    def _row_to_chunk(self, idx: int, score: float) -> RetrievedChunk:
        row = self._df.iloc[idx]
        metadata = {c: row[c] for c in self._meta_cols}
        return RetrievedChunk(text=row["text"], metadata=metadata, score=score)

    def retrieve(
        self, query: str, top_k: int = 5, where: dict | None = None
    ) -> list[RetrievedChunk]:
        # --- dense ---
        dense = self._store.query(
            self._embedder.embed_query(query), self._candidates, where=where
        )
        dense_ids = [c.metadata.get("chunk_id") for c in dense]

        # --- sparse (BM25) ---
        scores = self._bm25.get_scores(tokenize(query))
        order = scores.argsort()[::-1]
        sparse_idx = [int(i) for i in order[: self._candidates]]
        # where 필터(예: 특정 doc_id) 적용
        if where:
            (k, v), = where.items()
            sparse_idx = [i for i in sparse_idx if self._df.iloc[i].get(k) == v]
        id_to_idx = {self._df.iloc[i]["chunk_id"]: i for i in sparse_idx}
        sparse_ids = [self._df.iloc[i]["chunk_id"] for i in sparse_idx]

        # --- RRF 융합 ---
        rrf: dict[str, float] = defaultdict(float)
        for rank, cid in enumerate(dense_ids):
            if cid is not None:
                rrf[cid] += 1.0 / (self._k_rrf + rank + 1)
        for rank, cid in enumerate(sparse_ids):
            rrf[cid] += 1.0 / (self._k_rrf + rank + 1)

        top_ids = sorted(rrf, key=rrf.get, reverse=True)[:top_k]

        # 결과 조립 (dense 결과의 텍스트/메타 우선, 없으면 BM25 df 에서)
        dense_by_id = {c.metadata.get("chunk_id"): c for c in dense}
        results = []
        for cid in top_ids:
            if cid in dense_by_id:
                c = dense_by_id[cid]
                results.append(RetrievedChunk(c.text, c.metadata, rrf[cid]))
            elif cid in id_to_idx:
                results.append(self._row_to_chunk(id_to_idx[cid], rrf[cid]))
        return results
