# 입찰메이트 RFP RAG Extractor

복잡한 기업·정부 **제안요청서(RFP)** 에서 핵심 정보를 추출·요약하고
질의응답(Q&A)하는 사내 **RAG 시스템**.

> B2G 입찰지원 컨설팅 스타트업 **'입찰메이트'** 의 컨설턴트가, 나라장터 등에서
> 쏟아지는 수십 페이지 RFP 를 일일이 읽지 않고도 **요구조건·발주기관·예산·제출방식**
> 등 핵심을 빠르게 파악하도록 돕는 것이 목표.

## 진행 상황

| 단계 | 상태 |
|------|------|
| 데이터 파이프라인 (추출·보강·정제·청킹) | ✅ 완료 |
| 임베딩 & 벡터 적재 (ChromaDB, 모델별 컬렉션 분리) | ✅ 완료 |
| 질의응답 (질의재작성 → 하이브리드 검색 → LLM 재랭킹) | ✅ 동작 |
| 검색/생성 평가 (골든셋 + LLM-judge 교차검증) | ✅ 완료 |
| **모델 확정** (임베딩·LLM·검색, OpenAI 대비 정량 검증) | ✅ 완료 |
| GUI (FastAPI + React: 추천·필터·AI요약) | ✅ 동작 |
| 2단계 GCP VM(L4) 자체호스팅 + 배포·실동작 시연 | ✅ 완료 |

**확정 모델**: 임베딩 **bge-m3**, LLM **EXAONE-3.5-7.8B**, 검색 **하이브리드**(BM25+dense, RRF) — 근거 `results/model_decision.md`.
- EXAONE는 gpt-5-mini와 **정확도 동률**, **서술형 답변품질 우세**(4.37 vs 4.20, LLM-judge 교차검증), **응답 2.6배 빠름**, 무료·기밀보호.

**핵심 설계**: 임베딩·LLM·벡터스토어를 추상화 → **`.env`만 바꿔 OpenAI / Ollama(자체호스팅) / HuggingFace 전환** (코드 불변).

---

## 멀티 백엔드 (같은 코드, 다른 모델)

| 환경 | 임베딩 | LLM | 설정 |
|------|--------|-----|------|
| 로컬 (1단계) | OpenAI `text-embedding-3-small` | OpenAI `gpt-5-mini` | `.env.example` |
| **GCP VM (2단계, 배포)** | Ollama `bge-m3` | Ollama **`exaone3.5:7.8b`** | `.env.ollama.example` |
| GCP VM (HF직접, 대안) | `bge-m3` (sentence-transformers) | `EXAONE` (transformers) | `.env.hf.example` |

> Ollama는 **OpenAI 호환 API** 라, `provider=openai` + `OPENAI_BASE_URL=http://localhost:11434/v1` 로 기존 코드 재사용.

---

## 웹 기능 (FastAPI API)

| 엔드포인트 | 기능 |
|-----------|------|
| `POST /recommend` | 고객 프로필 → 적합 RFP 추천(재작성+하이브리드+LLM 재랭킹). 적합 공고 없으면 **나라장터 실시간 폴백**(옵트인) |
| `POST /eligibility` | RFP 입찰참가자격 vs **회사 프로필** 대조 → 적격/부적격/확인필요 + 항목별 O/X/? |
| `POST /summarize` | 문서를 **고정 스키마 표**(사업명·예산·기간·자격·평가 등 10항목)로 요약 |
| `POST /ask` | 문서 근거 질의응답(+출처) |
| `GET /documents` | 메타데이터 필터 목록(예산·기관·마감·키워드, LLM 미사용) |

- 프론트(`frontend/`, React): 추천·필터·회사프로필·AI요약(표)·적격성 판정 화면.
- 표시 관련도는 **코사인 유사도(%)** (RRF는 순위용, 절대값이 작아 UI엔 코사인 사용).

## 프로젝트 구조 (상세)

### 설계 한눈에
- **`src/`** = 라이브러리(핵심 로직). **`scripts/`** = 그 라이브러리를 호출하는 실행 진입점(CLI).
- **3단 추상화**가 세 계층(embeddings·llm·vectorstore)에 동일하게 적용됨:
  `base.py`(규격/ABC) + `구현체`(OpenAI/HF) + `__init__.py`(팩토리 `build_*()`).
  → 파이프라인은 규격에만 의존, `.env`로 구현체 교체.
- **RAG 파이프라인**(`src/rag/pipeline.py`)이 임베더·벡터스토어·LLM을 조립해 검색→생성을 오케스트레이션.
- **FastAPI**(`src/api/`)가 그 파이프라인을 HTTP로 노출, **React**(`frontend/`)가 호출.

```
rfp-rag-extractor/
├── src/                          # ── 핵심 라이브러리 ──
│   ├── config.py                 # .env 설정 로더(pydantic-settings): provider·모델·base_url·temperature·nara·top_k…
│   ├── catalog.py                # 문서 메타데이터 카탈로그: load_catalog/filter_docs/get_doc (corpus_clean.csv 기반, LLM 미사용·빠름)
│   ├── nara.py                   # 나라장터(조달청) 입찰공고 검색 API 클라이언트 search_bids (urllib, 폴백용)
│   │
│   ├── dataset_utill/            # ▸ 데이터 파이프라인 (zip → chunks.csv)
│   │   ├── extract.py            #   zip 해제 → data/raw+metadata (cp437→cp949 한글 파일명 복원)
│   │   ├── text_extract.py       #   PDF/HWP 본문 텍스트 추출
│   │   ├── clean.py              #   정제: PUA(U+E000~F8FF)·U+FFFD 등 깨진 문자 제거
│   │   ├── preprocess.py         #   build_corpus: 짧은 문서 원본 재추출 보강 + 정제 → corpus_clean.csv
│   │   ├── chunker.py            #   토큰 기반 청킹(_split_by_tokens, U+FFFD 경계 정제)
│   │   ├── chunk_corpus.py       #   build_chunks: .env(CHUNK_SIZE/OVERLAP) 적용 → chunks.csv
│   │   └── loader.py             #   원문/메타 로더(RawDocument), pypdf 지연 import
│   │
│   ├── embeddings/               # ▸ 임베딩 계층 (3단 추상화)
│   │   ├── base.py               #   BaseEmbedder(ABC): embed_documents/embed_query 규격
│   │   ├── openai_embedder.py    #   OpenAI 호환 구현(base_url로 Ollama bge-m3도 이 클래스로)
│   │   ├── hf_embedder.py        #   sentence-transformers 직접 로딩(대안 경로·현재 배포 미사용)
│   │   └── __init__.py           #   build_embedder() 팩토리
│   │
│   ├── vectorstore/              # ▸ 벡터 저장·검색 계층
│   │   ├── base.py               #   BaseVectorStore(ABC) + RetrievedChunk(text·metadata·score)
│   │   ├── chroma_store.py       #   ChromaDB 어댑터(cosine, distance→similarity 변환)
│   │   └── __init__.py           #   build_vector_store() + collection_name()(임베딩 모델명 접미사로 컬렉션 분리)
│   │
│   ├── llm/                      # ▸ 생성 LLM 계층 (3단 추상화)
│   │   ├── base.py               #   BaseLLM(ABC): generate(system, user) 규격
│   │   ├── openai_llm.py         #   OpenAI 호환 구현(base_url=Ollama로 EXAONE, temperature 옵션)
│   │   ├── hf_llm.py             #   transformers 직접 로딩(대안 경로·현재 배포 미사용)
│   │   └── __init__.py           #   build_llm() 팩토리
│   │
│   ├── rag/                      # ▸ RAG 오케스트레이션 + 도메인 프롬프트
│   │   ├── pipeline.py           #   RAGPipeline: index_chunks/rewrite_query/retrieve/ask/summarize/assess_eligibility + build_pipeline()
│   │   ├── hybrid.py             #   HybridRetriever: BM25(문자 바이그램)+dense를 RRF로 융합, tokenize()
│   │   ├── rerank.py             #   LLM 재랭킹(포함/제외 조건 반영해 후보 재정렬)
│   │   └── prompts.py            #   QA·요약(표)·적격성·질의재작성 프롬프트 + SUMMARY_FIELDS(고정 10항목)
│   │
│   ├── api/                      # ▸ 웹 백엔드
│   │   ├── main.py               #   FastAPI: /health·/documents·/recommend·/eligibility·/ask·/summarize + 파싱·게이트 헬퍼
│   │   └── schemas.py            #   요청/응답 pydantic 모델(DocumentItem·SummaryRow·EligibilityItem…)
│   │
│   └── evaluation/               # ▸ 평가 로직
│       └── evaluator.py          #   EvalItem·load_eval_set + 검색(Hit@k·MRR)·생성(LLM-judge) 지표
│
├── scripts/                      # ── 실행 진입점(CLI) ── (아래 "실행 스크립트" 표)
│   ├── ingest.py  ask.py         #   적재 / 질의응답
│   ├── eval_retrieval.py  eval_generation.py  evaluate.py   #   평가
│   ├── compare_embeddings.py  compare_llms.py  compare_llms_judge.py  #   모델 비교
│   ├── make_goldenset.py  make_content_goldenset.py  exp_chunk_size.py  #   골든셋·실험
│   ├── test_nara.py              #   나라장터 API 단독 테스트
│   └── setup_gcp.sh              #   (참고) VM 셋업 스크립트
│
├── frontend/                     # ── React(Vite) 웹 UI ──
│   ├── src/App.jsx               #   화면: 맞춤추천·필터·회사프로필·AI요약(표)·적격성 판정 (API 주소는 VITE_API)
│   ├── src/App.css  index.css  main.jsx  index.html
│   └── vite.config.js  package.json
│
├── notebooks/                    # 01_eda.ipynb(EDA) · demo.ipynb(VM 내부 라이브 데모)
├── data/                         # raw·metadata·processed(모두 gitignore) + eval/(골든셋 jsonl은 추적)
├── results/                      # 실험 결과(.md): compare_*·eval_*·model_decision·retrieval_experiment
├── docs/                         # architecture·gcp_setup·ollama_setup·presentation
├── tests/                        # test_smoke.py
├── .env.example / .env.ollama.example / .env.hf.example   # 백엔드별 설정 템플릿
├── requirements.txt              # 기본(전체)
├── requirements-run.txt          # 경량(Ollama 경로, torch 불필요)
├── requirements-hf.txt           # HF 직접 로딩(transformers)
└── 진행현황.md                    # 진행 상황 트래커
```

### 요청 한 건이 흐르는 경로 (예: 맞춤추천)
```
[React App.jsx] fetch → [api/main.py /recommend]
   → pipeline.rewrite_query() (프롬프트→LLM)         # 자연어→키워드
   → pipeline.retrieve() = rag/hybrid.py             # bge-m3 dense + BM25 → RRF
   → catalog.get_doc()/filter_docs()                 # 문서 집계·메타필터
   → (적합 없으면) 관련성 게이트 → nara.search_bids() # 폴백
   → rag/rerank.py (LLM 재랭킹)                       # 포함/제외 조건
   → schemas.DocumentList 응답
```

---

## 실행 스크립트

| 명령 | 기능 |
|------|------|
| `python -m src.dataset_utill.extract "<zip>"` | zip → data/raw·metadata |
| `python -m src.dataset_utill.preprocess` | 보강+정제 → corpus_clean.csv |
| `python -m src.dataset_utill.chunk_corpus` | 토큰 청킹 → chunks.csv |
| `python -m scripts.ingest` | 청크 임베딩 → ChromaDB 적재 |
| `python -m scripts.ask "질문"` | 질의응답 (질의재작성+하이브리드) |
| `python -m scripts.eval_retrieval` | 검색 평가 (dense vs hybrid) |
| `python -m scripts.eval_generation [N]` | 생성(답변) 평가 |
| `python -m scripts.compare_embeddings <모델...>` | 임베딩 모델 비교 |
| `python -m scripts.compare_llms <모델...> [N]` | LLM 비교(정확도·응답시간, `openai:` 접두사로 OpenAI 대비) |
| `python -m scripts.compare_llms_judge` | 서술형 답변품질 LLM-judge 교차검증 |
| `python -m scripts.test_nara "<키워드>"` | 나라장터 API 연동 단독 테스트(키 필요) |
| `python -m scripts.make_goldenset` | 메타데이터 골든셋 초안 |
| `python -m scripts.make_content_goldenset` | 내용형 골든셋 초안(LLM) |
| `python -m scripts.exp_chunk_size` | 청크 크기 실험 |
| `uvicorn src.api.main:app` | API 서버 |

---

## 데이터 흐름

```
dataset.zip
  └ extract_dataset()  → data/raw(HWP96+PDF4), data/metadata(data_list.csv)
     └ build_corpus()  → corpus_clean.csv (100, 짧은문서21 원본보강 + 정제)
        └ build_chunks() → chunks.csv (1,106 청크)
           └ index_chunks() → chroma_db (임베딩, 모델별 컬렉션)
              └ ask(): 질의재작성 → 하이브리드검색(BM25+dense, RRF) → LLM → 답변+출처
                 └ eval: 골든셋으로 검색(Hit@k,MRR)·생성 평가 → results/
```

---

## 핵심 설계 메모

- **추상화 3단**: `base.py`(규격) + 구현체(OpenAI/HF) + `__init__.py`(팩토리) → provider 전환.
- **하이브리드 검색**: 자연어 질문의 변별력 저하를 BM25(문자 바이그램)+dense를 RRF로 결합해 해결.
- **질의 재작성**: 질문 → 핵심 키워드로 변환 후 검색.
- **모델별 컬렉션 분리**: 임베딩 차원이 달라(1536/1024/384) `collection_name()`이 모델명을 접미사로 붙여 자동 분리.
- **데이터 보강**: CSV 텍스트가 잘린 문서는 원본(HWP/PDF) 재추출. 청킹 시 PUA·U+FFFD 정제.

---

## 빠른 시작 (로컬, OpenAI)

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # OPENAI_API_KEY 입력

python -m src.dataset_utill.extract "C:/.../dataset (2).zip"
python -m src.dataset_utill.preprocess
python -m src.dataset_utill.chunk_corpus
python -m scripts.ingest
python -m scripts.ask "이 사업의 예산과 마감일은?"
```

## GCP VM (2단계, 자체호스팅)
[docs/ollama_setup.md](docs/ollama_setup.md) 참고 (Ollama 설치 → 모델 pull → `.env.ollama` → 실행).

## 주요 결과
[results/](results/) — 검색평가(hybrid Hit@1 0.94), 청크실험, 임베딩 모델 비교 등.

## 테스트
```bash
pytest
```
자세한 설계: [docs/architecture.md](docs/architecture.md)
