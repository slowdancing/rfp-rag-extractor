"""HuggingFace 로컬 LLM 구현 (2단계, GCP VM + L4 GPU).

transformers 가 설치된 GPU 환경에서만 동작한다.
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
