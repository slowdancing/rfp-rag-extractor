

# 입찰메이트 RFP RAG Extractor

복잡한 정부·기업 **제안요청서(RFP)** 에서 핵심을 **추출·요약·질의응답**하고, 고객사에 맞는 공고를
**추천**하며 **입찰 적격성**까지 판정하는 RAG 웹 서비스.

> B2G 입찰지원 컨설팅 '입찰메이트' 컨설턴트가, 나라장터에 쏟아지는 수십 페이지 RFP를
> 일일이 읽지 않고 **요구조건·발주기관·예산·자격**을 빠르게 파악하도록 돕는다.

> 📄 **[개발 보고서 (PDF) 다운로드](docs/개발보고서.pdf)** — 전체 개발 과정 · 실험 결과 · 트러블슈팅 · 의사결정을 한눈에 종합.

---

## 🖥️ 실행 화면

<table>
  <tr>
    <td align="center"><b>초기 실행 화면</b></td>
    <td align="center"><b>AI 요약 결과 (10항목 표)</b></td>
  </tr>
  <tr>
    <td><img width="1054" height="783" alt="초기 실행화면" src="https://github.com/user-attachments/assets/5617f8af-4c47-4913-b2ac-c8cecaac8c35" /></td>
    <td><img width="1076" height="827" alt="요약본 자료" src="https://github.com/user-attachments/assets/abd46ed1-07c4-4110-b86b-f7f9425bf2ad" /></td>
  </tr>
</table>

---

## 핵심 기능

- **맞춤 추천** — 고객사 역량(자연어)으로 적합 RFP 추천. 로컬에 없으면 **나라장터 실시간 검색**(옵트인).
- **AI 요약** — 문서를 **고정 10항목 표**(사업명·예산·기간·자격·평가…)로 정리해 문서 간 비교 용이.
- **적격성 판정** — RFP 참가자격 vs 회사 프로필 대조 → **적격/부적격/확인필요** + 항목별 근거. 판정 정확도를 위해 이 기능만 **gpt-5-mini 라우팅**(옵트인, 키 없으면 EXAONE 폴백).
- **질의응답** — 문서 근거 기반 답변 + 출처.
- **임시저장·내보내기** — 관심 문서를 담아 문서별 선택 항목만 **엑셀(CSV)로 내보내기**.
- **자체호스팅** — bge-m3 + EXAONE-3.5-7.8B를 GCP VM에서 무료로 운영(OpenAI 대비 검증 완료).

---

## 빠른 시작

### A. 웹 서비스 (FastAPI + React)
```bash
# 1) 백엔드 (프로젝트 루트, .env 준비 후)
pip install -r requirements.txt
cp .env.example .env                 # OPENAI_API_KEY 입력 (또는 .env.ollama.example = 자체호스팅)
uvicorn src.api.main:app --port 8000

# 2) 프론트 (다른 터미널)
npm --prefix frontend install
npm --prefix frontend run dev        # http://localhost:5173
#    백엔드가 다른 곳이면:  VITE_API=http://<host>:<port> npm --prefix frontend run dev
```

### B. CLI (데이터 준비 → 질의)
```bash
python -m src.dataset_utill.extract "<dataset.zip>"   # zip → data/raw·metadata
python -m src.dataset_utill.preprocess                # 보강+정제 → corpus_clean.csv
python -m src.dataset_utill.chunk_corpus              # 청킹 → chunks.csv
python -m scripts.ingest                              # 임베딩 → ChromaDB
python -m scripts.ask "이 사업의 예산과 마감일은?"
```

**자체호스팅(GCP VM + Ollama)**: [docs/ollama_setup.md](docs/ollama_setup.md) 참고.

---

## 확정된 기술

| 구분 | 채택 | 근거 |
|------|------|------|
| 임베딩 | **bge-m3** | 한국어 검색에서 OpenAI 임베딩 능가 → [`results/compare_embeddings.md`](results/compare_embeddings.md) |
| LLM | **EXAONE-3.5-7.8B** | gpt-5-mini와 정확도 동률, 서술형 품질 우세(4.37 vs 4.20), 응답 2.6배 빠름 → [`results/model_decision.md`](results/model_decision.md) |
| 검색 | **하이브리드**(BM25+dense, RRF) | dense 대비 전 지표 우위 → [`results/eval_retrieval.md`](results/eval_retrieval.md) |
| 호스팅 | 자체호스팅(Ollama, GPU) | 무료·기밀보호 |

**핵심 설계**: 임베딩·LLM·벡터스토어를 추상화 → **`.env`만 바꿔 OpenAI ↔ Ollama(자체호스팅) ↔ HuggingFace 전환**(코드 불변).

| 환경 | 임베딩 | LLM | 설정 |
|------|--------|-----|------|
| 로컬(1단계) | OpenAI text-embedding-3-small | OpenAI gpt-5-mini | `.env.example` |
| **VM(2단계·배포)** | Ollama bge-m3 | Ollama **exaone3.5:7.8b** | `.env.ollama.example` |
| VM(HF 대안) | sentence-transformers | transformers | `.env.hf.example` |

> Ollama가 **OpenAI 호환 API** 라 `provider=openai` + `OPENAI_BASE_URL`만 바꾸면 기존 코드 그대로 EXAONE 사용.

---

## 웹 API

| 엔드포인트 | 기능 |
|-----------|------|
| `POST /recommend` | 프로필(자연어) → 적합 RFP 추천. 적합 없으면 나라장터 폴백(옵트인) |
| `POST /summarize` | 고정 10항목 표 요약 |
| `POST /eligibility` | 회사 프로필 vs RFP 자격 → 적격성 판정(O/X/?) |
| `POST /ask` | 문서 근거 질의응답(+출처) |
| `GET /documents` | 메타데이터 필터 목록(LLM 미사용) |

---

## 프로젝트 구조 (요약)

```
src/          핵심 라이브러리
  config.py · catalog.py · nara.py       설정 · 메타카탈로그 · 나라장터 클라이언트
  dataset_utill/   데이터 파이프라인(추출→정제→청킹)
  embeddings/ · vectorstore/ · llm/      각 계층 = base(규격)+구현체+__init__(팩토리)
  rag/         pipeline(조립) · hybrid(BM25+dense) · rerank · prompts
  api/         FastAPI(main·schemas)
  evaluation/  Hit@k·MRR·LLM-judge
scripts/      실행 진입점(ingest·ask·eval_*·compare_*·test_nara)
frontend/     React(Vite) 웹 UI
data/ results/ docs/ notebooks/ tests/
```
> **파일별 상세 구조 + 요청 흐름**: [docs/architecture.md](docs/architecture.md)

### 실행 스크립트 (주요)
| 명령 | 기능 |
|------|------|
| `python -m scripts.ingest` | 청크 임베딩 → ChromaDB |
| `python -m scripts.ask "질문"` | 질의응답 |
| `python -m scripts.eval_retrieval` / `eval_generation` | 검색/생성 평가 |
| `python -m scripts.compare_llms <모델...> [N]` | LLM 비교(`openai:` 접두사로 OpenAI 대비) |
| `python -m scripts.compare_llms_judge` | 서술형 답변품질 LLM-judge 교차검증 |
| `uvicorn src.api.main:app` | API 서버 |

---

## 설정 · 테스트 · 문서

- **설정**: `.env`(provider·모델·`OPENAI_BASE_URL`·`OPENAI_TEMPERATURE`·`NARA_*` 등) — 템플릿 3종 참고.
- **테스트**: `pytest`
- **문서**:
  - [docs/architecture.md](docs/architecture.md) — 설계·파일별 구조·데이터 흐름
  - [docs/ollama_setup.md](docs/ollama_setup.md) · [docs/gcp_setup.md](docs/gcp_setup.md) — 자체호스팅
  - 📄 [docs/개발보고서.pdf](docs/개발보고서.pdf) — **개발 결과 보고서(PDF)**: 과정·실험·트러블슈팅·의사결정 종합
  - [results/](results/) — 실험 결과(모델 비교·평가)
  - [진행현황.md](진행현황.md) — 진행 상황

---

## 🗒️ 협업일지

일자별 개발 협업일지
김건오 : **[열기](https://app.notion.com/p/38345e309755802b8911f6cd786b4866)**
하태진 : **[열기]([https://app.notion.com/p/38345e309755802b8911f6cd786b4866](https://excessive-delphinium-9d2.notion.site/AI-3972deb5db81808284b3f94f34009c52?source=copy_link))**
