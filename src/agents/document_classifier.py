from __future__ import annotations

import json

from groq import Groq

from ..utils.helpers import safe_json_loads
from ..config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)


class DocumentClassifier:
    """
    Classifies OCR extracted documents using Groq.
    """

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)

    def classify(self, text: str) -> dict:

        prompt = f"""
You are an expert document classification AI.

Your task is to classify the OCR extracted text into ONE document type.

Possible document types:

- Aadhaar Card
- PAN Card
- Passport
- Driving License
- Police FIR
- Police Complaint
- Court Notice
- Bank Statement
- WhatsApp Chat
- Email
- Scam Screenshot
- Educational Document
- Government Circular
- Invoice
- Unknown

Return ONLY valid JSON.

Example:

{{
    "document_type": "Police FIR",
    "language": "English",
    "confidence": 0.98
}}

OCR Text:

{text}
"""

        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            max_completion_tokens=200,
        )

        try:
            raw_answer = response.choices[0].message.content or ""
            answer = raw_answer.strip()
        except Exception:
            answer = ""

        default_classification = {
            "document_type": "Unknown",
            "language": "English",
            "confidence": 0.5,
        }

        result = safe_json_loads(answer, default=default_classification)
        result.setdefault("document_type", "Unknown")
        result.setdefault("language", "English")
        result.setdefault("confidence", 0.7)

        return result