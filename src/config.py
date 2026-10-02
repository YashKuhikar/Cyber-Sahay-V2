from __future__ import annotations

import os

from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# ---------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY not found. Please add it to your .env file."
    )

# ---------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------

GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_EXTRACTION_MODEL = "openai/gpt-oss-20b"
TEMPERATURE = 0.2

MAX_TOKENS = 2048