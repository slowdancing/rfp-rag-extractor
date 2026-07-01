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
