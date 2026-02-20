"""Pydantic schemas for the Query Dashboard."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Single query record ──────────────────────────────────────
class QueryRecord(BaseModel):
    query_id: int
    query_text: str
    segment: Optional[str] = None
    geo: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    source: str  # search engine name
    job_id: int
    status: str
    domains_found: int = 0
    targets_found: int = 0
    effectiveness_score: Optional[float] = None
    estimated_cost_usd: float = 0.0
    is_saturated: bool = False
    created_at: Optional[datetime] = None


class QueryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[QueryRecord]


# ── Saturation breakdown ─────────────────────────────────────
class SegmentSaturation(BaseModel):
    key: str
    total: int = 0
    saturated: int = 0
    saturation_rate: float = 0.0
    total_domains: int = 0
    total_targets: int = 0


# ── Summary / aggregates ─────────────────────────────────────
class QuerySummaryResponse(BaseModel):
    total_queries: int = 0
    done_queries: int = 0
    failed_queries: int = 0
    total_domains: int = 0
    total_targets: int = 0
    total_cost_usd: float = 0.0
    saturation_rate: float = 0.0
    avg_effectiveness: Optional[float] = None
    by_segment: list[SegmentSaturation] = Field(default_factory=list)
    by_geo: list[SegmentSaturation] = Field(default_factory=list)
    by_country: list[SegmentSaturation] = Field(default_factory=list)
    by_source: list[SegmentSaturation] = Field(default_factory=list)


# ── Filter options (distinct values) ─────────────────────────
class FilterOptionsResponse(BaseModel):
    segments: list[str] = Field(default_factory=list)
    geos: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


# ── Geo hierarchy ────────────────────────────────────────────
class GeoEntry(BaseModel):
    key: str
    country_en: str = ""
    cities_en: list[str] = Field(default_factory=list)


class CountryGroup(BaseModel):
    country: str
    geos: list[GeoEntry]


class GeoHierarchyResponse(BaseModel):
    countries: list[CountryGroup]
