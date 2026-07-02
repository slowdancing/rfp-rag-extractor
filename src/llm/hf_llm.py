"""HuggingFace 로컬 LLM 구현 — 대안 경로 (현재 배포 미사용).

⚠️ 현재 배포는 Ollama 경로를 사용한다: `provider=openai` + `base_url`(Ollama)로
   EXAONE를 호출하며, 그 처리는 `openai_llm.py`(OpenAI 호환 클라이언트)가 담당한다.
   → 즉 이 파일은 실행되지 않는다.

이 구현은 torch/transformers 로 모델을 GPU에 **직접 로딩**하는 대안 경로다.
- 남겨둔 이유: 추상화(백엔드 교체 가능) 예시 + Ollama에 없는 커스텀/파인튜닝 모델을
  직접 돌려야 할 때의 폴백. `provider=huggingface`일 때만 동작한다.
- transformers 가 설치된 GPU 환경에서만 사용 가능(무거운 import 는 지연 로딩).
"""
from __future__ import annotations

from .base import BaseLLM


class HuggingFaceLLM(BaseLLM):
    def __init__(self, model: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct", device: str = "cuda"):
        # 무거운 import 는 실제 사용할 때만 로드한다.
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(model)
        self._model = AutoModelForCausalLM.from_pretrained(
            model,
            torch_dtype=torch.bfloat16,
            device_map=device,
        )
        self._device = device

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(text, return_tensors="pt").to(self._device)
        out = self._model.generate(**inputs, max_new_tokens=1024, do_sample=False)
        # 입력 토큰을 제외한 생성분만 디코딩
        generated = out[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated, skip_special_tokens=True)
