from __future__ import annotations

import json

import re

from groq import Groq

from ..utils.helpers import safe_json_loads
from ..config import (
    GROQ_API_KEY,
    GROQ_EXTRACTION_MODEL,
)


class InformationExtractionAgent:
    """
    Extracts structured information from OCR text.
    """

    def __init__(self):
        self.client = Groq(
            api_key=GROQ_API_KEY,
        )

    def extract(
    self,
    text: str,
    mode: str = "document",
) -> dict:

        if mode == "document":

            prompt = f"""
Extract structured information from the OCR text below.

Rules:
- Extract ONLY information explicitly present.
- Never guess or infer.
- Return ONLY valid JSON.
- Do not explain anything.
- Do not use Markdown.
- Keep values concise.
- complainant_name only when the document explicitly identifies
  the complainant, writer, applicant, victim, or person submitting it.
- incident_date must be the actual incident date.
- incident_time must be the actual incident time.
- incident_location must be the actual place where the incident occurred.
- Do not assume a place mentioned as "returning from" is the incident location.
- Use "" for missing string fields.
- Use [] for missing list fields.

DOCUMENT STRUCTURE RULES:

- The name in the "To" section, recipient address, addressee,
  Police Commissioner, officer, or authority is NOT the complainant.

- The complainant is usually the person who writes the complaint
  and signs it at the end.

- If the document ends with phrases such as:
  "Thanks & regards",
  "Regards",
  "Sincerely",
  "Yours faithfully",
  "Yours sincerely"
  followed by a person's name, that person should be considered
  the complainant_name.

- Do NOT select a recipient or police officer as complainant when
  a clearly identified writer/signatory exists.

- The date at the top of a complaint letter is normally the
  document/complaint date, NOT necessarily the incident date.

- Do NOT copy the document date into incident_date unless the
  document explicitly states that the incident happened on that date.

- A location in the recipient address, office, workplace, police
  station, or organization name is NOT automatically the incident
  location.

- A phrase such as "returning from the city club" identifies the
  place the person came from, not necessarily where the incident
  happened.

- Only fill incident_location when the document explicitly says
  where the incident occurred.

Allowed incident_type:

mobile_theft
upi_fraud
phishing
otp_fraud
cyberbullying
identity_theft
ransomware
social_media
online_shopping_fraud
atm_fraud
police_misconduct
harassment
sexual_harassment
physical_assault
unknown

OCR TEXT:
{text}

Return exactly this JSON structure:

{{
    "person_names": [],
    "organizations": [],
    "locations": [],
    "dates": [],
    "times": [],
    "phone_numbers": [],
    "emails": [],
    "upi_ids": [],
    "bank_accounts": [],
    "vehicle_numbers": [],
    "urls": [],
    "ip_addresses": [],
    "important_identifiers": [],
    "complainant_name": "",
    "incident_type": "unknown",
    "incident_description": "",
    "document_date": "",
    "incident_date": "",
    "incident_time": "",
    "incident_location": ""
}}
"""

        else:

            prompt = f"""
        Extract structured information from the OCR text below.

        Rules:
        - Extract ONLY explicitly present information.
        - Never guess or infer.
        - Return ONLY valid JSON.
        - Do not explain anything.
        - complainant_name only when explicitly identified as complainant,
        applicant, writer, victim, or person submitting the complaint.
        - incident_date must be the actual incident date, not merely the
        complaint date.
        - incident_time must be the actual incident time.
        - incident_location must be the actual incident location.
        - A place mentioned only as "returning from", "coming from", etc.
        is not automatically the incident location.
        - Use "" for missing scalar values.
        - Use [] for missing arrays.

        Allowed incident types:
        mobile_theft
        upi_fraud
        phishing
        otp_fraud
        cyberbullying
        identity_theft
        ransomware
        social_media
        online_shopping_fraud
        atm_fraud
        police_misconduct
        harassment
        sexual_harassment
        physical_assault
        unknown

        OCR TEXT:
        {text}

        JSON:
        {{
            "person_names": [],
            "organizations": [],
            "locations": [],
            "dates": [],
            "times": [],
            "phone_numbers": [],
            "emails": [],
            "upi_ids": [],
            "bank_accounts": [],
            "vehicle_numbers": [],
            "urls": [],
            "ip_addresses": [],
            "important_identifiers": [],
            "complainant_name": "",
            "incident_type": "unknown",
            "incident_description": "",
            "incident_date": "",
            "incident_time": "",
            "incident_location": ""
        }}
        """

        response = self.client.chat.completions.create(
            model=GROQ_EXTRACTION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a structured information extraction system. "
                        "Return ONLY valid JSON. "
                        "Do not explain anything. "
                        "Do not use Markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
            max_completion_tokens=500,
            reasoning_effort="low",
            include_reasoning=False,
            response_format={
                "type": "json_object"
            },
        )
        answer = response.choices[0].message.content.strip()

        if not answer:

            print(
                "\n========== INFORMATION EXTRACTION EMPTY RESPONSE =========="
            )

            print("Groq returned an empty response.")
            print("Model:", GROQ_EXTRACTION_MODEL)
            print("Mode:", mode)

            print("Finish reason:")
            print(response.choices[0].finish_reason)

            print("============================================================\n")

            raise ValueError(
                "Information Extraction Agent returned an empty response."
            )

        default_result = {
            "person_names": [],
            "organizations": [],
            "locations": [],
            "dates": [],
            "times": [],
            "phone_numbers": [],
            "emails": [],
            "upi_ids": [],
            "bank_accounts": [],
            "vehicle_numbers": [],
            "urls": [],
            "ip_addresses": [],
            "important_identifiers": [],
            "complainant_name": "",
            "incident_type": "unknown",
            "incident_description": "",
            "incident_date": "",
            "incident_time": "",
            "incident_location": "",
        }

        result = safe_json_loads(answer, default=default_result)

        if not isinstance(result, dict):
            result = default_result

        # Ensure required keys are populated
        for key, val in default_result.items():
            if key not in result:
                result[key] = val

        if mode == "document":
            # Do not allow recipient-only locations to become the incident location
            if result.get("incident_location"):
                location = str(result["incident_location"]).lower()
                if "police station" in location or "police commissioner" in location:
                    result["incident_location"] = ""

            # If a clear signatory exists in the OCR text, prefer that person as complainant
            signature_patterns = [
                r"thanks\s*&\s*regards\s*[\r\n]+([A-Z][A-Za-z ]+)",
                r"thanks\s+and\s+regards\s*[\r\n]+([A-Z][A-Za-z ]+)",
                r"regards\s*[\r\n]+([A-Z][A-Za-z ]+)",
                r"sincerely\s*[\r\n]+([A-Z][A-Za-z ]+)",
                r"yours\s+sincerely\s*[\r\n]+([A-Z][A-Za-z ]+)",
            ]

            for pattern in signature_patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    result["complainant_name"] = match.group(1).strip()
                    break

        return result