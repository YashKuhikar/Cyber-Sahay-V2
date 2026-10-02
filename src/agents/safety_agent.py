from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from ..rag.knowledge_registry import OFFICIAL_REPORTING_CHANNELS


class EmergencyActionPlan(BaseModel):
    is_emergency: bool
    incident_category: str
    urgency_level: str  # "CRITICAL", "HIGH", "STANDARD", "INFO"
    immediate_actions: List[str]
    evidence_to_preserve: List[str]
    official_channels: List[dict]
    single_next_question: str
    safe_explanation: str
    confidence: float = 0.95


class SafetyAgent:
    """
    Dedicated Pre-RAG Safety and Emergency Triage Agent.
    Evaluates victim messages for active harm, containment urgency,
    and returns deterministic, safe immediate containment instructions.
    """

    # Deterministic triggers for active financial fraud
    FINANCIAL_EMERGENCY_PATTERNS = [
        r"(?:paise|money|rupaye|rs\.?|amount|inr|₹)\s*(?:[\d,]+\s*)?(?:was|got|is)?\s*(?:cut|kat|deducted|chale gaye|nikal gaye|debit|debited|stolen|lost|scammed)",
        r"(?:upi|bank|account|card|credit card|debit card|otp|atm|netbanking)\s*(?:fraud|scam|hack|chori|kat gaya|cut gaya|debited)",
        r"(?:transfer|sent|paid|debited)\s*(?:unauthorized|without\s*my\s*permission|dhoke\s*se|galti\s*se)",
        r"(?:lost|chale gaye|took|debited)\s*(?:₹|rs\.?|inr)?\s*[\d,]+",
        r"(?:job|vip task|tasks).*(?:stopped paying|telegram)",
        r"(?:anydesk|teamviewer|quicksupport|remote access).*(?:money|rs|took|deducted|stolen)",
        r"(?:kyc|manager|bank manager|call).*(?:otp|debited)",
        r"mere\s+account\s+se\s+paise",
        r"माझ्या\s+खात्यातून",
        r"mazya\s+account\s+madhun",
        r"खात्यातून\s+पैसे\s+गेले",
        r"मेरे\s+upi\s+से",
        r"(?:qr|क्युआर)\s*कोड",
    ]

    # Deterministic triggers for account takeover / unauthorized access
    TAKEOVER_PATTERNS = [
        r"(?:whatsapp|instagram|facebook|email|gmail|telegram)\s*(?:hack|hacked|taken over|otp forwarded|locked out|got hacked)",
        r"(?:hacked|access nahi ho raha|account chala gaya)",
        r"(?:sim\s*swap|e-?sim\s*fraud|network\s*gayab|no\s*service|no\s*signal)",
    ]

    # Deterministic triggers for extortion, sextortion, blackmail
    EXTORTION_PATTERNS = [
        r"(?:sextortion|blackmail|threaten|threat|video call|nude|private photo|leak|extortion)",
        r"(?:dhamki|police ban kar call|cbi ban kar call|digital arrest)",
    ]

    # Deterministic triggers for ransomware
    RANSOMWARE_PATTERNS = [
        r"(?:ransomware|files encrypted|bitcoin demand|locked computer|pay ransom|\.locked)",
    ]

    # Deterministic triggers for stolen device
    DEVICE_THEFT_PATTERNS = [
        r"(?:phone\s*stolen|mobile\s*(?:phone\s*)?(?:was\s*)?stolen|mobile\s*chori|lost\s*my\s*phone|phone\s*snatched|device\s*stolen|mobile\s*haravla|imei)",
    ]

    # Deterministic triggers for identity theft & loan fraud
    IDENTITY_THEFT_PATTERNS = [
        r"(?:loan\s+on\s+my\s+(?:pan|aadhaar|id)|identity\s*theft|fake\s*loan|cibil|pan\s*card\s*(?:misuse|without)|collection\s*agents)",
    ]

    # Deterministic triggers for social media impersonation & cyberbullying
    CYBERBULLYING_PATTERNS = [
        r"(?:fake\s*(?:profile|account|instagram|facebook)|vulgar\s*messages|cyber\s*bullying|harassment|photos?\s*(?:misuse|morphed))",
    ]

    def __init__(self):
        self._compiled_financial = [re.compile(p, re.IGNORECASE) for p in self.FINANCIAL_EMERGENCY_PATTERNS]
        self._compiled_takeover = [re.compile(p, re.IGNORECASE) for p in self.TAKEOVER_PATTERNS]
        self._compiled_extortion = [re.compile(p, re.IGNORECASE) for p in self.EXTORTION_PATTERNS]
        self._compiled_ransomware = [re.compile(p, re.IGNORECASE) for p in self.RANSOMWARE_PATTERNS]
        self._compiled_device = [re.compile(p, re.IGNORECASE) for p in self.DEVICE_THEFT_PATTERNS]
        self._compiled_identity = [re.compile(p, re.IGNORECASE) for p in self.IDENTITY_THEFT_PATTERNS]
        self._compiled_cyberbullying = [re.compile(p, re.IGNORECASE) for p in self.CYBERBULLYING_PATTERNS]

    def evaluate(self, query: str) -> EmergencyActionPlan:
        """
        Fast-triage user message before standard RAG processing.
        """
        text = query.strip()

        # 1. Active Financial Fraud
        for pat in self._compiled_financial:
            if pat.search(text):
                ch_1930 = OFFICIAL_REPORTING_CHANNELS["cybercrime_helpline"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="financial_fraud",
                    urgency_level="CRITICAL",
                    immediate_actions=[
                        "Call the National Cyber Financial Fraud Helpline at 1930 immediately or report on cybercrime.gov.in. Earlier reporting allows the financial intermediary to attempt freezing the beneficiary wallet/account before withdrawal.",
                        "Contact your bank's 24x7 emergency helpline or use your mobile banking app to immediately block the affected debit/credit card, UPI access, or account.",
                        "Do not delete SMS alerts, bank push notifications, or UPI debit reference messages.",
                    ],
                    evidence_to_preserve=[
                        "12-digit UPI reference (UTR number) or Bank Transaction ID",
                        "SMS debit notification showing time and amount",
                        "Screenshot of payment receipt showing recipient UPI ID / Account",
                        "Caller phone number, WhatsApp chat, or phishing link if applicable",
                    ],
                    official_channels=[
                        {
                            "name": ch_1930.name,
                            "helpline": ch_1930.helpline,
                            "portal_url": ch_1930.portal_url,
                            "authority": ch_1930.authority,
                            "notes": ch_1930.advisory_notes,
                        }
                    ],
                    single_next_question="Have you already contacted your bank to block the card/UPI, or do you need assistance drafting a formal Police Complaint / FIR Draft?",
                    safe_explanation="Unauthorized funds transfer detected. Prompt reporting to 1930 and your bank's fraud monitoring cell is critical to initiate the Citizen Financial Cyber Fraud inter-bank freeze protocol.",
                    confidence=0.98,
                )

        # 2. Extortion / Sextortion / Threat
        for pat in self._compiled_extortion:
            if pat.search(text):
                ncrp = OFFICIAL_REPORTING_CHANNELS["national_cyber_portal"]
                errs = OFFICIAL_REPORTING_CHANNELS["emergency_response"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="extortion_blackmail",
                    urgency_level="CRITICAL",
                    immediate_actions=[
                        "Do NOT transfer any money or comply with extortion demands. Paying scammers does not guarantee they will delete media and usually leads to higher demands.",
                        "Cease all communication with the blackmailer immediately. Do NOT delete chats or call logs.",
                        "Report the incident immediately on the National Cyber Crime Reporting Portal (cybercrime.gov.in) under the 'Women/Children related crime' or 'Other Cyber Crime' section.",
                        "If you face imminent physical threats or intimidation, dial 112 for immediate emergency police assistance.",
                    ],
                    evidence_to_preserve=[
                        "Screenshots of blackmail messages, threats, and profile details with timestamps",
                        "Phone numbers, usernames, and social media handles of the blackmailer",
                        "Payment account or UPI details sent by the blackmailer (without making payment)",
                    ],
                    official_channels=[
                        {"name": ncrp.name, "portal_url": ncrp.portal_url, "authority": ncrp.authority, "notes": ncrp.advisory_notes},
                        {"name": errs.name, "helpline": errs.helpline, "authority": errs.authority, "notes": errs.advisory_notes},
                    ],
                    single_next_question="Are you in immediate physical safety, and would you like guidance on preserving digital evidence for a cybercrime complaint?",
                    safe_explanation="Extortion or digital coercion detected. Legal authorities recommend immediate stoppage of payment and preserving all conversation records for investigation.",
                    confidence=0.96,
                )

        # 3. Account Takeover / SIM Fraud
        for pat in self._compiled_takeover:
            if pat.search(text):
                chakshu = OFFICIAL_REPORTING_CHANNELS["chakshu"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="account_takeover",
                    urgency_level="HIGH",
                    immediate_actions=[
                        "Use account recovery mechanisms from a trusted, secure device to terminate all active sessions.",
                        "If SIM swap is suspected (sudden total loss of cellular signal), immediately contact your telecom service provider operator helpline from another phone.",
                        "Alert key contacts that your account was compromised so they do not respond to fraudulent money requests in your name.",
                    ],
                    evidence_to_preserve=[
                        "Screenshots of security alert emails or password reset SMS",
                        "Suspicious IP addresses or session locations listed in security settings",
                        "SMS or WhatsApp messages received prior to losing access",
                    ],
                    official_channels=[
                        {"name": chakshu.name, "portal_url": chakshu.portal_url, "authority": chakshu.authority, "notes": chakshu.advisory_notes}
                    ],
                    single_next_question="Have you notified your mobile telecom operator or your primary bank linked to that phone number?",
                    safe_explanation="Account takeover or SIM-level risk detected. Securing associated banking credentials and notifying telecom provider is the highest priority.",
                    confidence=0.94,
                )

        # 4. Stolen Device
        for pat in self._compiled_device:
            if pat.search(text):
                ceir = OFFICIAL_REPORTING_CHANNELS["sanchar_saathi_ceir"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="device_theft",
                    urgency_level="HIGH",
                    immediate_actions=[
                        "Contact your telecom operator immediately to block the SIM card and get a duplicate SIM to prevent OTP interception.",
                        "Remotely lock or erase your device using Find My Device (Android) or Find My (Apple).",
                        "File a lost/stolen mobile police report (e-FIR or complaint) to obtain an acknowledgment receipt.",
                        "Block the IMEI of the stolen device on Sanchar Saathi (CEIR portal: sancharsaathi.gov.in) using the police acknowledgment number.",
                    ],
                    evidence_to_preserve=[
                        "Device IMEI numbers (found on invoice box or bill)",
                        "Purchase invoice showing serial number",
                        "Police complaint acknowledgment number",
                    ],
                    official_channels=[
                        {"name": ceir.name, "portal_url": ceir.portal_url, "authority": ceir.authority, "notes": ceir.advisory_notes}
                    ],
                    single_next_question="Do you have your 15-digit IMEI number and purchase invoice available to prepare your Police Complaint / FIR Draft?",
                    safe_explanation="Stolen mobile device detected. Prompt SIM deactivation and CEIR IMEI blocking prevents misuse of mobile banking apps and digital identity.",
                    confidence=0.95,
                )

        # 5. Ransomware
        for pat in self._compiled_ransomware:
            if pat.search(text):
                cert = OFFICIAL_REPORTING_CHANNELS["cert_in"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="ransomware",
                    urgency_level="CRITICAL",
                    immediate_actions=[
                        "Immediately disconnect infected devices from the local network (unplug Ethernet, turn off Wi-Fi, disable Bluetooth).",
                        "Do not connect backup external drives to the infected machine.",
                        "Do not pay the ransom. Decryption is never guaranteed and funds criminal operations.",
                        "Report the cybersecurity incident to CERT-In (incident@cert-in.org.in / 1800-11-4949).",
                    ],
                    evidence_to_preserve=[
                        "Ransom note text or screenshot",
                        "Sample encrypted file and file extension",
                        "System logs and network traffic logs if available",
                    ],
                    official_channels=[
                        {"name": cert.name, "helpline": cert.helpline, "portal_url": cert.portal_url, "authority": cert.authority, "notes": cert.advisory_notes}
                    ],
                    single_next_question="Have you isolated the affected computer from your Wi-Fi and local network?",
                    safe_explanation="Ransomware infection detected. Network isolation is required immediately to prevent lateral spread to other systems.",
                    confidence=0.96,
                )

        # 6. Identity Theft & Loan Fraud
        for pat in self._compiled_identity:
            if pat.search(text):
                ncrp = OFFICIAL_REPORTING_CHANNELS["national_cyber_portal"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="identity_theft",
                    urgency_level="HIGH",
                    immediate_actions=[
                        "Download your official credit information report (CIBIL / Experian / Equifax) to identify all fraudulent loan inquiries and accounts.",
                        "Raise a formal dispute with the credit bureau and notify the lending bank/NBFC grievance officer in writing.",
                        "Lodge a formal cybercrime complaint at cybercrime.gov.in under Section 66C of the IT Act (Identity Theft).",
                    ],
                    evidence_to_preserve=[
                        "CIBIL/credit report showing unauthorized loan accounts",
                        "Loan account numbers and collection agency notice letters or SMS",
                        "Aadhaar and PAN details with proof of non-involvement",
                    ],
                    official_channels=[
                        {"name": ncrp.name, "portal_url": ncrp.portal_url, "authority": ncrp.authority, "notes": ncrp.advisory_notes}
                    ],
                    single_next_question="Do you have the credit report or loan account reference number to prepare a formal police complaint?",
                    safe_explanation="Identity theft or fraudulent loan detected. Documenting disputes with the credit bureau and lending entity protects against false financial liabilities.",
                    confidence=0.95,
                )

        # 7. Cyberbullying & Social Media Impersonation
        for pat in self._compiled_cyberbullying:
            if pat.search(text):
                ncrp = OFFICIAL_REPORTING_CHANNELS["national_cyber_portal"]
                return EmergencyActionPlan(
                    is_emergency=True,
                    incident_category="cyberbullying",
                    urgency_level="HIGH",
                    immediate_actions=[
                        "Do not engage with or provoke the impersonator or harasser.",
                        "Report the impersonating profile directly within the social media platform using the 'Report Impersonation' feature.",
                        "File an official complaint on cybercrime.gov.in and at your local cyber police station under Section 66D of the Information Technology Act.",
                    ],
                    evidence_to_preserve=[
                        "Direct URL of the fake profile or abusive account",
                        "High-resolution screenshots of profile, posts, and abusive direct messages with timestamps",
                        "Original photos/media proving prior ownership if morphed or stolen",
                    ],
                    official_channels=[
                        {"name": ncrp.name, "portal_url": ncrp.portal_url, "authority": ncrp.authority, "notes": ncrp.advisory_notes}
                    ],
                    single_next_question="Have you captured URL links and screenshots of the fake profile before reporting it?",
                    safe_explanation="Online impersonation or harassment detected. Reporting on the platform while preserving forensic screenshots allows lawful identification under IT Act Section 66D.",
                    confidence=0.94,
                )

        # Standard non-emergency
        return EmergencyActionPlan(
            is_emergency=False,
            incident_category="general",
            urgency_level="STANDARD",
            immediate_actions=[],
            evidence_to_preserve=[],
            official_channels=[],
            single_next_question="",
            safe_explanation="",
            confidence=0.90,
        )
