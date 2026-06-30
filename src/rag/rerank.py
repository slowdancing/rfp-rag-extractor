"""LLM 재랭킹 — 검색 후보를 사용자 요구에 맞게 재정렬·선별한다.

임베딩/BM25 검색은 '의미가 비슷한 것'은 잘 찾지만, 자연어 질의의
**포함/제외 조건·논리**(예: "구매비용 O, 마케팅 비용 X")는 못 거른다.
후보를 LLM에게 보여주고 요구에 맞는 것만 골라 재정렬해 정밀도를 높인다.
"""
from __future__ import annotations

import json
import re

RERANK_SYSTEM = """당신은 RFP 검색 결과를 사용자 요구에 맞게 재정렬하는 평가자입니다.
사용자 질문의 의도와 조건을 정확히 파악해, 후보 중 요구를 만족하는 것만 골라
적합도 높은 순으로 번호를 나열하세요.

규칙:
- 질문의 '제외 조건'(예: "마케팅 비용 말고", "~제외")에 해당하는 후보는 빼세요.
- 질문 주제와 무관한 후보도 빼세요.
- 애매하면 포함하되 뒤 순위로.
- 출력은 JSON 배열(번호만), 적합도 높은 순. 예: [3, 0, 5]
- 다른 설명 없이 JSON 배열만 출력."""


def _build_prompt(query: str, candidates: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(candidates):
        title = c.get("title") or c.get("doc_id", "")
        snippet = (c.get("snippet") or c.get("summary") or "")[:300]
        blocks.append(f"[{i}] {title}\n{snippet}")
    return (
        f"[사용자 요구]\n{query}\n\n"
        f"[후보 목록]\n" + "\n\n".join(blocks) +
        "\n\n적합한 후보 번호를 적합도순 JSON 배열로 출력:"
    )


def rerank(llm, query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """LLM으로 후보를 재정렬해 상위 top_k 를 반환. 실패 시 원래 순서 폴백."""
    if not candidates:
        return []
    try:
        raw = llm.generate(RERANK_SYSTEM, _build_prompt(query, candidates))
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        order = json.loads(m.group()) if m else []
        picked = [candidates[i] for i in order
                  if isinstance(i, int) and 0 <= i < len(candidates)]
        return (picked or candidates)[:top_k]
    except Exception:  # noqa: BLE001 - 재랭킹 실패 시 검색 순서 유지
        return candidates[:top_k]
