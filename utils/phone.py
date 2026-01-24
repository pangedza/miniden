from __future__ import annotations

import re


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to a stable digits-only format."""

    raw_value = (phone or "").strip()
    digits = re.sub(r"\D", "", raw_value)
    if not digits:
        raise ValueError("phone_empty")

    if len(digits) == 10:
        digits = f"7{digits}"
    elif len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"

    if len(digits) != 11:
        raise ValueError("phone_invalid")

    return digits
