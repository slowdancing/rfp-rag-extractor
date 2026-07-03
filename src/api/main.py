"""FastAPI 진입점.

실행:  uvicorn src.api.main:app --reload
문서:  http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.catalog import filter_docs, load_catalog
from src.config import get_settings
from src.rag import RAGAnswer, build_pipeline

from .schemas import (
    AskRequest,
    AskResponse,
    DocumentItem,
    DocumentList,
    RecommendRequest,
    SourceItem,
    SummaryRequest,
    SummaryResponse,
)

app = FastAPI(
    title="입찰메이트 RFP RAG API",
    description="복잡한 RFP(제안요청서)에서 핵심 정보를 추출·요약하는 RAG 서비스",
    version="0.1.0",
)

# React 개발 서버 등 외부 출처에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 시 프론트 도메인으로 제한 권장
    allow_methods=["*"],
    allow_headers=["*"],
)

# 파이프라인은 비용이 큰 객체이므로 시작 시 1회만 생성.
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline(get_settings())
    return _pipeline


def _to_source_items(ans: RAGAnswer) -> list[SourceItem]:
    return [
        SourceItem(
            source=str(c.metadata.get("사업명") or c.metadata.get("doc_id") or "unknown"),
            doc_id=c.metadata.get("doc_id"),
            score=round(c.score, 4),
            preview=c.text[:200],
        )
        for c in ans.sources
    ]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/documents", response_model=DocumentList)
def documents(
    q: str | None = Query(None, description="제목·요약 키워드"),
    budget_min: int | None = None,
    budget_max: int | None = None,
    org: str | None = None,
    deadline_before: str | None = None,
    limit: int = 50,
) -> DocumentList:
    """메타데이터 필터 기반 RFP 목록 (LLM 미사용, 빠름)."""
    docs = filter_docs(
        load_catalog(), q=q, budget_min=budget_min, budget_max=budget_max,
        org=org, deadline_before=deadline_before,
    )
    return DocumentList(total=len(docs), items=[DocumentItem(**d) for d in docs[:limit]])


def _local_has_match(llm, query: str, cand: list[dict]) -> bool:
    """로컬 후보 중 사용자 요구에 '실제로' 부합하는 게 있는지 LLM으로 판정.

    RRF 점수는 절대 관련도가 아니라 판정에 못 쓰므로(1위도 ~0.03), 의미 기반으로 LLM에 물음.
    판정 실패 시 True(로컬 유지) — 나라장터 폴백 남발을 막기 위한 보수적 기본값.
    """
    if not cand:
        return False
    titles = "\n".join(f"- {c.get('title') or c.get('doc_id')}" for c in cand[:10])
    sys = ("사용자 요구에 실제로 부합하는 공고가 후보에 하나라도 있으면 YES, "
           "전혀 없으면 NO. 오직 YES 또는 NO만 출력.")
    user = f"[사용자 요구]\n{query}\n\n[후보 공고]\n{titles}\n\nYES 또는 NO:"
    try:
        ans = llm.generate(sys, user).strip().upper()
        return not ans.startswith("N")
    except Exception:  # noqa: BLE001
        return True


@app.post("/recommend", response_model=DocumentList)
def recommend(req: RecommendRequest) -> DocumentList:
    """고객사 역량/요구(profile)로 적합 RFP 추천.

    흐름: 질의 재작성(recall) → 하이브리드로 후보 다수 → 문서 단위 집계 → 메타필터
         → (적합 공고 없으면 나라장터 실시간 폴백) → (옵션) LLM 재랭킹 → 상위 top_k.
    """
    from src.catalog import get_doc
    from src.rag.rerank import rerank

    pipe = get_pipeline()
    try:
        # 1) 재작성된 질의로 후보 recall 높이기 + 넉넉히 검색
        search_q = pipe.rewrite_query(req.profile)
        chunks = pipe.retrieve(search_q, top_k=40)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 2) 청크 → 문서 단위(최고 점수 청크의 본문을 스니펫으로)
    docs: dict[str, dict] = {}
    for c in chunks:
        d = c.metadata.get("doc_id")
        if not d or d in docs:
            continue
        meta = get_doc(d)
        if meta:
            docs[d] = {**meta, "snippet": c.text[:300], "score": round(float(c.score), 4)}
    cand = list(docs.values())

    # 3) 메타데이터 필터
    cand = filter_docs(
        cand, budget_min=req.budget_min, budget_max=req.budget_max,
        org=req.org, deadline_before=req.deadline_before,
    )

    # 3-1) 로컬에 적합 공고가 없으면 → 나라장터 실시간 검색으로 폴백 (옵트인)
    settings = get_settings()
    if settings.nara_fallback and settings.nara_api_key and \
            not _local_has_match(pipe._llm, req.profile, cand):
        from src.nara import search_bids
        ext = search_bids(search_q or req.profile, settings.nara_api_key,
                          days=settings.nara_search_days, rows=req.top_k)
        if ext:
            return DocumentList(total=len(ext), items=[DocumentItem(**e) for e in ext])

    # 4) LLM 재랭킹(요구·조건 반영) 또는 점수순
    if req.rerank and cand:
        try:
            cand = rerank(pipe._llm, req.profile, cand, req.top_k)
        except Exception:  # noqa: BLE001
            cand = sorted(cand, key=lambda d: d["score"], reverse=True)[: req.top_k]
    else:
        cand = sorted(cand, key=lambda d: d["score"], reverse=True)[: req.top_k]

    return DocumentList(total=len(cand), items=[DocumentItem(**d) for d in cand])


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    where = {"doc_id": req.doc_id} if req.doc_id else None
    try:
        ans = get_pipeline().ask(req.question, top_k=req.top_k, where=where)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AskResponse(answer=ans.answer, sources=_to_source_items(ans))


@app.post("/summarize", response_model=SummaryResponse)
def summarize(req: SummaryRequest) -> SummaryResponse:
    try:
        ans = get_pipeline().summarize(req.doc_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SummaryResponse(
        doc_id=req.doc_id, summary=ans.answer, sources=_to_source_items(ans)
    )
