"""평가 스크립트.

실행:  python -m scripts.evaluate data/eval/eval_set.jsonl
검색(Hit@k, MRR)과 (정답이 있으면) LLM-judge 생성 평가를 수행한다.
"""
from __future__ import annotations

import json
import sys

from src.config import get_settings
from src.evaluation import (
    evaluate_generation_llm_judge,
    evaluate_retrieval,
    load_eval_set,
)
from src.llm import build_llm
from src.rag import build_pipeline


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m scripts.evaluate <eval_set.jsonl>")
        sys.exit(1)
    eval_path = sys.argv[1]

    settings = get_settings()
    pipeline = build_pipeline(settings)
    items = load_eval_set(eval_path)

    retrieval = evaluate_retrieval(pipeline, items, top_k=settings.top_k)
    print("[검색 평가]", json.dumps(retrieval, ensure_ascii=False, indent=2))

    judge = build_llm(settings)  # 동일 LLM 을 judge 로 사용(원하면 별도 모델 지정)
    generation = evaluate_generation_llm_judge(pipeline, items, judge)
    print("[생성 평가]", json.dumps(generation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
