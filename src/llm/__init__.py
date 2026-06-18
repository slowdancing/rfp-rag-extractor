"""LLM 팩토리: 설정에 따라 적절한 LLM 을 생성한다."""
from __future__ import annotations

from src.config import Settings

from .base import BaseLLM


def build_llm(settings: Settings) -> BaseLLM:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        from .openai_llm import OpenAILLM

        return OpenAILLM(
            api_key=settings.openai_api_key,
            model=settings.openai_llm_model,
        )
    if provider == "huggingface":
        from .hf_llm import HuggingFaceLLM

        return HuggingFaceLLM(model=settings.hf_llm_model, device=settings.hf_device)
    raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")


__all__ = ["BaseLLM", "build_llm"]
