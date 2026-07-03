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

## 5. 실험 결과

**① 검색 방식 (dense vs 하이브리드, 골든셋 285건)**

| 방식 | Hit@1 | Hit@5 | MRR |
|------|------:|------:|------:|
| dense | 0.807 | 0.937 | 0.861 |
| **hybrid** | **0.933** | **0.975** | **0.953** |

→ 하이브리드(BM25+dense)가 전 지표 우위. (자연어 질문: 실패 14위밖 → 1위)

**② 임베딩 모델 비교 (한국어 RFP, 검색 성능)**

| 모델 | 호스팅 | hybrid Hit@1 | MRR |
|------|--------|------:|------:|
| text-embedding-3-small | OpenAI(API) | 0.937 | 0.955 |
| **BAAI/bge-m3** | 자체(무료) | **0.961** | **0.981** |
| nlpai-lab/KURE-v1 | 자체(무료) | 0.958 | 0.978 |

→ 한국어 데이터에선 **한국어 강한 오픈모델(bge-m3·KURE)이 OpenAI 범용 임베딩을 능가**(dense 격차 +0.13). 무료·자체호스팅인데 품질도 우수.

**③ LLM 비교 — EXAONE vs OpenAI (검색 bge-m3 고정, 상세: `results/compare_llms.md`·`compare_llms_judge.md`)**

| 항목 | EXAONE-3.5-7.8B(자체) | gpt-5-mini(OpenAI) |
|------|:---:|:---:|
| 추출 정확도(30건) | 0.533 | 0.533 (동률) |
| 서술형 답변품질(59건, LLM-judge 교차) | **4.37** | 4.20 |
| 응답속도(중앙값) | **3.78s** | 9.81s |

- 답변품질 교차검증: **두 심판(EXAONE·gpt) 모두 EXAONE를 높게** 평가. 상대 심판 gpt조차 EXAONE(4.31)>자기(4.14) → 자기편향 아님.
- Qwen2.5는 최하위 + 한국어 답변에 중국어 혼입 → 부적합. 경량·풀사이즈 모두 EXAONE가 타 계열 앞섬(한국어 특화가 결정적).

**④ 종합**: **정확도 대등 + 서술형 품질·속도(2.6배)·비용(무료)·기밀보호 전 축에서 자체호스팅 EXAONE 우위.**

---

## 5-1. 최종 채택 (실험 근거 기반)

| 구분 | 채택 | 이유 |
|------|------|------|
| **임베딩** | **bge-m3** | 한국어 검색 우수(OpenAI 압도), 무료·범용(Ollama·HF) |
| **LLM** | **EXAONE-3.5-7.8B** | gpt-5-mini와 정확도 동률·서술형 품질 우세(4.37>4.20)·응답 2.6배 빠름·무료·한국어 특화 |
| **검색** | **하이브리드(BM25+dense, RRF)** | 전 지표 우위, 자연어 질문 해결 |
| **호스팅** | 자체호스팅(Ollama, GPU) | 무료·기밀보호 (개발·데모는 OpenAI 잠정 가능) |

> 한 줄: **bge-m3 + EXAONE + 하이브리드 검색**, Ollama 자체호스팅.
> 코드는 `.env`로 전환되므로 모델 교체 시 코드 변경 없음.

---

## 6. 2단계: 자체 호스팅 (GCP + Ollama)

- **1단계**: OpenAI API (text-embedding-3-small / gpt-5-mini)
- **2단계**: GCP VM(L4 GPU) + **Ollama** 로 자체 호스팅 (bge-m3 / **exaone3.5:7.8b**)
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

## 8. GUI 구현 (FastAPI + React) ✅

CLI → **웹 UI(FastAPI 백엔드 + React 프론트)** 로 구현 완료.

```
[React 프론트 :5173]
   │ 고객 역량 입력 / 필터 / AI요약 버튼
   ▼ (fetch, CORS)
[FastAPI 백엔드 — src/api]
   │ /recommend  /documents  /summarize  /ask
   ▼
[RAG 파이프라인] → [ChromaDB + Ollama(EXAONE·bge-m3)]
```

**구현된 화면 (`frontend/`)**
- **맞춤 추천**: 고객사 역량 입력 → 적합 RFP 목록(관련도순) — `/recommend`(임베딩)
- **필터 목록**: 예산·발주기관·마감일·키워드 필터 — `/documents`(메타데이터, LLM 미사용·빠름)
- **AI 요약 (온디맨드)**: 관심 문서의 [📄 AI 요약] 버튼 → 그 문서만 요약 생성 — `/summarize`

**설계 포인트**: 목록·필터는 빠르게(LLM 거의 없음), **AI 요약은 버튼 누를 때만** 생성 → 비용·속도 효율.

**실행**: `uvicorn src.api.main:app` + `cd frontend && npm run dev` → http://localhost:5173

**배포 ✅ (자체호스팅 실동작 확인)**
- GCP VM에서 **EXAONE + bge-m3 + FastAPI 상시구동**, GCP 방화벽으로 API 포트 개방(내 IP 한정).
- **로컬 브라우저(React) → VM의 EXAONE 서비스** 호출 성공 → 실제 자체호스팅 서비스 시연 완료.
- 웹전용·무sudo 환경 대응 노트북 데모(`notebooks/demo.ipynb`)도 준비. 상세: `VM_배포_학습정리.md`.

---

## 9. 결론

- 복잡한 RFP에 대해 **추출·정제·청킹 → 하이브리드 검색 → LLM 답변** 파이프라인 완성.
- **추상화 설계**로 OpenAI ↔ 자체호스팅(GCP/Ollama)을 코드 변경 없이 전환·비교.
- **정량 평가(골든셋)** 로 의사결정을 근거화.
- 다음: 모델 비교 마무리 → 리랭킹·추천 등 고도화 → **GUI 서비스화**.