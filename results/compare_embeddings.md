# 임베딩 모델 비교 (검색 성능)

- 평가셋: `data/eval/eval_set.draft.jsonl` (285건)
- base_url: OpenAI

| 모델 | 방식 | Hit@1 | Hit@3 | Hit@5 | MRR |
|------|------|------:|------:|------:|------:|
| text-embedding-3-small | dense | 0.807 | 0.923 | 0.940 | 0.863 |
| text-embedding-3-small | hybrid | 0.940 | 0.975 | 0.979 | 0.958 |