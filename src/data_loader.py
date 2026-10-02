from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import PyMuPDFLoader

# Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Knowledge Base Folder
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "Knowledge-Base"


def load_all_documents() -> List[Document]:
    """
    Recursively loads every PDF from the Knowledge-Base folder.

    Returns:
        List[Document]: LangChain Documents.
    """

    if not KNOWLEDGE_BASE_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge Base folder not found:\n{KNOWLEDGE_BASE_DIR}"
        )

    pdf_files = sorted(KNOWLEDGE_BASE_DIR.rglob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found inside:\n{KNOWLEDGE_BASE_DIR}"
        )

    print(f"\nKnowledge Base : {KNOWLEDGE_BASE_DIR}")
    print(f"PDFs Found     : {len(pdf_files)}\n")

    documents: List[Document] = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        try:
            print(f"[{index}/{len(pdf_files)}] Loading: {pdf_path.relative_to(PROJECT_ROOT)}")

            loader = PyMuPDFLoader(str(pdf_path))
            docs = loader.load()

            documents.extend(docs)

        except Exception as e:
            print(f"Failed to load {pdf_path.name}: {e}")

    print("\n------------------------------------")
    print(f"Total PDFs Loaded : {len(pdf_files)}")
    print(f"Total Pages Loaded: {len(documents)}")
    print("------------------------------------\n")

    return documents


if __name__ == "__main__":
    docs = load_all_documents()

    print(f"Loaded {len(docs)} pages.")

    if docs:
        print("\nSample Metadata:")
        print(docs[0].metadata)

        print("\nSample Content:")
        print(docs[0].page_content[:500])