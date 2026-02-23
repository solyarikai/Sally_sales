"""Query Dashboard API — read-only endpoints for search query exploration."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, literal, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.companies import get_required_company
from app.db import get_session
from app.models.contact import Contact
from app.models.domain import SearchJob, SearchQuery, SearchQueryStatus, SearchEngine, SearchResult
from app.models.pipeline import DiscoveredCompany
from app.models.user import Company
from app.schemas.query_dashboard import (
    FilterOptionsResponse,
    GeoHierarchyResponse,
    QueryListResponse,
    QueryRecord,
    QuerySummaryResponse,
    QueryTargetsResponse,
    TargetDomain,
    SegmentSaturation,
)
from app.services.geo_service import get_geo_hierarchy

router = APIRouter(prefix="/dashboard/queries", tags=["query-dashboard"])

# Engine cost rates (USD per 1000 queries)
ENGINE_COST_RATES: dict[str, float] = {
    "google_serp": 2.5,
    "yandex_api": 0.3,
    "apollo_org": 5.0,
    "clay": 10.0,
}


def _cost_expr():
    """SQL CASE expression for estimated cost per query."""
    return case(
        *[
            (SearchJob.search_engine == engine, literal(rate / 1000))
            for engine, rate in ENGINE_COST_RATES.items()
        ],
        else_=literal(0.0),
    ).label("estimated_cost_usd")


def _saturated_expr():
    """SQL CASE expression for is_saturated (done + domains>0 + targets=0)."""
    return case(
        (
            and_(
                SearchQuery.status == SearchQueryStatus.DONE,
                SearchQuery.domains_found > 0,
                SearchQuery.targets_found == 0,
            ),
            literal(True),
        ),
        else_=literal(False),
    ).label("is_saturated")


def _apply_filters(stmt, params: dict):
    """Apply common filter clauses to a SELECT already joining SQ+SJ."""
    if params.get("q"):
        stmt = stmt.where(SearchQuery.query_text.ilike(f"%{params['q']}%"))
    if params.get("segment"):
        vals = [s.strip() for s in params["segment"].split(",") if s.strip()]
        if vals:
            expanded = set(vals)
            for s in vals:
                if '_' in s:
                    expanded.add(s.replace('_', ' ').title())
            all_variants = list(expanded)
            stmt = stmt.where(func.lower(SearchQuery.segment).in_([v.lower() for v in all_variants]))
    if params.get("geo"):
        vals = [s.strip() for s in params["geo"].split(",") if s.strip()]
        if vals:
            stmt = stmt.where(SearchQuery.geo.in_(vals))
    if params.get("country"):
        vals = [s.strip() for s in params["country"].split(",") if s.strip()]
        if vals:
            stmt = stmt.where(SearchQuery.country.in_(vals))
    if params.get("language"):
        vals = [s.strip() for s in params["language"].split(",") if s.strip()]
        if vals:
            stmt = stmt.where(SearchQuery.language.in_(vals))
    if params.get("source"):
        vals = [s.strip() for s in params["source"].split(",") if s.strip()]
        if vals:
            stmt = stmt.where(SearchJob.search_engine.in_(vals))
    if params.get("status"):
        vals = [s.strip() for s in params["status"].split(",") if s.strip()]
        if vals:
            stmt = stmt.where(SearchQuery.status.in_(vals))
    if params.get("domains_min") is not None:
        stmt = stmt.where(SearchQuery.domains_found >= params["domains_min"])
    if params.get("domains_max") is not None:
        stmt = stmt.where(SearchQuery.domains_found <= params["domains_max"])
    if params.get("targets_min") is not None:
        stmt = stmt.where(SearchQuery.targets_found >= params["targets_min"])
    if params.get("targets_max") is not None:
        stmt = stmt.where(SearchQuery.targets_found <= params["targets_max"])
    if params.get("date_from"):
        stmt = stmt.where(SearchQuery.created_at >= params["date_from"])
    if params.get("date_to"):
        # include the entire day
        stmt = stmt.where(SearchQuery.created_at < f"{params['date_to']}T23:59:59+00:00")
    if params.get("is_saturated") is not None:
        if params["is_saturated"]:
            stmt = stmt.where(
                and_(
                    SearchQuery.status == SearchQueryStatus.DONE,
                    SearchQuery.domains_found > 0,
                    SearchQuery.targets_found == 0,
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    SearchQuery.status != SearchQueryStatus.DONE,
                    SearchQuery.domains_found == 0,
                    SearchQuery.targets_found > 0,
                )
            )
    return stmt


# ── GET /api/dashboard/queries ────────────────────────────────
@router.get("", response_model=QueryListResponse)
async def list_queries(
    project_id: int = Query(..., description="Project ID (required)"),
    q: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    geo: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    domains_min: Optional[int] = Query(None),
    domains_max: Optional[int] = Query(None),
    targets_min: Optional[int] = Query(None),
    targets_max: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    is_saturated: Optional[bool] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    params = dict(
        q=q, segment=segment, geo=geo, country=country, language=language, source=source,
        status=status, domains_min=domains_min, domains_max=domains_max,
        targets_min=targets_min, targets_max=targets_max,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        is_saturated=is_saturated,
    )

    # Base query — join SQ to SJ
    base = (
        select(
            SearchQuery.id.label("query_id"),
            SearchQuery.query_text,
            SearchQuery.segment,
            SearchQuery.geo,
            SearchQuery.country,
            SearchQuery.language,
            SearchJob.search_engine.label("source"),
            SearchJob.id.label("job_id"),
            SearchQuery.status,
            SearchQuery.domains_found,
            SearchQuery.targets_found,
            SearchQuery.effectiveness_score,
            _cost_expr(),
            _saturated_expr(),
            SearchQuery.created_at,
        )
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(SearchJob.project_id == project_id)
        .where(SearchJob.company_id == company.id)
    )
    base = _apply_filters(base, params)

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sorting
    sort_map = {
        "created_at": SearchQuery.created_at,
        "domains_found": SearchQuery.domains_found,
        "targets_found": SearchQuery.targets_found,
        "effectiveness_score": SearchQuery.effectiveness_score,
        "query_text": SearchQuery.query_text,
        "country": SearchQuery.country,
        "geo": SearchQuery.geo,
    }
    sort_col = sort_map.get(sort_by, SearchQuery.created_at)
    order = sort_col.desc() if sort_order == "desc" else sort_col.asc()

    data_q = base.order_by(order).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(data_q)).all()

    data = [
        QueryRecord(
            query_id=r.query_id,
            query_text=r.query_text,
            segment=r.segment,
            geo=r.geo,
            country=r.country,
            language=r.language,
            source=r.source.value if hasattr(r.source, 'value') else str(r.source),
            job_id=r.job_id,
            status=r.status.value if hasattr(r.status, 'value') else str(r.status),
            domains_found=r.domains_found,
            targets_found=r.targets_found,
            effectiveness_score=r.effectiveness_score,
            estimated_cost_usd=float(r.estimated_cost_usd),
            is_saturated=bool(r.is_saturated),
            created_at=r.created_at,
        )
        for r in rows
    ]

    return QueryListResponse(total=total, page=page, page_size=page_size, data=data)


# ── GET /api/dashboard/queries/summary ────────────────────────
@router.get("/summary", response_model=QuerySummaryResponse)
async def get_summary(
    project_id: int = Query(...),
    q: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    geo: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    domains_min: Optional[int] = Query(None),
    domains_max: Optional[int] = Query(None),
    targets_min: Optional[int] = Query(None),
    targets_max: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    is_saturated: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    params = dict(
        q=q, segment=segment, geo=geo, country=country, language=language, source=source,
        status=status, domains_min=domains_min, domains_max=domains_max,
        targets_min=targets_min, targets_max=targets_max,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        is_saturated=is_saturated,
    )

    saturated_case = case(
        (
            and_(
                SearchQuery.status == SearchQueryStatus.DONE,
                SearchQuery.domains_found > 0,
                SearchQuery.targets_found == 0,
            ),
            literal(1),
        ),
        else_=literal(0),
    )

    # Aggregate metrics
    agg_q = (
        select(
            func.count(SearchQuery.id).label("total_queries"),
            func.sum(case((SearchQuery.status == SearchQueryStatus.DONE, 1), else_=0)).label("done_queries"),
            func.sum(case((SearchQuery.status == SearchQueryStatus.FAILED, 1), else_=0)).label("failed_queries"),
            func.coalesce(func.sum(SearchQuery.domains_found), 0).label("total_domains"),
            func.coalesce(func.sum(SearchQuery.targets_found), 0).label("total_targets"),
            func.coalesce(func.sum(_cost_expr()), 0).label("total_cost_usd"),
            func.sum(saturated_case).label("saturated_count"),
            func.avg(SearchQuery.effectiveness_score).label("avg_effectiveness"),
        )
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(SearchJob.project_id == project_id)
        .where(SearchJob.company_id == company.id)
    )
    agg_q = _apply_filters(agg_q, params)
    agg = (await db.execute(agg_q)).one()

    total_queries = agg.total_queries or 0
    saturated_count = agg.saturated_count or 0
    done_queries = agg.done_queries or 0
    sat_rate = (saturated_count / done_queries * 100) if done_queries > 0 else 0.0

    # By-segment breakdown
    seg_q = (
        select(
            SearchQuery.segment.label("key"),
            func.count(SearchQuery.id).label("total"),
            func.sum(saturated_case).label("saturated"),
            func.coalesce(func.sum(SearchQuery.domains_found), 0).label("total_domains"),
            func.coalesce(func.sum(SearchQuery.targets_found), 0).label("total_targets"),
        )
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(SearchJob.project_id == project_id)
        .where(SearchJob.company_id == company.id)
        .where(SearchQuery.segment.isnot(None))
        .group_by(SearchQuery.segment)
        .order_by(func.count(SearchQuery.id).desc())
    )
    seg_q = _apply_filters(seg_q, params)
    seg_rows = (await db.execute(seg_q)).all()

    by_segment = [
        SegmentSaturation(
            key=r.key or "unknown",
            total=r.total,
            saturated=r.saturated or 0,
            saturation_rate=round((r.saturated or 0) / r.total * 100, 1) if r.total else 0,
            total_domains=r.total_domains,
            total_targets=r.total_targets,
        )
        for r in seg_rows
    ]

    # By-geo breakdown
    geo_q = (
        select(
            SearchQuery.geo.label("key"),
            func.count(SearchQuery.id).label("total"),
            func.sum(saturated_case).label("saturated"),
            func.coalesce(func.sum(SearchQuery.domains_found), 0).label("total_domains"),
            func.coalesce(func.sum(SearchQuery.targets_found), 0).label("total_targets"),
        )
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(SearchJob.project_id == project_id)
        .where(SearchJob.company_id == company.id)
        .where(SearchQuery.geo.isnot(None))
        .group_by(SearchQuery.geo)
        .order_by(func.count(SearchQuery.id).desc())
    )
    geo_q = _apply_filters(geo_q, params)
    geo_rows = (await db.execute(geo_q)).all()

    by_geo = [
        SegmentSaturation(
            key=r.key or "unknown",
            total=r.total,
            saturated=r.saturated or 0,
            saturation_rate=round((r.saturated or 0) / r.total * 100, 1) if r.total else 0,
            total_domains=r.total_domains,
            total_targets=r.total_targets,
        )
        for r in geo_rows
    ]

    # By-country breakdown
    country_q = (
        select(
            SearchQuery.country.label("key"),
            func.count(SearchQuery.id).label("total"),
            func.sum(saturated_case).label("saturated"),
            func.coalesce(func.sum(SearchQuery.domains_found), 0).label("total_domains"),
            func.coalesce(func.sum(SearchQuery.targets_found), 0).label("total_targets"),
        )
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(SearchJob.project_id == project_id)
        .where(SearchJob.company_id == company.id)
        .where(SearchQuery.country.isnot(None))
        .group_by(SearchQuery.country)
        .order_by(func.count(SearchQuery.id).desc())
    )
    country_q = _apply_filters(country_q, params)
    country_rows = (await db.execute(country_q)).all()

    by_country = [
        SegmentSaturation(
            key=r.key or "unknown",
            total=r.total,
            saturated=r.saturated or 0,
            saturation_rate=round((r.saturated or 0) / r.total * 100, 1) if r.total else 0,
            total_domains=r.total_domains,
            total_targets=r.total_targets,
        )
        for r in country_rows
    ]

    # By-source breakdown
    src_q = (
        select(
            SearchJob.search_engine.label("key"),
            func.count(SearchQuery.id).label("total"),
            func.sum(saturated_case).label("saturated"),
            func.coalesce(func.sum(SearchQuery.domains_found), 0).label("total_domains"),
            func.coalesce(func.sum(SearchQuery.targets_found), 0).label("total_targets"),
        )
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(SearchJob.project_id == project_id)
        .where(SearchJob.company_id == company.id)
        .group_by(SearchJob.search_engine)
        .order_by(func.count(SearchQuery.id).desc())
    )
    src_q = _apply_filters(src_q, params)
    src_rows = (await db.execute(src_q)).all()

    by_source = [
        SegmentSaturation(
            key=r.key.value if hasattr(r.key, 'value') else str(r.key),
            total=r.total,
            saturated=r.saturated or 0,
            saturation_rate=round((r.saturated or 0) / r.total * 100, 1) if r.total else 0,
            total_domains=r.total_domains,
            total_targets=r.total_targets,
        )
        for r in src_rows
    ]

    return QuerySummaryResponse(
        total_queries=total_queries,
        done_queries=done_queries,
        failed_queries=agg.failed_queries or 0,
        total_domains=agg.total_domains or 0,
        total_targets=agg.total_targets or 0,
        total_cost_usd=float(agg.total_cost_usd or 0),
        saturation_rate=round(sat_rate, 1),
        avg_effectiveness=round(float(agg.avg_effectiveness), 2) if agg.avg_effectiveness else None,
        by_segment=by_segment,
        by_geo=by_geo,
        by_country=by_country,
        by_source=by_source,
    )


# ── GET /api/dashboard/queries/filter-options ─────────────────
@router.get("/filter-options", response_model=FilterOptionsResponse)
async def get_filter_options(
    project_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    base_where = and_(
        SearchJob.project_id == project_id,
        SearchJob.company_id == company.id,
    )

    segments_q = (
        select(SearchQuery.segment)
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(base_where)
        .where(SearchQuery.segment.isnot(None))
        .distinct()
        .order_by(SearchQuery.segment)
    )
    geos_q = (
        select(SearchQuery.geo)
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(base_where)
        .where(SearchQuery.geo.isnot(None))
        .distinct()
        .order_by(SearchQuery.geo)
    )
    countries_q = (
        select(SearchQuery.country)
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(base_where)
        .where(SearchQuery.country.isnot(None))
        .distinct()
        .order_by(SearchQuery.country)
    )
    langs_q = (
        select(SearchQuery.language)
        .join(SearchJob, SearchQuery.search_job_id == SearchJob.id)
        .where(base_where)
        .where(SearchQuery.language.isnot(None))
        .distinct()
        .order_by(SearchQuery.language)
    )
    sources_q = (
        select(SearchJob.search_engine)
        .join(SearchQuery, SearchQuery.search_job_id == SearchJob.id)
        .where(base_where)
        .distinct()
        .order_by(SearchJob.search_engine)
    )

    segments = [r[0] for r in (await db.execute(segments_q)).all()]
    geos = [r[0] for r in (await db.execute(geos_q)).all()]
    countries = [r[0] for r in (await db.execute(countries_q)).all()]
    languages = [r[0] for r in (await db.execute(langs_q)).all()]
    sources = [r[0].value if hasattr(r[0], 'value') else str(r[0]) for r in (await db.execute(sources_q)).all()]

    return FilterOptionsResponse(
        segments=segments,
        geos=geos,
        countries=countries,
        languages=languages,
        sources=sources,
    )


# ── GET /api/dashboard/queries/geo-hierarchy ──────────────────
@router.get("/geo-hierarchy", response_model=GeoHierarchyResponse)
async def geo_hierarchy():
    return GeoHierarchyResponse(countries=get_geo_hierarchy())


# ── GET /api/dashboard/queries/{query_id}/targets ─────────────
@router.get("/{query_id}/targets", response_model=QueryTargetsResponse)
async def get_query_targets(
    query_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Return target domains found by a specific query, with contact linkage."""
    sq_row = (await db.execute(
        select(SearchQuery.id, SearchQuery.query_text, SearchQuery.search_job_id)
        .where(SearchQuery.id == query_id)
    )).first()
    if not sq_row:
        from fastapi import HTTPException
        raise HTTPException(404, "Query not found")

    sj_row = (await db.execute(
        select(SearchJob.project_id)
        .where(and_(SearchJob.id == sq_row.search_job_id, SearchJob.company_id == company.id))
    )).first()
    if not sj_row:
        from fastapi import HTTPException
        raise HTTPException(404, "Query not found")

    project_id = sj_row.project_id

    target_rows = (await db.execute(
        select(
            SearchResult.domain,
            SearchResult.is_target,
            SearchResult.confidence,
            SearchResult.matched_segment,
            DiscoveredCompany.name.label("company_name"),
        )
        .outerjoin(DiscoveredCompany, SearchResult.discovered_company_id == DiscoveredCompany.id)
        .where(and_(
            SearchResult.source_query_id == query_id,
            SearchResult.is_target == True,
        ))
        .order_by(SearchResult.domain)
    )).all()

    targets: list[TargetDomain] = []
    domains = [r.domain for r in target_rows]

    contact_counts: dict[str, list[int]] = {}
    if domains:
        contact_rows = (await db.execute(
            select(Contact.domain, Contact.id)
            .where(and_(
                func.lower(Contact.domain).in_([d.lower() for d in domains]),
                Contact.project_id == project_id,
                Contact.deleted_at.is_(None),
            ))
        )).all()
        for cr in contact_rows:
            contact_counts.setdefault(cr.domain.lower(), []).append(cr.id)

    with_contacts = 0
    without_contacts = 0
    for r in target_rows:
        cids = contact_counts.get(r.domain.lower(), [])
        if cids:
            with_contacts += 1
        else:
            without_contacts += 1
        targets.append(TargetDomain(
            domain=r.domain,
            company_name=r.company_name,
            is_target=True,
            confidence=r.confidence,
            matched_segment=r.matched_segment,
            contacts_count=len(cids),
            contact_ids=cids,
        ))

    return QueryTargetsResponse(
        query_id=query_id,
        query_text=sq_row.query_text,
        total_targets=len(targets),
        targets_with_contacts=with_contacts,
        targets_without_contacts=without_contacts,
        targets=targets,
    )
