"""
Contact Extraction Service — Extracts emails, phones, and contact names from scraped HTML via GPT-4o-mini.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Junk email domains and patterns — reject before storing
JUNK_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "test.org",
    "localhost", "email.com", "mail.com", "domain.com", "site.com",
    "yoursite.com", "yourdomain.com", "yourcompany.com", "company.com",
    "sampleemail.com", "sample.com",
}

_CYRILLIC_RE_EMAIL = re.compile(r"[\u0400-\u04FF]")


def is_valid_email(email: str) -> bool:
    """
    Validate email is real and not a placeholder/junk.
    Returns False for obviously bad emails that should never be stored or pushed.
    """
    if not email or not isinstance(email, str):
        return False

    email = email.strip().lower()

    # Too short or no @
    if len(email) < 6 or "@" not in email:
        return False

    local, _, domain = email.partition("@")

    # Missing local or domain
    if not local or not domain or "." not in domain:
        return False

    # Cyrillic in email address (not valid for SMTP)
    if _CYRILLIC_RE_EMAIL.search(email):
        return False

    # URL-encoded chars (garbled scrape)
    if "%" in email:
        return False

    # Spaces
    if " " in email:
        return False

    # Known junk domains
    if domain in JUNK_EMAIL_DOMAINS:
        return False

    # Domain TLD too short (e.g., "info@delo")
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if len(tld) < 2:
        return False

    # Local part is a common placeholder
    placeholder_locals = {
        "email", "name", "your", "user", "test", "corpora", "secretary",
        "example", "sample", "demo", "mail", "admin", "root", "null",
        "undefined", "nobody", "noreply", "no-reply",
    }
    if local in placeholder_locals:
        return False

    # Local part too short (e.g. "a@domain.com" — likely fake)
    if len(local) < 2:
        return False

    # Local part looks like Cyrillic word in transliteration or raw Cyrillic
    # (already caught above, but double-check for mixed)
    _cyrillic_word = re.compile(r"^[\u0400-\u04FF]+$")
    if _cyrillic_word.match(local):
        return False

    # Local part contains spaces encoded as words (e.g. "ваш email" becomes "ваш")
    # Already caught by cyrillic check, but catch transliterated versions
    ru_placeholder_locals = {
        "vash", "vashe", "pochta", "svyaz", "primer", "kontakt", "zapros",
    }
    if local in ru_placeholder_locals:
        return False

    # Local part is a single generic word with no dots, digits, or separators
    # (real emails usually have dots, underscores, or digits)
    if re.match(r"^[a-z]{2,}$", local) and local in {
        "email", "mail", "contact", "info", "office", "hello",
        "support", "sales", "help", "team", "feedback", "service",
        "marketing", "billing", "accounts", "webmaster", "postmaster",
    }:
        return False

    return True


# Generic emails to filter out
GENERIC_EMAIL_PATTERNS = {
    "info@", "support@", "contact@", "noreply@", "no-reply@",
    "admin@", "sales@", "help@", "hello@", "office@",
    "mail@", "webmaster@", "postmaster@", "abuse@",
    "marketing@", "team@", "feedback@", "service@",
}


class ContactExtractionService:
    """Extracts contacts from website HTML using GPT-4o-mini."""

    async def extract_contacts_from_html(
        self,
        domain: str,
        html_text: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract contacts from HTML content using GPT-4o-mini.

        Returns list of:
        {email, phone, first_name, last_name, job_title, confidence}
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.warning("No OpenAI API key configured for contact extraction")
            return []

        # Truncate HTML for context window
        html_excerpt = html_text[:12000] if html_text else ""
        if not html_excerpt.strip():
            return []

        prompt = f"""Extract all contact information from this website content.

WEBSITE DOMAIN: {domain}

WEBSITE CONTENT:
{html_excerpt}

Find ALL contacts mentioned on the page. For each person, extract:
- email (if found)
- phone (if found, include country code if available)
- first_name
- last_name
- job_title (position/role)

Respond with a JSON array:
[
  {{
    "email": "person@example.com",
    "phone": "+7 999 123 45 67",
    "first_name": "Ivan",
    "last_name": "Petrov",
    "job_title": "CEO",
    "confidence": 0.9
  }}
]

RULES:
- Include ONLY real people's contacts, not generic emails (info@, support@, etc.)
- If you find generic contact emails/phones without a person's name, still include them but set confidence lower
- If no contacts are found, return an empty array []
- Respond with ONLY valid JSON, nothing else"""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You extract contact information from website HTML. Respond only with a valid JSON array.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON response
            try:
                contacts = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON array from response
                start = content.find("[")
                end = content.rfind("]")
                if start != -1 and end != -1:
                    contacts = json.loads(content[start:end + 1])
                else:
                    logger.warning(f"Failed to parse contact extraction response for {domain}")
                    return []

            if not isinstance(contacts, list):
                return []

            # Filter and validate
            valid_contacts = []
            for c in contacts:
                if not isinstance(c, dict):
                    continue

                email = (c.get("email") or "").strip().lower()
                phone = (c.get("phone") or "").strip()

                # Skip if no email and no phone
                if not email and not phone:
                    continue

                # Check if email is generic
                is_generic = any(email.startswith(p) for p in GENERIC_EMAIL_PATTERNS)

                valid_contacts.append({
                    "email": email or None,
                    "phone": phone or None,
                    "first_name": (c.get("first_name") or "").strip() or None,
                    "last_name": (c.get("last_name") or "").strip() or None,
                    "job_title": (c.get("job_title") or "").strip() or None,
                    "confidence": c.get("confidence", 0.5) if not is_generic else 0.3,
                    "is_generic": is_generic,
                })

            return valid_contacts

        except Exception as e:
            logger.error(f"Contact extraction failed for {domain}: {e}")
            return []

    def extract_emails_regex(self, text: str) -> List[str]:
        """Fallback: extract emails using regex."""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, text)
        # Dedupe and filter
        seen = set()
        result = []
        for email in emails:
            email_lower = email.lower()
            if email_lower not in seen:
                seen.add(email_lower)
                result.append(email_lower)
        return result

    def extract_phones_regex(self, text: str) -> List[str]:
        """Fallback: extract phone numbers using regex."""
        patterns = [
            r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # Russian +7
            r'8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',     # Russian 8
            r'\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}',                    # UAE +971
            r'\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{2,4}',   # International
        ]
        phones = []
        for pattern in patterns:
            phones.extend(re.findall(pattern, text))
        return list(set(phones))


# Module-level singleton
contact_extraction_service = ContactExtractionService()
