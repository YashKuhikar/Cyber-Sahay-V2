import re
from datetime import datetime, timedelta

class FIRValidator:
    """
    Validates incident-specific information collected
    during the FIR workflow.
    """

    @staticmethod
    def validate_phone_number(value: str) -> tuple[bool, str]:
        value = value.strip()

        # Accept Indian 10-digit mobile numbers,
        # optionally with +91 or spaces/hyphens.
        cleaned = re.sub(r"[\s-]", "", value)

        if re.fullmatch(r"(?:\+91)?[6-9]\d{9}", cleaned):
            return True, ""

        return False, (
            "Please provide a valid 10-digit Indian mobile number."
        )

    @staticmethod
    def validate_imei(value: str) -> tuple[bool, str]:
        value = value.strip().replace(" ", "")

        if re.fullmatch(r"\d{15}", value):
            return True, ""

        return False, (
            "Please provide a valid 15-digit IMEI number."
        )

    @staticmethod
    def validate_upi_id(value: str) -> tuple[bool, str]:
        value = value.strip()

        if re.fullmatch(
            r"[A-Za-z0-9._-]{2,}@[A-Za-z0-9._-]{2,}",
            value
        ):
            return True, ""

        return False, (
            "Please provide a valid UPI ID, for example name@upi."
        )

    @staticmethod
    def validate_email(value: str) -> tuple[bool, str]:
        value = value.strip()

        if re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            value
        ):
            return True, ""

        return False, (
            "Please provide a valid email address."
        )

    @staticmethod
    def validate_vehicle_number(value: str) -> tuple[bool, str]:
        value = value.strip().upper().replace(" ", "")

        # Common Indian vehicle registration format.
        if re.fullmatch(
            r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}",
            value
        ):
            return True, ""

        return False, (
            "Please provide a valid vehicle registration number."
        )

    @staticmethod
    def validate_bank_account(value: str) -> tuple[bool, str]:
        value = value.strip().replace(" ", "")

        if re.fullmatch(r"\d{9,18}", value):
            return True, ""

        return False, (
            "Please provide a valid bank account number."
        )

    @classmethod
    def validate_incident_date(cls, value: str) -> tuple[bool, str]:
        if not value or not value.strip():
            return False, "Please provide the date of the incident."
        norm = cls.normalize_date(value)
        if norm:
            return True, ""
        return False, "I couldn't understand that date. Please provide the date of the incident, for example 1 October 2026 or 01/10/2026."

    @classmethod
    def validate_amount(cls, value: str) -> tuple[bool, str]:
        if not value or not value.strip():
            return False, "Please state the approximate financial loss amount."
        norm = cls.normalize_amount(value)
        if norm is not None and norm >= 0:
            return True, ""
        return False, "Please provide a valid financial amount lost, for example ₹25,000 or 25000."

    @classmethod
    def validate_incident_time(cls, value: str) -> tuple[bool, str]:
        if not value or not value.strip():
            return False, "Please provide the approximate time of the incident."
        norm = cls.normalize_time(value)
        if norm:
            return True, ""
        return False, "Please provide an approximate time (e.g. 7 PM, 19:00, or 6:30 PM)."

    @classmethod
    def validate_field(
        cls,
        field: str,
        value: str,
    ) -> tuple[bool, str]:

        validators = {
            "phone_number": cls.validate_phone_number,
            "imei_number": cls.validate_imei,
            "upi_id": cls.validate_upi_id,
            "email": cls.validate_email,
            "vehicle_number": cls.validate_vehicle_number,
            "bank_account": cls.validate_bank_account,
            "incident_date": cls.validate_incident_date,
            "amount": cls.validate_amount,
            "amount_lost": cls.validate_amount,
            "incident_time": cls.validate_incident_time,
        }

        validator = validators.get(field)

        # No special validator for this field.
        if not validator:
            return True, ""

        return validator(value)

    @staticmethod
    def normalize_amount(value: str) -> float | None:
        """
        Extract numerical amount from text strings such as:
        '₹25,000', '25000 rupees', 'around 10k', '1.5 lakh'
        """
        if not value:
            return None
        text = str(value).lower().strip()

        # If input resembles a date (e.g. 01/10/2026 or 2026-10-01) and has no currency indicator, do not treat as amount
        if re.search(r"\b\d{1,4}[/-]\d{1,2}[/-]\d{2,4}\b", text) and not re.search(r"[₹]|rs|inr|rupee", text):
            return None

        # Handle lakh
        lakh_match = re.search(r"([\d.]+)\s*(?:lakh|lac|lacs|lakhs)", text)
        if lakh_match:
            try:
                return float(lakh_match.group(1)) * 100000.0
            except ValueError:
                pass
        # Handle k (thousands)
        k_match = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text)
        if k_match:
            try:
                return float(k_match.group(1)) * 1000.0
            except ValueError:
                pass
        # Currency-prefixed number
        curr_match = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)", text)
        if curr_match:
            try:
                return float(curr_match.group(1).replace(",", ""))
            except ValueError:
                pass
        # Currency-suffixed number
        curr_post = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:rupees?|inr|rs\.?)", text)
        if curr_post:
            try:
                return float(curr_post.group(1).replace(",", ""))
            except ValueError:
                pass
        # Standard whole numbers with commas/currency
        clean_num = re.search(r"\b\d[\d,]*(?:\.\d+)?\b", text)
        if clean_num:
            raw = clean_num.group(0).replace(",", "")
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    @staticmethod
    def normalize_phone(value: str) -> str:
        """
        Extract 10-digit Indian phone number.
        """
        if not value:
            return ""
        cleaned = re.sub(r"[\s-]", "", str(value).strip())
        match = re.search(r"(?:\+91)?[6-9]\d{9}", cleaned)
        if match:
            digits = re.sub(r"\D", "", match.group(0))
            return digits[-10:]
        return ""

    @staticmethod
    def normalize_time(value: str) -> str:
        """
        Normalizes natural language time (e.g. 'around 7 PM', '19:00', '7:30 am')
        """
        if not value:
            return ""
        text = str(value).strip().lower()
        match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b|\b(\d{1,2}:\d{2})\b", text)
        if match:
            return (match.group(1) or match.group(2) or "").strip().upper()
        return ""

    @staticmethod
    def normalize_date(value: str) -> str:
        """
        Convert natural-language date input into YYYY-MM-DD.

        Examples:
            9th August 2026  -> 2026-08-09
            9 August 2026   -> 2026-08-09
            August 9, 2026  -> 2026-08-09
            01/10/2026      -> 2026-10-01 (Indian format DD/MM/YYYY)
            1/10/26         -> 2026-10-01
            01-10-2026      -> 2026-10-01
            yesterday / kal -> previous date
            today / aaj     -> current date
            last night      -> previous date
            two days ago    -> 2 days before today
        """

        if not value:
            return ""

        text = value.strip().lower()

        # Remove ordinal suffixes: 1st, 2nd, 3rd, 4th...
        text = re.sub(
            r"(\d+)(st|nd|rd|th)",
            r"\1",
            text,
        )

        # Remove common conversational prefixes
        text = re.sub(
            r"^(on|on the|date is|the date is|it happened on|happened on)\s+",
            "",
            text,
        )
        text = re.sub(r"\s+", " ", text).strip()

        today = datetime.now().date()

        # Relative dates (English & Roman Hindi)
        if text in ("today", "aaj"):
            return today.isoformat()

        if text in ("yesterday", "kal", "last night", "beete kal"):
            return (today - timedelta(days=1)).isoformat()

        if text in ("tomorrow"):
            return (today + timedelta(days=1)).isoformat()

        # Regex for 'X days ago'
        days_ago_match = re.match(r"^(\w+|\d+)\s+days?\s+ago$", text)
        if days_ago_match:
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            }
            raw_n = days_ago_match.group(1)
            num_days = word_to_num.get(raw_n) or (int(raw_n) if raw_n.isdigit() else None)
            if num_days:
                return (today - timedelta(days=num_days)).isoformat()

        # Common date formats (preferring Indian DD/MM/YYYY convention first)
        formats = [
            "%d %B %Y",
            "%d %b %Y",
            "%B %d %Y",
            "%b %d %Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%d-%m-%y",
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d.%m.%y",
        ]

        cleaned_text = text.replace(",", "")
        for fmt in formats:
            try:
                parsed = datetime.strptime(
                    cleaned_text,
                    fmt,
                )
                # Safeguard century for 2-digit years
                if parsed.year < 100:
                    parsed = parsed.replace(year=parsed.year + 2000)
                return parsed.date().isoformat()

            except ValueError:
                continue

        return ""
    @staticmethod
    def format_date_for_display(value: str) -> str:
        if not value:
            return ""

        try:
            date = datetime.strptime(
                value,
                "%Y-%m-%d"
            )

            return date.strftime("%d %B %Y")

        except ValueError:
            return value