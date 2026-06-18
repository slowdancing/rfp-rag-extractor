# 입찰메이트 RFP RAG Extractor

복잡한 기업·정부 **제안요청서(RFP)** 에서 핵심 정보를 추출·요약하고
질의응답(Q&A)할 수 있는 사내 **RAG 시스템**.

> B2G 입찰지원 컨설팅 스타트업 **'입찰메이트'** 의 컨설턴트가, 나라장터 등에서
> 쏟아지는 수십 페이지짜리 RFP 를 일일이 읽지 않고도 **주요 요구조건·발주기관·
> 예산·제출방식** 등 핵심을 빠르게 파악하도록 돕는 것이 목표.

## 진행 상황

| 단계 | 상태 |
|------|------|
| 데이터 추출·정제·청킹 파이프라인 (`src/dataset_utill`) | ✅ 완료·검증됨 |
| RAG 코어 (임베딩/벡터스토어/LLM/파이프라인/API) | 🟡 스캐폴드 (OpenAI 연결 전) |
| 평가 체계 | 🟡 골격 |
| GCP VM + HuggingFace (2단계) | ⬜ 예정 |

**설계 원칙**: 1단계는 OpenAI API, 2단계는 GCP VM(L4 GPU) + HuggingFace 모델로
**코드 수정 없이 `.env` 설정만으로** 전환 (임베딩/LLM/벡터스토어 전 계층 추상화).

---

## 폴더 구조

```
rfp-rag-extractor/
├── src/
│   ├── config.py            # .env 기반 중앙 설정
│   ├── dataset_utill/       # ★ 데이터 준비 파이프라인 (완성)
│   ├── ingestion/           # 청킹·로더 (저수준 유틸)
│   ├── embeddings/          # 임베딩 추상화 + OpenAI/HF 구현
│   ├── vectorstore/         # 벡터스토어 추상화 + Chroma 구현
│   ├── llm/                 # 생성 LLM 추상화 + OpenAI/HF 구현
│   ├── rag/                 # RAG 파이프라인 + 프롬프트
│   ├── api/                 # FastAPI 엔드포인트
│   └── evaluation/          # 검색/생성 평가
├── scripts/                 # 실행 진입점 (ingest/ask/evaluate)
├── notebooks/               # 01_eda.ipynb (EDA)
├── data/                    # raw/metadata/processed/eval (git 미포함)
├── docs/architecture.md     # 아키텍처 상세
└── requirements.txt
```

---

## 모듈별 상세

### `src/dataset_utill/` — 데이터 준비 파이프라인 ★

원시 zip → 청크까지, **실제로 동작하는 데이터 처리** 모듈. `data/` 관련 작업을 함수화해 모아둔 곳.

| 파일 | 함수 | 기능 |
|------|------|------|
| `extract.py` | `extract_dataset(zip_path, raw_dir, metadata_dir, overwrite=True)` | zip 압축 해제 → 문서(HWP/PDF)는 `data/raw`, 메타데이터(CSV/XLSX)는 `data/metadata` 로 분류. 한글 파일명 깨짐 보정 포함. `{"documents":n,"metadata":n,"skipped":n}` 반환 |
| `text_extract.py` | `extract_text(path)` | 확장자에 맞는 추출기로 원본 파일의 **전체 텍스트** 반환 |
| | `extract_pdf(path)` / `extract_hwp(path)` | 각각 PDF(pypdf) / HWP(pyhwp) 텍스트 추출 |
| `clean.py` | `clean_text(text, remove_artifacts=True)` | 줄바꿈 통일, `<표>/<그림>` 제거, 공백·빈줄 축소 등 **정제** |
| `preprocess.py` | `build_corpus(csv_path, raw_dir, out_path, min_length=1000)` | CSV 로드 → `min_length` 미만 문서는 원본 재추출로 **보강** → 정제 → `corpus_clean.csv` 저장 |
| `chunk_corpus.py` | `build_chunks(corpus_path, out_path, chunk_size=1000, chunk_overlap=150)` | 정제 코퍼스를 **토큰 청킹** → 청크별 메타데이터 부착 → `chunks.csv` 저장 |

**사용법 (데이터 준비 전체 흐름):**

```python
from src.dataset_utill import extract_dataset, build_corpus, build_chunks

extract_dataset("C:/Users/PC/Downloads/dataset (2).zip")  # zip → data/raw, data/metadata
build_corpus(min_length=1000)   # 보강+정제 → data/processed/corpus_clean.csv (100행)
build_chunks(chunk_size=1000, chunk_overlap=150)  # 청킹 → data/processed/chunks.csv (1107행)
```

```bash
# CLI 로도 실행 가능
python -m src.dataset_utill.extract "C:/.../dataset (2).zip"
python -m src.dataset_utill.preprocess
python -m src.dataset_utill.chunk_corpus
```

### `src/config.py` — 중앙 설정

| 함수/클래스 | 기능 |
|------|------|
| `Settings` | `.env`·환경변수에서 provider/모델/경로/청킹/검색 설정을 읽는 pydantic 설정 클래스 |
| `get_settings()` | 싱글톤 `Settings` 인스턴스 반환 |

```python
from src.config import get_settings
settings = get_settings()      # settings.openai_api_key, settings.top_k ...
```

### `src/ingestion/` — 청킹·로더 (저수준 유틸)

| 파일 | 함수/클래스 | 기능 |
|------|------|------|
| `chunker.py` | `chunk_document(doc_id, text, metadata, chunk_size, overlap)` | 토큰 기준 슬라이딩 윈도우 청킹. `Chunk` 리스트 반환 (`dataset_utill.chunk_corpus` 가 재사용) |
| `loader.py` | `load_documents(raw_dir, metadata_dir)` | 파일 직접 파싱 방식 로더 (현재 파이프라인은 CSV 기반이라 미사용) |

### `src/embeddings/` — 임베딩 (텍스트 → 벡터)

| 파일 | 함수/클래스 | 기능 |
|------|------|------|
| `base.py` | `BaseEmbedder` | 임베더 추상 인터페이스 (`embed_documents`, `embed_query`) |
| `openai_embedder.py` | `OpenAIEmbedder` | OpenAI 임베딩 (1단계) |
| `hf_embedder.py` | `HuggingFaceEmbedder` | bge-m3 등 로컬 임베딩 (2단계) |
| `__init__.py` | `build_embedder(settings)` | 설정의 provider 에 따라 적절한 임베더 생성 (팩토리) |

### `src/vectorstore/` — 벡터 저장·검색

| 파일 | 함수/클래스 | 기능 |
|------|------|------|
| `base.py` | `BaseVectorStore`, `RetrievedChunk` | 저장소 추상 인터페이스 (`add`, `query`, `count`) |
| `chroma_store.py` | `ChromaVectorStore` | ChromaDB 구현 (코사인 유사도) |
| `__init__.py` | `build_vector_store(settings)` | 팩토리 |

### `src/llm/` — 답변 생성 LLM

| 파일 | 함수/클래스 | 기능 |
|------|------|------|
| `base.py` | `BaseLLM` | LLM 추상 인터페이스 (`generate`) |
| `openai_llm.py` | `OpenAILLM` | OpenAI Chat (1단계) |
| `hf_llm.py` | `HuggingFaceLLM` | Qwen 등 로컬 LLM (2단계) |
| `__init__.py` | `build_llm(settings)` | 팩토리 |

### `src/rag/` — RAG 오케스트레이션 (핵심)

| 파일 | 함수/클래스 | 기능 |
|------|------|------|
| `pipeline.py` | `RAGPipeline` | 인덱싱·검색·질의·요약을 묶는 핵심 클래스 |
| | `RAGPipeline.index_corpus(...)` | 문서 청킹→임베딩→저장 |
| | `RAGPipeline.ask(question, top_k, where)` | 검색→프롬프트→생성. `RAGAnswer`(답변+출처) 반환 |
| | `RAGPipeline.summarize(doc_id)` | 특정 문서 표준 항목 요약 |
| | `build_pipeline(settings)` | 설정으로 완성된 파이프라인 생성 |
| `prompts.py` | `build_qa_user_prompt`, `build_summary_user_prompt` | RFP 특화 프롬프트 구성 |

### `src/api/` — FastAPI 서비스

| 파일 | 함수 | 기능 |
|------|------|------|
| `main.py` | `health()` / `ask()` / `summarize()` | `GET /health`, `POST /ask`, `POST /summarize` 엔드포인트 |
| `schemas.py` | `AskRequest`, `AskResponse` 등 | 요청/응답 스키마 |

```bash
uvicorn src.api.main:app --reload    # http://localhost:8000/docs
```

### `src/evaluation/` — 평가

| 함수 | 기능 |
|------|------|
| `load_eval_set(path)` | 평가셋(JSONL) 로드 |
| `evaluate_retrieval(pipeline, items, top_k)` | 검색 평가 (Hit@k, MRR) |
| `evaluate_generation_llm_judge(pipeline, items, judge_llm)` | 생성 평가 (LLM-as-judge) |

### `scripts/` — 실행 진입점

| 파일 | 실행 | 기능 |
|------|------|------|
| `ingest.py` | `python -m scripts.ingest` | 벡터 인덱스 생성 |
| `ask.py` | `python -m scripts.ask "질문"` | CLI 질의 |
| `evaluate.py` | `python -m scripts.evaluate <eval.jsonl>` | 성능 평가 |

### `notebooks/`

| 파일 | 내용 |
|------|------|
| `01_eda.ipynb` | 데이터 추출(섹션0) + EDA (결측·금액·기관·날짜·텍스트 품질) |

---

## 데이터 흐름

```
dataset.zip
  └─ extract_dataset() ─→ data/raw/ (HWP 96 + PDF 4), data/metadata/ (data_list.csv)
        └─ build_corpus() ─→ data/processed/corpus_clean.csv   (100행, 보강+정제)
              └─ build_chunks() ─→ data/processed/chunks.csv    (1107 청크)
                    └─ [다음] 임베딩 → 벡터스토어 → RAG 질의응답
```

---

## 빠른 시작

```bash
# 1. 환경
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 2. 설정
copy .env.example .env          # OPENAI_API_KEY 등 입력

# 3. 데이터 준비 (zip 경로만 본인 환경에 맞게)
python -m src.dataset_utill.extract "C:/Users/PC/Downloads/dataset (2).zip"
python -m src.dataset_utill.preprocess
python -m src.dataset_utill.chunk_corpus

# 4. (이후) 인덱싱 → 질의
python -m scripts.ingest
python -m scripts.ask "이 사업의 예산과 제출 마감일은?"
```

## 테스트

```bash
pytest
```

자세한 설계는 [docs/architecture.md](docs/architecture.md) 참고.
