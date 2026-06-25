"""검색 평가: dense vs 하이브리드 검색 품질을 골든셋으로 비교한다.

지표: Hit@1 / Hit@3 / Hit@5 / MRR (정답 doc_id 가 상위 k 안에 들어오는가)
LLM 을 쓰지 않아 빠르고 저렴하다(질의 임베딩만).

평가셋: data/eval/eval_set.jsonl 이 있으면 사용, 없으면 초안(draft) 사용.
결과: results/eval_retrieval.md 저장.

실행: python -m scripts.eval_retrieval
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from src.config import get_settings
from src.evaluation import load_eval_set
from src.rag import build_pipeline

KS = (1, 3, 5)


def _doc_ranks(chunks) -> list[str]:
    """검색된 청크들에서 문서 단위 순위(중복 제거)를 만든다."""
    docs = []
    for c in chunks:
        d = c.metadata.get("doc_id")
        if d not in docs:
            docs.append(d)
    return docs


def _evaluate(retrieve_fn, items) -> dict:
    metrics = {f"hit@{k}": 0 for k in KS}
    metrics["mrr"] = 0.0
    n = 0
    for it in items:
        if not it.doc_id:
            continue
        n += 1
        docs = _doc_ranks(retrieve_fn(it.question, max(KS)))
        if it.doc_id in docs:
            rank = docs.index(it.doc_id) + 1
            metrics["mrr"] += 1.0 / rank
            for k in KS:
                if rank <= k:
                    metrics[f"hit@{k}"] += 1
    return {key: (v / n if n else 0.0) for key, v in metrics.items()} | {"n": n}


def main() -> None:
    eval_path = "data/eval/eval_set.jsonl"
    if not Path(eval_path).exists():
        eval_path = "data/eval/eval_set.draft.jsonl"
    items = load_eval_set(eval_path)

    s = get_settings()
    pipe = build_pipeline(s)

    # 하이브리드 (현재 설정)
    hybrid = _evaluate(lambda q, k: pipe.retrieve(q, top_k=k), items)
    # dense (하이브리드 끄기)
    pipe._hybrid = None
    dense = _evaluate(lambda q, k: pipe.retrieve(q, top_k=k), items)

    lines = [
        "# 검색 평가 결과 (dense vs 하이브리드)",
        "",
        f"- 평가셋: `{eval_path}` ({hybrid['n']}건, doc_id 라벨 기준)",
        f"- 임베딩: {s.embedding_provider} / {s.openai_embedding_model}",
        "",
        "| 방식 | Hit@1 | Hit@3 | Hit@5 | MRR |",
        "|------|------:|------:|------:|------:|",
        f"| dense  | {dense['hit@1']:.3f} | {dense['hit@3']:.3f} | {dense['hit@5']:.3f} | {dense['mrr']:.3f} |",
        f"| hybrid | {hybrid['hit@1']:.3f} | {hybrid['hit@3']:.3f} | {hybrid['hit@5']:.3f} | {hybrid['mrr']:.3f} |",
        "",
    ]
    report = "\n".join(lines)
    print(report)

    out = Path("results/eval_retrieval.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"[eval] 저장 -> {out}")


if __name__ == "__main__":
    main()
