# LLM 비교 (답변 정답 포함 정확도)

> 검색·채점 고정, LLM만 교체. 같은 골든셋 30문항(`seed=42`)·같은 채점(`is_correct`).
> 정확도 높은 순. 원장: `compare_llms.json`.

- 평가셋: `data/eval/eval_set.draft.jsonl` (표본 30건)
- 검색: 하이브리드(BM25+dense) 고정. 자체호스팅 계열은 임베딩 **bge-m3**, OpenAI 계열은 **text-embedding-3-small**.

| LLM | 파라미터 | 검색(임베딩) | 실행 위치 | 정확도 | 정답/전체 |
|------|---:|------|------|------:|------:|
| **exaone3.5:7.8b** ★배포 | 7.8B | bge-m3 | 자체(Ollama) | **0.533** | 16/30 |
| gpt-5-mini | (비공개) | text-embedding-3-small | OpenAI(클라우드) | 0.500 | 15/30 |
| exaone3.5:2.4b | 2.4B | bge-m3 | 자체(Ollama) | 0.467 | 14/30 |
| gemma2:2b | 2.0B | bge-m3 | 자체(Ollama) | 0.367 | 11/30 |
| qwen2.5:3b | 3.0B | bge-m3 | 자체(Ollama) | 0.333 | 10/30 |

## 핵심

1. **자체호스팅 EXAONE-3.5-7.8B(0.533)가 OpenAI gpt-5-mini(0.500)를 앞섬.**
   - EXAONE는 더 강한 검색(bge-m3) 위에서, OpenAI는 자기 임베딩(상대적으로 약함, `compare_embeddings.md`) 위에서 측정.
   - 즉 **성능(정확도)·비용(무료)·기밀보호(외부 미유출) 모든 축에서 자체호스팅 우위.**
2. **한국어 특화가 파라미터 수보다 결정적**: EXAONE는 경량(2.4B)·풀사이즈(7.8B) 모두 gemma·qwen 계열을 앞섬.
3. qwen2.5는 최하위 + 한국어 답변에 중국어 혼입 이슈까지 있어 부적합.

> 주의: 이 평가셋은 날짜 표기 불일치로 deadline 유형이 0점 처리되는 채점 한계가 있어
> 절대 정확도는 낮게 나온다(`eval_generation.md` 참조). **모델 간 상대 순위**가 신호.

## 재현
```bash
# 자체호스팅(Ollama, bge-m3 검색) — VM
python -m scripts.compare_llms exaone3.5:7.8b 30
# OpenAI 클라우드 LLM — .env가 OpenAI 스택이면 그대로, 아니면 openai: 접두사
python -m scripts.compare_llms gpt-5-mini 30
#   (bge-m3 검색 유지한 채 LLM만 OpenAI로: OPENAI_CLOUD_KEY=sk-... python -m scripts.compare_llms openai:gpt-5-mini 30)
```
