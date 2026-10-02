from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agents.fir_agent import FIRAgent
from ..agents.validators import FIRValidator
from ..agents.fir_extractor import (
    FIRInformationExtractor,
    format_extracted_summary,
    format_confirmation_summary,
    FIELD_QUESTION_MAP,
    INCIDENT_REQUIREMENTS,
)
from ..database.db import get_db
from ..database.models import FIRRecord, User, ChatMessage
from ..memory.shared_memory import memory
from ..memory.case_profile import create_case_profile, update_case_profile
from ..services.auth_service import get_current_user, get_optional_user
from ..services.pdf_service import generate_fir_pdf
from ..security.auth_guard import verify_fir_ownership


router = APIRouter()
fir_agent = FIRAgent()


# ==========================================================
# Request & Response Models
# ==========================================================

class FIRStartRequest(BaseModel):
    session_id: Optional[str] = Field(None, example="session-123456")
    conversation_id: Optional[str] = None
    case_id: Optional[str] = None


class FIRContinueRequest(BaseModel):
    session_id: str = Field(..., example="session-123456")
    answer: str = Field(..., example="Rohit Sharma")


class FIRDirectGenerateRequest(BaseModel):
    session_id: Optional[str] = None
    category: Optional[str] = "Cyber Fraud"
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    amount_lost: Optional[str] = None
    bank_name: Optional[str] = None
    transaction_id: Optional[str] = None
    complainant_name: str
    complainant_phone: Optional[str] = None
    complainant_email: Optional[str] = None
    complainant_address: Optional[str] = None
    id_proof: Optional[str] = None
    suspect_phone: Optional[str] = None
    suspect_upi: Optional[str] = None
    platform: Optional[str] = None
    impersonating_as: Optional[str] = None
    narrative: str


class FIRItemResponse(BaseModel):
    id: int
    session_id: str
    incident_type: str
    complainant_name: str
    status: str
    form_data: dict
    fir_draft_text: Optional[str] = None
    created_at: datetime


def success_response(message: str, data: dict):
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.now(),
    }


def _save_or_update_fir_record(
    db: Session,
    session_id: str,
    form: dict,
    status_str: str,
    fir_draft: Optional[str] = None,
    current_user: Optional[User] = None,
) -> FIRRecord:
    record = db.query(FIRRecord).filter(FIRRecord.session_id == session_id).first()
    incident_type = form.get("incident_type", "unknown")
    complainant_name = form.get("complainant_name", "")

    if not record:
        record = FIRRecord(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            incident_type=incident_type,
            complainant_name=complainant_name,
            form_data_json=json.dumps(form),
            status=status_str,
            fir_draft_text=fir_draft,
        )
        db.add(record)
    else:
        record.incident_type = incident_type or record.incident_type
        record.complainant_name = complainant_name or record.complainant_name
        record.form_data_json = json.dumps(form)
        record.status = status_str
        if fir_draft:
            record.fir_draft_text = fir_draft
        if current_user and not record.user_id:
            record.user_id = current_user.id

    db.commit()
    db.refresh(record)
    return record


from ..security.rate_limiter import rate_limit
from ..security.sanitizer import sanitize_input


from ..agents.fir_orchestrator import FIROrchestrator

fir_orchestrator = FIROrchestrator()


# ==========================================================
# Start FIR
# ==========================================================

@router.post(
    "/start",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))],
    summary="Start an interactive FIR drafting session (Rate Limit: 20/min)",
)
def start_fir(
    request: FIRStartRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    raw_id = request.session_id or request.conversation_id or request.case_id or ""
    session_id = sanitize_input(raw_id).strip()
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id, conversation_id, or case_id is required.",
        )

    res = fir_orchestrator.start_workflow(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    data_payload = {
        "session_id": res.session_id,
        "status": res.status,
        "current_field": res.current_field,
        "form": res.form,
        "next_question": res.next_question,
        "extracted_summary": res.extracted_summary,
        "known_fields": res.known_fields,
        "missing_fields": res.missing_fields,
        "confirmation_required": res.confirmation_required,
        "fir": res.fir,
        "message": res.message,
    }
    return success_response(res.message or "FIR workflow started.", data_payload)


# ==========================================================
# Continue FIR
# ==========================================================

@router.post(
    "/continue",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))],
    summary="Submit an answer to the current FIR follow-up question (Rate Limit: 20/min)",
)
def continue_fir(
    request: FIRContinueRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session_id = sanitize_input(request.session_id).strip()
    answer = sanitize_input(request.answer).strip()

    res = fir_orchestrator.continue_workflow(
        session_id=session_id,
        answer=answer,
        db=db,
        current_user=current_user,
    )

    data_payload = {
        "session_id": res.session_id,
        "status": res.status,
        "current_field": res.current_field,
        "form": res.form,
        "next_question": res.next_question,
        "extracted_summary": res.extracted_summary,
        "known_fields": res.known_fields,
        "missing_fields": res.missing_fields,
        "confirmation_required": res.confirmation_required,
        "fir": res.fir,
        "message": res.message,
    }
    return success_response(res.message or "FIR workflow updated.", data_payload)


# ==========================================================
# Direct Multi-Step Form FIR Generation
# ==========================================================

@router.post(
    "/generate",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))],
    summary="Generate formal FIR draft directly from structured multi-step form",
)
def generate_fir_direct(
    request: FIRDirectGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    import uuid
    session_id = request.session_id or f"fir-{uuid.uuid4().hex[:8]}"

    form_dict = request.dict()
    form_dict["incident_type"] = request.category or "Cyber Fraud"
    form_dict["incident_location"] = f"{request.city or ''}, {request.state or ''}".strip(", ") or "Online / Digital"

    # Use fir_agent to generate the standard police complaint draft
    try:
        fir_draft = fir_agent.generate_fir(form_dict)
    except Exception as e:
        print("FIR generation error fallback:", e)
        fir_draft = None

    record = _save_or_update_fir_record(
        db=db,
        session_id=session_id,
        form=form_dict,
        status_str="ready",
        fir_draft=fir_draft,
        current_user=current_user,
    )

    return success_response(
        "FIR draft generated successfully.",
        {
            "id": record.id,
            "session_id": record.session_id,
            "incident_type": record.incident_type,
            "complainant_name": record.complainant_name,
            "status": record.status,
            "form_data": record.form_data,
            "fir_draft_text": record.fir_draft_text,
            "created_at": record.created_at,
        },
    )


# ==========================================================
# FIR Status
# ==========================================================

@router.get(
    "/status/{session_id}",
    summary="Check active FIR workflow status for a session",
)
def fir_status(session_id: str, db: Session = Depends(get_db)):
    form = memory.get_state(session_id, "fir_form", {})
    fir_draft = memory.get_state(session_id, "fir_draft", None)
    current_field = memory.get_state(session_id, "current_field")

    db_rec = db.query(FIRRecord).filter(FIRRecord.session_id == session_id).first()
    if db_rec:
        if not form:
            form = db_rec.form_data
        if not fir_draft:
            fir_draft = db_rec.fir_draft_text

    # If form still empty, check case_profile
    if not form:
        profile = memory.get_case_profile(session_id) or {}
        if profile and any(profile.values()):
            start_res = fir_agent.start_from_profile(profile)
            form = start_res.get("form", {})
            if not current_field:
                current_field = start_res.get("current_field")
            if start_res.get("status") == "ready" and not fir_draft:
                fir_draft = start_res.get("fir_draft")

    if not current_field and form and not fir_draft:
        missing = fir_agent.get_missing_fields(form)
        if missing:
            current_field = missing[0]

    next_question = None
    if current_field:
        next_question = fir_agent.FIELD_QUESTIONS.get(
            current_field,
            f"Please provide {current_field.replace('_', ' ')}."
        )

    if fir_draft or (db_rec and db_rec.status == "ready"):
        status_val = "ready"
    elif current_field or (form and any(form.values())):
        status_val = "incomplete"
    else:
        status_val = "not_started"

    return success_response(
        "FIR status retrieved successfully.",
        {
            "status": status_val,
            "workflow": memory.get_state(session_id, "workflow") or ("fir" if status_val == "incomplete" else None),
            "current_field": current_field,
            "form": form or {},
            "next_question": next_question,
            "fir": fir_draft,
            "case_profile": memory.get_case_profile(session_id),
        },
    )


# ==========================================================
# User FIRs & PDF Download
# ==========================================================

@router.get(
    "/my-firs",
    response_model=List[FIRItemResponse],
    summary="Get list of all FIRs generated by the authenticated user",
)
def get_user_firs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.query(FIRRecord)
        .filter(FIRRecord.user_id == current_user.id)
        .order_by(FIRRecord.updated_at.desc())
        .all()
    )

    return [
        FIRItemResponse(
            id=r.id,
            session_id=r.session_id,
            incident_type=r.incident_type,
            complainant_name=r.complainant_name,
            status=r.status,
            form_data=r.form_data,
            fir_draft_text=r.fir_draft_text,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get(
    "/download-pdf/{identifier}",
    summary="Download formal, printable FIR complaint report in PDF format",
)
def download_fir_pdf(
    identifier: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    # Try finding by session_id first, then by ID
    record = db.query(FIRRecord).filter(FIRRecord.session_id == identifier).first()
    if not record and identifier.isdigit():
        record = db.query(FIRRecord).filter(FIRRecord.id == int(identifier)).first()

    if record:
        verify_fir_ownership(record, current_user)


    form = {}
    draft = ""
    created_at = None

    if record:
        form = record.form_data
        draft = record.fir_draft_text or ""
        created_at = record.created_at
    else:
        # Fallback to memory
        form = memory.get_state(identifier, "fir_form", {})
        draft = memory.get_state(identifier, "fir_draft", "")

    if not form and not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIR record not found for the provided ID or session.",
        )

    pdf_bytes = generate_fir_pdf(
        session_id=identifier,
        form_data=form,
        fir_draft=draft,
        created_at=created_at,
    )

    filename = f"CyberSahay_FIR_{identifier[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )