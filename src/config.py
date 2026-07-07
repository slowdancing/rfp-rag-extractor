"""중앙 설정 로더.

.env 파일과 환경변수에서 설정을 읽어온다. OpenAI(1단계)와
HuggingFace(2단계, GCP VM) 백엔드를 같은 코드로 전환할 수 있도록
provider 값만 바꾸면 되게 설계했다.
"""
from __future__ import annotations  # 타입 힌트를 문자열로 처리

from functools import lru_cache  # 한번 만든 Settings를 저장하고 다음에 재사용

from pydantic_settings import BaseSettings, SettingsConfigDict

# 세팅 클래스 생성 - BaseSettings를 상속받음 .env에서 값을 자동으로 읽는 설정 전용 부모클래스
class Settings(BaseSettings):
    # model_config라는 클래스 속성, 딕셔너리 세팅 -> 기본세팅인 env파일을 읽어올 수 있도록 정보를 저장
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # provider 선택
    llm_provider: str = "openai"          # "openai" | "huggingface"
    embedding_provider: str = "openai"    # "openai" | "huggingface"

    # OpenAI
    openai_api_key: str = ""
    # OpenAI 호환 엔드포인트(예: Ollama "http://localhost:11434/v1"). 비우면 공식 OpenAI.
    openai_base_url: str = ""
    openai_llm_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # None 이면 temperature 미전송(모델 기본값). gpt-5 계열은 1만 허용하므로 기본 None.
    openai_temperature: float | None = None

    # HuggingFace (2단계) — 확정 모델(실험 근거: results/model_decision.md)
    hf_llm_model: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
    hf_embedding_model: str = "BAAI/bge-m3"
    hf_device: str = "cuda"

    # Vector store
    vector_store: str = "chroma"
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection: str = "rfp_documents"

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Retrieval
    top_k: int = 5
    retrieval_mode: str = "hybrid"   # "dense" | "hybrid"
    chunks_path: str = "data/processed/chunks.csv"

    # 나라장터(조달청) 실시간 폴백 — 로컬 DB에 적합 공고가 없을 때 외부 API 조회
    nara_fallback: bool = False          # True 이고 키가 있어야 동작(옵트인)
    nara_api_key: str = ""               # data.go.kr 서비스키(디코딩 키 권장)
    nara_search_days: int = 30           # 최근 N일 공고 검색

    # 적격성 판정 전용 LLM(옵트인) — EXAONE 7.8B는 근거기반 자격판정에서 환각이 잦아,
    # 키가 있으면 이 과제만 gpt-5-mini(공식 OpenAI)로 라우팅. 비우면 기본 LLM(EXAONE) 사용.
    eligibility_openai_key: str = ""     # 공식 OpenAI 키(비면 폴백)
    eligibility_openai_model: str = "gpt-5-mini"

    # Paths
    data_raw_dir: str = "./data/raw"
    data_metadata_dir: str = "./data/metadata"

# 위 함수를 호출하면 Settings 객체의 세팅값을 반환
@lru_cache
def get_settings() -> Settings:
    """싱글톤 설정 인스턴스를 반환한다."""
    return Settings()
