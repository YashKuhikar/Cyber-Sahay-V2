"""
embeddings.py

Creates dense vector embeddings for document chunks using
BAAI/bge-base-en-v1.5.

Input:
    List[Document] (already chunked)

Output:
    numpy.ndarray

Author: CyberSahay
"""

from __future__ import annotations

import time
from typing import List

import numpy as np
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer


# ==========================================================
# Configuration
# ==========================================================

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"

DEFAULT_BATCH_SIZE = 64


# ==========================================================
# Embedding Generator
# ==========================================================

class EmbeddingGenerator:
    """
    Generates dense embeddings for LangChain Documents.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):

        self.model_name = model_name
        self.batch_size = batch_size

        print("\n========== LOADING EMBEDDING MODEL ==========")

        start = time.time()

        self.model = SentenceTransformer(model_name)

        end = time.time()

        print(f"Model        : {model_name}")
        print(f"Load Time    : {end - start:.2f} sec")
        print("=============================================\n")

    # ------------------------------------------------------

    def generate_embeddings(
        self,
        chunks: List[Document],
    ) -> np.ndarray:

        """
        Generate embeddings for chunked documents.

        Args:
            chunks:
                List of LangChain Document objects.

        Returns:
            numpy.ndarray
        """

        if not chunks:
            raise ValueError(
                "No chunks supplied for embedding."
            )

        texts = [
            chunk.page_content.strip()
            for chunk in chunks
        ]

        if any(len(text) == 0 for text in texts):
            raise ValueError(
                "One or more chunks are empty."
            )

        print("========== GENERATING EMBEDDINGS ==========")
        print(f"Model            : {self.model_name}")
        print(f"Chunks           : {len(texts)}")
        print(f"Batch Size       : {self.batch_size}")
        print("-------------------------------------------")

        start = time.time()

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        elapsed = time.time() - start

        print("-------------------------------------------")
        print(f"Vectors Created  : {len(embeddings)}")
        print(f"Embedding Size   : {embeddings.shape[1]}")
        print(f"Time Taken       : {elapsed:.2f} sec")
        print("===========================================\n")

        # ---------------------------------------
        # Example embedding
        # ---------------------------------------

        print("Example Vector")
        print("-" * 60)

        preview = np.array2string(
            embeddings[0][:10],
            precision=4,
            separator=", "
        )

        print(preview + " ...")

        print("-" * 60)

        return embeddings


# ==========================================================
# Test
# ==========================================================

if __name__ == "__main__":

    from data_loader import load_all_documents
    from text_splitter_chunks import split_documents

    documents = load_all_documents()

    chunks = split_documents(documents)

    embedding_generator = EmbeddingGenerator()

    vectors = embedding_generator.generate_embeddings(
        chunks
    )

    print(f"\nTotal Embeddings : {len(vectors)}")