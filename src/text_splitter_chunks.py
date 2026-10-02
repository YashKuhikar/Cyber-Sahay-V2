"""
text_splitter.py

Splits loaded LangChain documents into smaller chunks for Hybrid RAG.

Input:
    List[Document]

Output:
    List[Document] (chunks)

Author: CyberSahay
"""

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ==========================================================
# Configuration
# ==========================================================

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150


# ==========================================================
# Split Documents
# ==========================================================

def split_documents(
    documents: List[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """
    Split LangChain Documents into smaller chunks.

    Args:
        documents (List[Document]):
            Documents returned from data_loader.py

        chunk_size (int):
            Maximum characters per chunk.

        chunk_overlap (int):
            Overlap between consecutive chunks.

    Returns:
        List[Document]:
            Chunked LangChain Documents.
    """

    # ------------------------------------------------------
    # Validation
    # ------------------------------------------------------

    if not documents:
        raise ValueError("No documents supplied for splitting.")

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size."
        )

    print("\n========== TEXT SPLITTING ==========")
    print(f"Input Documents : {len(documents)}")
    print(f"Chunk Size      : {chunk_size}")
    print(f"Chunk Overlap   : {chunk_overlap}")
    print("------------------------------------")

    # ------------------------------------------------------
    # Splitter
    # ------------------------------------------------------

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    chunks = text_splitter.split_documents(documents)

    # ------------------------------------------------------
    # Statistics
    # ------------------------------------------------------

    chunk_lengths = [len(chunk.page_content) for chunk in chunks]

    avg_length = (
        sum(chunk_lengths) / len(chunk_lengths)
        if chunk_lengths
        else 0
    )

    print(f"Chunks Created  : {len(chunks)}")
    print(f"Average Length  : {avg_length:.1f} characters")
    print("====================================\n")

    # ------------------------------------------------------
    # Example Chunk
    # ------------------------------------------------------

    if chunks:

        print("Example Chunk")
        print("-" * 60)

        metadata = chunks[0].metadata

        print(f"Source : {metadata.get('source', 'Unknown')}")
        print(f"Page   : {metadata.get('page', 'N/A')}")

        print("\nContent Preview:\n")

        preview = chunks[0].page_content[:500]

        print(preview)

        if len(chunks[0].page_content) > 500:
            print("...")

        print("-" * 60)

    return chunks


# ==========================================================
# Test
# ==========================================================

if __name__ == "__main__":

    from data_loader import load_all_documents

    documents = load_all_documents()

    chunks = split_documents(documents)

    print(f"\nFinal Chunk Count : {len(chunks)}")