from __future__ import annotations

from ..config import GROQ_API_KEY, GROQ_MODEL, MAX_TOKENS
from groq import Groq

from ..security.prompt_guard import wrap_untrusted_content
from .retrieval_agent import RetrievalAgent


class AdvisorAgent:

    def __init__(self):

        self.client = Groq(
            api_key=GROQ_API_KEY,
        )

        self.retrieval_agent = RetrievalAgent()

    def _build_advisor_prompt(
        self,
        message: str,
        category: str,
        context_text: str,
        history_text: str,
    ) -> str:
        safe_message = wrap_untrusted_content("user_question", message)
        safe_context = wrap_untrusted_content("retrieved_knowledge_base", context_text)

        return f"""
You are CyberSahay's Legal/Cyber Safety Advisor.

User's question:
{safe_message}

Category:
{category}

Relevant information from CyberSahay's knowledge base:
{safe_context}

Conversation history:
{history_text}

Give the user practical, complete, and easy-to-understand guidance.

Rules:
- Do NOT create an FIR.
- Do NOT ask FIR form questions.
- Do NOT pretend to be a lawyer.
- Give guidance grounded in the provided knowledge base and Indian cyber safety best practices.
- Do NOT add facts, laws, procedures, phone numbers, URLs,
  authorities, or reporting methods that are fabricated.
- Do not provide foreign-country-specific procedures unless requested.

Response style:
- Respond naturally like a helpful, empathetic cyber safety expert.
- For urgent situations (financial fraud, blackmail), prioritize immediate containment actions first (e.g. call 1930, notify bank helpline, freeze cards).
- Provide a complete, fully finished answer. Never cut off mid-sentence.
- Use numbered steps when explaining a procedure.
- Use simple, clear language with markdown bullet points.

FIR WORKFLOW RULES:
- Do not start the FIR form merely because a cybercrime occurred.
- If filing an FIR is an appropriate or necessary step according to the
  knowledge base, you may recommend filing an FIR as part of the advice.
- If the user explicitly says they want to file an FIR, recommend initiating the FIR workflow.

Return only the helpful advisory answer.
""".strip()

    def handle(
        self,
        message: str,
        category: str = "general",
        history: list | None = None,
    ) -> dict:

        history = history or []

        # Retrieve raw chunks directly to avoid double LLM summarization call
        clean_message = message.strip()
        contexts = self.retrieval_agent.ai.pipeline.retrieve(
            query=clean_message,
            top_k=5,
        )
        sources = self.retrieval_agent.ai.pipeline.build_sources(contexts)

        context_text = "\n\n".join(
            chunk.page_content for chunk in contexts
        ) if contexts else "No direct database chunks retrieved."

        history_text = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in history
        ) if history else "None"

        prompt = self._build_advisor_prompt(
            message=clean_message,
            category=category,
            context_text=context_text,
            history_text=history_text,
        )

        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
            max_completion_tokens=MAX_TOKENS,
        )

        answer = response.choices[0].message.content or ""
        if not answer:
            return {
                "response": (
                    "I’m sorry, I could not generate advice "
                    "right now."
                ),
                "sources": sources,
            }

        return {
            "response": answer.strip(),
            "sources": sources,
            "contexts": [getattr(c, "page_content", str(c)) for c in contexts] if contexts else [],
        }

    def handle_stream(
        self,
        message: str,
        category: str = "general",
        history: list | None = None,
    ):
        """
        Stream LLM tokens in real time directly from Groq.
        """
        history = history or []
        clean_message = message.strip()
        contexts = self.retrieval_agent.ai.pipeline.retrieve(
            query=clean_message,
            top_k=5,
        )
        sources = self.retrieval_agent.ai.pipeline.build_sources(contexts)

        context_text = "\n\n".join(
            chunk.page_content for chunk in contexts
        ) if contexts else "No direct database chunks retrieved."

        history_text = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in history
        ) if history else "None"

        prompt = self._build_advisor_prompt(
            message=clean_message,
            category=category,
            context_text=context_text,
            history_text=history_text,
        )

        stream = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
            max_completion_tokens=MAX_TOKENS,
            stream=True,
        )
        return stream, sources