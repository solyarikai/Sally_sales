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


def calculate_name_similarity(name1: str, name2: str) -> float:
    if not name1 or not name2:
        return 0.0
    return SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio()


def truncate(value: str | None, max_len: int = 500) -> str | None:
    if value is None:
        return None
    return str(value)[:max_len] if len(str(value)) > max_len else value
