"""텍스트 청킹.

토큰 기반(tiktoken)으로 chunk_size/overlap 만큼 문서를 분할한다.
문단 경계를 우선 존중하도록 먼저 문단 단위로 나눈 뒤,
토큰 한도를 넘으면 슬라이딩 윈도우로 자른다.
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict


def _split_by_tokens(text: str, chunk_size: int, overlap: int) -> list[str]:
    tokens = _ENCODER.encode(text)
    if len(tokens) <= chunk_size:
        return [text]
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + chunk_size]
        chunks.append(_ENCODER.decode(window))
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
