"""생성 평가: RAG가 생성한 답변이 골든 정답을 담고 있는지 측정한다.

지표: 정답 포함 정확도(accuracy) — 생성 답변에 골든 answer가 들어있으면 정답 처리.
유형별 매칭:
  - budget(예산): 숫자만 비교 (130,000,000원 ↔ 1억3천만 식 표기차 흡수 위해 숫자열 포함 검사)
  - deadline(마감일): 연/월/일 숫자가 모두 답변에 등장하는지
  - agency(기관): 기관명이 답변에 포함되는지

⚠️ 느슨한 자동 채점(표기 차이로 과소평가 가능). 엄밀히는 LLM-judge 권장.
ask()를 문항마다 호출(LLM 사용) → 비용 있음. 기본은 표본 평가.

실행: python -m scripts.eval_generation [표본수]   (예: python -m scripts.eval_generation 40)
      python -m scripts.eval_generation all          (전체)
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from src.config import get_settings
from src.rag import build_pipeline


def _digits(s: str) -> str:
    return re.sub(r"\D", "", str(s))


def _norm(s: str) -> str:
    return re.sub(r"[\s,]", "", str(s)).lower()


def is_correct(item: dict, pred: str) -> bool:
    t = item.get("type")
    gold = str(item["answer"])
    if t == "budget":
        d = _digits(gold)
        return bool(d) and d in _digits(pred)
    if t == "deadline":
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", gold)
        if not m:
            return _norm(gold) in _norm(pred)
        y, mo, da = m.groups()
        # 답변에 연/월/일이 모두 등장하면 정답 (표기 차이 허용)
        return all(n in pred for n in (y, str(int(mo)), str(int(da))))
    # agency / 기타
    return _norm(gold) in _norm(pred)


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "40"
    path = "data/eval/eval_set.jsonl"
    if not Path(path).exists():
        path = "data/eval/eval_set.draft.jsonl"
    items = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]

    if arg != "all":
        random.seed(42)
        items = random.sample(items, min(int(arg), len(items)))

    pipe = build_pipeline(get_settings())

    total = defaultdict(int)
    correct = defaultdict(int)
    for it in items:
        pred = pipe.ask(it["question"]).answer
        ok = is_correct(it, pred)
        t = it.get("type", "etc")
        total[t] += 1
        total["전체"] += 1
        if ok:
            correct[t] += 1
            correct["전체"] += 1

    lines = ["# 생성 평가 결과 (정답 포함 정확도)", "",
             f"- 평가셋: `{path}` (표본 {total['전체']}건)", "",
             "| 유형 | 정확도 | 정답/전체 |", "|------|------:|------:|"]
    for t in ["전체", "budget", "deadline", "agency"]:
        if total.get(t):
            lines.append(f"| {t} | {correct[t]/total[t]:.3f} | {correct[t]}/{total[t]} |")
    report = "\n".join(lines)
    print(report)
    out = Path("results/eval_generation.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\n[eval] 저장 -> {out}")


if __name__ == "__main__":
    main()
