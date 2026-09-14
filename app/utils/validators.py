"""Shared field validators used by multiple views (server-side enforcement)."""
import re


def validate_phone(raw) -> tuple[bool, str]:
    """Validate a Philippine mobile number.

    Mirrors the registration rule: the value must contain exactly 11 digits
    (non-digit characters are ignored, so spaces/dashes are tolerated).
    An empty value is allowed — phone is optional.

    Returns (ok, normalized) where normalized is the digit-only string
    ('' when empty). Use it to save the cleaned value.
    """
    if raw is None:
        return True, ''
    digits = re.sub(r'\D', '', str(raw))
    if not digits:
        return True, ''
    if len(digits) != 11:
        return False, digits
    return True, digits
