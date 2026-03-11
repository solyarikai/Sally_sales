"""Shared normalization functions for emails, LinkedIn URLs, and names.

Single source of truth — import from here instead of duplicating.
"""
import re
from typing import Optional
from difflib import SequenceMatcher


def normalize_email(email: str) -> Optional[str]:
    if not email:
        return None
    return email.lower().strip()


def normalize_linkedin_url(url: str) -> Optional[str]:
    """Normalize LinkedIn URL to 'linkedin.com/in/<handle>' form."""
    if not url:
        return None
    url = url.lower().strip()
    url = url.split("?")[0].rstrip("/")
    if "/in/" in url:
        parts = url.split("/in/")
        if len(parts) > 1:
            return f"linkedin.com/in/{parts[1].split('/')[0]}"
    url_stripped = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    return url_stripped if url_stripped else None


# Lowercase particles that should stay lowercase (unless first word)
_NAME_PARTICLES = {"de", "da", "di", "del", "della", "van", "von", "der", "den", "la", "le", "el", "al", "bin", "ibn", "dos", "das", "do", "du", "af", "av", "zu", "ten", "ter"}

# Prefixes that trigger capitalization of the next letter (Mc, Mac, O')
_MC_RE = re.compile(r"^(mc|mac)(.+)$", re.IGNORECASE)
_APOSTROPHE_RE = re.compile(r"^(o|d|l)(['\u2019])(.+)$", re.IGNORECASE)
_HYPHEN_RE = re.compile(r"-")


def _capitalize_part(part: str, is_first: bool) -> str:
    """Capitalize a single name part, handling Mc/Mac/O' prefixes."""
    if not part:
        return part

    low = part.lower()

    # Particles: lowercase unless first word
    if low in _NAME_PARTICLES and not is_first:
        return low

    # McDonald, MacArthur
    mc = _MC_RE.match(part)
    if mc:
        prefix = mc.group(1).capitalize()
        rest = mc.group(2).capitalize()
        return prefix + rest

    # O'Brien, D'Angelo, L'Oréal
    ap = _APOSTROPHE_RE.match(part)
    if ap:
        letter = ap.group(1).upper()
        apos = ap.group(2)
        rest = ap.group(3).capitalize()
        return letter + apos + rest

    return part.capitalize()


def normalize_name(name: str | None) -> str | None:
    """Normalize a person's name to proper case.

    - ROMANETTO → Romanetto
    - jean-pierre → Jean-Pierre
    - mcdonald → McDonald
    - o'brien → O'Brien
    - van der berg → van der Berg (particles stay lowercase except at start)
    - Already correct names pass through unchanged logic-wise
    """
    if not name or not isinstance(name, str):
        return name

    name = name.strip()
    if not name:
        return None

    # Already mixed case and not ALL UPPER/ALL LOWER — likely fine, but still normalize
    # Split by spaces first
    words = name.split()
    result = []
    for i, word in enumerate(words):
        is_first = (i == 0)
        # Handle hyphenated names: Jean-Pierre, Mary-Jane
        if "-" in word:
            parts = word.split("-")
            result.append("-".join(_capitalize_part(p, is_first or j == 0) for j, p in enumerate(parts)))
        else:
            result.append(_capitalize_part(word, is_first))

    return " ".join(result)


def calculate_name_similarity(name1: str, name2: str) -> float:
    if not name1 or not name2:
        return 0.0
    return SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio()


def truncate(value: str | None, max_len: int = 500) -> str | None:
    if value is None:
        return None
    return str(value)[:max_len] if len(str(value)) > max_len else value
