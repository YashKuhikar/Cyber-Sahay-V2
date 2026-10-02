import re


RELATIVE_DATES = {
    "today",
    "yesterday",
    "tomorrow",
    "last night",
    "this morning",
    "this evening",
}


def validate_date(value: str) -> bool:
    """
    Returns True if the date looks like an exact date.

    Rejects:
    - today
    - yesterday
    - tomorrow
    """

    if not value:
        return False

    value = value.strip().lower()

    if value in RELATIVE_DATES:
        return False

    patterns = [
        r"^\d{1,2}/\d{1,2}/\d{2,4}$",              # 30/07/2026
        r"^\d{1,2}-\d{1,2}-\d{2,4}$",              # 30-07-2026
        r"^\d{1,2}\s+[A-Za-z]+\s+\d{2,4}$",        # 30 July 2026
    ]

    return any(re.match(pattern, value) for pattern in patterns)


def validate_time(value: str) -> bool:
    """
    Accepts:
    - 6 PM
    - 6pm
    - 18:00
    - 06:30 PM
    """

    if not value:
        return False

    value = value.strip().lower()

    patterns = [
        r"^\d{1,2}:\d{2}$",                    # 18:30
        r"^\d{1,2}\s?(am|pm)$",                # 6 PM
        r"^\d{1,2}:\d{2}\s?(am|pm)$",          # 06:30 PM
    ]

    return any(re.match(pattern, value) for pattern in patterns)