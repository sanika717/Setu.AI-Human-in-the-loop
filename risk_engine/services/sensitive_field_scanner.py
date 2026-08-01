"""Phase D + G: detects when a guidance step is asking for a confidential
credential (OTP, password, PIN, CVV) so guidance can pause there.

This module only ever looks at descriptive page/step TEXT - form labels,
prompts, instructions - supplied by the caller. It never receives, stores,
or evaluates whatever a user actually types into such a field; Sahaay.AI
never stores or transmits passwords, OTPs, PINs, or CVVs anywhere, and this
scanner's job is limited to recognizing that a field of that *type* is on
screen, so the Trust & Governance / AI Guidance layers know to stop and let
the human act directly on the official site instead.
"""

import re

_SENSITIVE_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "otp": re.compile(r"\b(otp|one[-\s]?time\s+(?:password|pin|code))\b", re.IGNORECASE),
    "password": re.compile(r"\bpassword\b", re.IGNORECASE),
    "pin": re.compile(r"\b(m-?pin|atm\s+pin|\bpin\b)\b", re.IGNORECASE),
    "cvv": re.compile(r"\b(cvv2?|card\s+verification\s+(?:value|code)|security\s+code)\b", re.IGNORECASE),
}


def scan_for_sensitive_fields(text: str) -> list[str]:
    """Returns the sorted list of sensitive-field categories (a subset of
    {"otp", "password", "pin", "cvv"}) whose label keywords appear in
    `text`. Empty list means nothing sensitive was detected in this text.
    """

    if not text:
        return []
    detected = [category for category, pattern in _SENSITIVE_FIELD_PATTERNS.items() if pattern.search(text)]
    return sorted(detected)
