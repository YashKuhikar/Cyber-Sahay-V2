from __future__ import annotations

from html import entities
import json
from .entity_merge_agent import EntityMergeAgent

from groq import Groq
from ..utils.validators import (
    validate_date,
    validate_time,
)

from .information_extraction_agent import InformationExtractionAgent
from .validators import FIRValidator

from ..config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)

class FIRAgent:
    """
    AI-assisted FIR Agent.

    Collects required information,
    validates it,
    identifies missing fields,
    and later generates an FIR draft.
    """

    INCIDENT_FIELDS = {

    "mobile_theft": [
        "complainant_name",
        "incident_type",
        "incident_date",
        "incident_time",
        "incident_location",
        "imei_number",
        "description",
    ],

    "upi_fraud": [
        "complainant_name",
        "incident_type",
        "incident_date",
        "incident_time",
        "upi_id",
        "bank_account",
        "description",
    ],

    "phishing": [
        "complainant_name",
        "incident_type",
        "incident_date",
        "incident_time",
        "description",
    ],

    "vehicle_theft": [
        "complainant_name",
        "incident_type",
        "incident_date",
        "incident_time",
        "vehicle_number",
        "incident_location",
        "description",
    ],

    "unknown": [
        "complainant_name",
        "incident_type",
        "incident_date",
        "incident_time",
        "incident_location",
        "description",
    ]
}

    FIELD_QUESTIONS = {
    "complainant_name": "What is your full name?",
    "incident_type": "What type of incident occurred?",
    "incident_date": "On which date did the incident occur?",
    "incident_time": "At what time did the incident occur?",
    "incident_location": "Where did the incident occur?",
    "description": "Please describe what happened in detail.",

    "suspect_name": "Do you know the suspect's name?",
    "phone_number": "What is your contact number?",
    "email": "What is your email address?",
    "imei_number": "What is your mobile phone IMEI number?",
    "vehicle_number": "What is the vehicle registration number?",
    "bank_account": "What is the affected bank account number?",
    "upi_id": "What is the UPI ID involved in the incident?"
}

    def __init__(self):

        self.client = Groq(
            api_key=GROQ_API_KEY,
        )
        self.extractor = InformationExtractionAgent()
        self.validator = FIRValidator()
        self.merge_agent = EntityMergeAgent()
    def get_empty_form(self):

        return {
            "complainant_name": "",
            "incident_type": "",
            "incident_date": "",
            "incident_time": "",
            "incident_location": "",
            "description": "",

            "suspect_name": "",

            "phone_number": "",

            "email": "",

            "imei_number": "",

            "vehicle_number": "",

            "bank_account": "",
            "upi_id": "",
            "amount_lost": ""
        }

    def get_missing_fields(
        self,
        data: dict,
    ):

        missing = []

        incident_type = data.get(
            "incident_type",
            "unknown"
        )

        required_fields = self.INCIDENT_FIELDS.get(
            incident_type,
            self.INCIDENT_FIELDS["unknown"]
        )

        for field in required_fields:

            if not data.get(field):

                missing.append(field)

        return missing

    def update_form(
        self,
        form: dict,
        field: str,
        value: str,
    ):
        """
        Update a single field in the FIR form.
        """

        if field in form:
            form[field] = value.strip()

        return form

    def populate_from_entities(
        self,
        form: dict,
        entities: dict,
    ) -> dict:
        """
        Populate FIR form using extracted document entities.
        """

        if entities.get("complainant_name"):
            form["complainant_name"] = entities["complainant_name"]

        elif entities.get("person_names"):
            form["complainant_name"] = entities["person_names"][0]

        if entities.get("times"):
            form["incident_time"] = entities["times"][0]

        if entities.get("incident_date"):
            form["incident_date"] = entities["incident_date"]

        if entities.get("incident_location"):
            form["incident_location"] = entities["incident_location"]

        if entities.get("phone_numbers"):
            form["phone_number"] = entities["phone_numbers"][0]

        if entities.get("emails"):
            form["email"] = entities["emails"][0]

        if entities.get("upi_ids"):
            form["upi_id"] = entities["upi_ids"][0]

        if entities.get("bank_accounts"):
            form["bank_account"] = entities["bank_accounts"][0]

        if entities.get("vehicle_numbers"):
            form["vehicle_number"] = entities["vehicle_numbers"][0]

        incident_type = entities.get("incident_type")

        if (
            incident_type
            and incident_type != "unknown"
            and not form["incident_type"]
        ):
            form["incident_type"] = incident_type

        description = entities.get(
            "incident_description",
            entities.get("description", "")
        )

        if description and not form["description"]:
            form["description"] = description


        return form

    def collect_information(
        self,
        query: str = "",
        entities: dict | None = None,
    ):
        """
            Create a partially filled FIR form.

            If extracted entities are available,
            automatically populate the form.

            Returns:
                {
                    "status": "...",
                    "form": {...},
                    "missing_fields": [...]
                }
        """

        # Step 1
        form = self.get_empty_form()

        # Extract information from the first user message
        conversation_entities = self.extractor.extract(
            query,
            mode="conversation",
        )

        form = self.merge_agent.merge(
            form,
            conversation_entities,
        )

        # Step 2
        if entities:
            form = self.merge_agent.merge(
                form,
                entities,
            )

        # Step 3
        missing = self.get_missing_fields(form)

        # Step 4
        if missing:
            status = "incomplete"
        else:
            status = "ready"

        return {
            "status": status,
            "form": form,
            "missing_fields": missing,
            "next_question": self.generate_next_question(missing)
        }

    def generate_next_question(
        self,
        missing_fields: list,
    ):
        """
        Generate the next question for the user.
        """

        if not missing_fields:
            return None

        field = missing_fields[0]

        return self.FIELD_QUESTIONS.get(
            field,
            f"Please provide {field}."
        )

    def generate_ai_question(
    self,
    form: dict,
    field: str,
) -> str:
        """
        Generate a natural, context-aware follow-up question.
        """

        print("\n========== AI QUESTION GENERATOR ==========")
        print("Field:", field)
        print("===========================================")

        fallback = self.FIELD_QUESTIONS.get(
            field,
            f"Please provide {field}."
        )

        try:

            prompt = f"""
    You are CyberSahay, an empathetic AI legal assistant
    helping a citizen file an FIR.

    Current incident information:

    {json.dumps(form, indent=2)}

    The next missing field is:

    {field}

    Generate ONE short, natural question asking the user
    for ONLY this missing information.

    Rules:

    - Ask only about the missing field.
    - Do not ask for information already present.
    - Do not invent information.
    - Do not explain anything.
    - Do not mention the field name.
    - Do not start with "What is".
    - Use natural conversational language.
    - Keep it under 25 words.
    - Return ONLY the question.

    Examples:

    For imei_number:
    "To help identify your stolen phone, could you please provide its 15-digit IMEI number?"

    For upi_id:
    "Could you please share the UPI ID involved in the fraudulent transaction?"

    For vehicle_number:
    "Could you please provide the registration number of the stolen vehicle?"
    """

            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.2,
                max_completion_tokens=100,
            )

            content = response.choices[0].message.content
            if not content or not content.strip():
                print("AI QUESTION EMPTY - USING FALLBACK")
                return fallback

            question = content.strip()
            return question

        except Exception as e:

            print("AI QUESTION GENERATOR ERROR:", e)
            print("Using fallback question.")

            return fallback
        except Exception:
            return self.FIELD_QUESTIONS.get(field, f"Please provide {field}")

    def generate_fir(
    self,
    form: dict,
) -> str:
        """
        Generate a professional FIR draft.
        """ 

        display_date = FIRValidator.format_date_for_display(
            form.get("incident_date", "")
        )

        display_form = form.copy()

        display_form["incident_date"] = display_date

        prompt = f"""
    You are CyberSahay's FIR Draft Generator.

    Generate a professionally written FIR complaint draft based on the
    information provided below.

    Write the FIR in a formal, legally structured, and respectful tone.

    Do not invent any information.

    If a field is empty, simply omit it naturally.

    Information:

    {json.dumps(display_form, indent=4)}

    Structure the FIR with clear numbered sections:
    1. Details of the Incident
    2. Description of the Incident
    3. Suspect / Source Information
    4. Action Requested
    5. Declaration

    Use standard plain text formatting. Avoid non-ASCII punctuation.
    Generate ONLY the FIR complaint text.
    """

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0,
                max_completion_tokens=800,
            )
            content = response.choices[0].message.content or ""
            content = content.strip()
        except Exception as e:
            print("Groq FIR generation fallback due to:", e)
            c_name = display_form.get("complainant_name") or "Complainant"
            i_type = (display_form.get("incident_type") or "Cyber Offence").replace("_", " ").title()
            i_date = display_form.get("incident_date") or "Recently"
            i_time = display_form.get("incident_time") or "Unspecified"
            desc = display_form.get("description") or "Fraudulent unauthorized transaction reported."
            bank = display_form.get("bank_account") or "N/A"
            upi = display_form.get("upi_id") or "N/A"
            amt = display_form.get("amount_lost") or "N/A"
            content = f"""TO,\nTHE STATION HOUSE OFFICER,\nCYBER CRIME POLICE STATION.\n\nSUBJECT: COMPLAINT REGARDING {i_type.upper()} UNDER RELEVANT PROVISIONS OF IT ACT, 2000 & BNS, 2023.\n\nRespected Sir/Madam,\n\nI, {c_name}, wish to formally report a cyber offence committed against me.\n\n1. Details of the Incident:\n- Incident Type: {i_type}\n- Date of Occurrence: {i_date}\n- Time of Occurrence: {i_time}\n- Financial Loss / Amount: {amt}\n- Target Bank Account: {bank}\n- Involved UPI ID: {upi}\n\n2. Description of the Incident:\n{desc}\n\n3. Action Requested:\nKindly register a First Information Report (FIR) and initiate appropriate legal proceedings to recover funds and identify the perpetrator.\n\n4. Declaration:\nI hereby declare that the particulars furnished above are true to the best of my knowledge.\n\nYours faithfully,\n{c_name}"""

        # Sanitize non-standard unicode characters that cause rendering artifacts
        replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2014": " - ",
            "\u2013": "-",
            "\u2010": "-",
            "\u2011": "-",
            "\u25a0": "-",
            "\u2022": "-",
            "\u2026": "...",
            "\u00a0": " ",
            "\u00ad": "",
        }
        for k, v in replacements.items():
            content = content.replace(k, v)

        return content
    def start_from_profile(
        self,
        profile: dict,
    ):
        """
        Start FIR workflow using information already
        collected during normal chat.
        """

        form = self.get_empty_form()

        # Copy available profile information
        for field in form:

            value = profile.get(field)

            if value:
                form[field] = value

        # Normalize incident date if present
        if form.get("incident_date"):
            normalized_date = FIRValidator.normalize_date(form["incident_date"])
            if normalized_date:
                form["incident_date"] = normalized_date

        # Determine incident type
        incident_type = form.get("incident_type")

        if not incident_type:
            incident_type = "unknown"
            form["incident_type"] = incident_type

        # Find missing fields
        missing = self.get_missing_fields(form)

        if missing:

            return {
                "status": "incomplete",
                "form": form,
                "missing_fields": missing,
                "current_field": missing[0],
                "next_question": self.generate_next_question(
                    missing
                ),
            }

        # Everything available
        fir = self.generate_fir(form)

        return {
            "status": "ready",
            "form": form,
            "missing_fields": [],
            "fir_draft": fir,
        }
    def start_workflow(
    self,
    query: str,
    entities: dict | None = None,
):
        """
        Complete FIR workflow.
        """

        result = self.collect_information(
            query=query,
            entities=entities,
        )

        if result["status"] == "ready":

            result["fir_draft"] = self.generate_fir(
                result["form"]
            )

        else:

            result["current_field"] = result["missing_fields"][0]

        return result

    def handle(
        self,
        session_id: str,
        query: str,
        history=None,
        entities: dict | None = None,
    ):
        """
        Public entry point for the FIR Agent.

        Currently processes extracted entities and
        returns FIR workflow status.

        Later this method will also use conversation
        history to continue incomplete FIR sessions.
        """

        return self.start_workflow(
            query=query,
            entities=entities,
        )

    def continue_workflow(
        self,
        form: dict,
        current_field: str,
        user_answer: str,
    ):
        """
        Continue an existing FIR workflow.

        Updates the form using the latest answer,
        determines the next question or generates
        the final FIR.
        """
        if form is None:
            form = self.get_empty_form()

        if current_field is None:
            missing = self.get_missing_fields(form)

            if missing:
                current_field = missing[0]
            else:
                current_field = None
        # Update current field
        entities = self.extractor.extract(
            user_answer,
            mode="conversation",
        )

        # Validate the answer for the current field
        is_valid, validation_message = self.validator.validate_field(
            current_field,
            user_answer,
        )

        if not is_valid:

            return {
                "status": "incomplete",
                "form": form,
                "current_field": current_field,
                "next_question": validation_message,
            }

        # If the user is answering a specific field,
        # do not treat the answer as a new incident description.
        # If the user is answering a specific field,
        # do not treat the answer as a new incident description.
        if current_field != "description":
            entities["description"] = ""

        # Merge extracted entities
        form = self.merge_agent.merge(
            form,
            entities,
        )

        # If the user is answering the name question,
        # use the extracted person name.
        if current_field == "complainant_name":

            if entities.get("complainant_name"):
                form["complainant_name"] = entities["complainant_name"]

            elif entities.get("person_names"):
                form["complainant_name"] = entities["person_names"][0]

            else:
                form["complainant_name"] = user_answer.strip()


        # If the user is answering the location question,
        # use the extracted location.
        if current_field == "incident_location":

            if entities.get("locations"):
                form["incident_location"] = entities["locations"][0]

            else:
                form["incident_location"] = user_answer.strip()


        # Fallback for other fields
        if not form.get(current_field):

            form = self.update_form(
                form,
                current_field,
                user_answer,
            )

        

        # Validate incident date
        if current_field == "incident_date":

            normalized_date = FIRValidator.normalize_date(user_answer)

            if normalized_date:
                form["incident_date"] = normalized_date
            else:
                return {
                    "status": "incomplete",
                    "current_field": "incident_date",
                    "next_question": (
                        "Please enter the incident date, "
                        "for example: 9th August 2026."
                    ),
                    "form": form,
                }

        # Validate incident time
        if current_field == "incident_time":

            if not validate_time(form["incident_time"]):

                form["incident_time"] = ""

                return {
                    "status": "incomplete",
                    "form": form,
                    "current_field": "incident_time",
                    "next_question": (
                        "Please provide the exact incident time "
                        "(Example: 6:30 PM or 18:30)."
                    )
                }

        print("\n========== CURRENT FIR FORM ==========")
        print(json.dumps(form, indent=4))
        print("======================================\n")
        # Find remaining fields
        missing = self.get_missing_fields(form)

        if missing:

            next_field = missing[0]

            if next_field in [
                        "imei_number",
                        "upi_id",
                        "vehicle_number",
                        "bank_account",
                        "description",
                        "suspect_name",
                    ]:
                        question = self.generate_ai_question(
                            form,
                            next_field,
                        )
            else:
                        question = self.generate_next_question(
                            [next_field]
                        )

            return {
                "status": "incomplete",
                "form": form,
                "current_field": next_field,
                "next_question": question
            }

        fir = self.generate_fir(form)

        return {
            "status": "ready",
            "form": form,
            "fir_draft": fir
        }