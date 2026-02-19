"""
Geo service helper — builds geo metadata from query_templates.py SEGMENTS dict.

Provides country groupings for the Query Dashboard frontend dropdown.
Pure Python, no DB access, cached at import time.
"""
from __future__ import annotations

from typing import Any

from app.services.query_templates import SEGMENTS


def _build_geo_meta() -> dict[str, dict[str, Any]]:
    """
    Walk every segment's ``geos`` block and collect unique geo keys
    with their country_en, cities_en metadata.  When the same geo key
    appears in multiple segments, keep the richest entry (most cities).
    """
    meta: dict[str, dict[str, Any]] = {}
    for seg_data in SEGMENTS.values():
        geos = seg_data.get("geos", {})
        for geo_key, geo_data in geos.items():
            existing = meta.get(geo_key)
            if existing is None or len(geo_data.get("cities_en", [])) > len(existing.get("cities_en", [])):
                meta[geo_key] = {
                    "country_en": geo_data.get("country_en", ""),
                    "country_ru": geo_data.get("country_ru", ""),
                    "cities_en": geo_data.get("cities_en", []),
                    "cities_ru": geo_data.get("cities_ru", []),
                }
    return meta


# Cached at import time
GEO_META: dict[str, dict[str, Any]] = _build_geo_meta()


def get_geo_hierarchy() -> list[dict[str, Any]]:
    """
    Return countries list grouped by country_en with their geo keys.

    Example output::

        [
            {
                "country": "UAE",
                "geos": [
                    {"key": "dubai", "country_en": "UAE", "cities_en": ["Dubai", "Abu Dhabi"]},
                    {"key": "dubai_difc", "country_en": "UAE", "cities_en": ["Dubai", "Abu Dhabi"]},
                ]
            },
            ...
        ]
    """
    # Group by country_en
    by_country: dict[str, list[dict[str, Any]]] = {}
    for geo_key, meta in sorted(GEO_META.items()):
        country = meta["country_en"] or "Other"
        entry = {
            "key": geo_key,
            "country_en": meta["country_en"],
            "cities_en": meta["cities_en"],
        }
        by_country.setdefault(country, []).append(entry)

    return [
        {"country": country, "geos": geos}
        for country, geos in sorted(by_country.items())
    ]
