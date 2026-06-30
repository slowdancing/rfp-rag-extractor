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


class DocumentItem(BaseModel):
    doc_id: str
    title: str | None = None
    org: str | None = None
    budget: int | None = None
    posted: str | None = None
    deadline: str | None = None
    filetype: str | None = None
    summary: str | None = None
    score: float | None = None   # 추천 시 관련도 점수


class DocumentList(BaseModel):
    total: int
    items: list[DocumentItem]


class RecommendRequest(BaseModel):
    profile: str = Field(..., description="고객사 역량/관심 설명 (이걸로 적합 RFP 추천)")
    top_k: int = Field(10, description="추천 문서 수")
    budget_min: int | None = None
    budget_max: int | None = None
    org: str | None = None
    deadline_before: str | None = Field(None, description="이 날짜 이전 마감 (YYYY-MM-DD)")
    rerank: bool = Field(True, description="LLM 재랭킹으로 정밀도↑ (조건·제외 처리). 끄면 임베딩 순서)")
