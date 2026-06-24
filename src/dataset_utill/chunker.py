"""텍스트 청킹.

토큰 기반(tiktoken)으로 chunk_size/overlap 만큼 문서를 분할한다.
문단 경계를 우선 존중하도록 먼저 문단 단위로 나눈 뒤,
토큰 한도를 넘으면 슬라이딩 윈도우로 자른다.
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

# 기본 인코딩 베이스
_ENCODER = tiktoken.get_encoding("cl100k_base")

# 필드만 적으면 생성자등을 자동으로 만들어줌 (하나의 클래스 탄생)
@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict

# text와 chunk_size, overlap을 입력받으면 text를 청킹해서 chunks 리스트를 돌려주는 함수 (토큰화된 문자열)
def _split_by_tokens(text: str, chunk_size: int, overlap: int) -> list[str]:
    # 인코딩해서 tokens에 저장
    tokens = _ENCODER.encode(text)
    # 청킹 필요 여부 판단
    if len(tokens) <= chunk_size:
        return [text]
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + chunk_size]
        # 토큰 경계가 한글 글자 중간을 자르면 decode 시 U+FFFD 가 생김 → 제거
        # (overlap 영역에 온전한 글자가 보존되므로 안전)
        chunks.append(_ENCODER.decode(window).replace("�", ""))
        if start + chunk_size >= len(tokens):
            break
    return chunks


def chunk_document(
    doc_id: str,
    text: str,
    metadata: dict,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[Chunk]:
    pieces = _split_by_tokens(text, chunk_size, overlap)
    chunks: list[Chunk] = []
    for i, piece in enumerate(pieces):
        chunk_meta = dict(metadata)
        chunk_meta["chunk_index"] = i
        chunks.append(
            Chunk(chunk_id=f"{doc_id}::{i}", text=piece, metadata=chunk_meta)
        )
    return chunks
