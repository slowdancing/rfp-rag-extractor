"""OpenAI 임베딩 구현 (1단계)."""
from __future__ import annotations

from openai import OpenAI

from .base import BaseEmbedder


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", base_url: str | None = None):
        # base_url 지정 시 OpenAI 호환 엔드포인트(예: Ollama)로 임베딩 호출.
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # OpenAI 임베딩 API는 batch 입력을 지원한다.
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    def embed_query(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model=self._model, input=[text])
        return resp.data[0].embedding
