"""원본 문서(HWP/PDF)에서 텍스트를 추출한다.

CSV(`data_list.csv`)의 `텍스트` 컬럼이 일부 문서에서 잘려 있어,
원본 파일에서 전체 텍스트를 다시 뽑아 보강할 때 사용한다.

- PDF: pypdf
- HWP: pyhwp(hwp5) 의 TextTransform (HWPv5 형식)
"""
from __future__ import annotations

import io
import logging
import warnings
from contextlib import closing
from pathlib import Path

# pyhwp 가 내부적으로 발생시키는 pkg_resources Deprecation 경고 억제
warnings.filterwarnings("ignore", category=UserWarning, module="hwp5")
# hwp5 가 enum 미정의 값 등을 WARNING 으로 대량 출력하는 것을 억제
logging.getLogger("hwp5").setLevel(logging.ERROR)


# 경로를 입력받아 모든 페이지의 텍스트가 담긴 문자열을 리턴
def extract_pdf(path: str | Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    # page를 순회하며 page의 text를 뽑음 text가 없다면 빈 문자열을 반환, \n을 구분자로 하여 텍스트를 이어붙임
    return "\n".join((page.extract_text() or "") for page in reader.pages)


# 경로를 입력받아 모든 페이지의 텍스트가 담긴 문자열을 리턴 
def extract_hwp(path: str | Path) -> str:
    # 무거운 import 는 실제 호출 시에만 수행
    from hwp5.hwp5txt import TextTransform
    from hwp5.xmlmodel import Hwp5File

    transform = TextTransform().transform_hwp5_to_text
    with closing(Hwp5File(str(path))) as hwp5file:
        buf = io.BytesIO()  # buf 변수에 메모리의 가상 파일을 만들어 결과를 저장
        transform(hwp5file, buf)  # hwp파일이 buf안에 바이트로 채워짐
    return buf.getvalue().decode("utf-8")  # buf안에 채워진 바이트를 꺼내 utf-8로 인코딩해 리턴


_EXTRACTORS = {".pdf": extract_pdf, ".hwp": extract_hwp}


def extract_text(path: str | Path) -> str:
    """확장자에 맞는 추출기로 원본 파일의 전체 텍스트를 반환한다."""
    path = Path(path)
    extractor = _EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        raise ValueError(f"지원하지 않는 형식: {path.suffix}")
    return extractor(path)
