# 아키텍처 개요

## 설계 원칙: 백엔드 교체 가능성(Pluggability)

1단계(OpenAI API) → 2단계(GCP VM + L4 GPU, HuggingFace 모델) 전환을
**코드 수정 없이 설정(.env)만으로** 할 수 있도록, 3개 계층을 추상화했다.

| 계층 | 추상 인터페이스 | 1단계 구현 | 2단계 구현 |
|------|----------------|-----------|-----------|
| 임베딩 | `BaseEmbedder` | `OpenAIEmbedder` | `HuggingFaceEmbedder` (bge-m3 등) |
| 생성 LLM | `BaseLLM` | `OpenAILLM` | `HuggingFaceLLM` (Qwen 등) |
| 벡터 저장소 | `BaseVectorStore` | `ChromaVectorStore` | (Qdrant 등 추가 가능) |

각 계층은 `build_*()` 팩토리가 `Settings` 를 읽어 적절한 구현체를 생성한다.
RAG 파이프라인은 구체 클래스가 아니라 추상 타입에만 의존한다.

## 데이터 흐름

```
                    [인덱싱 파이프라인]
data/raw/*.pdf ──► loader ──► chunker ──► embedder ──► vector store(Chroma)
data/metadata/*.json ─┘                   (배치 임베딩)        │
                                                              ▼
                    [질의 파이프라인]                     chroma_db/
질문 ──► embed_query ──► vector search(top_k, 메타필터) ──► context 구성
                                                              │
                                          ┌───────────────────┘
                                          ▼
                          system+user 프롬프트 ──► LLM ──► 답변 + 출처
```

## 컴포넌트

- `src/config.py` — `.env`/환경변수 기반 설정 (pydantic-settings)
- `src/dataset_utill/` — zip 추출 + 원본 재추출(HWP/PDF) + 정제 + 토큰 청킹 + 로더
- `src/embeddings/` — 임베딩 추상화 + OpenAI/HF 구현 + 팩토리
- `src/llm/` — 생성 LLM 추상화 + OpenAI/HF 구현 + 팩토리
- `src/vectorstore/` — 벡터 저장소 추상화 + Chroma 구현 + 팩토리
- `src/rag/` — 검색→프롬프트→생성 오케스트레이션, RFP 도메인 프롬프트
- `src/api/` — FastAPI 엔드포인트 (`/ask`, `/summarize`, `/health`)
- `src/evaluation/` — 검색(Hit@k, MRR) + 생성(LLM-as-judge) 평가
- `scripts/` — 인덱싱/질의/평가 실행 진입점

## 평가 전략 (팀이 확장)

- **검색 품질**: 정답 문서 ID 라벨로 Hit@k, MRR 측정 → 청킹/임베딩/top_k 튜닝 근거
- **생성 품질**: LLM-as-judge(0~5점), 필요시 ROUGE/사람 평가 추가
- **실험 비교**: 청크 크기, overlap, 임베딩 모델, top_k 를 바꿔가며 결과를 `results/` 에 기록

## 2단계: GCP VM 전환 체크리스트

1. VM(L4 GPU)에 CUDA + PyTorch 설치
2. `requirements.txt` 의 HuggingFace 섹션 주석 해제 후 설치
3. `.env` 에서 `LLM_PROVIDER=huggingface`, `EMBEDDING_PROVIDER=huggingface` 설정
4. 임베딩 모델이 바뀌므로 **벡터 인덱스 재생성 필요** (`python -m scripts.ingest`)
5. (선택) Chroma → Qdrant 로 교체 시 `BaseVectorStore` 구현 추가
