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


@app.post("/recommend", response_model=DocumentList)
def recommend(req: RecommendRequest) -> DocumentList:
    """고객사 역량/요구(profile)로 적합 RFP 추천.

    흐름: 질의 재작성(recall) → 하이브리드로 후보 다수 → 문서 단위 집계
         → 메타필터 → (옵션) LLM 재랭킹(포함/제외 조건까지 반영) → 상위 top_k.
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
