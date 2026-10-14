from __future__ import annotations

import json

from groq import Groq

from ..security.prompt_guard import wrap_untrusted_content
from ..utils.helpers import safe_json_loads
from ..config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)


class DocumentAnalyzer:
    """
    Analyzes OCR extracted documents.
    """

    def __init__(self):
        self.client = Groq(
            api_key=GROQ_API_KEY,
        )

    def analyze(
        self,
        document_type: str,
        text: str,
    ) -> dict:

        safe_text = wrap_untrusted_content("untrusted_document_ocr", text)

        prompt = f"""
You are CyberSahay's AI Document Analyzer.

Document Type:
{document_type}

OCR Text:
{safe_text}

Analyze this document and provide:

1. A concise summary.
2. Important points in bullet form.
3. Risk level (Low, Medium, High).
4. Recommended actions for the user.

Determine whether retrieving additional knowledge from CyberSahay's Hybrid RAG knowledge base would improve the response.

If the document requires legal guidance, cyber laws,
government procedures, or official references:

- Set "requires_rag": true

- Generate a concise and focused search query in "rag_query"
  that can retrieve the most relevant documents from
  CyberSahay's knowledge base.

CyberSahay's knowledge base contains:

- Bharatiya Nyaya Sanhita (BNS)
- Information Technology Act, 2000
- I4C Guidelines
- CERT-In Advisories
- Government Cybercrime SOPs
- Cybercrime Reporting Procedures
- Citizen Awareness Documents

The search query should:

- Use Indian legal and cybercrime terminology.
- Contain important legal keywords.
- Avoid unnecessary details.
- Be suitable for semantic search.

If the uploaded document refers to another country,
generate the closest equivalent query for the Indian legal context.

If additional knowledge is NOT required:

- Set "requires_rag": false
- Keep "rag_query": ""

Do NOT explain your reasoning.

Do NOT include markdown.

Return ONLY valid JSON.

{{
    "summary": "",

    "important_points": [
        ""
    ],

    "risk_level": "Low",

    "recommended_actions": [
        ""
    ],

    "requires_rag": false,

    "rag_query": ""
}}
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
            max_completion_tokens=1200,
        )

        answer = response.choices[0].message.content.strip()

        default_analysis = {
            "summary": "Document analyzed successfully.",
            "important_points": ["Document processed by CyberSahay OCR."],
            "risk_level": "Low",
            "recommended_actions": ["Review document details and preserve evidence."],
            "requires_rag": False,
            "rag_query": "",
        }

        result = safe_json_loads(answer, default=default_analysis)

        result.setdefault("summary", default_analysis["summary"])
        result.setdefault("important_points", default_analysis["important_points"])
        result.setdefault("risk_level", "Low")
        result.setdefault("recommended_actions", default_analysis["recommended_actions"])
        result.setdefault("requires_rag", False)
        result.setdefault("rag_query", "")

        return result