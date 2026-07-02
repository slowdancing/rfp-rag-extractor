# 내용형 답변 품질 비교 (LLM-judge 교차검증)

metadata 골든셋의 '정답 포함(문자열 매칭)'으로는 서술형 답변을 평가할 수 없어,
**내용형 골든셋(서술형 59건)** 에 대해 각 후보 LLM의 답변을 **두 심판 LLM이
정답(gold) 대조로 0~5점 채점**한 교차검증 결과.

- 골든셋: `data/eval/eval_set.content.jsonl` (59건, 문서 원문 근거 서술형 — 직접 작성 49 + LLM초안 10)
- 검색: **bge-m3 하이브리드 고정** → 후보 LLM만 변수 (공정 비교)
- 실험 환경: GCP VM (GPU NVIDIA L4, vCPU 4/물리 2코어, RAM 16GB). EXAONE는 Ollama, gpt-5-mini는 OpenAI 클라우드.
- 심판(judge): EXAONE-3.5-7.8B, gpt-5-mini (둘 다 대결 당사자 → 교차검증)

## 결과

| 후보 LLM | EXAONE 심판 | gpt-5-mini 심판 | 평균 |
|------|------:|------:|------:|
| **exaone3.5:7.8b** | 4.42 (n=59) | **4.31** (n=59) | **4.37** |
| gpt-5-mini | 4.25 (n=59) | 4.14 (n=59) | 4.20 |

## 핵심

1. **두 심판 모두 EXAONE 답변을 더 높게 평가** (교차검증 일치) → EXAONE ≈ +0.17 우위.
2. **상대 심판(gpt-5-mini)조차 EXAONE(4.31) > 자기 자신(4.14)** 으로 채점.
   → "자기편향이라 EXAONE가 이겼다"는 반박을 차단. **가장 신뢰할 만한 신호.**
3. 즉 **한국어 서술형 RFP 답변 품질에서 EXAONE-3.5-7.8B가 gpt-5-mini보다 우수.**
   검색(bge-m3) 동일 + 무료 + 기밀보호까지 → **자체호스팅 채택 재확인.**

> 방법론 메모: 심판이 대결 당사자이므로 자기편향 가능성이 있으나, ① 정답 대조(reference-based)
> 채점이라 선호 편향이 제한되고 ② 두 심판(특히 상대 심판)이 같은 방향으로 EXAONE를 높게 줘
> 견고성이 확보됨. 자기 심판 점수(EXAONE→EXAONE 4.42)는 참고로만.

## 앞선 정확도 실험과의 관계
- 정답 '추출' 정확도(metadata 골든셋, 문자열 매칭): EXAONE ≈ gpt-5-mini **동률**(0.533, `compare_llms.md`).
- 서술형 '답변 품질'(내용형 골든셋, LLM-judge): **EXAONE 우세**(4.37 vs 4.20, 본 문서).
- 응답속도: EXAONE가 gpt-5-mini보다 약 2.6배 빠름(`compare_llms.md`).
- → 종합: **정확도 대등~우세 + 속도·비용·보안 우위** → EXAONE 자체호스팅 채택 정당.

## 재현
```bash
# 검색 bge-m3 고정, 후보·심판 모두 EXAONE + gpt-5-mini
OPENAI_CLOUD_KEY=sk-... python -m scripts.compare_llms_judge
```
