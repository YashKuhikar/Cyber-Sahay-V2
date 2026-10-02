from __future__ import annotations

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.db import init_db
from .exceptions.handlers import register_exception_handlers
from .routes.auth import router as auth_router
from .routes.chat import router as chat_router
from .routes.emergency import router as emergency_router
from .routes.fir import router as fir_router
from .routes.ocr import router as ocr_router
from .security.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite / SQLAlchemy database tables on startup
    init_db()
    yield


app = FastAPI(
    title="CyberSahay AI - National Cybercrime Assistance API",
    version="1.0.0",
    description=(
        "Production-grade Agentic Hybrid RAG and Emergency Advisory Backend for Cybercrime Victims. "
        "Protected by OWASP Security Headers, Sliding-Window Rate Limiting, File Magic-Byte Validation, "
        "and DPDP-Act Data Privacy Masking."
    ),
    lifespan=lifespan,
)

# 1. Security Headers Middleware (OWASP protection against clickjacking, sniffing, XSS)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Configurable CORS Middleware
allowed_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
if allowed_origins_raw.strip():
    allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Global Exception Handlers
register_exception_handlers(app)

# 4. Mount Routers
app.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication & Users"],
)

app.include_router(
    chat_router,
    prefix="/chat",
    tags=["AI Chat & Hybrid RAG Advisory"],
)

app.include_router(
    fir_router,
    prefix="/fir",
    tags=["FIR Generation & PDF Export"],
)

app.include_router(
    ocr_router,
    prefix="/ocr",
    tags=["Document OCR & Evidence Verification"],
)

app.include_router(
    emergency_router,
    prefix="/emergency",
    tags=["Emergency Victim Advisory & Helplines"],
)


@app.get("/", tags=["System"])
def root():
    return {
        "success": True,
        "message": "CyberSahay API is running in production-ready mode with enterprise security.",
        "docs": "/docs",
        "health": "/health",
        "security_features": [
            "Sliding-Window Rate Limiting (Brute-Force & DoS defense)",
            "OWASP Security Headers (X-Frame-Options, HSTS, nosniff, XSS)",
            "Magic-Byte File Upload & Payload Size Inspection (10MB limit)",
            "Input Sanitization (XSS & Injection defense)",
            "DPDP Act Sensitive Data Masking (Aadhaar & Card numbers)",
        ],
        "core_features": [
            "User Authentication (JWT & SQLite Persistence)",
            "Multi-Agent Hybrid RAG (BNS & IT Act 2000)",
            "Automated FIR & Police Complaint PDF Generation",
            "Document OCR & Risk Assessment",
            "Emergency Golden-Hour Triage & Helplines (1930/112/CEIR)",
        ],
    }


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "CyberSahay API",
        "version": "1.0.0",
    }