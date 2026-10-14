from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory for the backend
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the .env file in Backend root
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ---------------------------------------------------------------------
# Environment Mode
# ---------------------------------------------------------------------
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower().strip()
IS_PRODUCTION = ENVIRONMENT == "production"

# ---------------------------------------------------------------------
# API Keys & LLM Configuration
# ---------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
IS_GROQ_CONFIGURED = bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("your_groq"))

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_EXTRACTION_MODEL = os.getenv("GROQ_EXTRACTION_MODEL", "openai/gpt-oss-20b")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))

# ---------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cybersahay.db")

# ---------------------------------------------------------------------
# JWT Authentication Security
# ---------------------------------------------------------------------
_DEV_SECRET = "cybersahay-dev-secret-key-replace-in-production-2026"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", _DEV_SECRET).strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", str(24 * 7)))

if IS_PRODUCTION and (not JWT_SECRET_KEY or JWT_SECRET_KEY == _DEV_SECRET or len(JWT_SECRET_KEY) < 32):
    raise ValueError(
        "CRITICAL SECURITY CONFIGURATION ERROR: A strong JWT_SECRET_KEY (at least 32 characters) "
        "must be configured in environment variables for production mode."
    )

# ---------------------------------------------------------------------
# CORS & Networking
# ---------------------------------------------------------------------
CORS_ALLOWED_ORIGINS_RAW = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000"
)
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in CORS_ALLOWED_ORIGINS_RAW.split(",") if origin.strip()
]

# ---------------------------------------------------------------------
# Knowledge Base & Retrieval Paths
# ---------------------------------------------------------------------
CHROMA_PERSIST_DIR = str(BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "chroma_db"))
BM25_PERSIST_DIR = str(BASE_DIR / os.getenv("BM25_PERSIST_DIR", "bm25_store"))
KNOWLEDGE_BASE_DIR = str(BASE_DIR / os.getenv("KNOWLEDGE_BASE_DIR", "Knowledge-Base"))

# ---------------------------------------------------------------------
# File Uploads & OCR Configuration
# ---------------------------------------------------------------------
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))  # 10 MB limit
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "20"))
EVIDENCE_UPLOAD_DIR = str(BASE_DIR / os.getenv("EVIDENCE_UPLOAD_DIR", "uploads/evidence"))