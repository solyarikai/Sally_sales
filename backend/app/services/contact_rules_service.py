"""
Contact Rules Service — Reusable rules for contact filtering across all projects.

Rules:
1. Max 5 contacts per office (company + normalized location)
2. Prioritize by role relevance (CEO > CTO > VP > Director > Head > Manager > Other)
3. Decision-makers weighted higher

These rules apply to ANY project's contact export pipeline.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Role priority — lower number = higher priority
ROLE_PRIORITY = {
    "ceo": 1, "chief executive": 1, "founder": 1, "co-founder": 1, "owner": 1,
    "cto": 2, "chief technology": 2, "coo": 2, "chief operating": 2,
    "cfo": 3, "chief financial": 3, "cmo": 3, "chief marketing": 3,
    "cro": 3, "chief revenue": 3, "cpo": 3, "chief product": 3,
    "vp": 4, "vice president": 4,
    "director": 5,
    "head": 6, "head of": 6,
    "manager": 7, "lead": 7, "senior": 7,
    "specialist": 8, "analyst": 8, "coordinator": 8, "associate": 8,
}

# Location normalization — common variants to canonical form
LOCATION_MAP = {
    # Cyprus
    "limassol, cyprus": "Limassol, CY", "cyprus, cyprus": "Limassol, CY",
    "larnaca, cyprus": "Larnaca, CY", "nicosia, cyprus": "Nicosia, CY", "cyprus": "Limassol, CY",
    # Russia/CIS
    "moscow, russia": "Moscow, RU", "moscow, moscow city, russia": "Moscow, RU",
    "saint petersburg, russia": "St Petersburg, RU", "russia": "Moscow, RU",
    # Common locations
    "london, united kingdom": "London, UK", "london, england": "London, UK",
    "new york, new york": "New York, US", "san francisco, california": "San Francisco, US",
    "berlin, germany": "Berlin, DE", "amsterdam, netherlands": "Amsterdam, NL",
    "paris, france": "Paris, FR", "tokyo, japan": "Tokyo, JP",
    "singapore": "Singapore, SG", "hong kong": "Hong Kong, HK",
    "dubai, united arab emirates": "Dubai, AE", "tel aviv, israel": "Tel Aviv, IL",
}

MAX_PER_OFFICE = 5


def get_role_priority(title: str) -> int:
    """Get priority score for a job title. Lower = more important."""
    if not title:
        return 99
    title_lower = title.lower()
    for keyword, priority in ROLE_PRIORITY.items():
        if keyword in title_lower:
            return priority
    return 99


def is_decision_maker(title: str) -> bool:
    """Check if title is a decision-maker role."""
    return get_role_priority(title) <= 6


def normalize_location(location: str) -> str:
    """Normalize location string to canonical form for office grouping."""
    if not location:
        return "Unknown"
    loc_lower = location.lower().strip()
    # Check direct mapping
    if loc_lower in LOCATION_MAP:
        return LOCATION_MAP[loc_lower]
    # Try city, country pattern
    parts = [p.strip() for p in loc_lower.split(",")]
    if len(parts) >= 2:
        # Try city + country
        key = f"{parts[0]}, {parts[-1]}"
        if key in LOCATION_MAP:
            return LOCATION_MAP[key]
        # Return first city + last country
        return f"{parts[0].title()}, {parts[-1].strip().upper()[:2]}"
    return location.strip().title()


def apply_office_rules(
    contacts: List[Dict[str, Any]],
    max_per_office: int = MAX_PER_OFFICE,
    company_field: str = "company",
    location_field: str = "location",
    title_field: str = "title",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Apply 5-per-office rule with role prioritization.

    Args:
        contacts: List of contact dicts
        max_per_office: Max contacts per company+location office
        company_field: Key for company name in contact dict
        location_field: Key for location in contact dict
        title_field: Key for job title in contact dict

    Returns:
        (filtered_contacts, stats_dict)
    """
    # Sort by role priority (most important first)
    sorted_contacts = sorted(contacts, key=lambda c: get_role_priority(c.get(title_field, "")))

    # Group by company + normalized location (office)
    office_counts: Dict[str, int] = {}
    filtered = []
    skipped = 0

    for contact in sorted_contacts:
        company = (contact.get(company_field) or "Unknown").strip().lower()
        location = normalize_location(contact.get(location_field, ""))
        office_key = f"{company}|{location}"

        current_count = office_counts.get(office_key, 0)
        if current_count >= max_per_office:
            skipped += 1
            continue

        office_counts[office_key] = current_count + 1
        contact["_normalized_location"] = location
        contact["_role_priority"] = get_role_priority(contact.get(title_field, ""))
        contact["_is_decision_maker"] = is_decision_maker(contact.get(title_field, ""))
        filtered.append(contact)

    # Stats
    dm_count = sum(1 for c in filtered if c.get("_is_decision_maker"))
    unique_companies = len(set(
        (c.get(company_field) or "").strip().lower() for c in filtered
    ))

    stats = {
        "total_input": len(contacts),
        "total_output": len(filtered),
        "skipped_office_limit": skipped,
        "decision_makers": dm_count,
        "unique_companies": unique_companies,
        "unique_offices": len(office_counts),
        "max_per_office": max_per_office,
    }

    logger.info(
        f"Contact rules: {len(contacts)} input → {len(filtered)} output "
        f"({dm_count} DMs, {unique_companies} companies, {skipped} skipped)"
    )
    return filtered, stats


# Singleton
contact_rules_service = type("ContactRulesService", (), {
    "apply_office_rules": staticmethod(apply_office_rules),
    "get_role_priority": staticmethod(get_role_priority),
    "is_decision_maker": staticmethod(is_decision_maker),
    "normalize_location": staticmethod(normalize_location),
    "MAX_PER_OFFICE": MAX_PER_OFFICE,
})()
