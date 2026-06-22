"""중앙 설정 로더.

.env 파일과 환경변수에서 설정을 읽어온다. OpenAI(1단계)와
HuggingFace(2단계, GCP VM) 백엔드를 같은 코드로 전환할 수 있도록
provider 값만 바꾸면 되게 설계했다.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # provider 선택
    llm_provider: str = "openai"          # "openai" | "huggingface"
    embedding_provider: str = "openai"    # "openai" | "huggingface"

    # OpenAI
    openai_api_key: str = ""
    openai_llm_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # None 이면 temperature 미전송(모델 기본값). gpt-5 계열은 1만 허용하므로 기본 None.
    openai_temperature: float | None = None

    # HuggingFace (2단계)
    hf_llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
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

    # Paths
    data_raw_dir: str = "./data/raw"
    data_metadata_dir: str = "./data/metadata"


@lru_cache
def get_settings() -> Settings:
    """싱글톤 설정 인스턴스를 반환한다."""
    return Settings()
