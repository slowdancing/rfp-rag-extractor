# GCP VM(L4 GPU) + HuggingFace 실행 가이드

> 목표: OpenAI 대신 자체 호스팅(HF) 모델로 RAG 실행 → OpenAI vs HF 성능 비교.

## 0. 사전 (완료 가정)
- GCP 결제 등록 ✅
- L4 GPU 지원/할당량 ✅

## 1. VM 생성 (로컬 터미널 or Cloud Shell)

```bash
gcloud compute instances create rfp-rag-vm \
  --zone=asia-northeast3-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --maintenance-policy=TERMINATE \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=150GB \
  --metadata="install-nvidia-driver=True"
```
- `g2-standard-8` 머신타입이 L4 1장을 포함. (Seoul=asia-northeast3, L4 없는 zone이면 -a/-b/-c 변경)
- PyTorch GPU 이미지라 torch+CUDA 미리 설치됨.
- 디스크 150GB (모델 ~20GB + 여유).

## 2. SSH 접속
```bash
gcloud compute ssh rfp-rag-vm --zone=asia-northeast3-a
```
첫 접속 시 NVIDIA 드라이버 설치 프롬프트 → `y`. `nvidia-smi` 로 L4 인식 확인.

## 3. 코드 + 데이터 올리기

```bash
# (VM 안에서) 코드
git clone https://github.com/slowdancing/rfp-rag-extractor.git
cd rfp-rag-extractor
```

데이터(chunks.csv)는 git 에 없으므로 로컬에서 전송 (로컬 터미널에서):
```bash
gcloud compute scp data/processed/chunks.csv \
  rfp-rag-vm:~/rfp-rag-extractor/data/processed/ --zone=asia-northeast3-a
# (메타데이터 CSV 도 필요하면 동일하게 전송)
```

## 4. 환경 셋업
```bash
# (VM 안에서)
bash scripts/setup_gcp.sh        # 의존성 설치 + GPU 확인 + .env 준비
# .env 확인 (HF provider, cuda)
```

## 5. 재인덱싱 + 실행
```bash
python -m scripts.ingest                 # bge-m3 로 임베딩 (HF 컬렉션 생성)
python -m scripts.ask "이 사업의 예산은?"   # Qwen 으로 답변 (첫 실행 시 모델 다운로드)
python -m scripts.eval_retrieval         # 검색 평가 (HF)
```
> 모델 첫 사용 시 HuggingFace 에서 자동 다운로드 (bge-m3 ~2GB, Qwen-7B ~15GB).

## 6. OpenAI vs HF 비교
- HF 결과(`results/eval_retrieval.md`)를 OpenAI 결과와 비교.
- 같은 골든셋·같은 코드, provider만 다름 → 공정 비교.

## ⚠️ 비용 / 종료
- L4 VM ≈ 시간당 $0.7~1. **작업 끝나면 반드시 중지:**
```bash
gcloud compute instances stop rfp-rag-vm --zone=asia-northeast3-a
# 완전 삭제: gcloud compute instances delete rfp-rag-vm --zone=asia-northeast3-a
```

## 알려진 검증 포인트
- `hf_embedder.py` : 로컬에서 검증 완료 ✅
- `hf_llm.py` : GPU 첫 실행이라 chat template/생성 파라미터 손볼 수 있음 → 5단계 `ask` 에서 확인.
