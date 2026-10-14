# CyberSahay: AI-Powered Cybercrime Victim Assistance & Legal FIR Generator

**Final Year Engineering Capstone Project**  
*A multi-agent, Hybrid-RAG powered legal emergency and cybercrime complaint assistant designed for Indian citizens.*

---

## 1. Project Overview

**CyberSahay** is not a generic chatbot. It is a specialized, victim-centric cybercrime incident response application. When an individual suffers from financial fraud, identity theft, unauthorized account takeovers, sextortion, or ransomware, the system immediately:

1. **Assesses Emergency & Urgency**: Provides deterministic first-aid containment advice (e.g. 1930 National Cyber Crime Reporting Portal helpline, freezing bank accounts, preserving evidence).
2. **Maintains Conversational Memory**: Captures incident facts (amounts, timestamps, transaction IDs, phone numbers, UPI handles) during normal chat without repetitive interrogation.
3. **Preserves Digital Evidence**: Ingests screenshots and PDF receipts, calculates cryptographic SHA-256 hashes, runs OCR text extraction, reconstructs chronological timelines, and analyzes legal risks.
4. **Validates & Grounds AI Responses**: Audits generated advice against retrieved Indian cyber laws (BNS, IT Act 2000, RBI Customer Protection Circulars) using an independent Verifier Agent to prevent hallucinations.
5. **Generates Official FIR Complaints**: Compiles a formal police complaint draft in text and downloadable PDF format, ready for submission to local police stations or https://cybercrime.gov.in.

---

## 2. System Architecture & Component Map

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           Flutter Mobile / Web Frontend                        │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │ REST / SSE HTTP APIs
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                              FastAPI Backend                                   │
│  - JWT Authentication & RBAC        - Input Sanitizer & DPDP Act Data Masker   │
│  - In-Memory Token Bucket Limiter   - IDOR Session & Record Ownership Guards   │
└───────┬───────────────────────┬────────────────────────┬───────────────────────┘
        │                       │                        │
┌───────▼─────────────┐ ┌───────▼──────────────┐ ┌───────▼──────────────────────┐
│  Multi-Agent System │ │    Hybrid RAG V2     │ │   Evidence & OCR Pipeline    │
│ - SafetyAgent       │ │ - ChromaDB Vector DB │ │ - EasyOCR (Lazy-Loaded)      │
│ - CoordinatorAgent  │ │ - BM25 Keyword Index │ │ - PyMuPDF Native Text Parser │
│ - AdvisorAgent      │ │ - Cross-Encoder Rank │ │ - SHA-256 Immutability Hash  │
│ - FIROrchestrator   │ │ - Semantic Cache     │ │ - Timeline Builder           │
│ - VerifierAgent     │ │ - Multilingual NLP   │ │ - Legal Document Analyzer    │
└───────┬─────────────┘ └──────────────────────┘ └──────────────────────────────┘
        │
┌───────▼────────────────────────────────────────────────────────────────────────┐
│                        Data Persistence (SQLite & File Store)                  │
│ - Users, ChatSessions, ChatMessages, FIRRecords, EvidenceRecords, DocAnalyses  │
│ - uploads/evidence/ (cryptographically hashed raw user files)                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLite (SQLAlchemy ORM)
- **Vector Database**: ChromaDB
- **Keyword Retrieval**: BM25 (Rank-BM25)
- **Embeddings**: BAAI/bge-small-en-v1.5
- **LLM Engine**: Groq API (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`)
- **OCR Engine**: EasyOCR + PyMuPDF (`fitz`)
- **PDF Generation**: ReportLab
- **Security & Auth**: PyJWT, Passlib (bcrypt), RateLimiter, InputSanitizer

---

## 4. Key Architectural Features

### A. Pre-RAG Safety Triage & Containment
High-severity cyber attacks (active financial loss, sextortion blackmail, ransomware, device theft) bypass generic chatbot responses and invoke `SafetyAgent`, providing deterministic emergency actions within milliseconds.

### B. Conversation History Reuse (FIR Workflow)
When users discuss their incident in chat and subsequently request an FIR draft:
1. `FIRInformationExtractor` extracts all known facts from the multi-turn chat history.
2. The user is presented with an extracted facts checklist.
3. The system inquires **only** for missing mandatory details.
4. It performs strict typing (Luhn IMEI validation, date/time/amount normalization).
5. It requires explicit user confirmation before compiling the final FIR complaint.

### C. Independent Verifier Agent & Zero-Grounding Guard
`VerifierAgent` audits LLM responses against raw retrieved knowledge chunks:
- Validates cited legal sections (e.g. IT Act Section 66C/66D).
- Redacts unverified phone numbers or URLs not present in official registries.
- When knowledge base is offline or retrieved context is empty, the grounding score drops to **0.0** and verification fails, preventing hallucinated advice.

### D. Evidence Preservation & OCR Pipeline
- Preserves raw evidence files under `uploads/evidence/` with SHA-256 integrity verification.
- Employs lazy EasyOCR loading to guarantee fast backend startup.
- Reconstructs chronological event timelines from parsed transaction timestamps.
- Sandboxes untrusted OCR document text with instruction delimiters to eliminate prompt injection attacks.

---

## 5. Local Setup & Execution Guide

### Prerequisites
- Python 3.10+ (Python 3.11 or 3.13 tested)
- A free Groq API key from [https://console.groq.com/keys](https://console.groq.com/keys)

### Step 1: Clone & Navigate to Backend
```powershell
cd Backend
```

### Step 2: Configure Environment
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and set your `GROQ_API_KEY`:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
JWT_SECRET_KEY=a_very_secure_random_key_with_at_least_32_characters
```

### Step 3: Start the Backend Server
```powershell
$env:PYTHONPATH="."
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation (Swagger UI) is available at:  
👉 **http://localhost:8000/docs**

---

## 6. Running Automated Test Suites

The backend features a comprehensive offline automated test suite verifying all architectural requirements:

```powershell
# Set Python path
$env:PYTHONPATH="."

# 1. Run Master Engineering Submission Test Suite
python tests/test_master_submission.py

# 2. Run Comprehensive V2 Verification Suite (10 Tests)
python tests/test_cybersahay_v2.py

# 3. Run FIR Orchestrator End-to-End Suite
python tests/test_fir_orchestrator_complete.py

# 4. Run Conversation-to-FIR Fact Reuse Suite
python tests/test_conversation_fir_reuse.py

# 5. Run Date & Entity Normalization Suite
python tests/test_fir_date_validation.py
```

All test suites execute offline without external network dependencies and run cleanly against SQLite.

---

## 7. Submission Demo Checklist

During final-year project demonstration, follow this step-by-step presentation flow:

1. **Authentication & IDOR Shield**:
   - Register user A and user B via `/auth/register`.
   - Show that user B cannot inspect, delete, or download user A's chat sessions, FIR drafts, or PDF reports (blocked with 401/403).
2. **Emergency Financial Fraud Consultation**:
   - Send: `"Someone called pretending to be bank staff. I gave OTP and lost ₹25,000 on Google Pay at 7 PM yesterday. UTR is 123456789012."`
   - Show deterministic safety triage: 1930 emergency helpline, bank freeze guidance, and zero-liability timeline.
3. **Seamless FIR Drafting Without Repetition**:
   - Call `/fir/start`.
   - Observe that incident type, amount (₹25,000), UTR, and timestamp are **already extracted**.
   - Observe that the orchestrator only asks for genuinely missing fields (e.g. complainant name and bank).
   - Reply with complainant name and bank name, then confirm with `"Confirm"`.
   - Download the generated formal police complaint PDF from `/fir/download-pdf/{session_id}`.
4. **Evidence Upload & Cryptographic Hashing**:
   - Upload a payment receipt screenshot via `/ocr/`.
   - Demonstrate SHA-256 hash preservation, extracted timeline events, and legal risk classification.
5. **Verifier Grounding & Hallucination Defense**:
   - Show verifier score breakdown (`grounding_score`, `verification_score`, and official citations).
