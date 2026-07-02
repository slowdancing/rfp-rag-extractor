"""HuggingFace 임베딩 구현 — 대안 경로 (현재 배포 미사용).

⚠️ 현재 배포는 Ollama 경로를 사용한다: `provider=openai` + `base_url`(Ollama)로
   bge-m3 를 호출하며, 그 처리는 `openai_embedder.py`(OpenAI 호환 클라이언트)가 담당한다.
   → 즉 이 파일은 배포에서 실행되지 않는다.
   (단, 임베딩 모델 비교 실험 `scripts/compare_embeddings.py`의 `hf:` 옵션에서는
    sentence-transformers 로 직접 로딩해 비교하는 데 쓰였다.)

이 구현은 sentence-transformers 로 모델을 **직접 로딩**하는 대안 경로다.
`provider=huggingface`일 때만 동작하며, GPU/CPU 어디서나 쓸 수 있다.
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
