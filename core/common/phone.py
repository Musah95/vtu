import re

from .exceptions import ServiceError


def normalize_phone(raw):
    """Accepts 08012345678, +2348012345678, 2348012345678 -> 08012345678."""
    digits = re.sub(r"[\s\-]", "", str(raw))
    if digits.startswith("+234"):
        digits = "0" + digits[4:]
    elif digits.startswith("234") and len(digits) == 13:
        digits = "0" + digits[3:]
    if not re.fullmatch(r"0[789][01]\d{8}", digits):
        raise ServiceError("INVALID_NUMBER", "Enter a valid Nigerian phone number.")
    return digits