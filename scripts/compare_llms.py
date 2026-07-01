"""여러 LLM의 답변 정확도를 비교한다. (결과 누적 방식)

임베딩·검색은 고정(현재 .env 설정)하고 LLM만 바꿔가며,
골든셋(메타데이터)으로 '정답 포함 정확도'를 측정한다.
end-to-end: 질의재작성→하이브리드검색→해당 LLM 생성→채점.

사전: 비교할 LLM 을 ollama pull, 그리고 임베딩 인덱스가 적재돼 있어야 함(scripts.ingest).

실행(여러 개 한 번에):
  python -m scripts.compare_llms qwen2.5:3b exaone3.5:2.4b gemma2:2b [표본수]
실행(메모리 안전 — 한 개씩, 결과 자동 누적):
  python -m scripts.compare_llms qwen2.5:3b 30
  python -m scripts.compare_llms exaone3.5:2.4b 30
  python -m scripts.compare_llms gemma2:2b 30

결과는 `results/compare_llms.json`(원장)에 모델별로 누적되고,
매 실행마다 `results/compare_llms.md`(비교표)를 원장 전체로 다시 만든다.
따라서 한 개씩 따로 돌려도 이전 결과가 사라지지 않는다.
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

LEDGER = Path("results/compare_llms.json")
REPORT = Path("results/compare_llms.md")


def _load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {}


def _write_report(ledger: dict) -> None:
    lines = ["# LLM 비교 (답변 정답 포함 정확도)", "",
             "> 모델별로 누적 저장됨(한 개씩 실행해도 유지). 정확도 높은 순.", ""]
    if ledger:
        any_e = next(iter(ledger.values()))
        lines += [f"- 평가셋: `{any_e.get('eval_path','?')}` (표본 {any_e.get('n','?')}건)",
                  f"- 임베딩: {any_e.get('embedding','?')} · base_url: {any_e.get('base_url','?')}",
                  ""]
    lines += ["| LLM | 정확도 | 정답/전체 |", "|------|------:|------:|"]
    for model, e in sorted(ledger.items(), key=lambda kv: kv[1]["acc"], reverse=True):
        lines.append(f"| {model} | {e['acc']:.3f} | {e['correct']}/{e['total']} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


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

    ledger = _load_ledger()
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
        # 모델별 결과를 원장에 upsert 하고, 매번 리포트를 다시 써서 중간에 죽어도 보존
        ledger[model] = {
            "acc": acc, "correct": correct, "total": total, "n": n,
            "eval_path": path,
            "embedding": f"{s.embedding_provider}/{s.openai_embedding_model}",
            "base_url": s.openai_base_url or "OpenAI",
        }
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_report(ledger)
        print(f"  정확도 {acc:.3f} ({correct}/{total})  [저장됨]")

    print(f"\n[compare] 원장 -> {LEDGER}  /  표 -> {REPORT}")


if __name__ == "__main__":
    main()
