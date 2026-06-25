# 검색 평가 결과 (dense vs 하이브리드)

- 평가셋: `data/eval/eval_set.draft.jsonl` (285건, doc_id 라벨 기준)
- 임베딩: openai / text-embedding-3-small

| 방식 | Hit@1 | Hit@3 | Hit@5 | MRR |
|------|------:|------:|------:|------:|
| dense  | 0.807 | 0.916 | 0.937 | 0.861 |
| hybrid | 0.933 | 0.972 | 0.975 | 0.953 |
