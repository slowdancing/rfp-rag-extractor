"""골든 데이터셋 초안 생성기.

평가용 (질문·정답·정답문서) 골든셋의 초안을 자동 생성한다.
정답이 신뢰 가능한 **메타데이터 기반 질문**(예산·마감일·발주기관)을 만들어,
사람이 검수만 하면 바로 평가에 쓸 수 있게 한다.

⚠️ 이건 '초안'이다. 반드시 사람이 검수/수정 후 골든셋으로 확정할 것.

실행: python -m scripts.make_goldenset
출력: data/eval/eval_set.draft.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CORPUS = "data/processed/corpus_clean.csv"
OUT = "data/eval/eval_set.draft.jsonl"


def _fmt_won(v) -> str | None:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return f"{n:,}원"


def _short(name: str, n: int = 40) -> str:
    name = str(name)
    return name if len(name) <= n else name[:n]


def main() -> None:
    df = pd.read_csv(CORPUS)
    items = []

    for _, r in df.iterrows():
        doc_id = str(r["doc_id"])
        title = _short(r.get("사업명"))

        # 1) 예산 (사업 금액)
        won = _fmt_won(r.get("사업 금액"))
        if won:
            items.append({
                "question": f"'{title}' 사업의 예산(사업 금액)은 얼마인가?",
                "answer": won,
                "doc_id": doc_id,
                "type": "budget",
                "source": "metadata",
                "needs_review": True,
            })

        # 2) 입찰 마감일
        deadline = r.get("입찰 참여 마감일")
        if pd.notna(deadline):
            items.append({
                "question": f"'{title}' 사업의 입찰 참여 마감일은 언제인가?",
                "answer": str(deadline),
                "doc_id": doc_id,
                "type": "deadline",
                "source": "metadata",
                "needs_review": True,
            })

        # 3) 발주 기관
        org = r.get("발주 기관")
        if pd.notna(org):
            items.append({
                "question": f"'{title}' 사업의 발주 기관은 어디인가?",
                "answer": str(org),
                "doc_id": doc_id,
                "type": "agency",
                "source": "metadata",
                "needs_review": True,
            })

    out = Path(OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    by_type = pd.Series([it["type"] for it in items]).value_counts()
    print(f"[goldenset] 초안 {len(items)}건 생성 -> {OUT}")
    print("유형별:")
    for t, n in by_type.items():
        print(f"  {t}: {n}")
    print("\n⚠️ 사람 검수 후 data/eval/eval_set.jsonl 로 확정하세요.")


if __name__ == "__main__":
    main()
