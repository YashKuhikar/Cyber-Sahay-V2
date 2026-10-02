from __future__ import annotations

import os
from typing import List, Optional, Tuple
from langchain_core.documents import Document

from ..logs.logger import logger
from .knowledge_registry import TOPIC_METADATA_PRIORITIES


class EvidenceReranker:
    """
    Candidate Pool Reranker with Cross-Encoder scoring,
    metadata authority weighting, and threshold filtering.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        candidate_k: int = 30,
        top_k: int = 6,
        reranker_threshold: float = -4.0,
    ):
        self.model_name = model_name
        self.candidate_k = candidate_k
        self.top_k = top_k
        self.reranker_threshold = reranker_threshold
        self._cross_encoder = None
        self._load_attempted = False

    def _get_model(self):
        if not self._load_attempted:
            self._load_attempted = True
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder(self.model_name)
                logger.info(f"CrossEncoder reranker '{self.model_name}' loaded successfully.")
            except Exception as e:
                logger.warning(f"CrossEncoder lazy load failed (falling back to authority-weighted RRF): {e}")
        return self._cross_encoder

    def rerank(
        self,
        query: str,
        candidates: List[Document],
        category: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[Document]:
        """
        Reranks candidates using Cross-Encoder and boosts authoritative sources.
        """
        target_k = top_k or self.top_k
        if not candidates:
            return []

        # 1. Authority Level & Metadata Priority Weighting
        topic_spec = TOPIC_METADATA_PRIORITIES.get(category or "", {})
        priority_topics = topic_spec.get("topics", [])
        priority_laws = topic_spec.get("laws", [])

        weighted_candidates: List[Tuple[Document, float]] = []

        model = self._get_model()

        if model is not None:
            try:
                pairs = [(query, doc.page_content) for doc in candidates]
                scores = model.predict(pairs)

                for doc, score in zip(candidates, scores):
                    boost = 0.0
                    auth_level = doc.metadata.get("authority_level", 3)
                    # Higher boost for official government regulations (Level 1) & Acts (Level 2)
                    if auth_level == 1:
                        boost += 0.5
                    elif auth_level == 2:
                        boost += 0.3

                    # Boost if matches priority topic
                    doc_topic = doc.metadata.get("topic", "").lower()
                    if any(pt in doc_topic for pt in priority_topics):
                        boost += 0.4

                    total_score = float(score) + boost
                    weighted_candidates.append((doc, total_score))

                # Sort by score descending
                weighted_candidates.sort(key=lambda x: x[1], reverse=True)

                final_docs = []
                for doc, sc in weighted_candidates[:target_k]:
                    updated_meta = {**doc.metadata, "rerank_score": round(sc, 4)}
                    final_docs.append(Document(page_content=doc.page_content, metadata=updated_meta))
                return final_docs

            except Exception as err:
                logger.warning(f"Reranking prediction error: {err}")

        # Fallback: metadata authority weighted RRF order
        for idx, doc in enumerate(candidates):
            base_score = 1.0 / (idx + 1)
            auth_level = doc.metadata.get("authority_level", 3)
            auth_boost = (5 - auth_level) * 0.1
            weighted_candidates.append((doc, base_score + auth_boost))

        weighted_candidates.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in weighted_candidates[:target_k]]
