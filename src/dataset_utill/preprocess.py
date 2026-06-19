"""정제된 코퍼스 생성 (청킹 직전 단계).

두번째 처리

흐름:
  1. data_list.csv 로드
  2. 각 문서의 본문 텍스트 확보
     - CSV 텍스트가 충분히 길면 그대로 사용
     - `min_length` 미만(추출 빈약)이면 data/raw 의 원본에서 재추출해 보강
  3. 모든 텍스트를 clean_text 로 정제
  4. data/processed/corpus_clean.csv 로 저장

CLI:
    python -m src.dataset_utill.preprocess
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .clean import clean_text
from .text_extract import extract_text

# 코퍼스에 유지할 메타데이터 컬럼 (추후 필터링/출처표시에 사용) - 결과분석에 사용 가능
_META_COLS = [
    "사업명",
    "발주 기관",
    "사업 금액",
    "공개 일자",
    "입찰 참여 마감일",
    "파일형식",
    "사업 요약",
]


# 원본 메타데이터를 받아서 짧은 데이터면 보강, 이후 정제하여 csv파일로 저장
def build_corpus(
    csv_path: str | Path = "data/metadata/data_list.csv",
    raw_dir: str | Path = "data/raw",
    out_path: str | Path = "data/processed/corpus_clean.csv",
    min_length: int = 1000,
    verbose: bool = True,
) -> pd.DataFrame:
    """정제된 코퍼스 DataFrame 을 만들어 CSV 로 저장하고 반환한다.

    Args:
        csv_path: 원본 메타데이터 CSV 경로
        raw_dir: 원본 문서 폴더
        out_path: 결과 저장 경로
        min_length: 이 길이 미만이면 원본에서 텍스트 재추출(보강) 시도 (기준)
        verbose: 진행 로그 출력 여부

    Returns:
        컬럼: doc_id, (메타데이터), text, text_source, char_len
    """
    csv_path, raw_dir, out_path = Path(csv_path), Path(raw_dir), Path(out_path)
    df = pd.read_csv(csv_path)

    records = []
    augmented = 0
    failed = []
    for _, row in df.iterrows():  # 데이터의 한 행을 받아옴
        filename = str(row["파일명"])
        doc_id = Path(filename).stem
        text = str(row["텍스트"]) if pd.notna(row["텍스트"]) else ""
        source = "csv"

        # --- 짧은 문서 보강 ---
        if len(text) < min_length:
            original = raw_dir / filename
            if original.exists():
                try:
                    reextracted = extract_text(original)
                    if len(reextracted) > len(text):
                        text, source = reextracted, "reextracted"
                        augmented += 1
                except Exception as exc:  # noqa: BLE001
                    failed.append((doc_id, str(exc)))
            else:
                failed.append((doc_id, "원본 파일 없음"))

        cleaned = clean_text(text)
        record = {"doc_id": doc_id}
        record.update({col: row.get(col) for col in _META_COLS})
        record["text"] = cleaned
        record["text_source"] = source
        record["char_len"] = len(cleaned)
        records.append(record)

    corpus = pd.DataFrame(records)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_csv(out_path, index=False, encoding="utf-8-sig")

    if verbose:
        print(f"[preprocess] 문서 {len(corpus)}건 처리, 보강 {augmented}건 -> {out_path}")
        print(f"[preprocess] 정제 후 길이: 중앙값 {int(corpus['char_len'].median())}, "
              f"최소 {corpus['char_len'].min()}, 최대 {corpus['char_len'].max()}")
        if failed:
            print(f"[preprocess] 보강 실패 {len(failed)}건:")
            for doc_id, reason in failed:
                print(f"    - {doc_id[:40]}: {reason}")

    return corpus


def main() -> None:
    build_corpus()


if __name__ == "__main__":
    main()
