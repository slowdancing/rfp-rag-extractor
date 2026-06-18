"""RAG 성능 평가.

팀이 직접 평가지표를 선정/확장할 수 있도록 골격을 제공한다.
기본 제공:
  - 검색 평가(retrieval): Hit@k, MRR  (정답 문서 ID가 검색결과에 포함되는가)
  - 생성 평가(generation): LLM-as-judge (정답/근거 대비 정확성 채점)

평가셋(JSONL) 한 줄 형식 예:
  {"question": "...", "answer": "...", "doc_id": "정답문서ID"}
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.rag import RAGPipeline


@dataclass
class EvalItem:
    question: str
    answer: str | None = None      # 정답(있으면 생성 평가에 사용)
    doc_id: str | None = None      # 정답 문서 ID(있으면 검색 평가에 사용)


def load_eval_set(path: str) -> list[EvalItem]:
    items: list[EvalItem] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        items.append(
            EvalItem(
                question=d["question"],
                answer=d.get("answer"),
                doc_id=d.get("doc_id"),
            )
        )
    return items


def evaluate_retrieval(
    pipeline: RAGPipeline, items: list[EvalItem], top_k: int = 5
) -> dict:
    """정답 doc_id 가 있는 항목에 대해 Hit@k, MRR 계산."""
    hits, rr, n = 0, 0.0, 0
    for it in items:
        if not it.doc_id:
            continue
        n += 1
        results = pipeline.retrieve(it.question, top_k=top_k)
        retrieved_ids = [c.metadata.get("doc_id") for c in results]
        if it.doc_id in retrieved_ids:
            hits += 1
            rank = retrieved_ids.index(it.doc_id) + 1
            rr += 1.0 / rank
    if n == 0:
        return {"note": "doc_id 라벨이 있는 평가 항목이 없습니다."}
    return {"n": n, f"hit@{top_k}": hits / n, "mrr": rr / n}


_JUDGE_SYSTEM = """당신은 RFP QA 시스템의 답변을 채점하는 엄격한 평가자입니다.
질문, 모델 답변, (있다면) 참조 정답을 보고 0~5점으로 채점하세요.
JSON 한 줄로만 출력: {"score": <0-5>, "reason": "<간단한 근거>"}"""


def evaluate_generation_llm_judge(
    pipeline: RAGPipeline, items: list[EvalItem], judge_llm
) -> dict:
    """LLM-as-judge 로 생성 답변 품질을 채점한다. judge_llm 은 BaseLLM."""
    scores = []
    for it in items:
        pred = pipeline.ask(it.question).answer
        user = (
            f"[질문]\n{it.question}\n\n[모델 답변]\n{pred}\n\n"
            f"[참조 정답]\n{it.answer or '(없음)'}"
        )
        raw = judge_llm.generate(_JUDGE_SYSTEM, user)
        try:
            scores.append(float(json.loads(raw)["score"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            print(f"[judge] 파싱 실패: {raw[:120]}")
    if not scores:
        return {"note": "채점된 항목이 없습니다."}
    return {"n": len(scores), "avg_score": sum(scores) / len(scores)}
