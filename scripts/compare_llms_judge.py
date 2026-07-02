"""내용형(서술형) 답변 품질 비교 — LLM-judge 교차검증.

metadata 골든셋의 '정답 포함(문자열 매칭)'으로는 서술형 답변을 평가할 수 없어,
내용형 골든셋(eval_set.content.jsonl)에 대해 각 후보 LLM이 생성한 답변을
**여러 심판 LLM이 정답(gold) 대조로 0~5점 채점**한다.

- 검색(임베딩 bge-m3·하이브리드)은 .env대로 고정 → 후보 LLM만 변수.
- 심판이 여럿이면 교차검증(순위 일치 확인). 대결 당사자가 심판이어도
  정답 대조(reference-based)라 자기편향이 제한되며, 두 심판 결과를 함께 본다.

모델 표기:
  - 로컬 Ollama: `exaone3.5:7.8b`
  - OpenAI 클라우드: `openai:gpt-5-mini` (키는 OPENAI_CLOUD_KEY 환경변수)

실행(기본: 후보·심판 모두 EXAONE + gpt-5-mini):
  OPENAI_CLOUD_KEY=sk-... python -m scripts.compare_llms_judge
지정:
  python -m scripts.compare_llms_judge --candidates exaone3.5:7.8b openai:gpt-5-mini \
      --judges exaone3.5:7.8b openai:gpt-5-mini --n 59

산출물:
  results/compare_llms_judge.json  (예측·점수 원장, 재실행 시 예측 캐시 재사용)
  results/compare_llms_judge.md    (후보 × 심판 평균점수 표)
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from src.config import get_settings
from src.embeddings import build_embedder
from src.llm.openai_llm import OpenAILLM
from src.rag.hybrid import HybridRetriever
from src.rag.pipeline import RAGPipeline
from src.vectorstore import build_vector_store

GOLD = "data/eval/eval_set.content.jsonl"
LEDGER = Path("results/compare_llms_judge.json")
REPORT = Path("results/compare_llms_judge.md")

JUDGE_SYS = """당신은 RFP(제안요청서) QA 답변을 채점하는 평가자입니다.
[질문], [모범답안], [후보답변]이 주어집니다. 후보답변이 모범답안과 사실적으로 얼마나
일치하고 질문에 정확히 답하는지 0~5점으로 채점하세요.

채점 기준:
- 5: 모범답안의 핵심 사실을 정확하고 빠짐없이 포함.
- 3~4: 핵심은 맞으나 일부 누락/불명확.
- 1~2: 부분적으로만 맞거나 중요한 오류 포함.
- 0: 완전히 틀리거나 질문과 무관, 또는 "정보 없음"인데 모범답안엔 정보가 있음.
- 후보답변의 문장 스타일·길이는 채점 대상이 아니며, 오직 사실 일치·정확성만 본다.

출력은 JSON 하나만: {"score": 0~5 정수, "reason": "한 문장"}. 다른 텍스트 금지."""


def _judge_user(q: str, gold: str, pred: str) -> str:
    return (f"[질문]\n{q}\n\n[모범답안]\n{gold}\n\n[후보답변]\n{pred}\n\n"
            "위 기준으로 채점해 JSON으로만 출력:")


def make_llm(spec: str, s) -> tuple[OpenAILLM, str]:
    """모델 표기(spec)로 LLM 생성. `openai:` 접두사는 실제 OpenAI 클라우드."""
    if spec.startswith("openai:"):
        model = spec.split(":", 1)[1]
        key = os.environ.get("OPENAI_CLOUD_KEY") or s.openai_api_key
        return OpenAILLM(api_key=key, model=model, base_url=None,
                         temperature=s.openai_temperature), "OpenAI(cloud)"
    return OpenAILLM(api_key=s.openai_api_key or "x", model=spec,
                     base_url=s.openai_base_url, temperature=s.openai_temperature), \
        (s.openai_base_url or "OpenAI")


def _parse_score(raw: str):
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        # 숫자만 뽑아보기(폴백)
        m2 = re.search(r"[0-5]", raw)
        return int(m2.group()) if m2 else None
    try:
        obj = json.loads(m.group())
        sc = obj.get("score")
        return int(round(float(sc))) if sc is not None else None
    except Exception:  # noqa: BLE001
        return None


def _load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"preds": {}, "scores": {}}


def _save_ledger(led: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_report(led: dict, candidates: list[str], judges: list[str], n: int) -> None:
    lines = ["# 내용형 답변 품질 비교 (LLM-judge 교차검증)", "",
             f"- 골든셋: `{GOLD}` (표본 {n}건, 서술형)",
             "- 검색: bge-m3 하이브리드 고정. 후보 LLM만 변수. 점수는 정답 대조 0~5점.",
             f"- 심판(judge): {', '.join(judges)}  ·  후보: {', '.join(candidates)}",
             "", "| 후보 LLM | " + " | ".join(f"{j} 채점" for j in judges) + " | 평균 |",
             "|------|" + "------:|" * (len(judges) + 1)]
    for c in candidates:
        cells = []
        vals = []
        for j in judges:
            arr = [x for x in led["scores"].get(c, {}).get(j, []) if isinstance(x, (int, float))]
            if arr:
                avg = sum(arr) / len(arr)
                vals.append(avg)
                cells.append(f"{avg:.2f} (n={len(arr)})")
            else:
                cells.append("-")
        overall = f"**{sum(vals)/len(vals):.2f}**" if vals else "-"
        lines.append(f"| {c} | " + " | ".join(cells) + f" | {overall} |")
    lines += ["", "> 점수 0~5(높을수록 정답에 부합). 두 심판 결과가 함께 높/낮으면 신뢰도↑.",
              "> 심판이 대결 당사자이므로 자기편향 가능성은 있으나 정답 대조 방식으로 완화."]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", nargs="+",
                    default=["exaone3.5:7.8b", "openai:gpt-5-mini"])
    ap.add_argument("--judges", nargs="+",
                    default=["exaone3.5:7.8b", "openai:gpt-5-mini"])
    ap.add_argument("--n", type=int, default=0, help="표본 수(0=전체)")
    args = ap.parse_args()

    s = get_settings()
    items = [json.loads(l) for l in Path(GOLD).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.n:
        items = items[: args.n]
    n = len(items)

    embedder = build_embedder(s)
    store = build_vector_store(s)
    hybrid = HybridRetriever(embedder, store, s.chunks_path)

    led = _load_ledger()

    # 1) 후보별 예측 생성 (캐시 있으면 건너뜀)
    for cand in args.candidates:
        cached = led["preds"].get(cand)
        if cached and len(cached) >= n:
            print(f"[preds] {cand}: 캐시 재사용({len(cached)})")
            continue
        print(f"\n[preds] {cand} 답변 생성 중...")
        llm, _ = make_llm(cand, s)
        pipe = RAGPipeline(embedder, store, llm, top_k=s.top_k, hybrid_retriever=hybrid)
        preds = []
        for i, it in enumerate(items):
            preds.append(pipe.ask(it["question"]).answer)
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{n}")
        led["preds"][cand] = preds
        _save_ledger(led)

    # 2) 심판별 채점 (후보 × 심판)
    for judge in args.judges:
        jllm, _ = make_llm(judge, s)
        for cand in args.candidates:
            done = led["scores"].setdefault(cand, {}).get(judge, [])
            if len(done) >= n:
                print(f"[judge] {judge} → {cand}: 캐시 재사용")
                continue
            print(f"\n[judge] {judge} 가 {cand} 채점 중...")
            preds = led["preds"][cand]
            scores = []
            for i, it in enumerate(items):
                raw = jllm.generate(JUDGE_SYS, _judge_user(it["question"], it["answer"], preds[i]))
                scores.append(_parse_score(raw))
                if (i + 1) % 10 == 0:
                    print(f"  {i+1}/{n}")
            led["scores"][cand][judge] = scores
            _save_ledger(led)
            _write_report(led, args.candidates, args.judges, n)

    _write_report(led, args.candidates, args.judges, n)
    print(f"\n[done] 원장 -> {LEDGER}  /  표 -> {REPORT}")
    # 요약 출력
    for cand in args.candidates:
        parts = []
        for judge in args.judges:
            arr = [x for x in led["scores"].get(cand, {}).get(judge, []) if isinstance(x, (int, float))]
            if arr:
                parts.append(f"{judge}={sum(arr)/len(arr):.2f}")
        print(f"  {cand}: " + ", ".join(parts))


if __name__ == "__main__":
    main()
