"""여러 LLM의 답변 정확도를 한 번에 비교한다.

임베딩·검색은 고정(현재 .env 설정)하고 LLM만 바꿔가며,
골든셋(메타데이터)으로 '정답 포함 정확도'를 측정한다.
end-to-end: 질의재작성→하이브리드검색→해당 LLM 생성→채점.

사전: 비교할 LLM 을 ollama pull, 그리고 임베딩 인덱스가 적재돼 있어야 함(scripts.ingest).

실행:
  python -m scripts.compare_llms qwen2.5:7b exaone3.5:7.8b gemma2:9b [표본수]
출력: results/compare_llms.md
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from src.config import get_settings
from src.embeddings import build_embedder
from src.llm.openai_llm import OpenAILLM
from src.rag.hybrid import HybridRetriever
from src.rag.pipeline import RAGPipeline
from src.vectorstore import build_vector_store
from scripts.eval_generation import is_correct


def main() -> None:
    args = sys.argv[1:]
    n = 30
    if args and args[-1].isdigit():
        n = int(args[-1])
        args = args[:-1]
    models = args or [get_settings().openai_llm_model]

    s = get_settings()
    path = "data/eval/eval_set.jsonl"
    if not Path(path).exists():
        path = "data/eval/eval_set.draft.jsonl"
    items = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    random.seed(42)
    items = random.sample(items, min(n, len(items)))

    # 검색은 고정 (임베딩/하이브리드는 .env 설정 그대로)
    embedder = build_embedder(s)
    store = build_vector_store(s)
    hybrid = HybridRetriever(embedder, store, s.chunks_path)

    rows = []
    for model in models:
        print(f"\n=== {model} ===")
        llm = OpenAILLM(api_key=s.openai_api_key or "x", model=model,
                        base_url=s.openai_base_url, temperature=s.openai_temperature)
        pipe = RAGPipeline(embedder, store, llm, top_k=s.top_k, hybrid_retriever=hybrid)
        total = correct = 0
        for it in items:
            pred = pipe.ask(it["question"]).answer
            total += 1
            if is_correct(it, pred):
                correct += 1
        acc = correct / total if total else 0
        rows.append((model, acc, correct, total))
        print(f"  정확도 {acc:.3f} ({correct}/{total})")

    lines = ["# LLM 비교 (답변 정답 포함 정확도)", "",
             f"- 평가셋: `{path}` (표본 {n}건)",
             f"- 임베딩: {s.embedding_provider}/{s.openai_embedding_model} · base_url: {s.openai_base_url or 'OpenAI'}",
             "", "| LLM | 정확도 | 정답/전체 |", "|------|------:|------:|"]
    for model, acc, c, t in rows:
        lines.append(f"| {model} | {acc:.3f} | {c}/{t} |")
    out = Path("results/compare_llms.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[compare] 저장 -> {out}")


if __name__ == "__main__":
    main()
