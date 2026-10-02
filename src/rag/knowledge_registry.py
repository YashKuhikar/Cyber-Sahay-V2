from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OfficialReportingChannel(BaseModel):
    name: str
    helpline: Optional[str] = None
    portal_url: Optional[str] = None
    authority: str
    authority_level: int = Field(1, description="1: Official Govt/Regulator, 2: Official Legislation, 3: Institutional, 4: Educational")
    purpose: str
    operating_hours: str
    jurisdiction: str = "India"
    advisory_notes: str
    last_verified: str = "2026-10-01"


# Centralized Authoritative Source Registry for Cyber Crime Victims in India
OFFICIAL_REPORTING_CHANNELS: Dict[str, OfficialReportingChannel] = {
    "cybercrime_helpline": OfficialReportingChannel(
        name="Citizen Financial Cyber Fraud Reporting System (CFCFRS) / National Cyber Crime Helpline",
        helpline="1930",
        portal_url="https://cybercrime.gov.in",
        authority="Ministry of Home Affairs (MHA), Government of India / I4C",
        authority_level=1,
        purpose="Immediate reporting of unauthorized financial cyber transactions to facilitate swift banking alert and inter-bank freezing protocol.",
        operating_hours="24x7 Toll-Free Helpline",
        advisory_notes="Earlier reporting immediately after the transaction helps increase the likelihood of funds being put on hold before withdrawal.",
    ),
    "national_cyber_portal": OfficialReportingChannel(
        name="National Cyber Crime Reporting Portal (NCRP)",
        helpline=None,
        portal_url="https://cybercrime.gov.in",
        authority="Indian Cyber Crime Coordination Centre (I4C), MHA",
        authority_level=1,
        purpose="Official national portal for lodging online cybercrime complaints including financial fraud, cyber stalking, social media harassment, and child sexual abuse material (CSAM).",
        operating_hours="24x7 Online Portal",
        advisory_notes="Victims can download an acknowledgement receipt after filing on cybercrime.gov.in.",
    ),
    "sanchar_saathi_ceir": OfficialReportingChannel(
        name="Sanchar Saathi - Central Equipment Identity Register (CEIR)",
        helpline=None,
        portal_url="https://sancharsaathi.gov.in",
        authority="Department of Telecommunications (DoT), Ministry of Communications",
        authority_level=1,
        purpose="Blocking and tracing lost or stolen mobile phone IMEIs across all telecom operators across India.",
        operating_hours="24x7 Online Portal",
        advisory_notes="Requires police complaint acknowledgment number or police report to initiate IMEI blocking.",
    ),
    "chakshu": OfficialReportingChannel(
        name="Chakshu Portal - Suspected Fraud Communication Reporting",
        helpline=None,
        portal_url="https://sancharsaathi.gov.in/sfc/",
        authority="Department of Telecommunications (DoT)",
        authority_level=1,
        purpose="Reporting suspected fraudulent communications received via SMS, WhatsApp, or phone calls (e.g. fake KYC, electricity disconnection, impersonation).",
        operating_hours="24x7 Online Portal",
        advisory_notes="Used for intelligence and telecom-level number blocking; does not replace financial fraud reporting on 1930.",
    ),
    "emergency_response": OfficialReportingChannel(
        name="National Emergency Response Support System (ERSS)",
        helpline="112",
        portal_url="https://112.gov.in",
        authority="Ministry of Home Affairs, Government of India",
        authority_level=1,
        purpose="Immediate emergency police, fire, or medical dispatch for imminent physical danger, kidnapping, or grave extortion threats.",
        operating_hours="24x7 Toll-Free Emergency",
        advisory_notes="For emergencies requiring on-ground police dispatch.",
    ),
    "cert_in": OfficialReportingChannel(
        name="Indian Computer Emergency Response Team (CERT-In)",
        helpline="1800-11-4949",
        portal_url="https://www.cert-in.org.in",
        authority="Ministry of Electronics and Information Technology (MeitY)",
        authority_level=1,
        purpose="National agency for incident response, malware, ransomware analysis, and major cybersecurity breaches.",
        operating_hours="Working hours / Online Incident Reporting",
        advisory_notes="Mandated under Section 70B of the Information Technology Act 2000.",
    ),
    "rbi_ombudsman": OfficialReportingChannel(
        name="Reserve Bank of India (RBI) Ombudsman",
        helpline="14448",
        portal_url="https://cms.rbi.org.in",
        authority="Reserve Bank of India (RBI)",
        authority_level=1,
        purpose="Escalation channel if a scheduled commercial bank or payment aggregator fails to resolve unauthorized electronic banking transaction grievances within 30 days.",
        operating_hours="Working hours / Online CMS",
        advisory_notes="Subject to RBI Circular on Limiting Liability of Customers in Unauthorized Electronic Banking Transactions.",
    ),
}


class LegalDocumentMetadata(BaseModel):
    source: str
    authority: str
    document_type: str  # "Act", "Circular", "Advisory", "Regulation", "SOP"
    law_name: str
    section: Optional[str] = None
    topic: str
    jurisdiction: str = "India"
    effective_date: Optional[str] = None
    language: str = "English"
    page: Optional[str] = None
    source_url: Optional[str] = None
    authority_level: int = 1


# Topic-to-Authority priority mapping for metadata-aware retrieval
TOPIC_METADATA_PRIORITIES = {
    "upi_fraud": {"topics": ["financial_fraud", "banking", "electronic_transfer", "rbi"], "laws": ["IT Act Section 66D", "RBI Circular 2017"]},
    "banking_fraud": {"topics": ["banking", "unauthorized_transaction", "rbi"], "laws": ["RBI Circular 2017", "IT Act Section 43"]},
    "phishing": {"topics": ["phishing", "identity_theft", "social_engineering"], "laws": ["IT Act Section 66C", "IT Act Section 66D"]},
    "mobile_theft": {"topics": ["device_theft", "imei", "telecom"], "laws": ["CEIR SOP", "BNS Section 303"]},
    "identity_theft": {"topics": ["identity_theft", "impersonation", "aadhaar"], "laws": ["IT Act Section 66C", "IT Act Section 66D"]},
    "sextortion": {"topics": ["extortion", "blackmail", "intimate_image_abuse"], "laws": ["IT Act Section 67", "IT Act Section 67A", "BNS Section 308"]},
    "ransomware": {"topics": ["ransomware", "malware", "data_encryption"], "laws": ["IT Act Section 43", "IT Act Section 66", "CERT-In Advisory"]},
    "cyberbullying": {"topics": ["harassment", "cyberstalking", "defamation"], "laws": ["IT Act Section 67", "BNS Section 78", "BNS Section 356"]},
}


def enrich_document_metadata(metadata: dict) -> dict:
    """
    Enriches raw document metadata with structured legal classification,
    authority levels, official law names, and jurisdiction.
    """
    enriched = dict(metadata)
    source_str = str(enriched.get("source", "")).lower()

    # Default baseline
    enriched.setdefault("jurisdiction", "India")
    enriched.setdefault("language", "English")

    if "government_guidelines" in source_str or "rbi" in source_str or "guidelines" in source_str:
        enriched["authority"] = "Reserve Bank of India / Ministry of Home Affairs"
        enriched["document_type"] = "Government Guidelines / Circular"
        enriched["authority_level"] = 1
        enriched["topic"] = "financial_fraud_and_banking_safety"
        enriched["law_name"] = "RBI Master Direction / Citizen Protection Guidelines"
    elif "rules_and_regulations" in source_str:
        enriched["authority"] = "Ministry of Electronics and Information Technology (MeitY)"
        enriched["document_type"] = "Statutory Rules & Regulations"
        enriched["authority_level"] = 1
        enriched["topic"] = "intermediary_guidelines_and_digital_media"
        enriched["law_name"] = "Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules"
    elif "laws" in source_str or "act" in source_str:
        enriched["authority"] = "Parliament of India"
        enriched["document_type"] = "Primary Legislation / Statutory Act"
        enriched["authority_level"] = 2
        if "it act" in source_str or "information technology" in source_str:
            enriched["law_name"] = "Information Technology Act, 2000"
            enriched["topic"] = "cyber_offences_and_penalties"
        elif "consumer" in source_str:
            enriched["law_name"] = "Consumer Protection Act, 2019"
            enriched["topic"] = "e_commerce_consumer_rights"
        elif "bns" in source_str or "nyaya" in source_str:
            enriched["law_name"] = "Bharatiya Nyaya Sanhita, 2023"
            enriched["topic"] = "criminal_offences_cheating_extortion"
        else:
            enriched["law_name"] = "Indian Cyber Legislation"
            enriched["topic"] = "legal_aid"
    elif "consumer" in source_str:
        enriched["authority"] = "Ministry of Consumer Affairs"
        enriched["document_type"] = "Consumer Protection Legislation"
        enriched["authority_level"] = 2
        enriched["law_name"] = "Consumer Protection Act, 2019"
        enriched["topic"] = "unfair_trade_practices"
    else:
        enriched.setdefault("authority", "Official Indian Regulatory Source")
        enriched.setdefault("document_type", "Reference Material")
        enriched.setdefault("authority_level", 3)
        enriched.setdefault("law_name", "Indian Legal Framework")
        enriched.setdefault("topic", "general_cybercrime_guidance")

    return enriched

