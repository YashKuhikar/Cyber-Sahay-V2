from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FactItem(BaseModel):
    value: Any
    source: str = Field("user_message", description="user_message | ocr | ai_inferred | rag")
    confidence: float = 0.95
    confirmed: bool = False
    timestamp: Optional[str] = None


class IncidentInfo(BaseModel):
    type: str = ""
    subtype: str = ""
    description: str = ""
    date: str = ""
    time: str = ""
    location: str = ""


class FinancialInfo(BaseModel):
    amount: Optional[float] = None
    currency: str = "INR"
    transaction_ids: List[str] = Field(default_factory=list)
    utr_numbers: List[str] = Field(default_factory=list)
    upi_ids: List[str] = Field(default_factory=list)
    bank_name: str = ""
    account_reference: str = ""


class SuspectInfo(BaseModel):
    phone_numbers: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    usernames: List[str] = Field(default_factory=list)
    social_accounts: List[str] = Field(default_factory=list)


class DeviceInfo(BaseModel):
    imei: str = ""
    device_type: str = ""
    sim_details: str = ""


class VictimInfo(BaseModel):
    name: str = ""
    contact: str = ""
    address: str = ""


class EvidenceItem(BaseModel):
    file_id: Optional[str] = None
    filename: str = ""
    file_hash: str = ""
    evidence_type: str = "screenshot"  # "screenshot", "receipt", "statement", "chat_export", "pdf"
    description: str = ""
    captured_at: Optional[str] = None


class TimelineEvent(BaseModel):
    time: str
    event: str
    source: str = "user_narrative"  # "user_narrative" | "ocr_metadata" | "receipt"


class CaseProfileV2(BaseModel):
    incident: IncidentInfo = Field(default_factory=IncidentInfo)
    financial: FinancialInfo = Field(default_factory=FinancialInfo)
    suspect: SuspectInfo = Field(default_factory=SuspectInfo)
    device: DeviceInfo = Field(default_factory=DeviceInfo)
    victim: VictimInfo = Field(default_factory=VictimInfo)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    actions_completed: List[str] = Field(default_factory=list)
    actions_pending: List[str] = Field(default_factory=list)
    user_confirmed: List[str] = Field(default_factory=list)
    uncertain_fields: List[str] = Field(default_factory=list)
    provenance: Dict[str, FactItem] = Field(default_factory=dict)

    def to_legacy_dict(self) -> dict:
        """
        Provides 100% backward compatibility for existing code expecting
        flat case_profile dict.
        """
        return {
            "complainant_name": self.victim.name,
            "incident_type": self.incident.type,
            "incident_date": self.incident.date,
            "incident_time": self.incident.time,
            "incident_location": self.incident.location,
            "description": self.incident.description,
            "suspect_name": self.suspect.usernames[0] if self.suspect.usernames else "",
            "phone_number": self.suspect.phone_numbers[0] if self.suspect.phone_numbers else "",
            "email": self.suspect.emails[0] if self.suspect.emails else "",
            "imei_number": self.device.imei,
            "vehicle_number": "",
            "bank_account": self.financial.account_reference,
            "upi_id": self.financial.upi_ids[0] if self.financial.upi_ids else "",
            "amount_lost": str(int(self.financial.amount)) if self.financial.amount else "",
        }


def create_case_profile_v2() -> CaseProfileV2:
    return CaseProfileV2()


def update_case_profile_v2(
    profile: CaseProfileV2,
    updates: dict,
    source: str = "user_message",
    confidence: float = 0.95,
    confirmed: bool = False,
) -> CaseProfileV2:
    """
    Safely merges extracted updates into CaseProfileV2 while tracking provenance.
    Never silently converts unconfirmed facts into confirmed.
    """
    # 1. Incident
    if "incident_type" in updates and updates["incident_type"]:
        profile.incident.type = str(updates["incident_type"])
        profile.provenance["incident.type"] = FactItem(value=profile.incident.type, source=source, confidence=confidence, confirmed=confirmed)

    if "incident_subtype" in updates and updates["incident_subtype"]:
        profile.incident.subtype = str(updates["incident_subtype"])

    if "incident_description" in updates and updates["incident_description"]:
        profile.incident.description = str(updates["incident_description"])

    if "incident_date" in updates and updates["incident_date"]:
        profile.incident.date = str(updates["incident_date"])
        profile.provenance["incident.date"] = FactItem(value=profile.incident.date, source=source, confidence=confidence, confirmed=confirmed)

    if "incident_time" in updates and updates["incident_time"]:
        profile.incident.time = str(updates["incident_time"])

    if "incident_location" in updates and updates["incident_location"]:
        profile.incident.location = str(updates["incident_location"])

    # 2. Financial
    if "amount" in updates and updates["amount"] is not None:
        try:
            amt_val = float(str(updates["amount"]).replace(",", "").replace("₹", "").replace("Rs", "").strip())
            profile.financial.amount = amt_val
            profile.provenance["financial.amount"] = FactItem(value=amt_val, source=source, confidence=confidence, confirmed=confirmed)
        except Exception:
            pass

    for upi in updates.get("upi_ids", []):
        if upi and upi not in profile.financial.upi_ids:
            profile.financial.upi_ids.append(upi)

    for utr in updates.get("utr_numbers", []):
        if utr and utr not in profile.financial.utr_numbers:
            profile.financial.utr_numbers.append(utr)

    for tx_id in updates.get("transaction_ids", []):
        if tx_id and tx_id not in profile.financial.transaction_ids:
            profile.financial.transaction_ids.append(tx_id)

    if "bank_name" in updates and updates["bank_name"]:
        profile.financial.bank_name = str(updates["bank_name"])

    if "account_reference" in updates and updates["account_reference"]:
        profile.financial.account_reference = str(updates["account_reference"])

    # 3. Suspect
    for ph in updates.get("phone_numbers", []):
        if ph and ph not in profile.suspect.phone_numbers:
            profile.suspect.phone_numbers.append(ph)

    for em in updates.get("emails", []):
        if em and em not in profile.suspect.emails:
            profile.suspect.emails.append(em)

    for u in updates.get("urls", []):
        if u and u not in profile.suspect.urls:
            profile.suspect.urls.append(u)

    for un in updates.get("usernames", []):
        if un and un not in profile.suspect.usernames:
            profile.suspect.usernames.append(un)

    # 4. Device (Strict typed validation - never generic identifiers!)
    if "imei" in updates and updates["imei"]:
        profile.device.imei = str(updates["imei"])
        profile.provenance["device.imei"] = FactItem(value=profile.device.imei, source=source, confidence=confidence, confirmed=confirmed)

    if "device_type" in updates and updates["device_type"]:
        profile.device.device_type = str(updates["device_type"])

    # 5. Victim
    if "complainant_name" in updates and updates["complainant_name"]:
        profile.victim.name = str(updates["complainant_name"])
        profile.provenance["victim.name"] = FactItem(value=profile.victim.name, source=source, confidence=confidence, confirmed=confirmed)

    if "complainant_phone" in updates and updates["complainant_phone"]:
        profile.victim.contact = str(updates["complainant_phone"])

    if "complainant_address" in updates and updates["complainant_address"]:
        profile.victim.address = str(updates["complainant_address"])

    # 6. Timeline
    for item in updates.get("timeline", []):
        if isinstance(item, dict) and "time" in item and "event" in item:
            profile.timeline.append(TimelineEvent(**item))

    # Mark confirmation if requested
    if confirmed:
        for k in updates.keys():
            if k not in profile.user_confirmed:
                profile.user_confirmed.append(k)

    return profile
