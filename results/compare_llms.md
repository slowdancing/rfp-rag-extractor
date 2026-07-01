# LLM 비교 (정확도 + 응답시간)

> 검색·채점 고정, LLM만 교체. 같은 골든셋 30문항(`seed=42`)·같은 채점(`is_correct`).
> 응답시간 = 질문 1건당 `ask()`(질의재작성+검색+생성) 소요, 콜드스타트 1회 워밍업 후 측정(VM/GPU 기준).

- 평가셋: `data/eval/eval_set.draft.jsonl` (표본 30건)
- 검색: 하이브리드(BM25+dense) 고정. **핵심 두 모델(EXAONE·gpt-5-mini)은 임베딩 bge-m3로 동일**.

| LLM | 파라미터 | 검색(임베딩) | 실행 위치 | 정확도 | 정답/전체 | 평균응답 | 중앙응답 |
|------|---:|------|------|------:|------:|------:|------:|
| **exaone3.5:7.8b** ★배포 | 7.8B | bge-m3 | 자체(Ollama) | **0.533** | 16/30 | 3.91s | **3.78s** |
| openai:gpt-5-mini | 비공개 | bge-m3 | OpenAI(클라우드) | 0.533 | 16/30 | 9.96s | 9.81s |
| exaone3.5:2.4b | 2.4B | bge-m3 | 자체(Ollama) | 0.467 | 14/30 | — | — |
| gemma2:2b | 2.0B | bge-m3 | 자체(Ollama) | 0.367 | 11/30 | — | — |
| qwen2.5:3b | 3.0B | bge-m3 | 자체(Ollama) | 0.333 | 10/30 | — | — |

## 핵심

1. **동일 검색(bge-m3)에서 EXAONE-3.5-7.8B와 gpt-5-mini는 정확도 동률(0.533).**
   순수 답변 품질은 대등 → 우열은 속도·비용·보안에서 갈림.
2. **응답속도: EXAONE 3.78s vs gpt-5-mini 9.81s(중앙값) → EXAONE 약 2.6배 빠름.**
   여기에 **무료 + 기밀 RFP 외부 미유출** → **정확도 대등 + 속도·비용·보안 우위**로 자체호스팅 확정.
3. gpt-5-mini를 자기 임베딩(text-embedding-3-small) 풀스택으로 돌리면 0.500으로 하락
   → bge-m3 검색이 더 좋아 gpt-5-mini도 bge-m3에서 0.533으로 오른 것(임베딩 bge-m3 우수성 재확인).
4. **한국어 특화가 파라미터 수보다 결정적**: EXAONE는 경량(2.4B)·풀사이즈(7.8B) 모두 gemma·qwen 계열을 앞섬.
   qwen2.5는 최하위 + 한국어 답변에 중국어 혼입 이슈까지 있어 부적합.

> 주의: 이 평가셋은 날짜 표기 불일치로 deadline 유형이 0점 처리되는 채점 한계가 있어
> 절대 정확도는 낮게 나온다(`eval_generation.md` 참조). **모델 간 상대 순위·응답시간**이 신호.
> (경량 3종은 이번 응답시간 재측정 대상에서 제외 → `—`. 필요시 재실행하면 채워짐.)

## 재현
```bash
# 자체호스팅(Ollama, bge-m3 검색) — VM
python -m scripts.compare_llms exaone3.5:7.8b 30
# OpenAI LLM (bge-m3 검색 유지, LLM만 OpenAI) — VM
OPENAI_CLOUD_KEY=sk-... python -m scripts.compare_llms openai:gpt-5-mini 30
```
