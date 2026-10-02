"""
==========================================================
CyberSahay - Hybrid Retriever
==========================================================

Purpose
-------
Implements Hybrid Retrieval using:

1. Dense Retrieval (ChromaDB)
2. Sparse Retrieval (BM25)

The results from both retrievers are fused using
Reciprocal Rank Fusion (RRF).

Responsibilities
----------------
✔ Encode user queries
✔ Dense semantic retrieval
✔ Sparse keyword retrieval
✔ Reciprocal Rank Fusion
✔ Duplicate removal
✔ Final ranking
✔ Return LangChain Documents

Author
------
CyberSahay Team
==========================================================
"""

from __future__ import annotations

import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

from ..logs.logger import logger
from .bm25_index import BM25Indexer
from .vector_store import ChromaVectorStore


# ==========================================================
# Configuration
# ==========================================================

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

DEFAULT_DENSE_K = 10
DEFAULT_SPARSE_K = 10
DEFAULT_CANDIDATE_K = 10
DEFAULT_FINAL_K = 5

RRF_K = 60


# ==========================================================
# Retrieval Result
# ==========================================================

@dataclass(slots=True)
class RetrievalResult:
    """
    Internal representation of a retrieved document.
    """

    document: Document

    score: float

    source: str


# ==========================================================
# Hybrid Retriever with Cross-Encoder Reranker
# ==========================================================

from .multilingual import MultilingualProcessor
from .knowledge_registry import enrich_document_metadata
from .reranker import EvidenceReranker


class HybridRetriever:

    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        reranker_model: str = DEFAULT_RERANKER_MODEL,
    ) -> None:

        logger.info("Initializing Hybrid Retriever...")
        self.embedding_model_name = embedding_model
        self._embedding_model = None
        self._vector_store = None
        self._bm25 = None
        self.evidence_reranker = EvidenceReranker(model_name=reranker_model)
        logger.info("Hybrid Retriever Initialized.")

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            logger.info(f"Loading dense embedding model '{self.embedding_model_name}'...")
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        return self._embedding_model

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = ChromaVectorStore()
        return self._vector_store

    @property
    def bm25(self):
        if self._bm25 is None:
            self._bm25 = BM25Indexer()
            self._bm25.load()
        return self._bm25

    # ------------------------------------------------------

    def _embed_query(
        self,
        query: str,
    ) -> np.ndarray:

        if not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        return self.embedding_model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )


    # ------------------------------------------------------

    def dense_search(
        self,
        query: str,
        top_k: int = DEFAULT_DENSE_K,
    ) -> List[RetrievalResult]:

        embedding = self._embed_query(query)

        response = self.vector_store.query(
            query_embedding=embedding,
            top_k=top_k,
        )

        results: List[RetrievalResult] = []

        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        distances = response["distances"][0]

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):

            results.append(
                RetrievalResult(
                    document=Document(
                        page_content=document,
                        metadata=metadata,
                    ),
                    score=float(distance),
                    source="dense",
                )
            )

        return results

    # ------------------------------------------------------

    def sparse_search(
        self,
        query: str,
        top_k: int = DEFAULT_SPARSE_K,
    ) -> List[RetrievalResult]:

        docs = self.bm25.search(
            query=query,
            top_k=top_k,
        )

        results: List[RetrievalResult] = []

        for doc in docs:

            results.append(
                RetrievalResult(
                    document=doc,
                    score=doc.metadata.get(
                        "bm25_score",
                        0.0,
                    ),
                    source="bm25",
                )
            )

        return results
    
    # ------------------------------------------------------

    @staticmethod
    def _document_key(
        document: Document,
    ) -> str:
        """
        Generate a unique identifier for a document.

        Uses source + page + content to reliably
        identify duplicates retrieved by both
        Dense and BM25.
        """

        metadata = document.metadata

        return (
            f"{metadata.get('source','')}|"
            f"{metadata.get('page',-1)}|"
            f"{hash(document.page_content)}"
        )

    # ------------------------------------------------------

    def _rrf_fusion(
        self,
        dense_results: List[RetrievalResult],
        sparse_results: List[RetrievalResult],
        final_k: int = DEFAULT_FINAL_K,
    ) -> List[Document]:
        """
        Reciprocal Rank Fusion (RRF)

        Reference:
        Cormack et al. (2009)

        score = Σ 1 / (k + rank)
        """

        fused_scores: Dict[str, float] = defaultdict(float)

        documents: Dict[str, Document] = {}

        # ------------------------------------------
        # Dense Ranking
        # ------------------------------------------

        for rank, result in enumerate(
            dense_results,
            start=1,
        ):

            key = self._document_key(
                result.document,
            )

            fused_scores[key] += (
                1.0 / (RRF_K + rank)
            )

            documents[key] = result.document

        # ------------------------------------------
        # Sparse Ranking
        # ------------------------------------------

        for rank, result in enumerate(
            sparse_results,
            start=1,
        ):

            key = self._document_key(
                result.document,
            )

            fused_scores[key] += (
                1.0 / (RRF_K + rank)
            )

            documents[key] = result.document

        # ------------------------------------------
        # Sort
        # ------------------------------------------

        ranked = sorted(
            fused_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        final_documents: List[Document] = []

        for key, score in ranked[:final_k]:

            document = documents[key]

            metadata = {
                **document.metadata,
                "rrf_score": round(score, 6),
            }

            final_documents.append(
                Document(
                    page_content=document.page_content,
                    metadata=metadata,
                )
            )

        return final_documents

    # ------------------------------------------------------

    def _rerank(
        self,
        query: str,
        documents: List[Document],
        final_k: int = DEFAULT_FINAL_K,
    ) -> List[Document]:
        """
        Re-score candidate documents with local CrossEncoder for cross-attention relevance.
        """
        if not self.reranker or not documents:
            return documents[:final_k]

        try:
            pairs = [(query, doc.page_content) for doc in documents]
            scores = self.reranker.predict(pairs)

            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: float(x[1]), reverse=True)

            reranked_documents: List[Document] = []
            for doc, score in scored_docs[:final_k]:
                metadata = {
                    **doc.metadata,
                    "rerank_score": round(float(score), 4),
                }
                reranked_documents.append(
                    Document(
                        page_content=doc.page_content,
                        metadata=metadata,
                    )
                )
            return reranked_documents
        except Exception as rerank_err:
            logger.warning(f"Reranking error (fallback to RRF order): {rerank_err}")
            return documents[:final_k]

    # ------------------------------------------------------

    def retrieve(
        self,
        query: str,
        dense_k: int = 20,
        sparse_k: int = 20,
        final_k: int = DEFAULT_FINAL_K,
        category: Optional[str] = None,
    ) -> List[Document]:
        """
        Execute Multilingual Query Normalization + Parallel Hybrid Retrieval (20-40 candidates)
        + Legal Metadata Enrichment + Cross-Encoder Reranking.
        """
        total_start = time.perf_counter()

        # 1. Multilingual analysis and query expansion
        lang_profile = MultilingualProcessor.analyze_query(query)
        search_query = lang_profile.canonical_query_en

        def _run_dense():
            t0 = time.perf_counter()
            try:
                results = self.dense_search(
                    query=search_query,
                    top_k=dense_k,
                )
            except Exception as e:
                logger.warning(f"Dense search failed: {e}")
                results = []
            elapsed = time.perf_counter() - t0
            return results, elapsed

        def _run_sparse():
            t0 = time.perf_counter()
            try:
                results = self.sparse_search(
                    query=search_query,
                    top_k=sparse_k,
                )
            except Exception as e:
                logger.warning(f"Sparse search failed: {e}")
                results = []
            elapsed = time.perf_counter() - t0
            return results, elapsed

        with ThreadPoolExecutor(max_workers=2) as executor:
            dense_future = executor.submit(_run_dense)
            sparse_future = executor.submit(_run_sparse)

            dense_results, dense_time = dense_future.result()
            sparse_results, sparse_time = sparse_future.result()

        total_retrieval_time = time.perf_counter() - total_start

        # 2. Candidate Pool RRF Fusion (Top 25-35 candidates)
        candidates = self._rrf_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            final_k=max(25, final_k * 4),
        )

        # 3. Dynamic Legal Metadata Enrichment
        enriched_candidates: List[Document] = []
        for doc in candidates:
            enriched_meta = enrich_document_metadata(doc.metadata)
            enriched_meta["user_language"] = lang_profile.detected_language
            enriched_candidates.append(
                Document(page_content=doc.page_content, metadata=enriched_meta)
            )

        # 4. Cross-Encoder & Legal Authority Reranking
        fused = self.evidence_reranker.rerank(
            query=query,
            candidates=enriched_candidates,
            category=category,
            top_k=final_k,
        )

        logger.debug(
            f"Retrieval Complete for '{query[:30]}' ({lang_profile.detected_language}) - "
            f"Dense: {len(dense_results)}, Sparse: {len(sparse_results)}, "
            f"Final: {len(fused)} ({total_retrieval_time:.3f}s)"
        )

        return fused



# ==========================================================
# Smoke Test
# ==========================================================

if __name__ == "__main__":

    try:

        retriever = HybridRetriever()

        results = retriever.retrieve(
            query="UPI fraud through QR code",
            dense_k=10,
            sparse_k=10,
            final_k=5,
        )

        print("\n========== RESULTS ==========\n")

        for i, document in enumerate(results, start=1):

            print(f"\nResult {i}")
            print("-" * 60)

            print(document.metadata)

            print()

            print(document.page_content[:250])

    except Exception as e:

        print("\nERROR")

        print(type(e).__name__)

        print(e)

        raise