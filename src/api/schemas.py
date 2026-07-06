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


class SummaryRow(BaseModel):
    label: str
    value: str


class SummaryResponse(BaseModel):
    doc_id: str
    summary: str                 # 원본 텍스트(폴백/디버그용)
    rows: list[SummaryRow] = []  # 고정 스키마 표(항목·내용)
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
    link: str | None = None      # 외부(나라장터) 공고 상세 URL
    source: str | None = None    # "나라장터" 등 출처(로컬 DB면 None)


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


# ===== 적격성 판정 =====
class EligibilityRequest(BaseModel):
    doc_id: str = Field(..., description="판정할 문서 ID")
    company: str | None = Field(None, description="회사 소개 자연어(예: 서울 소재 중소기업, SI 전문…). 있으면 이걸 우선 사용")
    # (선택) 구조화 입력 — company 가 없을 때만 사용
    company_size: str | None = Field(None, description="기업규모(중소기업/중견기업/대기업)")
    industry: str | None = Field(None, description="업종/주력분야")
    region: str | None = Field(None, description="본사 소재지(지역)")
    track_record: str | None = Field(None, description="보유 실적/역량")
    certifications: str | None = Field(None, description="보유 인증/자격/면허")


class EligibilityItem(BaseModel):
    requirement: str            # RFP 자격요건
    status: str                 # "O"(충족) | "X"(미충족) | "?"(확인필요)
    reason: str                 # 판정 근거


class EligibilityResponse(BaseModel):
    doc_id: str
    verdict: str                # "적격" | "부적격" | "확인필요"
    summary: str                # 한 줄 종합
    items: list[EligibilityItem]
    sources: list[SourceItem]
    raw: str = ""               # (진단용) LLM 원본 출력
