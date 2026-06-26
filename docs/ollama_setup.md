# Ollama로 GCP VM에서 RAG 돌리기 (가장 쉬운 HF 경로)

> Ollama가 OpenAI 호환 API를 제공 → 기존 코드 거의 그대로, **torch/transformers 불필요**.
> 아까 겪은 torch/3.14/venv 문제를 통째로 우회한다.

## 0. 왜 Ollama인가
- 모델 다운로드·실행·서빙을 명령 한 줄로 (`ollama pull` / 자동 서빙)
- `http://localhost:11434/v1` 로 **OpenAI 호환 API** 제공 → `provider=openai` + `base_url`만 바꾸면 끝
- Python엔 무거운 ML 라이브러리 불필요 (Ollama 바이너리가 GPU로 모델 실행)

## 1. Ollama 설치 (VM 터미널)
```bash
curl -fsSL https://ollama.com/install.sh | sh
```
설치되면 보통 자동으로 서비스가 뜬다. 확인:
```bash
ollama --version
curl http://localhost:11434/api/tags   # 응답 오면 서버 동작 중
```
(안 떠 있으면 `ollama serve &` 로 백그라운드 실행)

## 2. 모델 받기
```bash
ollama pull qwen2.5:7b     # LLM (한국어 가능)
ollama pull bge-m3         # 임베딩 (한국어 강함)
```
GPU가 있으면 Ollama가 자동으로 GPU 사용. 확인: `ollama ps`

## 3. 코드 + 경량 의존성
```bash
cd ~/rfp-rag-extractor          # repo 위치 (없으면 git clone)
git pull
pip install -r requirements-run.txt   # openai, chromadb 등만 (torch 불필요!)
```

## 4. 데이터 (chunks.csv)
git에 없으므로 JupyterLab 파일창으로 `data/processed/chunks.csv` 업로드.

## 5. 설정 + 실행
```bash
cp .env.ollama.example .env
python -m scripts.ingest                 # bge-m3(Ollama)로 재인덱싱
python -m scripts.ask "이 사업의 주요 요구사항은?"   # qwen2.5(Ollama)로 답변
python -m scripts.eval_retrieval         # 검색 평가
```

## 6. OpenAI vs Ollama 비교
- 같은 골든셋·코드, provider/모델만 다름 → 결과(`results/`) 비교.

## 트러블슈팅
- **임베딩 배치 오류**: 우리 코드는 청크를 묶어 보냄. Ollama가 배치를 못 받으면
  `OPENAI_EMBEDDING_MODEL` 호출이 에러날 수 있음 → 그 경우 임베딩만 sentence-transformers로
  전환(`EMBEDDING_PROVIDER=huggingface`, `HF_EMBEDDING_MODEL=BAAI/bge-m3`, `HF_DEVICE=cuda`)하고
  `pip install -r requirements-hf.txt` 추가.
- **포트/서버**: `curl http://localhost:11434/api/tags` 로 Ollama 살아있는지 확인.
- **모델명 불일치**: `.env`의 모델명은 `ollama list` 의 이름과 정확히 같아야 함.

## 비용
- VM 끄기: `gcloud compute instances stop <VM> --zone=<zone>` (안 쓸 때 꼭).
