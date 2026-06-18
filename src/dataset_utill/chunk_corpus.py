"""정제된 코퍼스를 토큰 기준으로 청킹한다.

흐름:
  1. data/processed/corpus_clean.csv 로드 (build_corpus 산출물)
  2. 각 문서의 text 를 토큰 청크로 분할 (tiktoken 기반)
  3. 청크마다 문서 메타데이터(doc_id, 사업명, 기관 ...)를 부착
  4. data/processed/chunks.csv 로 저장

토큰 청킹 로직은 src/ingestion/chunker.py 의 chunk_document 를 재사용한다.

CLI:
    python -m src.dataset_utill.chunk_corpus
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.chunker import chunk_document

# 각 청크에 부착할 메타데이터 컬럼 (검색 결과 필터링/출처표시에 사용)
_META_COLS = [
    "사업명",
    "발주 기관",
    "사업 금액",
    "공개 일자",
    "입찰 참여 마감일",
    "파일형식",
]


def build_chunks(
    corpus_path: str | Path = "data/processed/corpus_clean.csv",
    out_path: str | Path = "data/processed/chunks.csv",
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    verbose: bool = True,
) -> pd.DataFrame:
    """코퍼스를 청킹해 chunks DataFrame 을 만들고 CSV 로 저장한다.

    Args:
        corpus_path: 정제 코퍼스 CSV 경로
        out_path: 청크 결과 저장 경로
        chunk_size: 청크당 최대 토큰 수
        chunk_overlap: 인접 청크 간 겹치는 토큰 수
        verbose: 진행 로그 출력 여부

    Returns:
        컬럼: chunk_id, doc_id, chunk_index, text, (메타데이터)
    """
    corpus_path, out_path = Path(corpus_path), Path(out_path)
    df = pd.read_csv(corpus_path)

    rows = []
    skipped = 0
    for _, r in df.iterrows():
        doc_id = str(r["doc_id"])
        text = str(r["text"]) if pd.notna(r["text"]) else ""
        if not text.strip():
            skipped += 1
            continue

        metadata = {"doc_id": doc_id}
        metadata.update({col: r.get(col) for col in _META_COLS})

        for chunk in chunk_document(doc_id, text, metadata, chunk_size, chunk_overlap):
            row = {
                "chunk_id": chunk.chunk_id,
                "doc_id": doc_id,
                "chunk_index": chunk.metadata["chunk_index"],
                "text": chunk.text,
            }
            row.update({col: r.get(col) for col in _META_COLS})
            rows.append(row)

    chunks = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chunks.to_csv(out_path, index=False, encoding="utf-8-sig")

    if verbose:
        per_doc = chunks.groupby("doc_id").size()
        print(f"[chunk] 문서 {df.shape[0] - skipped}건 -> 청크 {len(chunks)}개 "
              f"(빈 문서 {skipped}건 제외) -> {out_path}")
        print(f"[chunk] 문서당 청크 수: 평균 {per_doc.mean():.1f}, "
              f"최소 {per_doc.min()}, 최대 {per_doc.max()}")
        print(f"[chunk] 설정: chunk_size={chunk_size} 토큰, overlap={chunk_overlap}")

    return chunks


def main() -> None:
    build_chunks()


if __name__ == "__main__":
    main()
