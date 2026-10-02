from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StructuredVictimResponse(BaseModel):
    markdown_text: str
    response_type: str  # "emergency", "advice", "fact_confirmation", "fir_questionnaire", "fir_draft", "complaint_draft"
    urgency: str  # "critical", "high", "standard", "info"
    actions: List[str] = Field(default_factory=list)
    evidence_needed: List[str] = Field(default_factory=list)
    next_action: str = ""
    citations_summary: List[dict] = Field(default_factory=list)


class ResponseFormatter:
    """
    Formats multi-agent outcomes into clear, empathetic, victim-friendly markdown
    with immediate actionable containment steps placed first for high-urgency incidents.
    """

    @classmethod
    def format_incident_response(
        cls,
        summary_explanation: str,
        actions: List[str],
        evidence_items: List[str],
        legal_info: str,
        next_step: str,
        urgency: str = "standard",
        language: str = "English",
        why_it_matters: Optional[str] = None,
    ) -> StructuredVictimResponse:
        sections = []

        is_critical = urgency.upper() in {"CRITICAL", "HIGH"}

        # For critical emergencies, put "Do this now" at the very top!
        if is_critical and actions:
            action_lines = "\n".join(f"{i+1}. {act}" for i, act in enumerate(actions))
            sections.append(f"### Do this now\n\n{action_lines}")

        # What happened
        if summary_explanation:
            sections.append(f"### What happened\n\n{summary_explanation}")

        # If not critical, actions follow explanation
        if not is_critical and actions:
            action_lines = "\n".join(f"{i+1}. {act}" for i, act in enumerate(actions))
            sections.append(f"### Do this now\n\n{action_lines}")

        # Keep these details (Evidence)
        if evidence_items:
            evidence_lines = "\n".join(f"- {ev}" for ev in evidence_items)
            sections.append(f"### Keep these details\n\n{evidence_lines}")

        # Why this matters
        if why_it_matters:
            sections.append(f"### Why this matters\n\n{why_it_matters}")

        # Legal information
        if legal_info:
            sections.append(f"### Legal information\n\n{legal_info}")

        # Next step
        if next_step:
            sections.append(f"### Next step\n\n{next_step}")

        full_markdown = "\n\n".join(sections).strip()

        return StructuredVictimResponse(
            markdown_text=full_markdown,
            response_type="emergency" if is_critical else "advice",
            urgency=urgency.lower(),
            actions=actions,
            evidence_needed=evidence_items,
            next_action=next_step,
        )

    @classmethod
    def format_fact_confirmation(
        cls,
        extracted_facts: dict,
        target_document_type: str = "Police Complaint / FIR Draft",
        language: str = "English",
    ) -> StructuredVictimResponse:
        """
        Presents extracted facts to victim before inserting them into a legal document draft.
        """
        lines = [f"I found these incident details for your **{target_document_type}**:\n"]

        if extracted_facts.get("amount"):
            lines.append(f"- **Amount Lost:** ₹{extracted_facts['amount']:,}")
        if extracted_facts.get("incident_date"):
            lines.append(f"- **Incident Date:** {extracted_facts['incident_date']}")
        if extracted_facts.get("incident_time"):
            lines.append(f"- **Incident Time:** {extracted_facts['incident_time']}")
        if extracted_facts.get("upi_ids"):
            lines.append(f"- **UPI ID:** {', '.join(extracted_facts['upi_ids'])}")
        if extracted_facts.get("utr_numbers"):
            lines.append(f"- **Transaction Ref / UTR:** {', '.join(extracted_facts['utr_numbers'])}")
        if extracted_facts.get("phone_numbers"):
            lines.append(f"- **Suspect Phone:** {', '.join(extracted_facts['phone_numbers'])}")
        if extracted_facts.get("imei"):
            lines.append(f"- **Device IMEI:** {extracted_facts['imei']}")
        if extracted_facts.get("complainant_name"):
            lines.append(f"- **Complainant Name:** {extracted_facts['complainant_name']}")

        lines.append("\n**Are these details correct?** (Reply **'Yes'** to proceed, or specify what needs correction)")

        markdown = "\n".join(lines)

        return StructuredVictimResponse(
            markdown_text=markdown,
            response_type="fact_confirmation",
            urgency="standard",
            actions=["Confirm accuracy of the extracted details"],
            evidence_needed=[],
            next_action="confirm_facts",
        )
