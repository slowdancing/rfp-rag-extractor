"""RFP 원문 + 메타데이터 로더.

data/raw 에 있는 PDF/텍스트 RFP 문서와 data/metadata 의 메타데이터
(CSV/JSON)를 읽어 표준 형태(RawDocument)로 변환한다.

한글(HWP) 문서가 섞여 있을 수 있으므로, 지원하지 않는 확장자는
경고만 남기고 건너뛴다(추후 HWP 파서 추가 지점).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RawDocument:
    doc_id: str          # 파일명(확장자 제외) 기준 식별자
    text: str
    metadata: dict = field(default_factory=dict)


def _read_pdf(path: Path) -> str:
    # pypdf 는 실제 PDF 로딩 시에만 import (Ollama 등 경량 실행 경로에서 불필요)
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


_READERS = {".pdf": _read_pdf, ".txt": _read_text, ".md": _read_text}


def load_metadata(metadata_dir: str) -> dict[str, dict]:
    """doc_id -> metadata dict 매핑을 만든다.

    지원 형식:
      - 개별 JSON 파일들 (파일명이 doc_id)
      - 통합 JSON: {doc_id: {...}, ...} 또는 [{"doc_id": ..., ...}, ...]
    """
    meta_dir = Path(metadata_dir)
    result: dict[str, dict] = {}
    if not meta_dir.exists():
        return result

    for path in meta_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and path.stem not in ("metadata", "index"):
            # 단일 문서 메타데이터로 간주
            result[path.stem] = data
        elif isinstance(data, dict):
            result.update(data)
        elif isinstance(data, list):
            for item in data:
                key = str(item.get("doc_id") or item.get("id") or item.get("filename"))
                result[key] = item
    return result


def load_documents(raw_dir: str, metadata_dir: str | None = None) -> list[RawDocument]:
    """data/raw 의 모든 지원 문서를 읽어 RawDocument 리스트로 반환."""
    raw = Path(raw_dir)
    meta_map = load_metadata(metadata_dir) if metadata_dir else {}

    docs: list[RawDocument] = []
    for path in sorted(raw.iterdir()):
        if path.is_dir():
            continue
        reader = _READERS.get(path.suffix.lower())
        if reader is None:
            print(f"[loader] 지원하지 않는 형식, 건너뜀: {path.name}")
            continue
        text = reader(path)
        if not text.strip():
            print(f"[loader] 추출된 텍스트 없음, 건너뜀: {path.name}")
            continue
        doc_id = path.stem
        meta = {"source": path.name, "doc_id": doc_id}
        meta.update(meta_map.get(doc_id, {}))
        docs.append(RawDocument(doc_id=doc_id, text=text, metadata=meta))
    return docs
