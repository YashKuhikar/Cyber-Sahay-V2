"""
==========================================================
CyberSahay - Vector Store Module
==========================================================

Purpose:
--------
Stores document chunks and their embeddings into ChromaDB.

Responsibilities:
-----------------
✔ Create / Load Chroma Collection
✔ Persist Vector Database
✔ Store Chunk Text
✔ Store Embeddings
✔ Preserve Metadata
✔ Batch Insert Documents
✔ Collection Statistics

Author:
CyberSahay Team
==========================================================
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import List

import chromadb
import numpy as np
from langchain_core.documents import Document


class ChromaVectorStore:
    """
    Production-ready ChromaDB Vector Store
    """

    DEFAULT_COLLECTION_NAME = "cybersahay_knowledge_base"
    DEFAULT_BATCH_SIZE = 256

    def __init__(
        self,
        persist_directory: str = "chroma_db",
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:

        self.persist_directory = Path(persist_directory)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory)
        )

        self.collection_name = collection_name

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name
        )

        print("=" * 60)
        print("ChromaDB Initialized")
        print("=" * 60)
        print(f"Collection : {collection_name}")
        print(f"Database   : {self.persist_directory.resolve()}")
        print("=" * 60)

    # --------------------------------------------------

    def add_documents(
        self,
        chunks: List[Document],
        embeddings: np.ndarray,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """
        Store chunks and embeddings into ChromaDB.
        """

        if len(chunks) == 0:
            raise ValueError("No chunks supplied.")

        if len(embeddings) == 0:
            raise ValueError("No embeddings supplied.")

        if len(chunks) != len(embeddings):
            raise ValueError(
                "Number of chunks and embeddings do not match."
            )

        print("\nAdding Documents to ChromaDB...\n")

        start = time.time()

        total = len(chunks)

        for start_idx in range(0, total, batch_size):

            end_idx = min(start_idx + batch_size, total)

            batch = chunks[start_idx:end_idx]
            batch_embeddings = embeddings[start_idx:end_idx]

            ids = [
                str(uuid.uuid4())
                for _ in batch
            ]

            documents = [
                doc.page_content
                for doc in batch
            ]

            metadatas = [
                dict(doc.metadata)
                for doc in batch
            ]

            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=batch_embeddings.tolist(),
                metadatas=metadatas,
            )

            print(
                f"Stored Batch "
                f"{start_idx+1}-{end_idx}"
            )

        elapsed = time.time() - start

        print("\nVector Store Successfully Created!")
        print(f"Documents Stored : {total}")
        print(f"Time Taken       : {elapsed:.2f} sec\n")

    # --------------------------------------------------

    def collection_info(self) -> None:
        """
        Print Collection Statistics.
        """

        count = self.collection.count()

        print("=" * 60)
        print("Collection Information")
        print("=" * 60)
        print(f"Collection Name : {self.collection_name}")
        print(f"Documents       : {count}")
        print(f"Database        : {self.persist_directory}")
        print("=" * 60)

    # --------------------------------------------------

    def delete_collection(self) -> None:
        """
        Delete Collection.
        """

        self.client.delete_collection(
            self.collection_name
        )

        print(f"\nCollection '{self.collection_name}' deleted.")

    # --------------------------------------------------

    def reset_database(self) -> None:
        """
        Delete and recreate collection.
        """

        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass

        self.collection = self.client.get_or_create_collection(
            self.collection_name
        )

        print("\nDatabase Reset Complete.")

    # --------------------------------------------------

    def get_collection(self):
        """
        Return underlying Chroma Collection.
        """

        return self.collection

     # --------------------------------------------------

    def query(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ):
        """
        Perform semantic similarity search using ChromaDB.

        Args:
            query_embedding:
                Query embedding as a NumPy array.

            top_k:
                Number of results to retrieve.

        Returns:
            ChromaDB query result.
        """

        return self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )


# ==========================================================
# Example Usage
# ==========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Module Smoke Test")
    print("=" * 60)

    vector_store = ChromaVectorStore()
    vector_store.collection_info()

    print("\n✓ Vector Store initialized successfully.")