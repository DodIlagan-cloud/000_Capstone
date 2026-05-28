"""M5 - Document Parsing Module Start
Redacts sensitive values from evidence previews.
M5/M6 End"""

import re


REDACTION_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("REDACTED_EMAIL", "[REDACTED_EMAIL]", re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    ("REDACTED_CARD", "[REDACTED_CARD]", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    (
        "REDACTED_ACCOUNT",
        "[REDACTED_ACCOUNT]",
        re.compile(r"\b(?:account|acct|card)\s*(?:number|no\.?|#)?\s*[:\-]?\s*[A-Za-z0-9-]{4,}\b", re.IGNORECASE),
    ),
    ("REDACTED_PHONE", "[REDACTED_PHONE]", re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")),
]


def redact_text(text: str, preview_chars: int) -> tuple[str, dict[str, int]]:
    preview = (text or "")[: max(0, preview_chars)]
    counts: dict[str, int] = {}

    for code, replacement, pattern in REDACTION_PATTERNS:
        preview, count = pattern.subn(replacement, preview)
        if count:
            counts[code] = count

    return preview, counts
