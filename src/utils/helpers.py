from __future__ import annotations

import json
import re
from typing import Any, Dict


def safe_json_loads(text: str, default: dict | None = None) -> dict:
    """
    Safely parses JSON from an LLM response string.
    Handles markdown fences, leading/trailing prose, and malformed strings.
    """
    if default is None:
        default = {}

    if not text or not isinstance(text, str):
        return default

    cleaned = text.strip()

    # 1. Strip standard markdown code fences
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # 2. Try direct parsing
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 3. Try regex extraction to find JSON object { ... }
    try:
        match = re.search(r"(\{[\s\S]*\})", cleaned)
        if match:
            json_str = match.group(1).strip()
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass

    # 4. Try lenient fixes (common LLM trailing commas or single quotes)
    try:
        # replace single quotes around keys/values with double quotes if needed
        fixed = re.sub(r",\s*([\}\]])", r"\1", cleaned)
        parsed = json.loads(fixed)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return default
