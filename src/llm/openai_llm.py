"""OpenAI Chat 모델 구현 (1단계)."""
from __future__ import annotations

from openai import OpenAI

from .base import BaseLLM


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content or ""
