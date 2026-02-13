"""
Name language classifier — detects Russian/English names and generic emails.

Used by SmartLead push rules to route contacts to the right campaigns.
"""
import re
import unicodedata
from typing import Optional, Literal

# Generic email prefixes that indicate no personal name
GENERIC_PREFIXES = {
    "info", "contact", "contacts", "office", "hello", "hi", "support",
    "sales", "marketing", "admin", "administrator", "reception", "team",
    "enquiries", "enquiry", "inquiry", "general", "mail", "email",
    "service", "services", "help", "feedback", "press", "media",
    "hr", "jobs", "careers", "legal", "finance", "billing",
    "welcome", "connect", "request", "booking", "reservations",
    "post", "webmaster", "noreply", "no-reply", "donotreply",
}

# Cyrillic character ranges
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[a-zA-Z]")


def is_generic_email(email: str) -> bool:
    """Check if an email address is generic (info@, contact@, etc.)."""
    if not email or "@" not in email:
        return True
    local_part = email.split("@")[0].lower().strip()
    # Direct prefix match
    if local_part in GENERIC_PREFIXES:
        return True
    # Prefixes with numbers or dots: info1@, info.dept@
    base = re.split(r"[\d._\-+]", local_part)[0]
    if base in GENERIC_PREFIXES:
        return True
    return False


def detect_name_language(name: Optional[str]) -> Literal["ru", "en", "unknown"]:
    """Detect if a name is Russian (Cyrillic) or English (Latin)."""
    if not name or not name.strip():
        return "unknown"

    name = name.strip()
    has_cyrillic = bool(_CYRILLIC_RE.search(name))
    has_latin = bool(_LATIN_RE.search(name))

    if has_cyrillic and not has_latin:
        return "ru"
    if has_latin and not has_cyrillic:
        return "en"
    if has_cyrillic and has_latin:
        # Mixed — count which is dominant
        cyrillic_count = len(_CYRILLIC_RE.findall(name))
        latin_count = len(_LATIN_RE.findall(name))
        return "ru" if cyrillic_count >= latin_count else "en"
    return "unknown"


def has_personal_name(first_name: Optional[str], email: str) -> bool:
    """Check if the contact has a usable personal first name."""
    if first_name and first_name.strip() and len(first_name.strip()) > 1:
        # Make sure it's not just the email prefix
        local_part = email.split("@")[0].lower() if "@" in email else ""
        if first_name.strip().lower() != local_part:
            return True
    return False


def classify_contact(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> dict:
    """
    Classify a contact for campaign routing.

    Returns:
        {
            "language": "ru" | "en" | "unknown",
            "has_name": True | False,
            "is_generic_email": True | False,
            "bucket": "ru_name" | "ru_noname" | "en_name" | "en_noname" | "unknown"
        }
    """
    generic = is_generic_email(email)
    has_name = has_personal_name(first_name, email)

    # Determine language from name
    full_name = " ".join(filter(None, [first_name, last_name]))
    lang = detect_name_language(full_name)

    # If no name detected from first/last, try email local part
    if lang == "unknown" and not generic:
        local_part = email.split("@")[0] if "@" in email else ""
        # Check if local part has cyrillic (rare but possible in IDN)
        lang = detect_name_language(local_part)
        if lang == "unknown":
            lang = "en"  # Default to English for latin emails without names

    # Build bucket
    if not has_name or generic:
        bucket = f"{lang}_noname" if lang != "unknown" else "unknown"
    else:
        bucket = f"{lang}_name"

    return {
        "language": lang,
        "has_name": has_name,
        "is_generic_email": generic,
        "bucket": bucket,
    }


def match_rule(classification: dict, rule) -> bool:
    """
    Check if a contact classification matches a CampaignPushRule.

    Args:
        classification: Output from classify_contact()
        rule: CampaignPushRule instance
    """
    # Language check
    if rule.language != "any" and classification["language"] != rule.language:
        return False

    # Name check
    if rule.has_first_name is True and not classification["has_name"]:
        return False
    if rule.has_first_name is False and classification["has_name"]:
        return False
    # has_first_name=None means "any"

    return True
