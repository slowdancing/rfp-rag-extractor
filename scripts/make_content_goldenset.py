"""내용형 골든셋 생성기 (LLM 기반).

메타데이터로는 못 만드는 '내용형' Q&A(요구사항·자격·평가방식·제출방법 등)를
문서 본문에서 LLM으로 생성한다. 정답은 본문 근거 기반.

⚠️ LLM 생성 초안 → 반드시 사람 검수 후 골든셋으로 확정.
   (모델이 만든 답을 그대로 정답으로 쓰면 자기채점이 되므로 검수 필수)

실행:
  python -m scripts.make_content_goldenset            # 기본 8개 문서, 문서당 2문항
  python -m scripts.make_content_goldenset 20 3       # 20개 문서, 문서당 3문항
출력: data/eval/eval_set.content.draft.jsonl
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

from src.config import get_settings
from src.llm import build_llm

CORPUS = "data/processed/corpus_clean.csv"
OUT = "data/eval/eval_set.content.draft.jsonl"

SYS_PROMPT = """당신은 RFP(제안요청서) 기반 QA 평가셋 제작자입니다.
주어진 RFP 본문만 근거로, 입찰 컨설턴트가 실제로 물을 '내용형' 질문과 정답을 만드세요.

규칙:
- 요구사항/사업범위/입찰참가자격/평가방식·배점/제출방법·서류/과업기간 등 '내용'을 묻기.
- 정답은 반드시 본문에 명시된 사실. 본문에 근거가 없으면 그 질문은 만들지 말 것(추측 금지).
- 질문에는 어떤 사업인지 알 수 있도록 사업명(또는 핵심 키워드)을 포함.
- 정답은 1~3문장으로 핵심만.
- 출력은 JSON 배열만. 다른 설명 금지:
  [{"question": "...", "answer": "...", "category": "요구사항|자격|평가방식|제출방법|기간|범위"}]"""


def _build_user(title: str, text: str, k: int) -> str:
    return (f"[사업명]\n{title}\n\n[RFP 본문(일부)]\n{text[:6000]}\n\n"
            f"위 본문 근거로 내용형 Q&A {k}개를 JSON 배열로 생성하세요.")


def _parse_json(raw: str) -> list[dict]:
    # 코드펜스/잡텍스트 제거 후 JSON 배열만 추출
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return []


def main() -> None:
    n_docs = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    df = pd.read_csv(CORPUS)
    # 내용이 충분한 문서만 (너무 짧으면 내용 질문 불가)
    df = df[df["text"].str.len() >= 1500]
    random.seed(42)
    rows = df.sample(min(n_docs, len(df)))

    llm = build_llm(get_settings())
    items, failed = [], 0
    for _, r in rows.iterrows():
        doc_id, title, text = str(r["doc_id"]), str(r["사업명"]), str(r["text"])
        raw = llm.generate(SYS_PROMPT, _build_user(title, text, k))
        qas = _parse_json(raw)
        if not qas:
            failed += 1
            continue
        for qa in qas:
            if not qa.get("question") or not qa.get("answer"):
                continue
            items.append({
                "question": qa["question"],
                "answer": qa["answer"],
                "doc_id": doc_id,
                "type": "content",
                "category": qa.get("category", ""),
                "source": "llm",
                "needs_review": True,
            })
        print(f"  {doc_id[:35]}: {len(qas)}문항")

    out = Path(OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"\n[content-goldenset] 문서 {len(rows)}개 → 내용형 초안 {len(items)}건 "
          f"(파싱 실패 {failed}) -> {OUT}")
    print("⚠️ 사람 검수 후 eval_set.jsonl 로 합치세요.")


if __name__ == "__main__":
    main()
