#!/usr/bin/env bash
# GCP VM(L4 GPU) 초기 셋업 — repo 클론 후 VM 에서 실행한다.
#   bash scripts/setup_gcp.sh
set -e

echo "=== 1) GPU/드라이버 확인 ==="
nvidia-smi || { echo "GPU 미인식 — 드라이버 설치 확인 필요"; exit 1; }

echo "=== 2) 의존성 설치 ==="
pip install -r requirements.txt
pip install -r requirements-hf.txt

echo "=== 3) torch CUDA 인식 확인 ==="
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device:", torch.cuda.get_device_name(0))
PY

echo "=== 4) .env 준비 ==="
[ -f .env ] || cp .env.hf.example .env
echo "  .env 확인/수정 후, chunks.csv 를 data/processed/ 에 두고:"
echo "    python -m scripts.ingest        # HF 임베딩으로 재인덱싱"
echo "    python -m scripts.eval_retrieval  # 검색 평가"
echo "=== 셋업 완료 ==="
