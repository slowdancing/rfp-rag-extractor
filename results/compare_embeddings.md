# 임베딩 모델 비교 (검색 성능)

- 평가셋: `data/eval/eval_set.draft.jsonl` (285건, 메타데이터 기반 골든셋)
- 환경: 로컬 (OpenAI는 API, hf:* 는 sentence-transformers CPU)
- 지표: Hit@1/3/5, MRR (정답 문서 doc_id 기준)

## 결과표

| 모델 | 호스팅 | 방식 | Hit@1 | Hit@3 | Hit@5 | MRR |
|------|--------|------|------:|------:|------:|------:|
| text-embedding-3-small | OpenAI(API) | dense | 0.807 | 0.919 | 0.937 | 0.862 |
| text-embedding-3-small | OpenAI(API) | hybrid | 0.937 | 0.972 | 0.975 | 0.955 |
| BAAI/bge-m3 | 자체(무료) | dense | 0.940 | 0.972 | 0.986 | 0.957 |
| **BAAI/bge-m3** | 자체(무료) | **hybrid** | **0.961** | 1.000 | **1.000** | **0.981** |
| nlpai-lab/KURE-v1 | 자체(무료) | dense | 0.951 | 0.982 | 0.989 | 0.966 |
| **nlpai-lab/KURE-v1** | 자체(무료) | **hybrid** | 0.958 | 1.000 | **1.000** | 0.978 |

> 참고: text-embedding-3-large 는 사용 키 권한(rate limit 0)으로 측정 제외.

## 핵심 발견

1. **한국어 데이터에선 한국어 강한 오픈모델이 OpenAI 범용 임베딩을 능가.**
   - dense 격차 큼: OpenAI 0.807 vs bge-m3 0.940 / KURE 0.951 (+0.13~0.14).
2. **하이브리드(BM25+dense)는 약한 임베딩일수록 효과가 큼.**
   - OpenAI: dense 0.807 → hybrid 0.937 (+0.13 급등, BM25가 보완).
   - bge-m3/KURE: dense가 이미 강해 hybrid 추가 이득은 작음.
3. **자체호스팅(무료)이 품질도 우수.**
   - bge-m3/KURE hybrid 는 Hit@5 = 1.000 (상위 5 안에 항상 정답).

## 결론

> 한국어 RFP 검색은 **OpenAI 범용 임베딩보다 한국어 특화/멀티링구얼 오픈모델(KURE, bge-m3)이 우수**하며
> 자체호스팅이라 **비용 0**. OpenAI 사용 시에는 **하이브리드 검색이 필수**.
> → 시스템 임베딩 기본값으로 **bge-m3(또는 KURE-v1)** 채택 근거.

## 재현
```bash
python -m scripts.compare_embeddings text-embedding-3-small hf:BAAI/bge-m3 hf:nlpai-lab/KURE-v1
```
