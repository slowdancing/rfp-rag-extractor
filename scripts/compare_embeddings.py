"""여러 임베딩 모델의 검색 성능을 한 번에 비교한다.

각 모델마다: chunks.csv 임베딩 → 모델 전용 컬렉션 적재(이미 있으면 재사용) →
골든셋으로 Hit@1/3/5·MRR 측정 (dense / hybrid) → 비교표 저장.

사전 준비(Ollama 경로): 비교할 모델을 먼저 받아둘 것
  ollama pull bge-m3
  ollama pull nomic-embed-text
  ollama pull mxbai-embed-large

실행:
  python -m scripts.compare_embeddings bge-m3 nomic-embed-text mxbai-embed-large
출력: results/compare_embeddings.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import chromadb
import pandas as pd

from src.config import get_settings
from src.embeddings.openai_embedder import OpenAIEmbedder
from src.rag.hybrid import HybridRetriever, tokenize
from src.evaluation import load_eval_set

KS = (1, 3, 5)
CAND = 50


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-")


def _meta(row, cols):
    out = {}
    for c in cols:
        v = row[c]
        out[c] = "" if pd.isna(v) else (v if isinstance(v, (int, float, bool, str)) else str(v))
    return out


def _index(embedder, coll, df):
    """chunks 를 embedder 로 임베딩해 컬렉션에 적재 (배치)."""
    meta_cols = [c for c in df.columns if c != "text"]
    texts = df["text"].astype(str).tolist()
    ids = df["chunk_id"].astype(str).tolist()
    metas = [_meta(r, meta_cols) for _, r in df.iterrows()]
    B = 100
    for i in range(0, len(texts), B):
        embs = embedder.embed_documents(texts[i:i + B])
        coll.add(ids=ids[i:i + B], embeddings=embs,
                 documents=texts[i:i + B], metadatas=metas[i:i + B])


def _doc_ranks(items_meta):
    docs = []
    for m in items_meta:
        d = m.get("doc_id")
        if d not in docs:
            docs.append(d)
    return docs


def _evaluate(retrieve_fn, items):
    m = {f"hit@{k}": 0 for k in KS}
    m["mrr"] = 0.0
    n = 0
    for it in items:
        if not it.doc_id:
            continue
        n += 1
        docs = retrieve_fn(it.question)
        if it.doc_id in docs:
            rank = docs.index(it.doc_id) + 1
            m["mrr"] += 1.0 / rank
            for k in KS:
                if rank <= k:
                    m[f"hit@{k}"] += 1
    return {k: (v / n if n else 0) for k, v in m.items()}


def main() -> None:
    models = sys.argv[1:] or ["bge-m3"]
    s = get_settings()
    df = pd.read_csv(s.chunks_path)
    eval_path = "data/eval/eval_set.jsonl"
    if not Path(eval_path).exists():
        eval_path = "data/eval/eval_set.draft.jsonl"
    items = load_eval_set(eval_path)
    client = chromadb.PersistentClient(path=s.chroma_persist_dir)

    rows = []
    for model in models:
        print(f"\n=== {model} ===")
        embedder = OpenAIEmbedder(api_key=s.openai_api_key or "x",
                                  model=model, base_url=s.openai_base_url)
        cname = f"cmp_{_sanitize(model)}"
        coll = client.get_or_create_collection(cname, metadata={"hnsw:space": "cosine"})
        if coll.count() == 0:
            print(f"  임베딩·적재 중... ({len(df)} 청크)")
            _index(embedder, coll, df)
        else:
            print(f"  기존 컬렉션 재사용 ({coll.count()} 청크)")

        # dense
        def dense_docs(q, _coll=coll, _emb=embedder):
            r = _coll.query(query_embeddings=[_emb.embed_query(q)], n_results=max(KS))
            return _doc_ranks(r["metadatas"][0])
        dense = _evaluate(dense_docs, items)

        # hybrid (BM25 + 이 임베딩)
        hy = HybridRetriever(embedder, _StoreShim(coll), s.chunks_path, candidates=CAND)
        def hybrid_docs(q, _hy=hy):
            return _doc_ranks([c.metadata for c in _hy.retrieve(q, top_k=max(KS))])
        hybrid = _evaluate(hybrid_docs, items)

        rows.append((model, "dense", dense))
        rows.append((model, "hybrid", hybrid))
        print(f"  dense  Hit@1 {dense['hit@1']:.3f} MRR {dense['mrr']:.3f}")
        print(f"  hybrid Hit@1 {hybrid['hit@1']:.3f} MRR {hybrid['mrr']:.3f}")

    # 표 저장
    lines = ["# 임베딩 모델 비교 (검색 성능)", "",
             f"- 평가셋: `{eval_path}` ({len([i for i in items if i.doc_id])}건)",
             f"- base_url: {s.openai_base_url or 'OpenAI'}", "",
             "| 모델 | 방식 | Hit@1 | Hit@3 | Hit@5 | MRR |",
             "|------|------|------:|------:|------:|------:|"]
    for model, mode, r in rows:
        lines.append(f"| {model} | {mode} | {r['hit@1']:.3f} | {r['hit@3']:.3f} | {r['hit@5']:.3f} | {r['mrr']:.3f} |")
    out = Path("results/compare_embeddings.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[compare] 저장 -> {out}")


class _StoreShim:
    """HybridRetriever 가 기대하는 vector_store 인터페이스(query)를 컬렉션에 맞춰 제공."""
    def __init__(self, coll):
        self._coll = coll

    def query(self, embedding, top_k, where=None):
        from src.vectorstore.base import RetrievedChunk
        r = self._coll.query(query_embeddings=[embedding], n_results=top_k, where=where)
        return [RetrievedChunk(text=d, metadata=m or {}, score=1.0 - dist)
                for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])]


if __name__ == "__main__":
    main()
