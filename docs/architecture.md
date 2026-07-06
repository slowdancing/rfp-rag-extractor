# 아키텍처 개요

## 설계 원칙: 백엔드 교체 가능성(Pluggability)

1단계(OpenAI API) → 2단계(GCP VM + L4 GPU, 자체호스팅)를
**코드 수정 없이 설정(.env)만으로** 전환할 수 있도록, 3개 계층을 추상화했다.

| 계층 | 추상 인터페이스 | 1단계(OpenAI) | 2단계(자체호스팅) |
|------|----------------|-----------|-----------|
| 임베딩 | `BaseEmbedder` | `OpenAIEmbedder` (text-embedding-3-small) | **bge-m3** (Ollama) / `HuggingFaceEmbedder` |
| 생성 LLM | `BaseLLM` | `OpenAILLM` (gpt-5-mini) | **EXAONE-3.5-7.8B** (Ollama) / `HuggingFaceLLM` |
| 벡터 저장소 | `BaseVectorStore` | `ChromaVectorStore` | `ChromaVectorStore` (동일) |

각 계층은 `build_*()` 팩토리가 `Settings` 를 읽어 적절한 구현체를 생성한다.
RAG 파이프라인은 구체 클래스가 아니라 추상 타입에만 의존한다.

> **핵심 트릭 — Ollama = OpenAI 호환 API**: 자체호스팅(2단계)은 HuggingFace/PyTorch를
> 직접 쓰지 않고 **Ollama**로 모델을 서빙한다. Ollama가 OpenAI 호환 엔드포인트를 제공하므로
> `provider=openai` + `base_url=http://localhost:11434/v1` 만 바꾸면 **기존 OpenAI 코드가 그대로** 돈다.
> (torch/transformers 불필요 → 가볍고 파이썬 버전 제약 없음.)

## 모델 확정 (실험 근거 — `results/`)
- **임베딩 = bge-m3**: 한국어 검색에서 OpenAI 임베딩 압도(`compare_embeddings.md`).
- **LLM = EXAONE-3.5-7.8B**: gpt-5-mini와 정확도 동률(0.533)이나 응답 2.6배 빠름, 무료·한국어 특화(`compare_llms.md`, `model_decision.md`).
- **검색 = 하이브리드(BM25+dense, RRF)**: dense 대비 전 지표 우위(`eval_retrieval.md`).

## 데이터 흐름

```
                    [인덱싱 파이프라인]
data/raw/*(HWP/PDF) ─► loader ─► chunker ─► embedder(bge-m3) ─► vector store(Chroma)
data/metadata/*.csv ─┘  (정제·보강)  (토큰청킹)     (배치 임베딩)         │
                                                                        ▼
                    [질의 파이프라인]                                chroma_db/
질문 ─► ① rewrite_query(자연어→키워드)
      ─► ② 하이브리드 검색(BM25 + dense, RRF 융합, top_k, 메타필터)
      ─► ③ (추천 시) LLM 재랭킹(포함/제외 조건 반영)
      ─► context 구성 ─► system+user 프롬프트 ─► LLM(EXAONE) ─► 답변 + 출처
```

## 컴포넌트

- `src/config.py` — `.env`/환경변수 기반 설정 (pydantic-settings, `openai_base_url`로 Ollama 전환)
- `src/dataset_utill/` — zip 추출 + 원본 재추출(HWP/PDF) + 정제 + 토큰 청킹 + 로더
- `src/embeddings/` — 임베딩 추상화 + OpenAI/HF 구현 + 팩토리 (모델별 컬렉션 자동 분리)
- `src/llm/` — 생성 LLM 추상화 + OpenAI 구현(base_url로 Ollama 지원) + 팩토리
- `src/vectorstore/` — 벡터 저장소 추상화 + Chroma 구현 + 팩토리
- `src/rag/` — 오케스트레이션: `pipeline.py`(조립) + `hybrid.py`(BM25+dense RRF) + `rerank.py`(LLM 재랭킹) + 프롬프트
- `src/catalog.py` — 문서 메타데이터 카탈로그(목록·필터·추천용, `corpus_clean.csv` 기반)
- `src/api/` — FastAPI: `/ask` `/summarize` `/recommend`(맞춤추천) `/documents`(메타필터) `/health`
- `src/evaluation/` — 검색(Hit@k, MRR) + 생성(LLM-as-judge / 정답포함) 평가
- `scripts/` — 인덱싱/질의/평가/모델비교 실행 진입점 (`ingest`·`ask`·`eval_*`·`compare_*`)
- `notebooks/demo.ipynb` — VM 내부에서 API(localhost:8500)를 호출하는 라이브 데모

## 평가 전략

- **검색 품질**: 정답 문서 ID 라벨로 Hit@k, MRR 측정 → 청킹/임베딩/검색방식 튜닝 근거 (`eval_retrieval.md`, `compare_embeddings.md`)
- **생성 품질**: 정답 포함 정확도(메타 골든셋) + LLM-as-judge(내용형 골든셋) (`eval_generation.md`)
- **모델 비교**: 임베딩·LLM·응답시간을 바꿔가며 `results/`에 기록 (`compare_embeddings.md`, `compare_llms.md`)

## 2단계 배포: GCP VM + Ollama (실제 적용)

1. VM에 Ollama 설치 후 모델 받기: `ollama pull exaone3.5:7.8b`, `ollama pull bge-m3`
2. `cp .env.ollama.example .env` (LLM=exaone3.5:7.8b, EMBEDDING=bge-m3, base_url=Ollama, RETRIEVAL=hybrid)
3. `ollama serve` 상시구동 → `python -m scripts.ingest` (bge-m3로 벡터 인덱스 생성)
4. `python -m scripts.ask "..."` 로 실동작 확인
5. FastAPI 상시구동: `nohup uvicorn src.api.main:app --host 127.0.0.1 --port 8500 & disown`
6. 시연: (외부 노출 가능 시) SSH 터널/프록시, 아니면 **VM 내부 노트북(`demo.ipynb`)** 으로 라이브 데모

> 상세 배포 가이드·트러블슈팅: `VM_배포_학습정리.md`, `docs/ollama_setup.md`, `docs/gcp_setup.md`
> (대안) HuggingFace 직접 로딩 경로도 유지: `LLM_PROVIDER=huggingface` + CUDA/PyTorch 설치.

---

## 파일별 구조 (상세)

> README에는 요약 트리만 두고, 파일 단위 상세는 여기서 관리한다.

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
│   ├── embeddings/               # ▸ 임베딩 계층 (base.py 규격 + 구현체 + __init__ 팩토리)
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
│   ├── llm/                      # ▸ 생성 LLM 계층
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
├── scripts/                      # ── 실행 진입점(CLI) ──
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
└── requirements-hf.txt           # HF 직접 로딩(transformers)
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
