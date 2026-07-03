"""나라장터(조달청) 입찰공고 실시간 검색 — 로컬 DB에 적합 공고가 없을 때 폴백.

공공데이터포털(data.go.kr) '조달청_나라장터 입찰공고정보서비스'의 용역 공고
검색 API(getBidPblancListInfoServcPPSSrch)를 호출해, 최근 공고를 키워드로 찾는다.

⚠️ 무료지만 서비스키 필요:
   data.go.kr 가입 → '입찰공고정보서비스' 활용신청 → 인증키 발급 → .env `NARA_API_KEY`.
   키가 없거나 `NARA_FALLBACK=false`면 이 기능은 비활성(앱은 기존대로 로컬만 사용).

표준 라이브러리(urllib)만 사용 — 추가 의존성 없음.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

ENDPOINT = (
    "http://apis.data.go.kr/1230000/BidPublicInfoService/"
    "getBidPblancListInfoServcPPSSrch"
)


def _to_int(v) -> int | None:
    """'1,234,000' 같은 금액 문자열 → int. 실패 시 None."""
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _normalize(it: dict) -> dict:
    """나라장터 공고 항목 → 우리 DocumentItem 형식으로 매핑."""
    return {
        "doc_id": f"나라장터:{it.get('bidNtceNo', '') or it.get('bidNtceNm', '')}",
        "title": it.get("bidNtceNm"),
        "org": it.get("dminsttNm") or it.get("ntceInsttNm"),
        "budget": _to_int(it.get("asignBdgtAmt") or it.get("presmptPrce")),
        "posted": it.get("bidNtceDt"),
        "deadline": it.get("bidClseDt"),
        "filetype": None,
        "summary": None,          # 목록 API엔 본문 없음(상세 링크로 확인)
        "score": None,
        "link": it.get("bidNtceDtlUrl"),
        "source": "나라장터",
    }


def search_bids(keyword: str, api_key: str, days: int = 30, rows: int = 10) -> list[dict]:
    """키워드로 최근 나라장터 용역 공고를 검색해 정규화 목록을 반환.

    실패(네트워크·키 오류·파싱)하면 빈 리스트를 반환해 앱이 죽지 않게 한다.
    """
    if not api_key or not keyword:
        return []

    now = datetime.now()
    params = {
        "serviceKey": api_key,        # data.go.kr '디코딩' 키 권장(urlencode가 인코딩)
        "type": "json",               # JSON 응답
        "inqryDiv": "1",              # 1 = 공고게시일시 기준 조회
        "inqryBgnDt": (now - timedelta(days=days)).strftime("%Y%m%d%H%M"),
        "inqryEndDt": now.strftime("%Y%m%d%H%M"),
        "numOfRows": str(rows),
        "pageNo": "1",
        "bidNtceNm": keyword,         # 공고명 키워드 검색
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except Exception:  # noqa: BLE001 - 외부 API 오류는 조용히 폴백
        return []

    # 응답 구조: response.body.items ( [ {...}, ... ] 또는 { "item": [...] } )
    body = (data.get("response", {}) or {}).get("body", {}) or {}
    items = body.get("items", [])
    if isinstance(items, dict):       # { "item": ... } 형태 대응
        items = items.get("item", [])
    if isinstance(items, dict):       # 단일 건이면 dict 하나
        items = [items]

    return [_normalize(it) for it in (items or []) if it.get("bidNtceNm")]
