"""RFP 카탈로그 — 문서 목록/필터/추천용 메타데이터 제공.

corpus_clean.csv(문서당 1행, 메타데이터 포함)를 읽어 목록·필터에 쓴다.
검색 엔진(임베딩)과 별개로, 빠른 메타데이터 조회/필터링을 담당.
"""
from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

CORPUS = "data/processed/corpus_clean.csv"


def _clean(v):
    return None if (v is None or (isinstance(v, float) and pd.isna(v))) else v


@lru_cache
def load_catalog() -> list[dict]:
    """문서별 메타데이터 리스트 반환 (요약용 항목 포함)."""
    df = pd.read_csv(CORPUS)
    docs = []
    for _, r in df.iterrows():
        budget = r.get("사업 금액")
        docs.append({
            "doc_id": str(r["doc_id"]),
            "title": _clean(r.get("사업명")),
            "org": _clean(r.get("발주 기관")),
            "budget": None if pd.isna(budget) else int(float(budget)),
            "posted": _clean(r.get("공개 일자")),
            "deadline": _clean(r.get("입찰 참여 마감일")),
            "filetype": _clean(r.get("파일형식")),
            "summary": _clean(r.get("사업 요약")),
        })
    return docs


def filter_docs(
    docs: list[dict],
    q: str | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    org: str | None = None,
    deadline_before: str | None = None,
) -> list[dict]:
    """메타데이터 조건으로 문서를 필터링한다."""
    out = []
    for d in docs:
        if q:
            hay = f"{d.get('title') or ''} {d.get('summary') or ''}".lower()
            if q.lower() not in hay:
                continue
        if budget_min is not None and (d["budget"] is None or d["budget"] < budget_min):
            continue
        if budget_max is not None and (d["budget"] is None or d["budget"] > budget_max):
            continue
        if org and org.lower() not in (d.get("org") or "").lower():
            continue
        if deadline_before and d.get("deadline"):
            # 문자열 날짜 비교 (YYYY-MM-DD ... 형식이라 사전식 비교 가능)
            if str(d["deadline"]) > deadline_before + "￿":
                continue
        out.append(d)
    return out


@lru_cache
def _catalog_index() -> dict:
    return {d["doc_id"]: d for d in load_catalog()}


def get_doc(doc_id: str) -> dict | None:
    return _catalog_index().get(doc_id)
