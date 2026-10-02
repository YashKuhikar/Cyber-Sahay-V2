from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agents.ocr_agent import OCRAgent
from ..agents.response_formatter import ResponseFormatter
from ..agents.shared_agents import coordinator
from ..database.db import get_db
from ..database.models import DocumentAnalysisRecord, EvidenceRecord, User
from ..memory.case_profile_v2 import update_case_profile_v2
from ..memory.shared_memory import memory
from ..ocr.timeline_builder import build_evidence_timeline
from ..security.file_validator import validate_uploaded_file
from ..security.rate_limiter import rate_limit
from ..security.sanitizer import sanitize_input
from ..services.auth_service import get_current_user, get_optional_user

router = APIRouter()
ocr_agent = OCRAgent()

EVIDENCE_DIR = Path("uploads/evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Schemas
# ==========================================================

class DocumentAnalysisResponseItem(BaseModel):
    id: int
    filename: str
    document_type: str
    confidence: float
    language: str
    risk_level: str
    summary: str
    important_points: List[str]
    recommended_actions: List[str]
    legal_guidance: Optional[dict | str] = None
    created_at: datetime


def success_response(message: str, data: dict):
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.now(),
    }


# ==========================================================
# Document OCR / Evidence Extraction & Timeline
# ==========================================================

@router.post(
    "/",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))],
    summary="Upload image or PDF for OCR extraction, SHA-256 hash preservation, timeline reconstruction & legal advice (Rate Limit: 10/min)",
)
async def extract_text(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    saved_filepath = None
    try:
        suffix, file_size = await validate_uploaded_file(file)

        # 1. Compute SHA-256 hash of original file without modification
        file_bytes = await file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        await file.seek(0)

        # 2. Store original evidence securely separate from OCR output
        file_uuid = str(uuid.uuid4())
        stored_filename = f"{file_uuid}{suffix}"
        saved_filepath = EVIDENCE_DIR / stored_filename

        with open(saved_filepath, "wb") as buffer:
            buffer.write(file_bytes)

        # 3. Perform OCR extraction & analysis
        result = ocr_agent.analyze_document(str(saved_filepath))

        classification = result["classification"]
        analysis = result["analysis"]
        information = result["information"]
        legal_guidance = result["legal_guidance"]
        ocr_text = result["ocr_text"]

        # 4. Reconstruct evidence timeline
        timeline = build_evidence_timeline(ocr_text)

        # 5. Persist original evidence record with SHA-256 hash in DB
        evidence_rec = EvidenceRecord(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            file_id=file_uuid,
            original_filename=file.filename or "evidence_file",
            file_path=str(saved_filepath),
            file_hash=file_hash,
            file_size=file_size,
            mime_type=file.content_type,
            ocr_text=ocr_text,
            extracted_entities_json=json.dumps(information),
            timeline_events_json=json.dumps(timeline),
        )
        db.add(evidence_rec)

        # 6. Persist analysis summary to DB
        doc_record = DocumentAnalysisRecord(
            user_id=current_user.id if current_user else None,
            filename=file.filename or "uploaded_document",
            document_type=classification.get("document_type", "Unknown"),
            confidence=float(classification.get("confidence", 0.0)),
            language=classification.get("language", "English"),
            risk_level=analysis.get("risk_level", "Low"),
            summary=analysis.get("summary", ""),
            important_points_json=json.dumps(analysis.get("important_points", [])),
            recommended_actions_json=json.dumps(analysis.get("recommended_actions", [])),
            legal_guidance_json=json.dumps(legal_guidance) if legal_guidance else None,
            ocr_text=ocr_text,
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

        # If a session_id was passed, synchronize with Case Profile V2
        if session_id:
            profile_v2 = memory.get_case_profile_v2(session_id)
            profile_v2 = update_case_profile_v2(
                profile_v2,
                information,
                source="ocr",
                confidence=float(classification.get("confidence", 0.9)),
                confirmed=False,
            )
            memory.set_case_profile(session_id, profile_v2)

        return success_response(
            "Document processed and evidence preserved successfully.",
            {
                "analysis_id": doc_record.id,
                "file_id": file_uuid,
                "file_hash": file_hash,
                "filename": file.filename,
                "document_type": classification.get("document_type", "Unknown"),
                "confidence": classification.get("confidence", 0.0),
                "language": classification.get("language", "English"),
                "summary": analysis.get("summary", ""),
                "important_points": analysis.get("important_points", []),
                "risk_level": analysis.get("risk_level", "Low"),
                "recommended_actions": analysis.get("recommended_actions", []),
                "information": information,
                "timeline": timeline,
                "legal_guidance": legal_guidance,
                "ocr_text": ocr_text,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print("OCR ERROR:", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to process the uploaded document: {str(e)}",
        )


# ==========================================================
# OCR -> FIR with Fact Confirmation
# ==========================================================

@router.post(
    "/fir",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))],
    summary="Upload document, extract evidence with SHA-256 hash, and initiate fact confirmation for FIR (Rate Limit: 10/min)",
)
async def create_fir_from_document(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        session_id = sanitize_input(session_id).strip()
        suffix, file_size = await validate_uploaded_file(file)

        file_bytes = await file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        file_uuid = str(uuid.uuid4())
        saved_filepath = EVIDENCE_DIR / f"{file_uuid}{suffix}"
        with open(saved_filepath, "wb") as buffer:
            buffer.write(file_bytes)

        result = ocr_agent.analyze_document(str(saved_filepath))
        information = result["information"]
        ocr_text = result["ocr_text"]
        timeline = build_evidence_timeline(ocr_text)

        # Store evidence record
        evidence_rec = EvidenceRecord(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            file_id=file_uuid,
            original_filename=file.filename or "evidence_file",
            file_path=str(saved_filepath),
            file_hash=file_hash,
            file_size=file_size,
            mime_type=file.content_type,
            ocr_text=ocr_text,
            extracted_entities_json=json.dumps(information),
            timeline_events_json=json.dumps(timeline),
        )
        db.add(evidence_rec)
        db.commit()

        # Update case profile with provenance
        profile_v2 = memory.get_case_profile_v2(session_id)
        profile_v2 = update_case_profile_v2(
            profile_v2,
            information,
            source="ocr",
            confidence=0.92,
            confirmed=False,
        )
        memory.set_case_profile(session_id, profile_v2)

        fir_result = coordinator.start_fir_from_entities(
            session_id=session_id,
            entities=information,
        )

        return success_response(
            "Document processed, evidence hashed (SHA-256), and FIR drafting initiated.",
            {
                "file_id": file_uuid,
                "file_hash": file_hash,
                "filename": file.filename,
                "document_type": result["classification"]["document_type"],
                "information": information,
                "timeline": timeline,
                "fir": fir_result,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print("OCR FIR ERROR:", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to process the document for FIR generation: {str(e)}",
        )


# ==========================================================
# User Analyses History
# ==========================================================

@router.get(
    "/my-analyses",
    response_model=List[DocumentAnalysisResponseItem],
    summary="Get list of all documents analyzed by the authenticated user",
)
def get_user_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.query(DocumentAnalysisRecord)
        .filter(DocumentAnalysisRecord.user_id == current_user.id)
        .order_by(DocumentAnalysisRecord.created_at.desc())
        .all()
    )

    return [
        DocumentAnalysisResponseItem(
            id=r.id,
            filename=r.filename,
            document_type=r.document_type,
            confidence=r.confidence,
            language=r.language,
            risk_level=r.risk_level,
            summary=r.summary,
            important_points=r.important_points,
            recommended_actions=r.recommended_actions,
            legal_guidance=r.legal_guidance,
            created_at=r.created_at,
        )
        for r in records
    ]