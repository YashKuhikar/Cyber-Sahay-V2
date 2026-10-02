from __future__ import annotations

import re
from typing import List, Dict


TIMESTAMPS_REGEX = re.compile(
    r"\b((?:[0-1]?[0-9]|2[0-3])[:.][0-5][0-9](?::[0-5][0-9])?\s*(?:AM|PM|am|pm)?|(?:[0-1]?[0-9]|2[0-3])\s*(?:AM|PM|am|pm))\b"
)


def build_evidence_timeline(text: str) -> List[Dict[str, str]]:
    """
    Scans evidence/chat/statement OCR text for timestamps and reconstructs
    a chronological timeline of events.
    """
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    timeline: List[Dict[str, str]] = []

    for line in lines:
        match = TIMESTAMPS_REGEX.search(line)
        if match:
            timestamp = match.group(1).strip()
            # Clean up the event text
            event_text = line.replace(timestamp, "").strip(" -:|,")
            if len(event_text) > 3:
                timeline.append({
                    "time": timestamp,
                    "event": event_text,
                    "source": "ocr_evidence",
                })

    # If no timestamps found on single lines, check for sequential actions
    if not timeline and len(lines) >= 2:
        for idx, line in enumerate(lines[:5]):
            if any(k in line.lower() for k in ["received", "clicked", "transferred", "otp", "debit", "paid", "call", "sms", "link"]):
                timeline.append({
                    "time": f"Step {idx+1}",
                    "event": line[:120],
                    "source": "ocr_narrative",
                })

    return timeline
