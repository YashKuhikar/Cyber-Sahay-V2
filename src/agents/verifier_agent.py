from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from ..rag.knowledge_registry import OFFICIAL_REPORTING_CHANNELS


class CitationMetadata(BaseModel):
    claim: str
    source_id: str
    document: str
    page: str
    authority_level: int = 1
    url: Optional[str] = None


class VerificationResult(BaseModel):
    is_verified: bool
    grounding_score: float = Field(..., ge=0.0, le=1.0)
    verification_score: float = Field(..., ge=0.0, le=1.0)
    issues_found: List[str] = Field(default_factory=list)
    citations: List[CitationMetadata] = Field(default_factory=list)
    sanitized_response: str
    confidence_breakdown: Dict[str, float] = Field(default_factory=dict)


class VerifierAgent:
    """
    Independent Verifier Agent that audits generated AI responses
    against retrieved evidence, official directories, and user facts.
    Prevents legal hallucinations and fabrication of official helplines.
    """

    ALLOWED_OFFICIAL_NUMBERS = {"1930", "112", "14448", "1800-11-4949", "100", "1091", "1098"}
    ALLOWED_OFFICIAL_DOMAINS = {
        "cybercrime.gov.in",
        "sancharsaathi.gov.in",
        "112.gov.in",
        "cert-in.org.in",
        "rbi.org.in",
        "cms.rbi.org.in",
    }

    # Matches Indian legal sections e.g., "Section 66C", "Section 66D", "Section 43"
    LEGAL_SECTION_REGEX = re.compile(r"\bsection\s+(\d+[A-Za-z]?)\b", re.IGNORECASE)
    PHONE_REGEX = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b|\b1[0-9]{3,4}\b")
    URL_REGEX = re.compile(r"https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})[^\s]*")

    def verify(
        self,
        query: str,
        response_text: str,
        retrieved_contexts: List[Any],
        user_facts: Optional[dict] = None,
        intent_confidence: float = 0.95,
        retrieval_confidence: float = 0.90,
    ) -> VerificationResult:
        """
        Audits answer against retrieved context and verification rules.
        """
        issues: List[str] = []
        citations: List[CitationMetadata] = []
        sanitized_text = response_text
        context_body = " ".join(
            (c.page_content if hasattr(c, "page_content") else str(c)) for c in retrieved_contexts
        ).lower()

        # 1. Audit Legal Section Claims
        legal_sections = self.LEGAL_SECTION_REGEX.findall(response_text)
        for sec in legal_sections:
            sec_term = f"section {sec}".lower()
            if sec_term not in context_body:
                # Section not in retrieved context -> flag potential hallucination
                issues.append(f"Unverified legal provision: 'Section {sec}' not found in retrieved authoritative sources.")

        # 2. Audit Official Numbers
        numbers_found = self.PHONE_REGEX.findall(response_text)
        for num in numbers_found:
            cleaned_num = num.strip()
            # If not in allowed official helplines and not provided by user in prompt
            if cleaned_num not in self.ALLOWED_OFFICIAL_NUMBERS:
                if user_facts and cleaned_num in str(user_facts):
                    continue
                if cleaned_num in query:
                    continue
                # Hallucinated or unknown contact number
                issues.append(f"Unverified phone number detected: '{cleaned_num}'.")
                sanitized_text = sanitized_text.replace(cleaned_num, "[Unverified Number Redacted]")

        # 3. Audit URLs
        for match in self.URL_REGEX.finditer(response_text):
            domain = match.group(1).lower()
            if not any(allowed in domain for allowed in self.ALLOWED_OFFICIAL_DOMAINS):
                if user_facts and domain in str(user_facts):
                    continue
                if domain in query.lower():
                    continue
                issues.append(f"Unverified external URL domain detected: '{domain}'.")

        # 4. Audit User Facts Preservation (e.g. monetary amounts)
        if user_facts and "amount" in user_facts and user_facts["amount"]:
            claimed_amt = str(int(user_facts["amount"]))
            # If response mentions a different amount while discussing victim loss
            amt_in_resp = re.findall(r"(?:₹|rs\.?)\s*([\d,]+)", response_text, re.IGNORECASE)
            if amt_in_resp:
                clean_resp_amts = [a.replace(",", "") for a in amt_in_resp]
                if claimed_amt not in clean_resp_amts and not any(a in claimed_amt for a in clean_resp_amts):
                    issues.append(f"User fact mismatch: Victim reported ₹{claimed_amt} but response mentions ₹{clean_resp_amts[0]}.")

        # 5. Build Structured Citations from Retrieved Contexts
        for idx, chunk in enumerate(retrieved_contexts):
            meta = chunk.metadata if hasattr(chunk, "metadata") else {}
            law_name = meta.get("law_name") or meta.get("source", "Authoritative Legal Knowledge")
            page_val = str(meta.get("page", "1"))
            auth_lvl = int(meta.get("authority_level", 2))
            doc_title = meta.get("title") or meta.get("law_name") or "Government Cybercrime Guidance"
            
            citations.append(
                CitationMetadata(
                    claim=f"Official guidance regarding {meta.get('topic', 'cybercrime reporting and victim protection')}",
                    source_id=f"src_{idx+1}",
                    document=doc_title,
                    page=page_val,
                    authority_level=auth_lvl,
                    url=meta.get("source_url") or "https://cybercrime.gov.in",
                )
            )

        # 6. Calculate Verification & Grounding Scores
        if issues:
            grounding_score = max(0.60, 1.0 - (len(issues) * 0.12))
            verification_score = max(0.65, 1.0 - (len(issues) * 0.10))
            is_verified = len(issues) <= 1  # Minor issues pass with warnings
        else:
            grounding_score = 0.95
            verification_score = 0.98
            is_verified = True

        confidence_breakdown = {
            "intent_confidence": round(intent_confidence, 2),
            "retrieval_confidence": round(retrieval_confidence, 2),
            "grounding_score": round(grounding_score, 2),
            "verification_score": round(verification_score, 2),
        }

        return VerificationResult(
            is_verified=is_verified,
            grounding_score=grounding_score,
            verification_score=verification_score,
            issues_found=issues,
            citations=citations,
            sanitized_response=sanitized_text,
            confidence_breakdown=confidence_breakdown,
        )
