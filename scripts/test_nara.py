"""나라장터 API 클라이언트 단독 테스트.

키가 있을 때 API 연동이 되는지 빠르게 확인한다(파이프라인과 무관).
키는 .env의 NARA_API_KEY 또는 인자로.

실행:
  python -m scripts.test_nara "전자조달 시스템"
  python -m scripts.test_nara "전자조달 시스템" <서비스키>
"""
from __future__ import annotations

import sys

from src.config import get_settings
from src.nara import search_bids


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "정보시스템 구축"
    key = sys.argv[2] if len(sys.argv) > 2 else get_settings().nara_api_key
    if not key:
        print("NARA_API_KEY 가 없습니다. .env에 넣거나 인자로 전달하세요.")
        sys.exit(1)

    rows = search_bids(keyword, key, days=30, rows=5)
    print(f"검색어='{keyword}' → {len(rows)}건\n")
    for r in rows:
        b = f"{r['budget']:,}원" if r.get("budget") else "-"
        print(f"- {r.get('title')}")
        print(f"    발주 {r.get('org') or '-'} · 예산 {b} · 마감 {r.get('deadline') or '-'}")
        print(f"    링크 {r.get('link') or '-'}")
    if not rows:
        print("(결과 없음: 키/검색어/최근30일 공고 여부 확인. 키 인코딩 문제면 '디코딩' 키 사용)")


if __name__ == "__main__":
    main()
