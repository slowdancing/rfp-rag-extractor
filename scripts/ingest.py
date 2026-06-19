"""인덱싱 스크립트: chunks.csv 를 임베딩하여 벡터스토어에 적재한다.

사전 준비:
  python -m src.dataset_utill.preprocess     # corpus_clean.csv 생성
  python -m src.dataset_utill.chunk_corpus   # chunks.csv 생성
  .env 에 OPENAI_API_KEY 설정

실행:
  python -m scripts.ingest
"""
from __future__ import annotations

from pathlib import Path

from src.config import get_settings
from src.rag import build_pipeline

CHUNKS_PATH = "data/processed/chunks.csv"


def main() -> None:
    if not Path(CHUNKS_PATH).exists():
        raise SystemExit(
            f"{CHUNKS_PATH} 가 없습니다. 먼저 청킹을 실행하세요: "
            "python -m src.dataset_utill.chunk_corpus"
        )

    settings = get_settings()
    pipeline = build_pipeline(settings)
    print(f"[ingest] provider={settings.embedding_provider}, "
          f"model={settings.openai_embedding_model}, store={settings.vector_store}")

    total = pipeline.index_chunks(CHUNKS_PATH)
    print(f"[ingest] 완료: 총 {total} 청크 적재 -> {settings.chroma_persist_dir}")


if __name__ == "__main__":
    main()
