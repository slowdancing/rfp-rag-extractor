"""RAG 오케스트레이션.

적재(인덱싱)와 질의(검색→생성)를 담당하는 핵심 파이프라인.
임베더/벡터스토어/LLM 은 모두 추상 인터페이스로 주입받으므로
OpenAI ↔ HuggingFace, Chroma ↔ 기타 전환이 자유롭다.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.base import BaseEmbedder
from src.dataset_utill.chunker import chunk_document
from src.dataset_utill.loader import load_documents
from src.llm.base import BaseLLM
from src.rag import prompts
from src.vectorstore.base import BaseVectorStore, RetrievedChunk


@dataclass
class RAGAnswer:
    answer: str
    sources: list[RetrievedChunk]


class RAGPipeline:
    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        llm: BaseLLM,
        top_k: int = 5,
    ):
        self._embedder = embedder
        self._store = vector_store
        self._llm = llm
        self._top_k = top_k

    # ---------- 인덱싱 ----------
    def index_corpus(
        self,
        raw_dir: str,
        metadata_dir: str | None,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int = 64,
    ) -> int:
        """data/raw 의 문서를 청킹·임베딩하여 벡터스토어에 적재. 청크 수 반환."""
        docs = load_documents(raw_dir, metadata_dir)
        total = 0
        for doc in docs:
            chunks = chunk_document(
                doc.doc_id, doc.text, doc.metadata, chunk_size, chunk_overlap
            )
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                embeddings = self._embedder.embed_documents([c.text for c in batch])
                self._store.add(
                    ids=[c.chunk_id for c in batch],
                    embeddings=embeddings,
                    documents=[c.text for c in batch],
                    metadatas=[c.metadata for c in batch],
                )
                total += len(batch)
            print(f"[index] {doc.doc_id}: {len(chunks)} chunks")
        return total

    def index_chunks(
        self,
        csv_path: str,
        batch_size: int = 100,
        verbose: bool = True,
    ) -> int:
        """이미 청킹된 chunks.csv 를 임베딩하여 벡터스토어에 적재. 청크 수 반환.

        dataset_utill.build_chunks 산출물(chunks.csv)을 입력으로 받는다.
        'text' 컬럼은 본문, 나머지 컬럼은 메타데이터로 저장한다.
        """
        import pandas as pd

        df = pd.read_csv(csv_path)
        meta_cols = [c for c in df.columns if c != "text"]

        def _sanitize(value):
            # ChromaDB 메타데이터는 str/int/float/bool 만 허용 (None/NaN 불가)
            if pd.isna(value):
                return ""
            if isinstance(value, (int, float, bool, str)):
                return value
            return str(value)

        total = 0
        for start in range(0, len(df), batch_size):
            batch = df.iloc[start : start + batch_size]
            texts = batch["text"].astype(str).tolist()
            ids = batch["chunk_id"].astype(str).tolist()
            metadatas = [
                {col: _sanitize(row[col]) for col in meta_cols}
                for _, row in batch.iterrows()
            ]
            embeddings = self._embedder.embed_documents(texts)
            self._store.add(
                ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
            )
            total += len(batch)
            if verbose:
                print(f"[index] {total}/{len(df)} 청크 적재 완료")
        return total

    # ---------- 검색 ----------
    def retrieve(
        self, query: str, top_k: int | None = None, where: dict | None = None
    ) -> list[RetrievedChunk]:
        q_emb = self._embedder.embed_query(query)
        return self._store.query(q_emb, top_k or self._top_k, where=where)

    def rewrite_query(self, question: str) -> str:
        """자연어 질문을 검색용 핵심 키워드 질의로 변환한다(LLM 사용).

        실패하거나 빈 결과면 원 질문을 그대로 반환한다.
        """
        try:
            rewritten = self._llm.generate(
                prompts.QUERY_REWRITE_SYSTEM_PROMPT,
                prompts.build_query_rewrite_prompt(question),
            ).strip()
            return rewritten or question
        except Exception:  # noqa: BLE001 - 재작성 실패 시 원 질문으로 폴백
            return question

    @staticmethod
    def _format_context(chunks: list[RetrievedChunk]) -> str:
        parts = []
        for c in chunks:
            src = c.metadata.get("source", c.metadata.get("doc_id", "unknown"))
            parts.append(f"[출처: {src}]\n{c.text}")
        return "\n\n---\n\n".join(parts)

    # ---------- 질의응답 ----------
    def ask(
        self,
        question: str,
        top_k: int | None = None,
        where: dict | None = None,
        rewrite: bool = True,
    ) -> RAGAnswer:
        # 검색은 재작성된 질의로, 답변 생성은 원 질문으로 수행한다.
        search_query = self.rewrite_query(question) if rewrite else question
        chunks = self.retrieve(search_query, top_k, where)
        context = self._format_context(chunks)
        answer = self._llm.generate(
            prompts.QA_SYSTEM_PROMPT,
            prompts.build_qa_user_prompt(question, context),
        )
        return RAGAnswer(answer=answer, sources=chunks)

    # ---------- 요약 ----------
    def summarize(self, doc_id: str, max_chunks: int = 12) -> RAGAnswer:
        """특정 문서를 요약. doc_id 메타데이터로 필터링하여 청크를 모은다."""
        chunks = self._store.query(
            self._embedder.embed_query("사업 개요 예산 기간 요구사항 자격 제출"),
            top_k=max_chunks,
            where={"doc_id": doc_id},
        )
        context = self._format_context(chunks)
        answer = self._llm.generate(
            prompts.SUMMARY_SYSTEM_PROMPT,
            prompts.build_summary_user_prompt(context),
        )
        return RAGAnswer(answer=answer, sources=chunks)


def build_pipeline(settings) -> RAGPipeline:
    """설정으로부터 완전히 구성된 파이프라인을 만든다."""
    from src.embeddings import build_embedder
    from src.llm import build_llm
    from src.vectorstore import build_vector_store

    return RAGPipeline(
        embedder=build_embedder(settings),
        vector_store=build_vector_store(settings),
        llm=build_llm(settings),
        top_k=settings.top_k,
    )
