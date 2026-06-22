"""청크 크기 실험: 어떤 청크 크기가 검색 품질이 좋은지 측정한다.

평가셋(자동 생성): 각 문서의 '사업 요약'을 질의로, 해당 doc_id 를 정답으로 사용.
지표: Hit@1, Hit@5, MRR (정답 문서의 청크가 상위 k 안에 들어오는가).

여러 청크 크기를 임시 ChromaDB 컬렉션에 적재해 비교한다(기존 chroma_db 는 건드리지 않음).
질의 임베딩은 청크 크기와 무관하므로 1회만 계산해 재사용한다.

실행: python -m scripts.exp_chunk_size
"""
from __future__ import annotations

import chromadb
import pandas as pd

from src.config import get_settings
from src.dataset_utill.chunker import chunk_document
from src.embeddings import build_embedder

CONFIGS = [(256, 40), (384, 60), (512, 80), (1024, 150)]  # (chunk_size, overlap)
TOP_K = 5


def _embed_all(embedder, texts, batch=100):
    out = []
    for i in range(0, len(texts), batch):
        out.extend(embedder.embed_documents(texts[i : i + batch]))
    return out


def main() -> None:
    settings = get_settings()
    embedder = build_embedder(settings)
    df = pd.read_csv("data/processed/corpus_clean.csv")

    # 평가셋: 사업요약 → 정답 doc_id (요약 있는 문서만)
    evalset = df[df["사업 요약"].notna()][["doc_id", "사업 요약"]].copy()
    print(f"평가 질의 수: {len(evalset)}")

    # 질의 임베딩 1회 계산 (모든 config 공유)
    q_emb = _embed_all(embedder, evalset["사업 요약"].astype(str).tolist())

    print(f"\n{'chunk_size':>10} {'overlap':>8} {'#chunks':>8} {'Hit@1':>7} {'Hit@5':>7} {'MRR':>7}")
    print("-" * 56)

    for size, overlap in CONFIGS:
        # 1) 청킹
        chunks = []
        for _, r in df.iterrows():
            text = str(r["text"])
            if not text.strip():
                continue
            for c in chunk_document(str(r["doc_id"]), text, {"doc_id": str(r["doc_id"])}, size, overlap):
                chunks.append((c.chunk_id, c.text, str(r["doc_id"])))

        # 2) 임베딩 + 인메모리 컬렉션 적재 (파일 잠금 회피)
        client = chromadb.EphemeralClient()
        coll = client.create_collection(f"exp_{size}", metadata={"hnsw:space": "cosine"})
        embs = _embed_all(embedder, [c[1] for c in chunks])
        coll.add(
            ids=[c[0] for c in chunks],
            embeddings=embs,
            documents=[c[1] for c in chunks],
            metadatas=[{"doc_id": c[2]} for c in chunks],
        )

        # 3) 평가
        hit1 = hit5 = 0
        rr = 0.0
        for gold_id, qv in zip(evalset["doc_id"], q_emb):
            r = coll.query(query_embeddings=[qv], n_results=TOP_K)
            ranked_docs = []
            for m in r["metadatas"][0]:
                d = m.get("doc_id")
                if d not in ranked_docs:
                    ranked_docs.append(d)
            if gold_id in ranked_docs:
                rank = ranked_docs.index(gold_id) + 1
                hit5 += 1
                rr += 1.0 / rank
                if rank == 1:
                    hit1 += 1
        n = len(evalset)
        print(f"{size:>10} {overlap:>8} {len(chunks):>8} "
              f"{hit1/n:>7.3f} {hit5/n:>7.3f} {rr/n:>7.3f}")


if __name__ == "__main__":
    main()
