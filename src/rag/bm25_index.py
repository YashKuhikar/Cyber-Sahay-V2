"""
==========================================================
CyberSahay - BM25 Index
==========================================================

Purpose
-------
Creates and persists a BM25 index for sparse retrieval.

Responsibilities
----------------
✔ Build BM25 Index
✔ Preserve Chunk Order
✔ Save Index
✔ Load Index
✔ Query Index
✔ Return LangChain Documents

Author
------
CyberSahay Team
==========================================================
"""

from __future__ import annotations

import pickle
import time
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


class BM25Indexer:

    DEFAULT_DIRECTORY = "bm25_store"

    def __init__(
        self,
        persist_directory: str = DEFAULT_DIRECTORY,
    ):

        self.persist_directory = Path(persist_directory)

        self.persist_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.index = None
        self.documents: List[Document] = []

    # --------------------------------------------------

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Basic tokenizer.
        """

        return text.lower().split()

    # --------------------------------------------------

    def build_index(
        self,
        chunks: List[Document],
    ):

        if not chunks:
            raise ValueError("No chunks provided.")

        print("\nBuilding BM25 Index...\n")

        start = time.time()

        corpus = [
            self.tokenize(doc.page_content)
            for doc in chunks
        ]

        self.index = BM25Okapi(corpus)

        self.documents = chunks

        elapsed = time.time() - start

        print("=" * 60)
        print("BM25 Index Built")
        print("=" * 60)
        print(f"Chunks Indexed : {len(chunks)}")
        print(f"Time Taken     : {elapsed:.2f} sec")
        print("=" * 60)

    # --------------------------------------------------

    def save(self):

        if self.index is None:
            raise ValueError("Build the index first.")

        with open(
            self.persist_directory / "bm25_index.pkl",
            "wb",
        ) as f:
            pickle.dump(self.index, f)

        with open(
            self.persist_directory / "documents.pkl",
            "wb",
        ) as f:
            pickle.dump(self.documents, f)

        print("\nBM25 Index Saved.")

    # --------------------------------------------------

    def load(self):

        with open(
            self.persist_directory / "bm25_index.pkl",
            "rb",
        ) as f:
            self.index = pickle.load(f)

        with open(
            self.persist_directory / "documents.pkl",
            "rb",
        ) as f:
            self.documents = pickle.load(f)

        print("\nBM25 Index Loaded.")

    # --------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Document]:

        if self.index is None:
            raise ValueError("Index not loaded.")

        tokenized_query = self.tokenize(query)

        scores = self.index.get_scores(
            tokenized_query
        )

        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        results = []

        for idx, score in ranked[:top_k]:

            results.append(
                Document(
                    page_content=self.documents[idx].page_content,
                    metadata={
                        **self.documents[idx].metadata,
                        "bm25_score": float(score),
                    },
                )
            )

        return results

    # --------------------------------------------------

    def info(self):

        print("=" * 60)
        print("BM25 Information")
        print("=" * 60)
        print(f"Indexed Chunks : {len(self.documents)}")
        print(f"Storage Path   : {self.persist_directory.resolve()}")
        print("=" * 60)


# ======================================================
# Module Smoke Test
# ======================================================

if __name__ == "__main__":

    print("=" * 60)
    print("BM25 Module")
    print("=" * 60)

    indexer = BM25Indexer()

    print("BM25 Indexer initialized successfully.")