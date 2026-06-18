"""데이터셋 zip 압축 해제 유틸.

`dataset.zip` 같은 배포 압축파일에서 문서(HWP/PDF)와 메타데이터(CSV/XLSX)를
구분해 `data/` 하위 폴더로 정리한다.

CLI 사용:
    python -m src.dataset_utill.extract "C:/Users/PC/Downloads/다운로드받은 데이터셋 이름 (2).zip"

코드 사용:
    from src.dataset_utill import extract_dataset
    extract_dataset("다운로드 받은 데이터셋 이름.zip")
"""
from __future__ import annotations

import zipfile
from pathlib import Path

# 분류 기준 확장자
DOC_EXTS = {".hwp", ".pdf"}
META_EXTS = {".csv", ".xlsx"}


# info는 매개변수(타입 힌트), -> str은 문자열을 반환(타입힌트)
def _decode_name(info: zipfile.ZipInfo) -> str:
    """한글 zip 파일명 보정.

    UTF-8 플래그가 없으면 zipfile 이 cp437 로 디코딩해 한글이 깨지므로,
    cp437 로 되돌린 뒤 cp949(한국어)로 다시 디코딩한다.
    """
    if info.flag_bits & 0x800:  # UTF-8 플래그가 설정된 경우
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def extract_dataset(
    zip_path: str | Path,
    raw_dir: str | Path = "data/raw",
    metadata_dir: str | Path = "data/metadata",
    overwrite: bool = True,
) -> dict[str, int]:
    """zip 에서 문서/메타데이터를 분류해 각 폴더로 추출한다.

    Args:
        zip_path: 압축 파일 경로
        raw_dir: 문서(HWP/PDF) 저장 폴더
        metadata_dir: 메타데이터(CSV/XLSX) 저장 폴더
        overwrite: 이미 존재하는 파일을 덮어쓸지 여부

    Returns:
        {"documents": 추출한 문서 수, "metadata": 추출한 메타데이터 수, "skipped": 건너뛴 수}
    """
    # 실제 코드잇에서 다운로드받은 압축파일 경로를 zip_path에 저장
    zip_path = Path(zip_path)
    # zip_path가 없는경우 예외처리
    if not zip_path.exists():
        raise FileNotFoundError(f"압축 파일을 찾을 수 없습니다: {zip_path}")

    # 기본 경로 설정과 폴더 생성
    raw_dir = Path(raw_dir)
    metadata_dir = Path(metadata_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # 함수 실행 결과를 저장할 딕셔너리
    counts = {"documents": 0, "metadata": 0, "skipped": 0}

    # 실제 zipfile에서 데이터를 읽어오는 과정
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _decode_name(info)  # 이름을 추출
            ext = Path(name).suffix.lower()  # 확장자를 추출

            if ext in DOC_EXTS:  # 확장자가 .hwp / .pdf 일 경우 
                dest_dir = raw_dir
                key = "documents"
            elif ext in META_EXTS:  # 확장자가 .csv / .xlsx 인 경우
                dest_dir = metadata_dir
                key = "metadata"
            else:
                counts["skipped"] += 1
                continue

            # 압축 내부 경로는 버리고 파일명만 사용해 평탄화
            dest = dest_dir / Path(name).name
            if dest.exists() and not overwrite:
                counts["skipped"] += 1
                continue
            
            # 실제 파일을 복사해서 저장
            with zf.open(info) as src, open(dest, "wb") as out:
                out.write(src.read())
            counts[key] += 1

    return counts


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print('사용법: python -m src.dataset_utill.extract "<zip 경로>"')
        sys.exit(1)
    result = extract_dataset(sys.argv[1])
    print(
        f"[extract] 문서 {result['documents']}개 -> data/raw, "
        f"메타데이터 {result['metadata']}개 -> data/metadata "
        f"(건너뜀 {result['skipped']})"
    )


if __name__ == "__main__":
    main()
