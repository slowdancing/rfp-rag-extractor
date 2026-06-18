"""CLI 질의 스크립트 (빠른 동작 확인용).

실행:  python -m scripts.ask "이 사업의 예산은 얼마인가요?"
"""
from __future__ import annotations

import sys

from src.config import get_settings
from src.rag import build_pipeline


def main() -> None:
    if len(sys.argv) < 2:
        print('사용법: python -m scripts.ask "질문 내용"')
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    pipeline = build_pipeline(get_settings())
    ans = pipeline.ask(question)
    print("\n=== 답변 ===")
    print(ans.answer)
    print("\n=== 출처 ===")
    for c in ans.sources:
        print(f"- {c.metadata.get('source')} (score={c.score:.3f})")


if __name__ == "__main__":
    main()
