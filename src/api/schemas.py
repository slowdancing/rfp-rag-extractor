"""API 요청/응답 스키마."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., description="RFP 에 대한 질문")
    top_k: int | None = Field(None, description="검색할 청크 수 (미지정시 기본값)")
    doc_id: str | None = Field(None, description="특정 문서로 한정해 검색 (선택)")


class SourceItem(BaseModel):
    source: str
    doc_id: str | None = None
    score: float
    preview: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class SummaryRequest(BaseModel):
    doc_id: str = Field(..., description="요약할 문서 ID(파일명, 확장자 제외)")


class SummaryResponse(BaseModel):
    doc_id: str
    summary: str
    sources: list[SourceItem]
