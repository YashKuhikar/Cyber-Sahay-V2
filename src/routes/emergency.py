from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


# ==========================================================
# Schemas
# ==========================================================

class HelplineItem(BaseModel):
    name: str
    number: Optional[str] = None
    portal_url: Optional[str] = None
    purpose: str
    operating_hours: str
    category: str


class ChecklistStep(BaseModel):
    step_number: int
    title: str
    action: str
    urgency: str  # "Immediate" | "High" | "Medium"
    reference_link: Optional[str] = None


class IncidentChecklist(BaseModel):
    incident_type: str
    title: str
    golden_period: str
    steps: List[ChecklistStep]


class PanicTriageRequest(BaseModel):
    incident_type: str = Field(..., example="upi_fraud")
    time_elapsed_hours: float = Field(..., example=0.5)
    amount_lost: Optional[float] = Field(None, example=25000.0)
    bank_name: Optional[str] = Field(None, example="State Bank of India")


class PanicTriageResponse(BaseModel):
    success: bool
    urgency_level: str  # "CRITICAL - GOLDEN HOUR" | "HIGH" | "STANDARD"
    summary: str
    immediate_actions: List[str]
    helpline_numbers: List[str]
    reporting_urls: List[str]
    timestamp: datetime


# ==========================================================
# Data Definitions
# ==========================================================

HELPLINES: List[HelplineItem] = [
    HelplineItem(
        name="National Cyber Financial Fraud Helpline",
        number="1930",
        portal_url="https://cybercrime.gov.in",
        purpose="Immediate reporting and fund freezing for online financial frauds within golden hours.",
        operating_hours="24x7 Free Service",
        category="Financial Fraud",
    ),
    HelplineItem(
        name="National Cyber Crime Reporting Portal",
        number=None,
        portal_url="https://cybercrime.gov.in",
        purpose="Official portal by Ministry of Home Affairs (MHA) to file cybercrime complaints online.",
        operating_hours="24x7 Online Portal",
        category="All Cybercrimes",
    ),
    HelplineItem(
        name="Sanchar Saathi (CEIR)",
        number=None,
        portal_url="https://sancharsaathi.gov.in",
        purpose="Block lost or stolen mobile phone IMEIs across all telecom operators across India.",
        operating_hours="24x7 Online Portal",
        category="Mobile Theft",
    ),
    HelplineItem(
        name="Chakshu Portal",
        number=None,
        portal_url="https://sancharsaathi.gov.in/sfc/",
        purpose="Report suspected fraud calls, SMS, WhatsApp spam, and fraudulent SIM connections.",
        operating_hours="24x7 Online Portal",
        category="Spam & Phishing",
    ),
    HelplineItem(
        name="National Emergency Response Support System (ERSS)",
        number="112",
        portal_url="https://112.gov.in",
        purpose="All-in-one emergency number for Police, Fire, and Ambulance across India.",
        operating_hours="24x7",
        category="Emergency Services",
    ),
    HelplineItem(
        name="National Women Helpline",
        number="1091",
        portal_url="http://ncw.nic.in",
        purpose="Support and rescue for women facing cyberstalking, harassment, and morphing/blackmail.",
        operating_hours="24x7",
        category="Women Safety & Harassment",
    ),
    HelplineItem(
        name="CERT-In (Indian Computer Emergency Response Team)",
        number="1800-11-4949",
        portal_url="https://www.cert-in.org.in",
        purpose="National agency for cyber incident response, malware analysis, and ransomware reporting.",
        operating_hours="Working Hours & Incident Email (incident@cert-in.org.in)",
        category="Hacking & Ransomware",
    ),
]

CHECKLISTS = {
    "financial_fraud": IncidentChecklist(
        incident_type="financial_fraud",
        title="Financial / UPI / Banking Fraud Response",
        golden_period="Golden Hour (First 2 - 24 hours is critical to freeze funds)",
        steps=[
            ChecklistStep(
                step_number=1,
                title="Dial 1930 Immediately",
                action="Call 1930 to trigger the Citizen Financial Cyber Fraud Reporting and Management System (CFCFRMS) to freeze money in transit.",
                urgency="Immediate",
            ),
            ChecklistStep(
                step_number=2,
                title="Notify Your Bank & Request Card/Account Freeze",
                action="Contact your bank's 24x7 customer care or mobile banking app to block debit cards, net banking, and UPI channels.",
                urgency="Immediate",
            ),
            ChecklistStep(
                step_number=3,
                title="Collect UTR & Transaction Evidence",
                action="Download bank statement, note 12-digit UPI UTR numbers, screenshot debit SMS alerts and payment screens.",
                urgency="High",
            ),
            ChecklistStep(
                step_number=4,
                title="File Official Complaint on cybercrime.gov.in",
                action="Submit an acknowledgment report on National Cybercrime Reporting Portal under 'Financial Fraud'.",
                urgency="High",
                reference_link="https://cybercrime.gov.in",
            ),
            ChecklistStep(
                step_number=5,
                title="Claim Zero Liability with Bank within 3 Days",
                action="Submit a written dispute letter under RBI Zero Liability Policy for unauthorized electronic transactions.",
                urgency="Medium",
            ),
        ],
    ),
    "mobile_theft": IncidentChecklist(
        incident_type="mobile_theft",
        title="Stolen or Lost Mobile Phone Response",
        golden_period="Immediate (Before SIM misuse or financial account takeover)",
        steps=[
            ChecklistStep(
                step_number=1,
                title="Deactivate / Block the SIM Card",
                action="Contact your telecom operator immediately to deactivate your SIM card and prevent OTP interception.",
                urgency="Immediate",
            ),
            ChecklistStep(
                step_number=2,
                title="Block Device IMEI on Sanchar Saathi (CEIR)",
                action="Submit your 15-digit IMEI number and police complaint copy on CEIR to blacklist the handset across all Indian networks.",
                urgency="Immediate",
                reference_link="https://sancharsaathi.gov.in",
            ),
            ChecklistStep(
                step_number=3,
                title="Remote Wipe and Lock Device",
                action="Use Google Find My Device (Android) or Apple Find My (iOS) to trigger remote lock and secure data erase.",
                urgency="High",
            ),
            ChecklistStep(
                step_number=4,
                title="Log Out of All Active Digital Accounts",
                action="From a desktop, change passwords and force logout on Google, Apple ID, WhatsApp, UPI apps, and social media.",
                urgency="High",
            ),
            ChecklistStep(
                step_number=5,
                title="File Police Complaint / FIR",
                action="File a lost property report or theft FIR at your local police station / e-FIR portal.",
                urgency="Medium",
            ),
        ],
    ),
    "sextortion_blackmail": IncidentChecklist(
        incident_type="sextortion_blackmail",
        title="Sextortion & Online Blackmail Response",
        golden_period="Immediate (Do NOT pay ransom)",
        steps=[
            ChecklistStep(
                step_number=1,
                title="DO NOT Pay Any Ransom Money",
                action="Paying money never stops blackmailers; they will only demand more. Cease all financial transfers immediately.",
                urgency="Immediate",
            ),
            ChecklistStep(
                step_number=2,
                title="Preserve Evidence Without Alteration",
                action="Take full screenshots of chats, video call logs, profile links, phone numbers, and payment QR codes before blocking.",
                urgency="Immediate",
            ),
            ChecklistStep(
                step_number=3,
                title="Deactivate / Privatize Social Accounts Temporarily",
                action="Lock your Facebook/Instagram friend lists and change privacy settings so fraudsters cannot contact your contacts.",
                urgency="High",
            ),
            ChecklistStep(
                step_number=4,
                title="Report on National Cybercrime Portal (Anonymously if Preferred)",
                action="File a complaint under 'Report Crime Related to Women/Children' or 'Cyber Blackmail' on cybercrime.gov.in.",
                urgency="High",
                reference_link="https://cybercrime.gov.in",
            ),
            ChecklistStep(
                step_number=5,
                title="Utilize StopNCII for Intimate Image Takedown",
                action="Create non-identifying cryptographic hashes on StopNCII.org to prevent intimate media distribution across Meta/tech platforms.",
                urgency="Medium",
                reference_link="https://stopncii.org",
            ),
        ],
    ),
}


# ==========================================================
# Endpoints
# ==========================================================

@router.get(
    "/helplines",
    response_model=List[HelplineItem],
    summary="Get verified directory of Indian national cyber emergency helplines",
)
def get_helplines():
    return HELPLINES


@router.get(
    "/checklists",
    response_model=List[IncidentChecklist],
    summary="Get all incident-specific panic and emergency checklists",
)
def get_checklists():
    return list(CHECKLISTS.values())


@router.get(
    "/checklists/{incident_type}",
    response_model=IncidentChecklist,
    summary="Get panic checklist for a specific cybercrime type",
)
def get_checklist_by_type(incident_type: str):
    normalized = incident_type.lower().strip()
    if normalized in CHECKLISTS:
        return CHECKLISTS[normalized]
    # Default to financial fraud checklist if unknown
    return CHECKLISTS["financial_fraud"]


from fastapi import Depends
from ..security.rate_limiter import rate_limit


@router.post(
    "/panic-triage",
    response_model=PanicTriageResponse,
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))],
    summary="Instant triage assessment and emergency action plan for victims (Rate Limit: 30/min)",
)
def panic_triage(request: PanicTriageRequest):
    is_golden_hour = request.time_elapsed_hours <= 2.0
    is_financial = "fraud" in request.incident_type.lower() or "upi" in request.incident_type.lower()

    if is_financial and is_golden_hour:
        urgency = "CRITICAL - GOLDEN HOUR"
        summary = (
            f"You are currently within the critical 2-hour Golden Window. Immediate action can prevent "
            f"the scammer from withdrawing the funds from the banking channel."
        )
        actions = [
            "DIAL 1930 IMMEDIATELY: Connect with the National Cyber Financial Reporting System.",
            "CALL BANK 24x7 HELPLINE: Request instant freeze on beneficiary account and transaction reversal.",
            "GATHER TRANSACTION UTRs: Keep your 12-digit UPI / IMPS reference numbers ready.",
            "LOG INTO CYBERCRIME.GOV.IN: Complete the formal ticket submission.",
        ]
        helplines = ["1930", "112"]
        urls = ["https://cybercrime.gov.in"]
    elif "theft" in request.incident_type.lower() or "mobile" in request.incident_type.lower():
        urgency = "HIGH"
        summary = "Prevent unauthorized access to your banking OTPs and personal data on the stolen device."
        actions = [
            "BLOCK SIM CARD IMMEDIATELY: Call your telecom operator to stop OTP receipt.",
            "BLOCK IMEI ON CEIR: Visit sancharsaathi.gov.in to blacklist handset nationwide.",
            "REMOTE WIPE DEVICE: Use Google Find My or Apple iCloud to erase phone.",
            "CHANGE PASSWORDS: Reset master passwords for Google, Apple ID, and Banking.",
        ]
        helplines = ["112"]
        urls = ["https://sancharsaathi.gov.in", "https://cybercrime.gov.in"]
    else:
        urgency = "HIGH"
        summary = "Follow standard emergency containment procedures to secure your digital identity and legal standing."
        actions = [
            "PRESERVE EVIDENCE: Take full screenshots with visible timestamps, URLs, and phone numbers.",
            "DO NOT PAY RANSOM OR ENGAGE FURTHER with the perpetrator.",
            "FILE REPORT ON CYBERCRIME.GOV.IN under appropriate category.",
            "CONTACT LOCAL CYBER POLICE STATION with generated CyberSahay FIR draft.",
        ]
        helplines = ["1930", "112", "1091"]
        urls = ["https://cybercrime.gov.in"]

    return PanicTriageResponse(
        success=True,
        urgency_level=urgency,
        summary=summary,
        immediate_actions=actions,
        helpline_numbers=helplines,
        reporting_urls=urls,
        timestamp=datetime.now(),
    )
