"""
==========================================================
CyberSahay - In-Memory Semantic Cache
==========================================================

Purpose:
--------
Caches FAQ-style cyber safety and legal queries.
Matches semantic similarity of incoming queries against
cached questions using BGE embeddings. If cosine similarity
>= threshold (0.92), returns the cached response in < 15ms.

Responsibilities:
-----------------
✔ Embed query using shared SentenceTransformer
✔ Cosine similarity search over cached questions
✔ Thread-safe get/set/clear operations
✔ Zero disk I/O, fast in-memory lookups
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np

from ..logs.logger import logger


class SemanticCache:

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        max_size: int = 500,
    ) -> None:
        self.threshold = similarity_threshold
        self.max_size = max_size
        self._lock = threading.Lock()
        self._queries: List[str] = []
        self._embeddings: List[np.ndarray] = []
        self._responses: List[Dict[str, Any]] = []

    def get(
        self,
        query: str,
        embedding: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if query matches a cached entry with similarity >= threshold.
        """
        with self._lock:
            if not self._embeddings:
                return None

            # Matrix multiplication for cosine similarity (vectors are L2 normalized)
            cached_matrix = np.array(self._embeddings)
            sim_scores = np.dot(cached_matrix, embedding)

            best_idx = int(np.argmax(sim_scores))
            best_score = float(sim_scores[best_idx])

            if best_score >= self.threshold:
                matched_query = self._queries[best_idx]
                logger.info(
                    f"Semantic Cache HIT (Score: {best_score:.4f}) - "
                    f"Query: '{query}' -> Matched: '{matched_query}'"
                )
                cached_res = dict(self._responses[best_idx])
                cached_res["cache_hit"] = True
                cached_res["matched_query"] = matched_query
                cached_res["similarity_score"] = round(best_score, 4)
                return cached_res

            return None

    @staticmethod
    def contains_pii_or_incident_facts(query: str, response: str) -> bool:
        """
        Detects personal identifying information (PII) or victim-specific incident
        details (phone numbers, UPI IDs, OTPs, transaction IDs) to prevent caching
        and leaking private incident facts across victims.
        """
        import re
        text = f"{query} {response}"
        # Indian phone numbers
        if re.search(r"\b[6-9]\d{9}\b", text):
            return True
        # UPI handles
        if re.search(r"\b[\w.-]+@(?:ok[a-zA-Z]+|okhdfcbank|oksbi|paytm|ybl|axl|ibl)\b", text, re.IGNORECASE):
            return True
        # Personal incident credentials / identifiers
        if re.search(r"\b(?:otp|transaction id|utr|account number|debit card|credit card|cvv|password)\b", text, re.IGNORECASE):
            return True
        return False

    def set(
        self,
        query: str,
        embedding: np.ndarray,
        response: str,
        sources: list,
    ) -> None:
        """
        Store a new query-response pair in the semantic cache.
        Skips caching if the query or response contains PII or incident-specific data.
        """
        if self.contains_pii_or_incident_facts(query, response):
            logger.info("Semantic Cache: Skipping caching due to victim PII or sensitive incident facts.")
            return

        with self._lock:
            # Evict oldest if max capacity reached
            if len(self._queries) >= self.max_size:
                self._queries.pop(0)
                self._embeddings.pop(0)
                self._responses.pop(0)

            self._queries.append(query)
            self._embeddings.append(embedding)
            self._responses.append({
                "answer": response,
                "sources": sources,
                "cached_at": time.time(),
            })

    def clear(self) -> None:
        """
        Clear all cached entries.
        """
        with self._lock:
            self._queries.clear()
            self._embeddings.clear()
            self._responses.clear()
            logger.info("Semantic Cache cleared.")
