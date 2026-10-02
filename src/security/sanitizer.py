from __future__ import annotations

import html
import re


def sanitize_input(text: str, max_length: int = 4000) -> str:
    """
    Sanitizes user input string against XSS, HTML injections, and excessive length.
    """
    if not text or not isinstance(text, str):
        return ""

    # Truncate to maximum permissible length to prevent buffer/token exhaustion
    cleaned = text[:max_length].strip()

    # Strip dangerous HTML/script tags
    cleaned = re.sub(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*iframe[^>]*>[\s\S]*?<\s*/\s*iframe\s*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*style[^>]*>[\s\S]*?<\s*/\s*style\s*>", "", cleaned, flags=re.IGNORECASE)

    # Escape HTML special characters (&, <, >, ", ')
    cleaned = html.escape(cleaned)

    return cleaned


def mask_sensitive_data(text: str) -> str:
    """
    Redacts sensitive personal information (Aadhaar, Credit Card numbers)
    from logs in compliance with India's DPDP Act 2023.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Mask 16-digit Credit/Debit Card numbers (e.g. 4111 2222 3333 4444 -> XXXX-XXXX-XXXX-4444)
    text = re.sub(
        r"\b(?:\d{4}[ -]?){3}(\d{4})\b",
        r"XXXX-XXXX-XXXX-\1",
        text,
    )

    # 2. Mask 12-digit Indian Aadhaar Numbers (e.g. 1234 5678 9012 -> XXXX-XXXX-9012)
    text = re.sub(
        r"\b\d{4}[ -]?\d{4}[ -]?(\d{4})\b",
        r"XXXX-XXXX-\1",
        text,
    )

    return text
