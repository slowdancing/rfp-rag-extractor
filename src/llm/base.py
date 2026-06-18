"""LLM 백엔드 추상 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """답변 생성 LLM 공통 인터페이스."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """system/user 프롬프트를 받아 텍스트 답변을 생성한다."""
