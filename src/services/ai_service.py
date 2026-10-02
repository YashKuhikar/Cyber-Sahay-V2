from ..rag.hybrid_retriever import HybridRetriever
from ..rag.rag_pipeline import RAGPipeline
from ..rag.semantic_cache import SemanticCache
from ..logs.logger import logger


class AIService:

    _retriever = None
    _semantic_cache = None

    def __init__(self):

        # Create HybridRetriever only once
        if AIService._retriever is None:
            logger.info("Initializing Shared HybridRetriever...")
            AIService._retriever = HybridRetriever()

        if AIService._semantic_cache is None:
            logger.info("Initializing Shared SemanticCache...")
            AIService._semantic_cache = SemanticCache(
                similarity_threshold=0.92,
                max_size=500,
            )

        self.pipeline = RAGPipeline(
            AIService._retriever
        )

    def ask(
        self,
        query: str,
        history=None,
    ):
        clean_query = query.strip()

        # Semantic Cache check for standalone / FAQ questions
        if not history:
            try:
                emb = self.pipeline.retriever._embed_query(clean_query)
                cached = AIService._semantic_cache.get(clean_query, emb)
                if cached:
                    return cached
            except Exception as cache_err:
                logger.warning(f"Semantic cache lookup error: {cache_err}")

        result = self.pipeline.ask(
            query=clean_query,
            history=history,
        )

        # Store response in semantic cache for standalone questions
        if not history and result and result.get("answer"):
            try:
                emb = self.pipeline.retriever._embed_query(clean_query)
                AIService._semantic_cache.set(
                    query=clean_query,
                    embedding=emb,
                    response=result["answer"],
                    sources=result.get("sources", []),
                )
            except Exception as cache_set_err:
                logger.warning(f"Semantic cache save error: {cache_set_err}")

        return result

    def ask_stream(
        self,
        query: str,
        history=None,
    ):
        return self.pipeline.ask_stream(
            query=query,
            history=history,
        )