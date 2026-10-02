from __future__ import annotations

from typing import Any, Dict, List

import os

from groq import Groq

from src.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    TEMPERATURE,
    MAX_TOKENS,
)

from .hybrid_retriever import HybridRetriever



class RAGPipeline:
    """
    Main orchestration class for the Hybrid RAG system.

    Responsibilities:
        - Retrieve relevant documents
        - Build prompt
        - Send prompt to the LLM
        - Return the generated answer
    """

    def __init__(
        self,
        retriever: HybridRetriever,
    ):
        """
        Initialize the RAG pipeline.

        Args:
            retriever: Initialized HybridRetriever instance.
        """

        self.retriever = retriever

        # Initialize the Groq client once
        self.client = Groq(
            api_key=GROQ_API_KEY,
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant document chunks for a user query.

        Args:
            query: User's natural language query.
            top_k: Number of document chunks to retrieve.

        Returns:
            A list of retrieved document chunks with their metadata.
        """
        
        return self.retriever.retrieve(
            query=query,
            final_k=top_k,
        )

    def build_prompt(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        history: list | None = None,
    ) -> str:
        """
        Build the prompt for the language model using the retrieved context.

        Args:
            query: User's natural language query.
            contexts: Retrieved document chunks.

        Returns:
            A formatted prompt string.
        """

        context_text = "\n\n".join(
            chunk.page_content
            for chunk in contexts
        )     
        history_text = ""

        if history:
            history_text = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in history
        )  

        prompt = f"""
You are CyberSahay, an AI assistant specializing in Indian cybercrime
awareness, Indian cyber laws, Indian government procedures, and digital safety.

IMPORTANT JURISDICTION & GUIDANCE RULES:
- CyberSahay is designed primarily for users in India.
- Use Indian legal and government context (e.g., Information Technology Act 2000, Bharatiya Nyaya Sanhita / BNS, RBI guidelines, CERT-In, 1930 Helpline).
- Use the provided knowledge context as the primary source of reference.
- For definitions, conceptual explanations, or awareness questions (e.g., "What is phishing?", "Explain ransomware", "What is cyber stalking?"), provide a clear, accurate, and structured explanation including warning signs and prevention steps.
- Do NOT invent fake laws, fabricated legal sections, non-existent phone numbers, or fake URLs.
- If a question is completely unrelated to cybercrime, legal aid, or digital safety and has no basis in the knowledge context, politely state:
"I couldn't find this information in the knowledge base."

-----------------------
Conversation History:

{history_text}

-----------------------
Knowledge Context:

{context_text}

-----------------------
Current User Question:

{query}

Instructions:
- Answer the question directly and professionally.
- For definition or awareness questions, give a clear explanation and key safety signs.
- For procedural or legal questions, give structured, actionable steps under Indian context.
- Format the response with clean markdown headings and bullet points where helpful.
- Do not mention the internal retrieval process.

Answer:
"""

        return prompt.strip()

    def generate(
        self,
        prompt: str,
    ) -> str:
        """
        Generate a response from the language model.

        Args:
            prompt: The formatted prompt to send to the LLM.

        Returns:
            The generated response.
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
                temperature=TEMPERATURE,
                max_completion_tokens=MAX_TOKENS,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise RuntimeError(
                f"Failed to generate response from Groq: {e}"
            ) from e
    def generate_stream(
        self,
        prompt: str,
    ):
        """
        Stream response tokens from Groq LLM.
        """
        try:
            return self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=TEMPERATURE,
                max_completion_tokens=MAX_TOKENS,
                stream=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to stream response from Groq: {e}"
            ) from e

    def build_sources(
        self,
        contexts,
    ) -> list[dict]:
        """
        Build structured source information from retrieved documents.
        """
        unique_sources = {}
        for chunk in contexts:
            source = os.path.basename(
                chunk.metadata.get("source", "Unknown")
            )
            page = chunk.metadata.get("page", "N/A")
            key = f"{source}|{page}"
            if key not in unique_sources:
                unique_sources[key] = {
                    "title": source,
                    "page": page,
                }
        return list(unique_sources.values())

    def ask(
        self,
        query: str,
        history: list | None = None,
        top_k: int = 5,
    ) -> dict:
        """
        Execute the complete RAG pipeline.

        Returns:
            {
                "answer": "...",
                "sources": [...]
            }
        """
        clean_query = query.strip()
        contexts = self.retrieve(
            query=clean_query,
            top_k=top_k,
        )
        prompt = self.build_prompt(
            query=clean_query,
            contexts=contexts,
            history=history,
        )
        response = self.generate(prompt)
        sources = self.build_sources(contexts)

        return {
            "answer": response,
            "sources": sources,
        }

    def ask_stream(
        self,
        query: str,
        history: list | None = None,
        top_k: int = 5,
    ):
        """
        Execute RAG retrieval and return Groq token stream and sources.
        """
        clean_query = query.strip()
        contexts = self.retrieve(
            query=clean_query,
            top_k=top_k,
        )
        prompt = self.build_prompt(
            query=clean_query,
            contexts=contexts,
            history=history,
        )
        stream = self.generate_stream(prompt)
        sources = self.build_sources(contexts)
        return stream, sources