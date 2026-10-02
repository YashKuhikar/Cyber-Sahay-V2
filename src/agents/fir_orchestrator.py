"""
FIROrchestrator - Single Canonical Orchestrator for FIR / Police Complaint Workflow.

Responsibilities:
1. Load conversation history from persistent database & memory
2. Load case profile & existing FIR state
3. Extract FIR-relevant facts using FIRInformationExtractor
4. Merge facts from all sources with clear provenance hierarchy
   (User confirmed > User statements > Case profile > OCR > AI inferred)
5. Detect conflicts/contradictions and manage 'needs_confirmation'
6. Dynamically determine required, useful, and not-applicable fields per incident type
7. Determine missing fields and ask ONE question at a time
8. Validate answers using canonical FIRValidator (returning controlled workflow responses, never 500)
9. Extract all facts when an answer contains multiple entities
10. Manage final confirmation summary before document generation
11. Generate FIR complaint draft with robust fallback (timeout safe)
12. Ensure idempotency and persistence across server restarts
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .fir_agent import FIRAgent
from .fir_extractor import (
    FIRInformationExtractor,
    ExtractedFIRData,
    FieldProvenance,
    INCIDENT_REQUIREMENTS,
    FIELD_QUESTION_MAP,
    format_extracted_summary,
    format_confirmation_summary,
    get_next_question,
)
from .validators import FIRValidator
from ..database.models import FIRRecord, ChatMessage, User
from ..memory.shared_memory import memory

logger = logging.getLogger("cybersahay.fir_orchestrator")


class FIROrchestrationResult(BaseModel):
    status: str  # "collecting_information" | "ready_for_confirmation" | "ready" | "needs_clarification" | "multiple_incidents"
    workflow: str = "fir"
    session_id: str
    current_field: Optional[str] = None
    form: Dict[str, Any] = Field(default_factory=dict)
    next_question: Optional[str] = None
    extracted_summary: Optional[str] = None
    known_fields: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    confirmation_required: bool = False
    fir: Optional[str] = None
    message: Optional[str] = None
    document_id: Optional[str] = None


class FIROrchestrator:
    """
    Central controller for FIR generation across both Chat and Direct REST API flows.
    """

    def __init__(self):
        self.extractor = FIRInformationExtractor()
        self.fir_agent = FIRAgent()
        self.validator = FIRValidator()

    def start_workflow(
        self,
        session_id: str,
        db: Optional[Session] = None,
        current_user: Optional[User] = None,
    ) -> FIROrchestrationResult:
        """
        Starts or resumes the FIR collection process using persistent conversation history.
        """
        logger.info(f"FIROrchestrator: Starting FIR workflow for session={session_id}")

        # 1. Check if already generated and ready
        existing_record = None
        if db is not None:
            existing_record = db.query(FIRRecord).filter(FIRRecord.session_id == session_id).first()
        if existing_record and existing_record.status == "ready" and existing_record.fir_draft_text:
            return FIROrchestrationResult(
                status="ready",
                session_id=session_id,
                current_field=None,
                form=existing_record.form_data,
                next_question=None,
                fir=existing_record.fir_draft_text,
                confirmation_required=False,
                missing_fields=[],
                known_fields=existing_record.form_data,
                message="FIR complaint draft has already been generated.",
            )

        # 2. Retrieve conversation history (Persistent DB > Memory)
        db_messages = []
        if db is not None:
            db_messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.asc())
                .all()
            )
        mem_messages = memory.get_history(session_id) or []
        all_messages = list(db_messages) if db_messages else mem_messages

        # 3. Extract facts from multi-turn conversation
        existing_profile = memory.get_case_profile(session_id) or {}
        extracted_data = self.extractor.extract_from_conversation(
            messages=all_messages,
            session_id=session_id,
            existing_profile=existing_profile,
        )

        form = extracted_data.to_legacy_form()
        # Merge case profile items if not already present
        if existing_profile:
            for k, v in existing_profile.items():
                if v and not form.get(k):
                    form[k] = str(v)

        # 4. Check for multiple distinct incident types in conversation
        user_texts = [
            (getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else "")).lower()
            for m in all_messages
            if (getattr(m, "sender", None) or (m.get("sender") if isinstance(m, dict) else "")) == "user"
        ]
        combined_text = " ".join(user_texts)
        detected_incidents = self._detect_multiple_incidents(combined_text)

        # Check if user already picked an incident type
        chosen_type = memory.get_state(session_id, "chosen_incident_type")
        if len(detected_incidents) > 1 and not chosen_type:
            incident_list_str = "\n".join(f"{i+1}. {inc.replace('_', ' ').title()}" for i, inc in enumerate(detected_incidents))
            multi_q = (
                f"I noticed details about multiple cyber incidents in our conversation:\n\n{incident_list_str}\n\n"
                f"Which incident would you like to prepare this complaint for?"
            )
            memory.set_state(session_id, "workflow", "fir_incident_selection")
            memory.set_state(session_id, "available_incidents", detected_incidents)
            return FIROrchestrationResult(
                status="multiple_incidents",
                session_id=session_id,
                current_field="incident_type",
                form=form,
                next_question=multi_q,
                message="Multiple incidents detected. Please select one.",
            )

        # 5. Persist state
        memory.set_state(session_id, "fir_data", extracted_data.model_dump())
        memory.set_state(session_id, "fir_form", form)
        memory.set_case_profile(session_id, form)

        summary = format_extracted_summary(extracted_data)
        missing = self._calculate_missing_fields(form, extracted_data)

        # 6. Evaluate if complete or if questions are needed
        if not missing:
            confirmation_text = format_confirmation_summary(extracted_data)
            memory.set_state(session_id, "workflow", "fir_confirmation")
            memory.set_state(session_id, "current_field", None)

            self._save_or_update_record(
                db=db,
                session_id=session_id,
                form=form,
                status_str="incomplete",
                current_user=current_user,
            )

            return FIROrchestrationResult(
                status="ready_for_confirmation",
                session_id=session_id,
                current_field=None,
                form=form,
                next_question=confirmation_text,
                extracted_summary=summary,
                known_fields=extracted_data.known_fields,
                missing_fields=[],
                confirmation_required=True,
                message="All incident details extracted. Please review and confirm.",
            )

        # 7. Ask ONLY the first missing question
        current_field = missing[0]
        next_q_text = FIELD_QUESTION_MAP.get(
            current_field,
            f"Please provide your {current_field.replace('_', ' ')}."
        )

        has_meaningful_facts = bool(
            extracted_data.financial.amount.value
            or extracted_data.financial.transaction_id.value
            or extracted_data.incident.date.value
            or (extracted_data.incident.type.value and extracted_data.incident.type.value != "unknown")
        )
        combined_prompt = f"{summary}\n\n**To complete your complaint:** {next_q_text}" if has_meaningful_facts else next_q_text

        memory.set_state(session_id, "workflow", "fir")
        memory.set_state(session_id, "current_field", current_field)

        self._save_or_update_record(
            db=db,
            session_id=session_id,
            form=form,
            status_str="incomplete",
            current_user=current_user,
        )

        return FIROrchestrationResult(
            status="incomplete",
            session_id=session_id,
            current_field=current_field,
            form=form,
            next_question=next_q_text,
            extracted_summary=summary,
            known_fields=extracted_data.known_fields,
            missing_fields=missing,
            confirmation_required=False,
            message="FIR information collection started.",
        )

    def continue_workflow(
        self,
        session_id: str,
        answer: str,
        db: Optional[Session] = None,
        current_user: Optional[User] = None,
    ) -> FIROrchestrationResult:
        """
        Processes a user response, extracts all entities present in the answer,
        validates the applicable fields, recalculates missing fields, and advances the workflow.
        """
        logger.info(f"FIROrchestrator: continue_workflow session={session_id}, answer_len={len(answer)}")

        form = memory.get_state(session_id, "fir_form", {})
        current_field = memory.get_state(session_id, "current_field")
        active_workflow = memory.get_state(session_id, "workflow")

        # Recover from DB if memory was cleared/restarted
        if not form and db is not None:
            rec = db.query(FIRRecord).filter(FIRRecord.session_id == session_id).first()
            if rec:
                form = rec.form_data
                current_field = self._calculate_missing_fields(form)[0] if self._calculate_missing_fields(form) else None

        # Handle multiple incident resolution
        if active_workflow == "fir_incident_selection":
            available = memory.get_state(session_id, "available_incidents", [])
            selected_type = "financial_cyber_fraud"
            for inc in available:
                if inc.replace("_", " ") in answer.lower() or inc in answer.lower():
                    selected_type = inc
                    break
            memory.set_state(session_id, "chosen_incident_type", selected_type)
            form["incident_type"] = selected_type
            memory.set_state(session_id, "workflow", "fir")
            return self.start_workflow(session_id=session_id, db=db, current_user=current_user)

        # Handle confirmation state
        if active_workflow == "fir_confirmation" or not current_field:
            answer_lower = answer.lower()
            if any(w in answer_lower for w in ["yes", "confirm", "proceed", "haan", "sahi", "generate", "correct", "ok", "done", "fine", "approved"]):
                # Idempotency check: if already generated, return existing
                rec = db.query(FIRRecord).filter(FIRRecord.session_id == session_id).first()
                if rec and rec.status == "ready" and rec.fir_draft_text:
                    fir_draft = rec.fir_draft_text
                else:
                    fir_draft = self.fir_agent.generate_fir(form)

                memory.set_state(session_id, "workflow", None)
                memory.set_state(session_id, "current_field", None)
                memory.set_state(session_id, "fir_draft", fir_draft)

                self._save_or_update_record(
                    db=db,
                    session_id=session_id,
                    form=form,
                    status_str="ready",
                    fir_draft=fir_draft,
                    current_user=current_user,
                )

                return FIROrchestrationResult(
                    status="ready",
                    session_id=session_id,
                    current_field=None,
                    form=form,
                    next_question=None,
                    fir=fir_draft,
                    confirmation_required=False,
                    missing_fields=[],
                    document_id=session_id,
                    message="FIR complaint draft generated successfully.",
                )

        if not form or not current_field:
            return FIROrchestrationResult(
                status="collecting_information",
                session_id=session_id,
                current_field=None,
                form=form or {},
                next_question="Please start the FIR process by sharing what happened.",
            )

        # Validate answer against current field rules
        is_valid, validation_message = self.validator.validate_field(current_field, answer)
        if not is_valid:
            return FIROrchestrationResult(
                status="incomplete",
                session_id=session_id,
                current_field=current_field,
                form=form,
                next_question=validation_message,
                missing_fields=[current_field],
                confirmation_required=False,
                message=validation_message,
            )

        # Extract ALL facts contained in this single answer (Section 15)
        multi_facts = self._extract_multi_facts_from_answer(answer)
        for field_name, field_val in multi_facts.items():
            if field_val and (not form.get(field_name) or current_field == field_name):
                form[field_name] = field_val

        # Update primary field
        if current_field == "incident_date":
            form["incident_date"] = self.validator.normalize_date(answer) or answer
        elif current_field == "complainant_name":
            if not form.get("complainant_name") or len(form["complainant_name"].split()) > 4:
                clean_name = re.sub(r"^(?:my name is|i am|mera naam|naam hai)\s+", "", answer, flags=re.I).strip()
                clean_name = re.split(r"[,.]|\band\b|\bi live\b|\bmy phone\b", clean_name, flags=re.I)[0].strip()
                form["complainant_name"] = clean_name
        elif current_field in ("amount", "amount_lost"):
            amt = self.validator.normalize_amount(answer)
            form["amount_lost"] = str(int(amt)) if amt is not None else answer
        elif current_field == "incident_time":
            norm_t = self.validator.normalize_time(answer)
            form["incident_time"] = norm_t or answer
        elif current_field == "phone_number":
            norm_ph = self.validator.normalize_phone(answer)
            form["phone_number"] = norm_ph or answer
        else:
            form[current_field] = answer

        # Check user correction pattern (e.g. "No, amount was 30000 not 25000")
        correction_match = re.search(r"\b(?:no|actually|instead|correction)[,\s]+.*?(?:₹|rs\.?|inr)?\s*(\d[\d,]+)", answer, re.I)
        if correction_match:
            corrected_amt = self.validator.normalize_amount(correction_match.group(1))
            if corrected_amt:
                form["amount_lost"] = str(int(corrected_amt))

        # Persist updated state
        memory.set_state(session_id, "fir_form", form)
        memory.set_case_profile(session_id, form)

        # Recalculate missing fields dynamically
        missing = self._calculate_missing_fields(form)

        if missing:
            next_field = missing[0]
            memory.set_state(session_id, "workflow", "fir")
            memory.set_state(session_id, "current_field", next_field)
            next_q = FIELD_QUESTION_MAP.get(next_field, f"Please provide your {next_field.replace('_', ' ')}.")

            self._save_or_update_record(
                db=db,
                session_id=session_id,
                form=form,
                status_str="incomplete",
                current_user=current_user,
            )

            return FIROrchestrationResult(
                status="incomplete",
                session_id=session_id,
                current_field=next_field,
                form=form,
                next_question=next_q,
                missing_fields=missing,
                confirmation_required=False,
                message="FIR information updated.",
            )

        # All required fields satisfied -> Transition to Confirmation Summary!
        memory.set_state(session_id, "workflow", "fir_confirmation")
        memory.set_state(session_id, "current_field", None)

        confirmation_summary = self._build_form_confirmation_summary(form)

        self._save_or_update_record(
            db=db,
            session_id=session_id,
            form=form,
            status_str="incomplete",
            current_user=current_user,
        )

        return FIROrchestrationResult(
            status="ready_for_confirmation",
            session_id=session_id,
            current_field=None,
            form=form,
            next_question=confirmation_summary,
            missing_fields=[],
            confirmation_required=True,
            message="Please confirm these details before complaint generation.",
        )

    def _calculate_missing_fields(self, form: Dict[str, Any], extracted: Optional[ExtractedFIRData] = None) -> List[str]:
        """
        Dynamically calculates missing fields based on incident type and required/useful schemas.
        """
        incident_type = form.get("incident_type") or (extracted.incident.type.value if extracted else "general")
        reqs = INCIDENT_REQUIREMENTS.get(incident_type, INCIDENT_REQUIREMENTS["general"])
        required_list = reqs["required"]

        missing: List[str] = []
        for rf in required_list:
            if rf == "amount":
                if not form.get("amount_lost") and not form.get("amount"):
                    missing.append("amount")
            elif rf == "complainant_name":
                if not form.get("complainant_name"):
                    missing.append("complainant_name")
            elif rf == "incident_date":
                if not form.get("incident_date"):
                    missing.append("incident_date")
            elif rf == "description":
                if not form.get("description"):
                    missing.append("description")
            elif rf == "imei_number":
                if not form.get("imei_number"):
                    missing.append("imei_number")
            elif rf == "device_type":
                if not form.get("device_type"):
                    missing.append("device_type")
            elif rf == "incident_location":
                if not form.get("incident_location"):
                    missing.append("incident_location")
            elif not form.get(rf):
                missing.append(rf)

        # If all required fields satisfied, check useful fields
        if not missing:
            for uf in reqs.get("useful", []):
                if uf == "bank" and not form.get("bank_account") and not form.get("bank"):
                    missing.append("bank")
                elif uf == "transaction_id" and not form.get("transaction_id"):
                    # Only ask if amount was involved
                    if form.get("amount_lost"):
                        missing.append("transaction_id")

        return missing

    def _extract_multi_facts_from_answer(self, answer: str) -> Dict[str, Any]:
        """
        Extracts multiple facts when a single user utterance provides several details
        (e.g., "My name is Akshdeep, it happened yesterday at 8 PM and I lost ₹25,000").
        """
        facts: Dict[str, Any] = {}

        # 1. Name
        name_m = re.search(r"\b(?:my\s*name\s*is|i\s*am|naam\s*hai|mera\s*naam)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", answer, re.I)
        if name_m:
            facts["complainant_name"] = name_m.group(1).strip()

        # 2. Amount - only extract in multi-fact parsing if currency indicator or loss context is present
        has_currency_hint = bool(re.search(r"(?:₹|rs\.?|inr|rupees?|lakh|lac|bucks?|\bk\b)", answer, re.I))
        has_loss_context = bool(re.search(r"\b(?:lost|deducted|transferred|stolen|paid|fraud|chori)\b", answer, re.I))
        if has_currency_hint or has_loss_context:
            amt = self.validator.normalize_amount(answer)
            if amt is not None and amt > 0:
                facts["amount_lost"] = str(int(amt))

        # 3. Date
        if any(w in answer.lower() for w in ["yesterday", "today", "kal", "aaj", "last night"]) or re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", answer):
            norm_d = self.validator.normalize_date(answer)
            if norm_d:
                facts["incident_date"] = norm_d

        # 4. Time
        norm_t = self.validator.normalize_time(answer)
        if norm_t:
            facts["incident_time"] = norm_t

        # 5. Phone
        norm_p = self.validator.normalize_phone(answer)
        if norm_p and ("my phone" in answer.lower() or "mobile" in answer.lower()):
            facts["phone_number"] = norm_p

        return facts

    def _detect_multiple_incidents(self, text: str) -> List[str]:
        """
        Detects if user discussed multiple disparate cybercrimes in one conversation.
        """
        types_found = []
        if any(w in text for w in ["upi", "bank account", "paise kat", "debited", "transferred"]):
            types_found.append("financial_cyber_fraud")
        if any(w in text for w in ["hacked", "instagram", "facebook", "account takeover", "locked out"]):
            types_found.append("account_takeover")
        if any(w in text for w in ["stolen", "lost my phone", "mobile chori", "imei"]):
            types_found.append("mobile_theft")
        if any(w in text for w in ["courier", "phishing", "fake link"]):
            types_found.append("phishing")
        if any(w in text for w in ["blackmail", "video call", "nude", "sextortion"]):
            types_found.append("sextortion")
        return list(dict.fromkeys(types_found))

    def _build_form_confirmation_summary(self, form: Dict[str, Any]) -> str:
        """
        Builds formal confirmation checklist for user before final document generation.
        """
        lines = [
            "### Complaint Details for Confirmation",
            "",
            f"- **Complainant Name:** {form.get('complainant_name') or 'N/A'}",
            f"- **Incident Type:** {form.get('incident_type', 'Cyber Offence').replace('_', ' ').title()}",
        ]
        if form.get("amount_lost"):
            try:
                lines.append(f"- **Financial Loss:** ₹{int(float(form['amount_lost'])):,}")
            except (ValueError, TypeError):
                lines.append(f"- **Financial Loss:** ₹{form['amount_lost']}")

        if form.get("incident_date"):
            lines.append(f"- **Date of Occurrence:** {form['incident_date']}")
        if form.get("incident_time"):
            lines.append(f"- **Time of Occurrence:** {form['incident_time']}")
        if form.get("incident_location"):
            lines.append(f"- **Location:** {form['incident_location']}")
        if form.get("transaction_id"):
            lines.append(f"- **Transaction ID / Reference:** {form['transaction_id']}")
        if form.get("bank_account") or form.get("bank"):
            lines.append(f"- **Bank Involved:** {form.get('bank') or form.get('bank_account')}")
        if form.get("upi_id"):
            lines.append(f"- **UPI ID:** {form['upi_id']}")
        if form.get("imei_number"):
            lines.append(f"- **IMEI Number:** {form['imei_number']}")

        lines.append("")
        lines.append(f"**Incident Narrative:**\n{form.get('description', '')}")
        lines.append("")
        lines.append("Please reply with **Confirm** to generate your official police complaint draft, or tell me any changes.")
        return "\n".join(lines)

    def _save_or_update_record(
        self,
        db: Optional[Session],
        session_id: str,
        form: dict,
        status_str: str,
        fir_draft: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> Optional[FIRRecord]:
        if db is None:
            return None
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
