"""기본 스모크 테스트: 외부 API 없이 동작하는 단위들만 검증.

실행:  pytest
"""
from __future__ import annotations

from src.dataset_utill.chunker import chunk_document


def test_chunk_short_document_single_chunk():
    chunks = chunk_document("doc1", "짧은 텍스트입니다.", {"doc_id": "doc1"})
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc1::0"
    assert chunks[0].metadata["chunk_index"] == 0


def test_chunk_long_document_overlaps():
    text = "가나다 " * 2000  # 토큰 한도를 충분히 초과
    chunks = chunk_document("doc2", text, {"doc_id": "doc2"}, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    # 모든 청크가 동일 doc_id 메타데이터를 가진다
    assert all(c.metadata["doc_id"] == "doc2" for c in chunks)
    # chunk_id 가 순차적으로 부여된다
    assert [c.chunk_id for c in chunks] == [f"doc2::{i}" for i in range(len(chunks))]


def test_settings_defaults():
    from src.config import Settings

    s = Settings(_env_file=None)
    assert s.llm_provider == "openai"
    assert s.chunk_size > s.chunk_overlap
