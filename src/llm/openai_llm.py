"""OpenAI Chat 모델 구현 (1단계)."""
from __future__ import annotations

from openai import OpenAI

from .base import BaseLLM


class OpenAILLM(BaseLLM):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float | None = None,
        base_url: str | None = None,
    ):
        # temperature=None 이면 요청에 포함하지 않음(모델 기본값 사용).
        # gpt-5 계열 등 추론형 모델은 temperature=1 만 허용하므로 기본을 None 으로 둔다.
        # base_url 지정 시 OpenAI 호환 엔드포인트(예: Ollama http://localhost:11434/v1) 사용.
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model
        self._temperature = temperature

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        kwargs = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
