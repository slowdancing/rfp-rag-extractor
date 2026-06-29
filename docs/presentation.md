# 입찰메이트 RFP RAG — 발표 자료

> 복잡한 RFP(제안요청서)에서 핵심 정보를 추출·요약·질의응답하는 사내 RAG 시스템
> 4팀 · B2G 입찰지원 컨설팅 '입찰메이트' 엔지니어링

---

## 1. 문제 정의

- 나라장터 등에 **하루 수백 건 RFP**(한 건당 수십 페이지)가 올라옴.
- 컨설턴트가 일일이 읽기 불가 → **요구조건·발주기관·예산·제출방식** 핵심만 빠르게 파악 필요.
- 목표: **RFP 100건 기반 Q&A·요약 RAG 시스템** 구축 + 모델 실험·평가.

---

## 2. 작업 폴더 구조

```
rfp-rag-extractor/
├── src/                      # 핵심 로직 (라이브러리)
│   ├── config.py             #  .env 설정 로더 (provider·모델·base_url)
│   ├── dataset_utill/        #  데이터 파이프라인 (추출·정제·청킹·로더)
│   ├── embeddings/           #  임베딩 추상화 + OpenAI/HF 구현 + 팩토리
│   ├── vectorstore/          #  벡터 저장·검색 (Chroma, 모델별 컬렉션 분리)
│   ├── llm/                  #  LLM 추상화 + OpenAI/HF 구현 (base_url=Ollama 지원)
│   ├── rag/                  #  pipeline(조립) + hybrid(BM25+dense) + prompts
│   ├── api/                  #  FastAPI 엔드포인트
│   └── evaluation/           #  검색/생성 평가 로직
├── scripts/                  # 실행 진입점 (ingest·ask·eval·compare 등)
├── data/                     # raw·metadata·processed (gitignore) + eval(골든셋)
├── results/                  # 실험 결과(.md)
└── docs/                     # architecture·gcp_setup·ollama_setup·presentation
```

**설계 핵심 — 3단 추상화**: 각 계층이 `base.py(규격) + 구현체(OpenAI/HF) + __init__.py(팩토리)`
→ **`.env`만 바꿔 OpenAI / HuggingFace / Ollama 전환** (코드 불변).

---

## 3. 실행 파이프라인

```
dataset.zip
  │ extract_dataset()         zip → data/raw(HWP96+PDF4), data/metadata(CSV)
  ▼
원본 + 메타데이터
  │ build_corpus()            짧은문서 21건 원본 재추출 보강 + 정제(PUA·공백)
  ▼
corpus_clean.csv (100행)
  │ build_chunks()            토큰 청킹(1000/overlap150)
  ▼
chunks.csv (1,106 청크)
  │ index_chunks()            임베딩 → ChromaDB (모델별 컬렉션)
  ▼
ChromaDB (벡터 + 텍스트 + 메타데이터)
  │ ask()
  │   ① rewrite_query()       자연어 질문 → 핵심 키워드
  │   ② retrieve()            하이브리드 검색 (BM25 + dense, RRF)
  │   ③ prompts + LLM         근거 기반 답변 생성
  ▼
답변 + 출처
  │ eval                      골든셋으로 검색(Hit@k·MRR)·생성 평가
  ▼
results/
```

---

## 4. 핵심 의사결정 (실험으로 검증)

| 이슈 | 의사결정 | 근거 |
|------|---------|------|
| HWP 96% | CSV에 추출 텍스트 존재 → CSV 기반 + 짧은 문서만 원본 재추출 보강 | 89자→2만자 복원 |
| 청크 크기 | 1000 토큰 유지 | 실험: 256~1024 비슷, 1024 근소 우위 |
| 검색 실패(자연어 질문) | **원인=질의 표현**(청크 아님) → 질의재작성 + 하이브리드 | 실패 질의 14위 밖 → 1위 |
| 평가 | 골든셋(메타데이터 + 내용형) + Hit@k/MRR/정답포함 | 정량 비교 가능 |

---

## 5. 실험 결과 (요약)

**검색 (dense vs 하이브리드, 골든셋 285건)**

| 방식 | Hit@1 | Hit@5 | MRR |
|------|------:|------:|------:|
| dense | 0.807 | 0.937 | 0.861 |
| **hybrid** | **0.933** | **0.975** | **0.953** |

→ 하이브리드(BM25+dense)가 전 지표 우위. *(상세: `results/`)*

**모델/환경 비교 축** (진행 중)
- 임베딩: bge-m3(multilingual) vs 영어중심(nomic 등) → `compare_embeddings`
- LLM: qwen2.5 vs EXAONE(한국어 특화) vs gemma2 → `compare_llms`
- **API(OpenAI) vs 자체호스팅(Ollama, GCP L4 GPU)**

---

## 6. 2단계: 자체 호스팅 (GCP + Ollama)

- **1단계**: OpenAI API (text-embedding-3-small / gpt-5-mini)
- **2단계**: GCP VM(L4 GPU) + **Ollama** 로 자체 호스팅 (bge-m3 / qwen2.5)
- Ollama가 **OpenAI 호환 API** 제공 → `provider=openai` + `base_url`만 바꿔 **코드 0줄 수정**으로 전환.
- 의미: 외부 API 의존 제거 · 데이터 외부 미유출(기밀 RFP) · 대량 처리 비용 통제.

---

## 7. 앞으로의 고도화 전략

### 7-1. 검색 품질
- **리랭킹(reranker)** 도입: 1차 검색 결과를 cross-encoder로 재정렬 → 정밀도↑
- **메타데이터 필터 검색**: "예산 N억 이상 / 특정 발주기관 / 마감 임박" 등 조건 결합
- **한국어 특화 임베딩**(KURE 등) 비교·채택

### 7-2. 답변 품질
- **출처 하이라이트**: 답변 근거 문장을 원문에서 강조 표시
- **구조화 출력**: 요약을 표준 항목(사업명·예산·자격·평가방식)으로 고정 포맷
- **환각 억제 강화** + 인용 정확도 평가(LLM-judge 정식 도입)

### 7-3. 데이터·운영
- **신규 RFP 자동 수집**(나라장터 연계) → 자동 인덱싱 파이프라인
- **HWP 원본 파싱 고도화**(표·이미지 OCR 포함)
- 평가셋(골든셋) 확대 + 정기 회귀 평가

### 7-4. 비즈니스 기능
- **고객사 맞춤 추천**: 고객 프로필 ↔ RFP 매칭 점수 → 입찰 기회 추천
- 알림(마감 임박·신규 적합 공고)

---

## 8. GUI 구현 계획 (예정)

현재는 CLI/스크립트 기반 → **컨설턴트가 쓰는 웹 UI** 로 확장 예정.

```
[웹 브라우저 UI]
   │ 질문 입력 / 문서 선택 / 필터
   ▼
[FastAPI 백엔드 (src/api)]
   │ /ask  /summarize  /search
   ▼
[RAG 파이프라인] → [ChromaDB + Ollama/OpenAI]
```

- **백엔드**: 이미 있는 `src/api`(FastAPI) 활용 — `/ask`, `/summarize` 엔드포인트.
- **프론트엔드**: 1차로 **Streamlit/Gradio**(빠른 데모) → 이후 **React** 등 정식 UI.
- 주요 화면(안):
  - **검색·질의 화면**: 자연어 질문 → 답변 + 근거 출처 표시
  - **문서 요약 카드**: 사업명·발주기관·예산·마감일·요구사항 한눈에
  - **필터/대시보드**: 예산·기관·마감일 기준 정렬·필터, 추천 목록
- 배포: GCP VM의 FastAPI + UI를 외부 접속(인증/방화벽) 또는 사내망.

---

## 9. 결론

- 복잡한 RFP에 대해 **추출·정제·청킹 → 하이브리드 검색 → LLM 답변** 파이프라인 완성.
- **추상화 설계**로 OpenAI ↔ 자체호스팅(GCP/Ollama)을 코드 변경 없이 전환·비교.
- **정량 평가(골든셋)** 로 의사결정을 근거화.
- 다음: 모델 비교 마무리 → 리랭킹·추천 등 고도화 → **GUI 서비스화**.