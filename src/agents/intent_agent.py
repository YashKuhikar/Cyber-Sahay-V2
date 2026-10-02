from __future__ import annotations

import json

from groq import Groq

from ..utils.helpers import safe_json_loads
from ..schemas import response
from ..config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    TEMPERATURE,
)


class IntentAgent:
    """
    Detects the user's intent using Groq.
    """

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)

    def detect(self, query: str) -> dict:
        prompt = f"""
You are CyberSahay's Intent Classification Agent.

Your task is to understand the user's request and determine:

1. intent
2. category
3. workflow
4. language
5. confidence
6. whether Hybrid RAG knowledge is required

-------------------------
INTENTS

1. advice
- User wants guidance, advice, explanation, precautions,
  next steps, rights, or information about a legal/cyber issue.
- User is NOT explicitly asking to file or generate a complaint/FIR.

Examples:
- What should I do if I get a phishing message?
- My UPI money was stolen, what should I do?
- My phone was stolen, what are my options?
- How can I report phishing?
- Explain what I should do after an OTP fraud.

2. complaint
- User explicitly wants to write a complaint, application,
  complaint letter, or email.

Examples:
- Write a complaint to my bank.
- Generate an application to the bank.
- Help me write a complaint letter.

3. fir
- User explicitly wants to file, create, generate, draft,
  or prepare an FIR / police complaint.

Examples:
- I want to file an FIR for my stolen phone.
- Generate an FIR for UPI fraud.
- Help me write a police complaint.
- I want to report this to the police.

4. greeting
- hi
- hello
- good morning
- namaste

5. unknown
- The request does not fit the above categories.
-------------------------
WORKFLOWS

Choose ONLY ONE workflow.

1. advisor
Use AdvisorAgent for advice, guidance, legal information,
cyber safety information, rights, precautions, and next steps.

Examples:
- What should I do if someone stole my phone?
- What should I do after a phishing attack?
- My UPI money was stolen. What should I do?
- Explain cyberbullying.
- What are my rights?

2. fir
Use FIRAgent only when the user explicitly wants
to create, generate, draft, or file an FIR/police complaint.

Examples:
- I want to file an FIR for my stolen phone.
- Generate an FIR for mobile theft.
- Help me prepare a police complaint for phishing.
- I want to report this crime to the police.

3. complaint
Use ComplaintAgent when the user wants a non-FIR complaint,
application, letter, or email.

Examples:
- Write a complaint to my bank.
- Draft an email to my bank.
- Write an application to the cybercrime department.

4. greeting
Use greeting response.

5. unknown
Use when the request cannot be classified.
-------------------------
POSSIBLE CATEGORIES

- mobile_theft
- upi_fraud
- phishing
- otp_fraud
- cyberbullying
- identity_theft
- ransomware
- social_media
- bank_complaint
- legal_information
- general

-------------------------
-------------------------
-------------------------
WORKFLOW DECISION RULES

Determine the workflow from what the USER WANTS TO DO.

A. RAG / RETRIEVAL

Choose:

intent = "retrieval"
workflow = "rag"

when the user is asking for GENERAL KNOWLEDGE or EXPLANATION.

Examples:
- What is phishing?
- Explain phishing.
- What is OTP fraud?
- What is cyberbullying?
- What is ransomware?
- How does phishing work?
- What are the signs of phishing?
- Explain Section 66C.
- What is the Information Technology Act?

IMPORTANT:
A general question about a cybercrime is NOT an advice request.

B. ADVISOR

Choose:

intent = "advice"
workflow = "advisor"

ONLY when the user describes their own situation and asks what to do,
how to protect themselves, what steps to take, or how to respond.

Examples:
- I was a victim of phishing. What should I do?
- I clicked a phishing link. What should I do?
- Someone hacked my account. How can I protect myself?
- My bank account may be compromised. What should I do?

C. FIR

Choose:

intent = "complaint"
workflow = "fir"

ONLY when the user explicitly wants to file an FIR, make a police complaint,
or report the incident to police.

Examples:
- I want to file an FIR for mobile theft.
- Generate an FIR for this incident.
- I want to report this to the police.

D. COMPLAINT

Choose:

intent = "complaint"
workflow = "complaint"

when the user wants a non-FIR complaint, letter, application, or email.

Examples:
- Write a complaint to my bank.
- Draft an application to the bank.
- Write an email to the company.

E. FOLLOW-UP

If there is already an active workflow for the session, keep using that
workflow unless the user explicitly starts a different task.

Examples:

"I was a victim of phishing. What should I do?"
→ advisor

"Explain this in detail."
→ advisor

"What is phishing?"
→ rag

"Explain phishing."
→ rag

PRIORITY RULE:

If the user asks "what is", "what are", "explain", "define", "how does",
or "why does" and is not describing a personal incident requiring action,
choose workflow = "rag".

Do NOT choose advisor merely because the topic is a cybercrime.
Only change workflow when the user clearly starts a new task.

Example:

{{
    "intent": "advice",
    "category": "phishing",
    "workflow": "advisor",
    "language": "English",
    "confidence": 0.97,
    "requires_rag": true
}}

FIR example:

{{
    "intent": "complaint",
    "category": "mobile_theft",
    "workflow": "fir",
    "language": "English",
    "confidence": 0.97,
    "requires_rag": false
}}

Complaint example:

{{
    "intent": "complaint",
    "category": "bank_complaint",
    "workflow": "complaint",
    "language": "English",
    "confidence": 0.96,
    "requires_rag": false
}}

-------------------------
User Query:

{query}
"""

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an intent classification agent for CyberSahay. "
                            "You must respond ONLY with a valid JSON object. Do not include markdown or reasoning."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,
                max_completion_tokens=350,
                response_format={
                    "type": "json_object"
                },
            )
            raw_answer = response.choices[0].message.content or ""
            answer = raw_answer.strip()
        except Exception:
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    temperature=0,
                    max_completion_tokens=350,
                )
                raw_answer = response.choices[0].message.content or ""
                answer = raw_answer.strip()
            except Exception:
                answer = ""

        default_result = {
            "intent": "advice",
            "category": "general",
            "workflow": "advisor",
            "language": "English",
            "confidence": 0.8,
            "requires_rag": True,
        }

        result = safe_json_loads(answer, default=default_result)

        if not result or not isinstance(result, dict):
            result = default_result

        result.setdefault("intent", "advice")
        result.setdefault("category", "general")
        result.setdefault("workflow", "advisor")
        result.setdefault("confidence", 0.9)
        result.setdefault("language", "English")

        return result