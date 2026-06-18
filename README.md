# 입찰메이트 RFP RAG Extractor

복잡한 기업·정부 **제안요청서(RFP)** 에서 핵심 정보를 추출·요약하고
질의응답(Q&A)할 수 있는 사내 **RAG 시스템**.

> B2G 입찰지원 컨설팅 스타트업 **'입찰메이트'** 의 컨설턴트가, 나라장터 등에서
> 쏟아지는 수십 페이지짜리 RFP 를 일일이 읽지 않고도 **주요 요구조건·발주기관·
> 예산·제출방식** 등 핵심을 빠르게 파악하도록 돕는 것이 목표.

## 핵심 특징

- **백엔드 교체 가능**: 1단계는 OpenAI API, 2단계는 GCP VM(L4 GPU) + HuggingFace
  모델로 **코드 수정 없이 `.env` 설정만으로** 전환 (임베딩/LLM/벡터스토어 전 계층 추상화)
- **출처 기반 답변**: 환각을 억제하고 답변에 근거 문서를 함께 제시
- **RFP 특화 요약**: 사업명/발주기관/예산/기간/요구사항/자격/제출방식/평가방식 자동 정리
- **평가 내장**: 검색(Hit@k, MRR) + 생성(LLM-as-judge) 평가 스크립트 제공

## 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 (예: venv)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 설정 파일 준비
copy .env.example .env          # Windows (PowerShell: Copy-Item .env.example .env)
# .env 를 열어 OPENAI_API_KEY 등을 입력
```

### 2. 데이터 배치

```
data/
├── raw/         # 100개 RFP 원문 (PDF/TXT)  ← 여기에 문서 투입
└── metadata/    # RFP 메타데이터 (JSON, doc_id=파일명 기준 매핑)
```

### 3. 인덱싱 → 질의

```bash
# 벡터 인덱스 생성
python -m scripts.ingest

# CLI 로 빠르게 질문
python -m scripts.ask "이 사업의 예산과 제출 마감일은?"

# API 서버 실행
uvicorn src.api.main:app --reload
# → http://localhost:8000/docs  (Swagger UI)
```

### 4. 평가

```bash
# data/eval/eval_set.jsonl 작성 후 (예시: eval_set.example.jsonl 참고)
python -m scripts.evaluate data/eval/eval_set.jsonl
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET`  | `/health`    | 헬스 체크 |
| `POST` | `/ask`       | RFP 에 대한 질의응답 (특정 `doc_id` 한정 검색 가능) |
| `POST` | `/summarize` | 특정 RFP 문서를 표준 항목으로 요약 |

## 프로젝트 구조

```
rfp-rag-extractor/
├── src/
│   ├── config.py            # .env 기반 중앙 설정
│   ├── ingestion/           # 로더(PDF/TXT) + 메타데이터 + 청킹
│   ├── embeddings/          # 임베딩 추상화 + OpenAI/HF 구현
│   ├── llm/                 # 생성 LLM 추상화 + OpenAI/HF 구현
│   ├── vectorstore/         # 벡터스토어 추상화 + Chroma 구현
│   ├── rag/                 # RAG 파이프라인 + RFP 프롬프트
│   ├── api/                 # FastAPI 엔드포인트
│   └── evaluation/          # 검색/생성 평가
├── scripts/                 # ingest / ask / evaluate 실행 진입점
├── data/                    # raw, metadata, processed, eval (git 미포함)
├── tests/                   # pytest 스모크 테스트
├── docs/architecture.md     # 아키텍처 상세
└── requirements.txt
```

## 단계별 로드맵

- [x] 프로젝트 스캐폴드 + 추상화 아키텍처
- [ ] **1단계** — OpenAI API 기반 RAG 동작 (임베딩 + GPT)
- [ ] 청킹/임베딩/top_k 실험 및 평가지표 확정
- [ ] **2단계** — GCP VM(L4 GPU) + HuggingFace 모델로 전환 ([docs/architecture.md](docs/architecture.md) 체크리스트)
- [ ] 추가 기능 (메타데이터 필터 고도화, 고객사 매칭 추천 등)

## 테스트

```bash
pytest
```

자세한 설계는 [docs/architecture.md](docs/architecture.md) 참고.
