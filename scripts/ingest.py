"""인덱싱 스크립트: data/raw 의 RFP 문서를 벡터스토어에 적재한다.

실행:  python -m scripts.ingest
"""
from __future__ import annotations

from src.config import get_settings
from src.rag import build_pipeline


def main() -> None:
    settings = get_settings()
    pipeline = build_pipeline(settings)
    print(f"[ingest] provider={settings.embedding_provider}, "
          f"store={settings.vector_store}")
    total = pipeline.index_corpus(
        raw_dir=settings.data_raw_dir,
        metadata_dir=settings.data_metadata_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    print(f"[ingest] 완료: 총 {total} 청크 적재")


if __name__ == "__main__":
    main()
