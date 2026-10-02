"""
==========================================================
CyberSahay - Knowledge Base Ingestion Pipeline
==========================================================

Purpose
-------
Builds the complete Hybrid RAG Knowledge Base.

Pipeline
--------
1. Load Documents
2. Split into Chunks
3. Generate Embeddings
4. Store in ChromaDB
5. Build BM25 Index
6. Save BM25 Index

Run
---
uv run python src/ingest.py

Author
------
CyberSahay Team
==========================================================
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

from data_loader import load_all_documents
from text_splitter_chunks import split_documents
from embeddings import EmbeddingGenerator
from rag.vector_store import ChromaVectorStore
from rag.bm25_index import BM25Indexer


# ==========================================================
# Pipeline Summary
# ==========================================================

@dataclass(slots=True)
class IngestionSummary:
    documents: int
    chunks: int
    vectors: int
    bm25_chunks: int
    total_time: float


# ==========================================================
# Knowledge Base Ingestor
# ==========================================================

class KnowledgeBaseIngestor:
    """
    Orchestrates the complete ingestion pipeline.
    """

    def __init__(
        self,
        reset_vector_database: bool = True,
    ) -> None:

        self.reset_vector_database = reset_vector_database

    # ------------------------------------------------------

    @staticmethod
    def _header(title: str) -> None:

        print("\n" + "=" * 70)
        print(title)
        print("=" * 70)

    # ------------------------------------------------------

    def ingest(self) -> IngestionSummary:

        overall_start = time.perf_counter()

        self._header("CyberSahay Knowledge Base Ingestion")

        # ==================================================
        # STEP 1
        # ==================================================

        print("\n[1/6] Loading Documents...\n")

        documents = load_all_documents()

        if not documents:
            raise RuntimeError(
                "No documents were loaded."
            )

        print(f"✓ Loaded {len(documents)} pages")

        # ==================================================
        # STEP 2
        # ==================================================

        print("\n[2/6] Splitting Documents...\n")

        chunks = split_documents(documents)

        if not chunks:
            raise RuntimeError(
                "No chunks generated."
            )

        print(f"✓ Generated {len(chunks)} chunks")

                # ==================================================
        # ADD KNOWLEDGE BASE METADATA
        # ==================================================

        for chunk in chunks:

            chunk.metadata["jurisdiction"] = "India"

            chunk.metadata.setdefault(
                "knowledge_domain",
                "cybercrime"
            )

        # ==================================================
        # STEP 3
        # ==================================================

        print("\n[3/6] Generating Embeddings...\n")

        embedding_generator = EmbeddingGenerator()

        embeddings = embedding_generator.generate_embeddings(
            chunks
        )

        print(f"✓ Generated {len(embeddings)} embeddings")

        # ==================================================
        # STEP 4
        # ==================================================

        print("\n[4/6] Building Vector Store...\n")

        vector_store = ChromaVectorStore()

        if self.reset_vector_database:
            vector_store.reset_database()

        vector_store.add_documents(
            chunks,
            embeddings,
        )

        vector_store.collection_info()

        # ==================================================
        # STEP 5
        # ==================================================

        print("\n[5/6] Building BM25 Index...\n")

        bm25 = BM25Indexer()

        bm25.build_index(chunks)

        bm25.save()

        bm25.info()

        # ==================================================
        # STEP 6
        # ==================================================

        elapsed = time.perf_counter() - overall_start

        summary = IngestionSummary(
            documents=len(documents),
            chunks=len(chunks),
            vectors=len(embeddings),
            bm25_chunks=len(chunks),
            total_time=elapsed,
        )

        self._header("Knowledge Base Ready")

        print(f"Documents Loaded      : {summary.documents}")
        print(f"Chunks Created        : {summary.chunks}")
        print(f"Embeddings Generated  : {summary.vectors}")
        print(f"BM25 Indexed Chunks   : {summary.bm25_chunks}")
        print(f"Total Time            : {summary.total_time:.2f} sec")

        print("\n✓ Hybrid RAG Knowledge Base successfully created.")

        return summary


# ==========================================================
# Main
# ==========================================================

def main() -> int:

    try:

        ingestor = KnowledgeBaseIngestor()

        ingestor.ingest()

        return 0

    except KeyboardInterrupt:

        print("\n\nIngestion cancelled by user.")
        return 1

    except Exception as exc:

        print("\n" + "=" * 70)
        print("INGESTION FAILED")
        print("=" * 70)
        print(type(exc).__name__)
        print(exc)

        return 1


if __name__ == "__main__":
    sys.exit(main())