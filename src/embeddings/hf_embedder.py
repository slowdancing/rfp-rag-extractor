"""HuggingFace 임베딩 구현 (2단계, GCP VM + L4 GPU).

sentence-transformers 가 설치된 환경에서만 동작한다.
BAAI/bge-m3 등 multilingual 모델을 쓰면 한국어 RFP 에 적합하다.
"""
from __future__ import annotations

from .base import BaseEmbedder


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, model: str = "BAAI/bge-m3", device: str = "cuda"):
        # import 를 지연시켜, OpenAI 단계에서는 무거운 의존성을 요구하지 않는다.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model, device=device)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec[0].tolist()
