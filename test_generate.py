import sys
from pathlib import Path

# Add the src directory to Python's module search path
sys.path.append(str(Path(__file__).parent / "src"))

from rag.hybrid_retriever import HybridRetriever
from rag.rag_pipeline import RAGPipeline

retriever = HybridRetriever()
pipeline = RAGPipeline(retriever)

response = pipeline.generate(
    "Say hello in one sentence."
)

print(response)