"""FastAPI 진입점.

실행:  uvicorn src.api.main:app --reload
문서:  http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from src.config import get_settings
from src.rag import RAGAnswer, build_pipeline

from .schemas import (
    AskRequest,
    AskResponse,
    SourceItem,
    SummaryRequest,
    SummaryResponse,
)

app = FastAPI(
    title="입찰메이트 RFP RAG API",
    description="복잡한 RFP(제안요청서)에서 핵심 정보를 추출·요약하는 RAG 서비스",
    version="0.1.0",
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
            source=c.metadata.get("source", "unknown"),
            doc_id=c.metadata.get("doc_id"),
            score=round(c.score, 4),
            preview=c.text[:200],
        )
        for c in ans.sources
    ]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
