import re

# Canonical Nigerian mobile: 234 + 10 digits, starting with 7, 8, or 9
_NIGERIAN_MOBILE_RE = re.compile(r"^234[789]\d{9}$")


def normalize_nigerian_phone(raw: str) -> str:
    """
    Normalize a Nigerian phone number to the canonical 13-digit format: 234XXXXXXXXXX.

    Accepted input variants:
        +2348012345678  →  2348012345678
         2348012345678  →  2348012345678
          08012345678   →  2348012345678
           8012345678   →  2348012345678
    """
    phone = raw.strip()

    if phone.startswith("+"):
        phone = phone[1:]

    # Full international format: 234 + 10 digits
    if phone.startswith("234") and len(phone) == 13:
        return phone

    # Local format with leading zero: 0XXXXXXXXXX (11 digits)
    if phone.startswith("0") and len(phone) == 11:
        return "234" + phone[1:]

    # Local format without leading zero: XXXXXXXXXX (10 digits)
    if len(phone) == 10 and not phone.startswith("0"):
        return "234" + phone

    raise ValueError(f"Unrecognised phone number format: {raw!r}")


def validate_nigerian_phone(raw: str) -> str:
    """
    Normalize and validate a Nigerian mobile number.
    Returns the canonical 13-digit string or raises ValueError.
    """
    try:
        normalized = normalize_nigerian_phone(raw)
    except ValueError:
        raise ValueError("Invalid phone number format")

    if not _NIGERIAN_MOBILE_RE.match(normalized):
        raise ValueError("Invalid Nigerian mobile number")

    return normalized