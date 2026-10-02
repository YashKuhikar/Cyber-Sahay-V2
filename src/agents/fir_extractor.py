from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

from .entity_extractor import TypedEntityExtractor, validate_imei_luhn
from .validators import FIRValidator
from ..config import GROQ_API_KEY, GROQ_MODEL
from ..utils.validators import validate_time

logger = logging.getLogger("cybersahay.fir_extractor")

try:
    from groq import Groq
    _groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception:
    _groq_client = None


# ==========================================================
# Provenance & Field Schemas
# ==========================================================

class FieldProvenance(BaseModel):
    value: Any = None
    status: Literal["confirmed", "inferred", "missing", "needs_confirmation"] = "missing"
    source: Literal["user_message", "ai_inferred", "ocr", "case_profile", "unknown"] = "unknown"
    source_text: Optional[str] = None
    previous_value: Optional[Any] = None


class ComplainantInfo(BaseModel):
    name: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    phone: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    address: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    email: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))


class IncidentInfo(BaseModel):
    type: FieldProvenance = Field(default_factory=lambda: FieldProvenance(value="unknown", status="missing"))
    description: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    date: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    time: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    location: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    method: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    platform: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))


class FinancialInfo(BaseModel):
    amount: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    currency: str = "INR"
    transaction_id: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    utr: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    upi_id: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    bank: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    account_number: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))


class SuspectInfo(BaseModel):
    name: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    phone: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    email: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    url: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    username: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    impersonating_as: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))


class DeviceInfo(BaseModel):
    device_type: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    imei: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))
    sim_details: FieldProvenance = Field(default_factory=lambda: FieldProvenance(status="missing"))


class ExtractedFIRData(BaseModel):
    complainant: ComplainantInfo = Field(default_factory=ComplainantInfo)
    incident: IncidentInfo = Field(default_factory=IncidentInfo)
    financial: FinancialInfo = Field(default_factory=FinancialInfo)
    suspect: SuspectInfo = Field(default_factory=SuspectInfo)
    device: DeviceInfo = Field(default_factory=DeviceInfo)
    evidence: List[str] = Field(default_factory=list)
    actions_taken: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    known_fields: Dict[str, Any] = Field(default_factory=dict)
    contradictions: List[str] = Field(default_factory=list)

    def to_legacy_form(self) -> Dict[str, str]:
        """
        Provides 100% backward compatibility for existing code and templates
        expecting flat form dictionary.
        """
        amt_val = self.financial.amount.value
        amt_str = ""
        if amt_val is not None:
            try:
                amt_str = str(int(float(amt_val)))
            except (ValueError, TypeError):
                amt_str = str(amt_val)

        return {
            "complainant_name": str(self.complainant.name.value or ""),
            "incident_type": str(self.incident.type.value or "unknown"),
            "incident_date": str(self.incident.date.value or ""),
            "incident_time": str(self.incident.time.value or ""),
            "incident_location": str(self.incident.location.value or ""),
            "description": str(self.incident.description.value or ""),
            "suspect_name": str(self.suspect.name.value or ""),
            "phone_number": str(self.complainant.phone.value or self.suspect.phone.value or ""),
            "email": str(self.complainant.email.value or self.suspect.email.value or ""),
            "imei_number": str(self.device.imei.value or ""),
            "vehicle_number": "",
            "bank_account": str(self.financial.account_number.value or self.financial.bank.value or ""),
            "upi_id": str(self.financial.upi_id.value or ""),
            "amount_lost": amt_str,
            "transaction_id": str(self.financial.transaction_id.value or ""),
        }


# ==========================================================
# Incident Requirements Schema
# ==========================================================

INCIDENT_REQUIREMENTS: Dict[str, Dict[str, List[str]]] = {
    "financial_cyber_fraud": {
        "required": ["complainant_name", "description", "amount", "incident_date"],
        "useful": ["bank", "transaction_id"],
        "not_applicable": ["imei_number", "vehicle_number"],
    },
    "upi_fraud": {
        "required": ["complainant_name", "description", "amount", "incident_date"],
        "useful": ["bank", "transaction_id", "upi_id"],
        "not_applicable": ["imei_number", "vehicle_number"],
    },
    "phishing": {
        "required": ["complainant_name", "description", "incident_date"],
        "useful": ["url", "amount"],
        "not_applicable": ["imei_number", "vehicle_number"],
    },
    "account_takeover": {
        "required": ["complainant_name", "description", "incident_date"],
        "useful": ["platform"],
        "not_applicable": ["imei_number", "vehicle_number", "bank_account"],
    },
    "mobile_theft": {
        "required": ["complainant_name", "device_type", "incident_date", "incident_location", "imei_number", "description"],
        "useful": ["device_type"],
        "not_applicable": ["vehicle_number", "upi_id", "bank_account"],
    },
    "device_theft": {
        "required": ["complainant_name", "incident_date", "incident_location", "imei_number", "description"],
        "useful": ["device_type"],
        "not_applicable": ["vehicle_number", "upi_id", "bank_account"],
    },
    "sextortion": {
        "required": ["complainant_name", "description", "incident_date"],
        "useful": ["platform"],
        "not_applicable": ["imei_number", "vehicle_number"],
    },
    "identity_theft": {
        "required": ["complainant_name", "description", "incident_date"],
        "useful": ["amount", "bank"],
        "not_applicable": ["imei_number", "vehicle_number"],
    },
    "general": {
        "required": ["complainant_name", "description", "incident_date"],
        "useful": ["incident_location"],
        "not_applicable": ["imei_number", "vehicle_number"],
    },
    "unknown": {
        "required": ["complainant_name", "description", "incident_date"],
        "useful": ["incident_location"],
        "not_applicable": ["vehicle_number"],
    },
}

FIELD_QUESTION_MAP: Dict[str, str] = {
    "complainant_name": "What is your full name?",
    "description": "Please provide a brief description of what happened.",
    "amount": "What was the total financial amount lost?",
    "incident_date": "On which date did the incident occur?",
    "incident_time": "At approximately what time did the incident occur?",
    "incident_location": "Where did the incident occur (City or Police Station area)?",
    "bank": "Which bank or financial service was involved (e.g., SBI, HDFC)?",
    "bank_account": "What is your affected bank account number?",
    "transaction_id": "What is the transaction ID or reference number?",
    "upi_id": "What was the suspect UPI ID or handle involved?",
    "imei_number": "What is the 15-digit IMEI number of the stolen mobile phone?",
    "device_type": "What was the model or make of your device?",
    "platform": "On which platform did this occur (e.g. WhatsApp, Instagram, Telegram)?",
    "url": "What was the suspicious website URL or link?",
}


# ==========================================================
# Deterministic Patterns
# ==========================================================

RE_TXN_ID = re.compile(
    r"\b(?:transaction\s*id|txn\s*id|txnid|ref\s*id|reference\s*id|payment\s*id|upi\s*ref|order\s*id)[\s:#-]*(?:is|was|no\.?|number)?[\s:#-]*([A-Za-z0-9_-]{5,30})\b",
    re.IGNORECASE,
)

RE_TIME = re.compile(
    r"\b(?:at|around|approx\.?)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b|\b(\d{1,2}:\d{2})\b",
    re.IGNORECASE,
)

RE_COMPLAINANT_NAME = re.compile(
    r"\b(?:my\s*name\s*is|i\s*am|this\s*is|naam\s*hai|mera\s*naam)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
    re.IGNORECASE,
)

COMMON_BANKS = sorted([
    "State Bank of India", "SBI", "HDFC Bank", "HDFC", "ICICI Bank", "ICICI",
    "Axis Bank", "Axis", "Kotak Mahindra Bank", "Kotak", "Punjab National Bank", "PNB",
    "Bank of Baroda", "BOB", "Canara Bank", "Union Bank", "IndusInd Bank",
    "Yes Bank", "IDFC First Bank", "Paytm Payments Bank", "Airtel Payments Bank",
], key=len, reverse=True)


# ==========================================================
# Core Extractor Implementation
# ==========================================================

class FIRInformationExtractor:
    """
    Intelligent conversation-to-FIR extractor.
    Reuses multi-turn chat history, distinguishes CONFIRMED vs INFERRED vs MISSING,
    and ensures the victim is never asked redundant questions.
    """

    def __init__(self):
        self.entity_extractor = TypedEntityExtractor()

    def extract_from_conversation(
        self,
        messages: List[Any],
        session_id: str = "",
        existing_profile: Optional[Dict[str, Any]] = None,
        evidence_records: Optional[List[Any]] = None,
    ) -> ExtractedFIRData:
        """
        Extracts structured FIR information from multi-turn conversation.
        """
        data = ExtractedFIRData()
        user_messages: List[str] = []
        user_turns: List[Tuple[int, str]] = []

        # 1. Parse & filter messages (strictly prioritizing user messages for facts)
        turn_idx = 0
        for m in messages:
            sender = getattr(m, "sender", None) or (m.get("sender") if isinstance(m, dict) else None)
            text = getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else None) or ""
            text = str(text).strip()
            if not text:
                continue

            if sender == "user":
                user_messages.append(text)
                user_turns.append((turn_idx, text))
                turn_idx += 1

        logger.info(
            f"FIR Extractor: Analyzing {len(user_messages)} user messages for session {session_id}"
        )

        # 2. Extract facts across user messages (Chronological multi-pass)
        detected_amounts: List[Tuple[float, str, int]] = []
        detected_txn_ids: List[Tuple[str, str]] = []
        detected_times: List[Tuple[str, str]] = []
        detected_dates: List[Tuple[str, str]] = []
        detected_banks: List[Tuple[str, str]] = []
        detected_urls: List[str] = []
        detected_upis: List[str] = []
        detected_utrs: List[str] = []
        detected_phones: List[str] = []
        detected_imeis: List[str] = []

        for idx, text in user_turns:
            # Deterministic typed entities
            entities = self.entity_extractor.extract_deterministic(text)

            # Amount
            if entities.get("amount") is not None:
                detected_amounts.append((float(entities["amount"]), text, idx))

            # UPIs
            for u in entities.get("upi_ids", []):
                if u not in detected_upis:
                    detected_upis.append(u)

            # UTRs
            for utr in entities.get("utr_numbers", []):
                if utr not in detected_utrs:
                    detected_utrs.append(utr)

            # Phones
            for ph in entities.get("phone_numbers", []):
                if ph not in detected_phones:
                    detected_phones.append(ph)

            # URLs
            for url in entities.get("urls", []):
                if url not in detected_urls:
                    detected_urls.append(url)

            # IMEI
            if entities.get("imei"):
                if entities["imei"] not in detected_imeis:
                    detected_imeis.append(entities["imei"])

            # Transaction ID
            txn_match = RE_TXN_ID.search(text)
            if txn_match:
                candidate_txn = txn_match.group(1).strip()
                if candidate_txn.upper() not in {"IS", "WAS", "NO", "NOT", "YES", "NULL"}:
                    detected_txn_ids.append((candidate_txn, text))

            # Complainant name match
            name_match = RE_COMPLAINANT_NAME.search(text)
            if name_match and data.complainant.name.status == "missing":
                c_name = name_match.group(1).strip()
                data.complainant.name = FieldProvenance(
                    value=c_name,
                    status="confirmed",
                    source="user_message",
                    source_text=text,
                )

            # Time parsing
            time_match = RE_TIME.search(text)
            if time_match:
                extracted_t = (time_match.group(1) or time_match.group(2) or "").strip()
                if extracted_t and validate_time(extracted_t):
                    detected_times.append((extracted_t, text))

            # Date parsing
            lower_text = text.lower()
            if "yesterday" in lower_text or "kal" in lower_text:
                normalized_yesterday = FIRValidator.normalize_date("yesterday")
                detected_dates.append((normalized_yesterday or "Yesterday", text))
            elif "today" in lower_text or "aaj" in lower_text:
                normalized_today = FIRValidator.normalize_date("today")
                detected_dates.append((normalized_today or "Today", text))
            else:
                norm_d = FIRValidator.normalize_date(text)
                if norm_d:
                    detected_dates.append((norm_d, text))

            # Bank matching
            for bank_name in COMMON_BANKS:
                if re.search(r"\b" + re.escape(bank_name) + r"\b", text, re.I):
                    if not any(b[0].lower() == bank_name.lower() for b in detected_banks):
                        detected_banks.append((bank_name, text))
                    break

        # 3. Resolve Amount & Handle Contradictions (Section 7)
        if detected_amounts:
            if len(detected_amounts) == 1:
                amt, src_txt, _ = detected_amounts[0]
                data.financial.amount = FieldProvenance(
                    value=amt,
                    status="confirmed",
                    source="user_message",
                    source_text=src_txt,
                )
            else:
                # Multiple amounts mentioned
                first_amt, first_txt, _ = detected_amounts[0]
                latest_amt, latest_txt, _ = detected_amounts[-1]
                if abs(first_amt - latest_amt) > 0.01:
                    # Contradiction detected!
                    data.financial.amount = FieldProvenance(
                        value=latest_amt,
                        status="needs_confirmation",
                        source="user_message",
                        source_text=latest_txt,
                        previous_value=first_amt,
                    )
                    data.contradictions.append(
                        f"Amount changed from ₹{int(first_amt):,} to ₹{int(latest_amt):,}"
                    )
                else:
                    data.financial.amount = FieldProvenance(
                        value=latest_amt,
                        status="confirmed",
                        source="user_message",
                        source_text=latest_txt,
                    )

        # 4. Resolve Transaction ID / UTR
        if detected_txn_ids:
            txn_val, txn_txt = detected_txn_ids[-1]
            data.financial.transaction_id = FieldProvenance(
                value=txn_val,
                status="confirmed",
                source="user_message",
                source_text=txn_txt,
            )
        elif detected_utrs:
            data.financial.utr = FieldProvenance(
                value=detected_utrs[0],
                status="confirmed",
                source="user_message",
            )
            data.financial.transaction_id = FieldProvenance(
                value=detected_utrs[0],
                status="confirmed",
                source="user_message",
            )

        if detected_upis:
            data.financial.upi_id = FieldProvenance(
                value=detected_upis[0],
                status="confirmed",
                source="user_message",
            )

        if detected_banks:
            b_val, b_txt = detected_banks[0]
            data.financial.bank = FieldProvenance(
                value=b_val,
                status="confirmed",
                source="user_message",
                source_text=b_txt,
            )

        # 5. Resolve Date and Time
        if detected_dates:
            d_val, d_txt = detected_dates[-1]
            data.incident.date = FieldProvenance(
                value=d_val,
                status="confirmed",
                source="user_message",
                source_text=d_txt,
            )

        if detected_times:
            t_val, t_txt = detected_times[-1]
            data.incident.time = FieldProvenance(
                value=t_val,
                status="confirmed",
                source="user_message",
                source_text=t_txt,
            )

        # 6. Resolve Device & IMEI
        if detected_imeis:
            data.device.imei = FieldProvenance(
                value=detected_imeis[0],
                status="confirmed",
                source="user_message",
            )
            data.device.device_type = FieldProvenance(
                value="Mobile Phone",
                status="inferred",
                source="ai_inferred",
            )

        # 7. Resolve Complainant vs Suspect Phone & Identifiers
        if detected_phones:
            for ph in detected_phones:
                # Check if phone was mentioned as complainant's phone
                is_complainant_phone = False
                for u_text in user_messages:
                    if ph in u_text and re.search(r"\b(?:my\s*(?:phone|mobile|number|contact)|mobile\s*:?\s*" + re.escape(ph) + r"|phone\s*:?\s*" + re.escape(ph) + r")\b", u_text, re.I):
                        is_complainant_phone = True
                        break
                    if ph in u_text and data.complainant.name.value and data.complainant.name.value.lower() in u_text.lower():
                        is_complainant_phone = True
                        break

                if is_complainant_phone and data.complainant.phone.status == "missing":
                    data.complainant.phone = FieldProvenance(
                        value=ph,
                        status="confirmed",
                        source="user_message",
                    )
                elif data.suspect.phone.status == "missing":
                    data.suspect.phone = FieldProvenance(
                        value=ph,
                        status="confirmed",
                        source="user_message",
                    )

        if detected_urls:
            data.suspect.url = FieldProvenance(
                value=detected_urls[0],
                status="confirmed",
                source="user_message",
            )

        # 8. Detect Incident Type
        combined_user_text = " ".join(user_messages).lower()
        incident_type = self._classify_incident_type(combined_user_text, data)
        data.incident.type = FieldProvenance(
            value=incident_type,
            status="confirmed" if any(w in combined_user_text for w in ["upi", "fraud", "phishing", "stolen"]) else "inferred",
            source="user_message" if "upi" in combined_user_text else "ai_inferred",
        )

        # 9. Synthesize Incident Narrative Description
        narrative = self._build_incident_narrative(user_messages, data)
        data.incident.description = FieldProvenance(
            value=narrative,
            status="confirmed",
            source="user_message",
        )

        # 10. Merge Case Profile / OCR if Available (Preserving user confirmation priority)
        if existing_profile:
            self._merge_case_profile(data, existing_profile)

        # 11. Determine Missing Fields based on Incident Requirements
        reqs = INCIDENT_REQUIREMENTS.get(incident_type, INCIDENT_REQUIREMENTS["general"])
        missing: List[str] = []

        for req_field in reqs["required"]:
            if req_field == "complainant_name" and data.complainant.name.status == "missing":
                missing.append("complainant_name")
            elif req_field == "amount" and data.financial.amount.status == "missing":
                missing.append("amount")
            elif req_field == "incident_date" and data.incident.date.status == "missing":
                missing.append("incident_date")
            elif req_field == "incident_location" and data.incident.location.status == "missing":
                missing.append("incident_location")
            elif req_field == "imei_number" and data.device.imei.status == "missing":
                missing.append("imei_number")
            elif req_field == "description" and data.incident.description.status == "missing":
                missing.append("description")

        # Useful contextual fields if required fields are satisfied
        for useful_field in reqs.get("useful", []):
            if useful_field == "bank" and data.financial.bank.status == "missing":
                missing.append("bank")
            elif useful_field == "transaction_id" and data.financial.transaction_id.status == "missing" and data.financial.utr.status == "missing":
                # Only ask for transaction ID if amount was involved and transaction ID not known
                if data.financial.amount.value:
                    missing.append("transaction_id")

        data.missing_fields = missing

        # 12. Build Known Fields Map
        data.known_fields = {
            "incident_type": data.incident.type.value,
            "complainant_name": data.complainant.name.value,
            "amount": data.financial.amount.value,
            "transaction_id": data.financial.transaction_id.value,
            "incident_date": data.incident.date.value,
            "incident_time": data.incident.time.value,
            "bank": data.financial.bank.value,
            "upi_id": data.financial.upi_id.value,
            "imei": data.device.imei.value,
            "description": data.incident.description.value,
        }

        return data

    def _classify_incident_type(self, text: str, data: ExtractedFIRData) -> str:
        if any(w in text for w in ["upi", "qr code", "paise kat", "deducted", "debited", "bank account se", "paise chale gaye"]):
            return "financial_cyber_fraud"
        if any(w in text for w in ["stolen", "chori", "imei", "lost my phone", "snatched"]):
            return "mobile_theft"
        if any(w in text for w in ["courier", "phishing", "fake link", "clicked the link", "lottery link"]):
            return "phishing"
        if any(w in text for w in ["whatsapp hack", "instagram hack", "locked out", "otp forward"]):
            return "account_takeover"
        if any(w in text for w in ["video call", "blackmail", "leak", "sextortion", "nude"]):
            return "sextortion"
        if any(w in text for w in ["pan card", "cibil", "fake loan", "identity theft"]):
            return "identity_theft"
        if data.financial.amount.value:
            return "financial_cyber_fraud"
        return "general"

    def _build_incident_narrative(self, user_messages: List[str], data: ExtractedFIRData) -> str:
        """
        Builds a factual, chronological narrative from user statements
        without hallucinating fictional details or motives.
        """
        if not user_messages:
            return ""

        # Filter out short acknowledgments or noise
        meaningful_statements = []
        for msg in user_messages:
            cleaned = msg.strip()
            if len(cleaned) >= 8 and not cleaned.lower() in {"create fir", "yes", "ok", "haan", "thanks", "hello", "hi"}:
                meaningful_statements.append(cleaned)

        if not meaningful_statements:
            meaningful_statements = user_messages

        # If Groq client is available, generate a concise factual synthesis
        if _groq_client and len(meaningful_statements) > 1:
            try:
                prompt = (
                    "You are a cybercrime legal reporting assistant. "
                    "Synthesize the victim's chronological statements below into a factual incident description for a police complaint/FIR. "
                    "STRICT RULES:\n"
                    "- Use ONLY the facts explicitly provided by the user.\n"
                    "- Do NOT invent names, motives, dates, locations, or legal sections.\n"
                    "- Write in third-person formal style (e.g., 'The complainant received...').\n"
                    "- Maximum 3 sentences.\n\n"
                    "User statements:\n" + "\n".join(f"- {s}" for s in meaningful_statements)
                )
                res = _groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=150,
                    temperature=0.0,
                )
                content = res.choices[0].message.content
                if content and len(content.strip()) > 20:
                    return content.strip()
            except Exception as e:
                logger.debug(f"LLM narrative synthesis fallback: {e}")

        # Deterministic chronological synthesis fallback
        narrative_parts = []
        for s in meaningful_statements:
            cleaned = s.rstrip(".")
            narrative_parts.append(cleaned)
        return ". ".join(narrative_parts) + "."

    def _merge_case_profile(self, data: ExtractedFIRData, profile: Dict[str, Any]):
        """
        Merges existing case profile fields if not already confirmed by conversation.
        """
        if not profile:
            return

        # Complainant Name
        c_name = profile.get("complainant_name") or profile.get("victim_name")
        if c_name and data.complainant.name.status == "missing":
            data.complainant.name = FieldProvenance(
                value=c_name,
                status="inferred",
                source="case_profile",
            )

        # Amount
        amt = profile.get("amount_lost") or profile.get("amount")
        if amt and data.financial.amount.status == "missing":
            try:
                data.financial.amount = FieldProvenance(
                    value=float(amt),
                    status="inferred",
                    source="case_profile",
                )
            except ValueError:
                pass

        # Transaction ID
        txn = profile.get("transaction_id") or profile.get("utr_number")
        if txn and data.financial.transaction_id.status == "missing":
            data.financial.transaction_id = FieldProvenance(
                value=str(txn),
                status="inferred",
                source="case_profile",
            )

        # Date
        d_val = profile.get("incident_date")
        if d_val and data.incident.date.status == "missing":
            data.incident.date = FieldProvenance(
                value=str(d_val),
                status="inferred",
                source="case_profile",
            )

        # Time
        t_val = profile.get("incident_time")
        if t_val and data.incident.time.status == "missing":
            data.incident.time = FieldProvenance(
                value=str(t_val),
                status="inferred",
                source="case_profile",
            )

        # Location
        loc_val = profile.get("incident_location")
        if loc_val and data.incident.location.status == "missing":
            data.incident.location = FieldProvenance(
                value=str(loc_val),
                status="inferred",
                source="case_profile",
            )


# ==========================================================
# Question & Summary Formatters
# ==========================================================

def format_extracted_summary(fir_data: ExtractedFIRData) -> str:
    """
    Builds the user-facing summary of facts already extracted from the conversation,
    ensuring trust and explicitly letting the user know they will not repeat info.
    """
    lines = ["**I found these details from our conversation:**", ""]

    i_type = (fir_data.incident.type.value or "Cyber Offence").replace("_", " ").title()
    lines.append(f"- **Incident:** {i_type}")

    if fir_data.financial.amount.value is not None:
        try:
            amt_num = int(float(fir_data.financial.amount.value))
            lines.append(f"- **Amount:** ₹{amt_num:,}")
        except (ValueError, TypeError):
            lines.append(f"- **Amount:** {fir_data.financial.amount.value}")

    if fir_data.incident.date.value:
        lines.append(f"- **Date:** {fir_data.incident.date.value}")

    if fir_data.incident.time.value:
        lines.append(f"- **Approximate Time:** {fir_data.incident.time.value}")

    if fir_data.financial.transaction_id.value:
        lines.append(f"- **Transaction ID:** {fir_data.financial.transaction_id.value}")

    if fir_data.financial.bank.value:
        lines.append(f"- **Bank:** {fir_data.financial.bank.value}")

    if fir_data.financial.upi_id.value:
        lines.append(f"- **UPI ID:** {fir_data.financial.upi_id.value}")

    if fir_data.device.imei.value:
        lines.append(f"- **IMEI:** {fir_data.device.imei.value}")

    if fir_data.incident.description.value:
        desc_snippet = fir_data.incident.description.value
        if len(desc_snippet) > 120:
            desc_snippet = desc_snippet[:117] + "..."
        lines.append(f"- **Incident Summary:** {desc_snippet}")

    lines.append("")
    lines.append("**I won't ask you to repeat these.**")
    return "\n".join(lines)


def format_confirmation_summary(fir_data: ExtractedFIRData) -> str:
    """
    Formats the final structured complaint summary for user confirmation
    before document generation.
    """
    form = fir_data.to_legacy_form()
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
    if form.get("bank_account"):
        lines.append(f"- **Bank / Account Involved:** {form['bank_account']}")
    if form.get("upi_id"):
        lines.append(f"- **UPI ID:** {form['upi_id']}")
    if form.get("imei_number"):
        lines.append(f"- **IMEI Number:** {form['imei_number']}")

    lines.append("")
    lines.append(f"**Incident Narrative:**\n{form.get('description', '')}")
    lines.append("")
    lines.append("Please confirm that these details are correct before I generate your official police complaint draft.")

    return "\n".join(lines)


def get_next_question(fir_data: ExtractedFIRData) -> Optional[Tuple[str, str]]:
    """
    Returns (field_name, question_text) for the next genuinely missing field.
    Returns None if all required fields are present.
    """
    if fir_data.contradictions:
        # Ask to resolve contradiction first
        c_msg = fir_data.contradictions[0]
        q = f"You previously mentioned an earlier amount, but later updated it. Which amount should I record in the complaint?"
        return ("amount", q)

    if not fir_data.missing_fields:
        return None

    next_field = fir_data.missing_fields[0]
    question = FIELD_QUESTION_MAP.get(
        next_field,
        f"Please provide your {next_field.replace('_', ' ')}."
    )
    return (next_field, question)
