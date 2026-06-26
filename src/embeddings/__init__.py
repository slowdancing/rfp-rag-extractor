"""임베딩 팩토리: 설정에 따라 적절한 임베더를 생성한다."""
from __future__ import annotations

from src.config import Settings

from .base import BaseEmbedder


def build_embedder(settings: Settings) -> BaseEmbedder:
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        from .openai_embedder import OpenAIEmbedder

        return OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            base_url=settings.openai_base_url,
        )
    if provider == "huggingface":
        from .hf_embedder import HuggingFaceEmbedder

        return HuggingFaceEmbedder(
            model=settings.hf_embedding_model,
            device=settings.hf_device,
        )
    raise ValueError(f"Unknown embedding_provider: {settings.embedding_provider}")


__all__ = ["BaseEmbedder", "build_embedder"]
