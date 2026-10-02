from __future__ import annotations

from groq import Groq
from ..config import GROQ_API_KEY, GROQ_MODEL
from .retrieval_agent import RetrievalAgent


class ComplaintAgent:
    """
    AI Agent specializing in drafting formal legal, banking, cyber cell,
    and platform grievance complaint letters for cybercrime victims.
    """

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.retrieval_agent = RetrievalAgent()

    def handle(self, query: str, history: list | None = None) -> dict:
        history = history or []

        # Retrieve relevant laws / procedures if applicable
        rag_result = self.retrieval_agent.handle(query, history=history)
        rag_answer = rag_result.get("answer", "") if isinstance(rag_result, dict) else str(rag_result)
        sources = rag_result.get("sources", []) if isinstance(rag_result, dict) else []

        history_text = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in history[-4:]
        ) if history else "None"

        prompt = f"""
You are CyberSahay's Official Complaint & Application Drafting Specialist.

The user needs a formal complaint letter, dispute application, or grievance notice.

User Request:
{query}

Relevant Indian Cyber Laws & Knowledge Context:
{rag_answer}

Recent Conversation History:
{history_text}

Instructions:
1. Draft a formal, professional, ready-to-use complaint application tailored to the user's specific scenario (e.g. Bank Branch Manager, Cyber Crime Cell SHO, Social Media Grievance Officer, or Telecom Service Provider).
2. Follow standard formal formatting:
   - Date: [Current Date]
   - To: [The Branch Manager / SHO / Grievance Officer, Organization / Police Station Name, Address]
   - Subject: [Clear, concise subject line mentioning incident & transaction/account number]
   - Salutation: [Respected Sir/Madam,]
   - Body:
     * Paragraph 1: Self-introduction, account/phone/identity details, and statement of the grievance.
     * Paragraph 2: Chronological details of the cyber incident (date, time, suspect info, unauthorized amount/actions, transaction IDs).
     * Paragraph 3: Specific relief requested (e.g. immediate transaction freeze, reversal/chargeback under RBI Zero Liability circular, FIR registration, content takedown, account restoration).
     * Paragraph 4: Legal references (e.g. Information Technology Act 2000, Bharatiya Nyaya Sanhita, RBI Master Directions on Limiting Liability).
   - Enclosures / Attachments Checklist: (e.g. Bank statement, screenshot evidence, copy of identity proof, transaction receipts).
   - Sign-off: [Yours faithfully, Name, Contact details, Signature placeholder].
3. Use clear placeholders like [Your Name], [Account Number], [Transaction ID] where specific information is missing so the user can easily fill them.
4. Keep the tone assertive, respectful, and legally sound.
"""

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.2,
                max_completion_tokens=1000,
            )
            draft = response.choices[0].message.content or ""
            return {
                "answer": draft.strip(),
                "response": draft.strip(),
                "sources": sources,
            }
        except Exception as e:
            err_msg = f"Unable to generate complaint letter at this moment: {str(e)}"
            return {
                "answer": err_msg,
                "response": err_msg,
                "sources": sources,
            }