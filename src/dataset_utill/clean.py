"""RFP 본문 텍스트 정제.

추출된 raw 텍스트에는 다음과 같은 노이즈가 섞여 있다:
  - 윈도우식 줄바꿈(\\r\\n), 비단절 공백(\\u00a0)
  - HWP 추출 시 생기는 구조 표시자(<표>, <그림>, <개체>)
  - 과도한 연속 공백/빈 줄

청킹 직전 단계에서 이를 정규화해, 임베딩 품질을 높인다.
"""
from __future__ import annotations

import re

# HWP 추출 placeholder (표/그림/개체 등) — 의미 없는 구조 표시자
_ARTIFACT = re.compile(r"<\s*(표|그림|개체|수식|차트)\s*>")
# 연속 공백/탭/비단절공백
_INLINE_WS = re.compile(r"[ \t 　]+")
# 3줄 이상 연속 빈 줄
_MULTI_BLANK = re.compile(r"\n{3,}")


def clean_text(text: str | None, remove_artifacts: bool = True) -> str:
    """본문 텍스트를 정제해 반환한다.

    Args:
        text: 원본 텍스트 (None/NaN 허용)
        remove_artifacts: HWP 구조 표시자(<표> 등) 제거 여부

    Returns:
        정제된 텍스트
    """
    if not text or not isinstance(text, str):
        return ""

    # 1) 줄바꿈 통일
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2) HWP 구조 표시자 제거
    if remove_artifacts:
        text = _ARTIFACT.sub("", text)

    # 3) 줄 단위 정리: 줄 내부 다중 공백 축소 + 양끝 공백 제거
    lines = (_INLINE_WS.sub(" ", line).strip() for line in text.split("\n"))
    text = "\n".join(lines)

    # 4) 과도한 빈 줄 축소 (문단 구분용 2줄까지 허용)
    text = _MULTI_BLANK.sub("\n\n", text)

    return text.strip()
