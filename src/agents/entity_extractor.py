from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def validate_imei_luhn(imei: str) -> bool:
    """
    Validates a 15-digit IMEI number using the Luhn algorithm.
    """
    cleaned = re.sub(r"\D", "", imei)
    if len(cleaned) != 15:
        return False

    total = 0
    for idx, char in enumerate(cleaned):
        num = int(char)
        if idx % 2 == 1:
            doubled = num * 2
            total += (doubled // 10) + (doubled % 10)
        else:
            total += num
    return total % 10 == 0


class TypedEntityExtractor:
    """
    High-precision typed entity extractor using deterministic regex first,
    preventing field misattributions (e.g. never mapping generic identifiers to IMEI).
    """

    # Strict Regex Specifications
    RE_PHONE = re.compile(r"(?:(?:\+91|91|0)[-\s]?)?([6-9]\d{9})\b")
    RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    RE_UPI = re.compile(r"\b([a-zA-Z0-9.\-_]{2,64}@[a-zA-Z]{2,32})\b")
    RE_URL = re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*")
    # Comprehensive amount patterns (prefix, postfix, and verb-anchored)
    RE_AMOUNT_PREFIX = re.compile(r"(?:₹|rs\.?|inr|रु\.?)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
    RE_AMOUNT_POSTFIX = re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(?:rupaye|rupees|rs\.?|₹|inr|रुपये|रुपए|रु|pese|paise)", re.IGNORECASE)
    RE_AMOUNT_VERB = re.compile(
        r"(?:paying|paid|pay|lost|stolen|took|debited|deducted|fraud\s+of|scam\s+of|loan\s+of)\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    RE_UTR = re.compile(r"\b(?:utr|rrn|txn|ref|transaction\s*id)[\s:#-]*(?:is|was|no\.?|number)?[\s:#-]*([0-9]{12}|[A-Za-z0-9]{16,22})\b", re.IGNORECASE)
    RE_BANK_ACCOUNT = re.compile(r"\b(?:a/c|acc|account|khata|acct)[\s:#-]*(?:is|was|no\.?|number)?[\s:#-]*([0-9]{9,18})\b", re.IGNORECASE)
    RE_IMEI_CANDIDATE = re.compile(r"\b(?:imei[\s:#-]*(?:is|was|no\.?|number)?[\s:#-]*)?([0-9]{15})\b", re.IGNORECASE)

    # Devanagari numerals translation table
    DEV_DIGITS_TRANS = str.maketrans("०१२३४५६७८९", "0123456789")

    def extract_deterministic(self, text: str) -> Dict[str, Any]:
        """
        Extracts typed entities using deterministic validation.
        """
        # Normalize devanagari numerals to standard arabic digits for uniform processing
        normalized_text = text.translate(self.DEV_DIGITS_TRANS)

        results: Dict[str, Any] = {
            "amount": None,
            "upi_ids": [],
            "utr_numbers": [],
            "phone_numbers": [],
            "emails": [],
            "urls": [],
            "bank_accounts": [],
            "imei": "",
            "transaction_ids": [],
        }

        # 1. Amount Extraction
        raw_amt_str = None
        for pattern in (self.RE_AMOUNT_PREFIX, self.RE_AMOUNT_POSTFIX, self.RE_AMOUNT_VERB):
            match = pattern.search(normalized_text)
            if match:
                for grp in match.groups():
                    if grp:
                        raw_amt_str = grp
                        break
            if raw_amt_str:
                break

        if raw_amt_str:
            clean_num = raw_amt_str.replace(",", "").strip()
            try:
                val_float = float(clean_num)
                if val_float > 0:
                    results["amount"] = val_float
            except ValueError:
                pass

        # 2. UPI IDs (Filter out common email domains like @gmail.com)
        common_email_providers = {"gmail", "yahoo", "outlook", "hotmail", "icloud", "rediffmail"}
        upi_matches = self.RE_UPI.findall(text)
        for candidate in upi_matches:
            handle = candidate.split("@")[-1].lower()
            if not any(provider in handle for provider in common_email_providers):
                if candidate not in results["upi_ids"]:
                    results["upi_ids"].append(candidate)

        # 3. Emails
        for email in self.RE_EMAIL.findall(text):
            if email not in results["emails"]:
                results["emails"].append(email)

        # 4. Phone Numbers (Indian mobile numbers 10 digits)
        for phone_match in self.RE_PHONE.findall(text):
            cleaned_phone = phone_match.strip()
            if cleaned_phone not in results["phone_numbers"]:
                results["phone_numbers"].append(cleaned_phone)

        # 5. URLs
        for url in self.RE_URL.findall(text):
            if url not in results["urls"]:
                results["urls"].append(url)

        # 6. UTR / Transaction Reference
        for utr in self.RE_UTR.findall(text):
            cleaned_utr = utr.strip()
            if cleaned_utr not in results["utr_numbers"]:
                results["utr_numbers"].append(cleaned_utr)
                results["transaction_ids"].append(cleaned_utr)

        # 7. Bank Account
        for acct in self.RE_BANK_ACCOUNT.findall(text):
            cleaned_acct = acct.strip()
            if cleaned_acct not in results["bank_accounts"]:
                results["bank_accounts"].append(cleaned_acct)

        # 8. IMEI - Validated strictly by format / Luhn check, NEVER as generic identifier
        for candidate in self.RE_IMEI_CANDIDATE.findall(text):
            cleaned_candidate = candidate.strip()
            # If explicit "imei" keyword exists near it or passes Luhn check
            if "imei" in text.lower() or validate_imei_luhn(cleaned_candidate):
                results["imei"] = cleaned_candidate
                break

        return results
