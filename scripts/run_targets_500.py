"""
All-in-one search + contacts + export pipeline.
================================================
Runs inside Docker container with DB + API access.

Part A: ArchiStruct search (project_id=24, company_id=1) — 500+ targets
Part B: Deliryo HNWI search — Cyprus + all international Russian HNWI hubs
Part C: Contact extraction + Apollo enrichment for ALL new targets
Part D: Google Sheets export

Usage (Docker):
  docker run -d --name run-targets --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL=... -e OPENAI_API_KEY=... \
    -e YANDEX_SEARCH_API_KEY=... -e YANDEX_SEARCH_FOLDER_ID=... \
    -e CRONA_EMAIL=... -e CRONA_PASSWORD=... \
    -e APOLLO_API_KEY=... \
    -e GOOGLE_SERVICE_ACCOUNT_JSON=... \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/run_targets_500.py'
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("run_targets_500")

# Silence noisy HTTP loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ============================================================
# Config
# ============================================================
ARCHISTRUCT_PROJECT_ID = 24
ARCHISTRUCT_COMPANY_ID = 1
ARCHISTRUCT_MAX_QUERIES = 3000
ARCHISTRUCT_TARGET_GOAL = 500

DELIRYO_PROJECT_ID = 18
# Deliryo company_id loaded from DB

ARCHISTRUCT_APOLLO_TITLES = [
    "CEO", "Founder", "Co-Founder", "Managing Director", "Owner",
    "General Manager", "Director", "Head of Sales",
    "VP Business Development", "Chief Operating Officer",
    "General Director", "Commercial Director",
]

DELIRYO_APOLLO_TITLES = [
    "CEO", "Founder", "Co-Founder", "Managing Partner", "Director",
    "Head of Family Office", "CIO", "Portfolio Manager", "Partner",
    "Managing Director", "Chief Investment Officer",
    "Head of Wealth Management", "Senior Partner",
]

SHARE_WITH = ["pn@getsally.io"]

# Extended target_segments for Deliryo international search
# Original says "ТОЛЬКО Россия" — we expand to include international HNWI hubs
DELIRYO_INTERNATIONAL_TARGET_SEGMENTS = """Мульти фэмили офисы, инвестиционные фонды, консультационные фирмы для HNWI, управляющие компании, wealth management фирмы — МЕЖДУНАРОДНЫЙ поиск.

Deliryo предлагает B2B2C сервис: легальный, быстрый USDT <> RUB обмен для состоятельных клиентов (HNWI). Целевые клиенты Deliryo — компании, которые работают с деньгами российских HNWI и нуждаются в крипто/фиат транзакциях:
- Мульти фэмили офисы (multi-family offices)
- Инвестиционные фонды и управляющие компании
- Private banking / wealth management фирмы
- Консультационные компании для состоятельных клиентов
- Трасты и структуры для управления активами

ГЕОГРАФИЯ — МЕЖДУНАРОДНЫЕ ХАБЫ, где концентрируются русскоязычные HNWI:
Cyprus (Limassol, Paphos, Nicosia), Monaco, London/UK, Dubai/UAE, Switzerland (Zurich, Geneva, Lugano), Israel (Tel Aviv, Herzliya), Montenegro, Serbia (Belgrade), Turkey (Istanbul), Singapore.

ЯЗЫК САЙТА: Английский, Русский — ОБА приемлемы для международных хабов. language_match = 1.0 для English и Russian.

ВАЖНО: Ищем компании, обслуживающие РУССКОЯЗЫЧНЫХ состоятельных клиентов за рубежом. Признаки:
- Упоминание Russian/CIS/Russian-speaking clients
- Русскоязычная версия сайта или русскоязычный персонал
- Офис в хабе с большой русскоязычной диаспорой
- Услуги релокации активов, offshore структуры, cross-border wealth management

НЕ ЦЕЛЕВЫЕ:
- Крупные международные банки (UBS, Credit Suisse, HSBC, Goldman Sachs)
- Чисто локальные компании без связи с русскоязычными клиентами
- Агрегаторы, новостные сайты, справочники
- Компании, работающие ТОЛЬКО с институциональными инвесторами"""

# ============================================================
# Deliryo international HNWI queries
# ============================================================
DELIRYO_INTERNATIONAL_QUERIES = [
    # --- Cyprus ---
    "family office Cyprus", "family office Limassol", "family office Paphos",
    "family office Nicosia", "wealth management Cyprus",
    "HNWI services Limassol", "private wealth advisory Cyprus",
    "trust company Cyprus", "investment advisory Limassol",
    "asset management Cyprus", "private banking Cyprus",
    "фэмили офис Кипр", "фэмили офис Лимассол",
    "управление капиталом Кипр", "управление активами Кипр",
    "трастовая компания Кипр", "инвестиционный советник Кипр",
    "состоятельные клиенты Кипр", "private wealth Cyprus Russian",
    "Cyprus investment fund", "Limassol wealth advisory",
    "offshore trust Cyprus", "CIF Cyprus investment firm",

    # --- Monaco ---
    "family office Monaco", "wealth management Monaco",
    "wealth management Monaco Russian", "HNWI services Monaco",
    "multi family office Monaco", "private banking Monaco",
    "фэмили офис Монако", "управление капиталом Монако",
    "Monaco wealth advisory", "Monaco private wealth",

    # --- London / UK ---
    "family office London", "family office London Russian",
    "wealth management London Russian", "HNWI advisory London",
    "Russian wealth management UK", "multi family office London",
    "private wealth London", "family office Mayfair",
    "фэмили офис Лондон", "управление капиталом Лондон",
    "wealth management UK Russian clients",

    # --- Dubai / UAE ---
    "family office Dubai", "family office Dubai Russian",
    "HNWI services Dubai", "wealth advisory UAE",
    "wealth management Dubai Russian", "multi family office Dubai",
    "private wealth Dubai", "family office Abu Dhabi",
    "фэмили офис Дубай", "управление капиталом Дубай",
    "family office DIFC", "wealth management DIFC",

    # --- Switzerland ---
    "family office Zurich", "family office Geneva",
    "wealth management Geneva Russian", "private banking Switzerland",
    "multi family office Switzerland", "Swiss wealth management Russian",
    "фэмили офис Швейцария", "управление капиталом Женева",
    "family office Lugano", "wealth advisory Zurich",

    # --- Israel ---
    "family office Tel Aviv", "family office Israel",
    "wealth management Israel Russian", "HNWI services Israel",
    "investment advisory Israel", "private wealth Israel",
    "фэмили офис Израиль", "управление капиталом Израиль",
    "family office Herzliya",

    # --- Montenegro / Serbia ---
    "family office Montenegro", "wealth management Montenegro",
    "investment advisory Belgrade", "family office Belgrade",
    "wealth management Serbia", "private banking Montenegro",
    "фэмили офис Черногория", "управление капиталом Сербия",

    # --- Turkey / Istanbul ---
    "family office Istanbul", "HNWI services Turkey",
    "wealth management Istanbul Russian", "family office Turkey",
    "private wealth Istanbul", "investment advisory Turkey",
    "фэмили офис Стамбул", "управление капиталом Турция",

    # --- Singapore ---
    "family office Singapore", "family office Singapore Russian",
    "wealth management Singapore Russian", "HNWI advisory Singapore",
    "multi family office Singapore", "private wealth Singapore",
    "фэмили офис Сингапур",

    # --- General international ---
    "Russian family office international", "HNWI advisory Russian clients",
    "wealth management Russian diaspora", "family office CIS clients",
    "multi family office Russian speaking", "private wealth Russian HNWI",
    "trust services Russian clients", "offshore wealth management Russian",
    "фэмили офис для русских клиентов за рубежом",
    "управление капиталом русскоязычные клиенты",
]


# ============================================================
# Part A: ArchiStruct Search
# ============================================================
async def run_archistruct_search():
    """Run improved ArchiStruct search for 500+ targets."""
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service

    logger.info("=" * 70)
    logger.info("PART A: ARCHISTRUCT SEARCH")
    logger.info(f"  project_id={ARCHISTRUCT_PROJECT_ID}, max_queries={ARCHISTRUCT_MAX_QUERIES}, target_goal={ARCHISTRUCT_TARGET_GOAL}")
    logger.info("=" * 70)

    async with async_session_maker() as session:
        job = await company_search_service.run_project_search(
            session=session,
            project_id=ARCHISTRUCT_PROJECT_ID,
            company_id=ARCHISTRUCT_COMPANY_ID,
            max_queries=ARCHISTRUCT_MAX_QUERIES,
            target_goal=ARCHISTRUCT_TARGET_GOAL,
        )
        logger.info(f"ArchiStruct search completed! Job ID: {job.id}")
        logger.info(f"Config: {json.dumps(job.config or {}, indent=2)}")
        return job.id


# ============================================================
# Part B: Deliryo International HNWI Search
# ============================================================
async def run_deliryo_search():
    """Run Deliryo search for Cyprus + all international Russian HNWI hubs."""
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.services.search_service import search_service
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchQuery
    from sqlalchemy import text, select

    logger.info("=" * 70)
    logger.info("PART B: DELIRYO INTERNATIONAL HNWI SEARCH")
    logger.info(f"  project_id={DELIRYO_PROJECT_ID}, {len(DELIRYO_INTERNATIONAL_QUERIES)} pre-built queries")
    logger.info("=" * 70)

    async with async_session_maker() as session:
        # Get company_id from project
        row = await session.execute(
            text("SELECT company_id FROM projects WHERE id = :pid"),
            {"pid": DELIRYO_PROJECT_ID},
        )
        company_id = row.scalar_one()
        logger.info(f"Deliryo company_id: {company_id}")

        # Create a search job with pre-built queries
        job = SearchJob(
            company_id=company_id,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=len(DELIRYO_INTERNATIONAL_QUERIES),
            project_id=DELIRYO_PROJECT_ID,
            config={
                "max_queries": len(DELIRYO_INTERNATIONAL_QUERIES),
                "target_goal": 200,
                "type": "international_hnwi",
                "max_pages": 3,
                "workers": 8,
            },
        )
        session.add(job)
        await session.flush()

        # Add pre-built queries
        for q_text in DELIRYO_INTERNATIONAL_QUERIES:
            sq = SearchQuery(search_job_id=job.id, query_text=q_text)
            session.add(sq)
        await session.commit()

        logger.info(f"Created Deliryo search job {job.id} with {len(DELIRYO_INTERNATIONAL_QUERIES)} queries")

        # Run Yandex search
        await search_service.run_search_job(session, job.id)
        await session.refresh(job)
        logger.info(f"Deliryo Yandex search done: found={job.domains_found}, new={job.domains_new}")

        # Build skip set and get new domains
        skip_set = await company_search_service._build_skip_set(session, DELIRYO_PROJECT_ID)
        new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
        logger.info(f"Deliryo: {len(new_domains)} new domains to analyze")

        if new_domains:
            # Use INTERNATIONAL target_segments (not the Russia-only one from DB)
            await company_search_service._scrape_and_analyze_domains(
                session=session,
                job=job,
                domains=new_domains,
                target_segments=DELIRYO_INTERNATIONAL_TARGET_SEGMENTS,
            )

        # Also run GPT-generated queries for Russia (uses DB target_segments = Russia only)
        logger.info("Generating additional GPT queries for Deliryo (Russia)...")
        job2 = await company_search_service.run_project_search(
            session=session,
            project_id=DELIRYO_PROJECT_ID,
            company_id=company_id,
            max_queries=500,
            target_goal=200,
        )
        logger.info(f"Deliryo GPT search completed! Job ID: {job2.id}")
        logger.info(f"Config: {json.dumps(job2.config or {}, indent=2)}")
        return job.id, job2.id


# ============================================================
# Part C: Contact Extraction + Apollo Enrichment
# ============================================================
async def run_contacts_and_apollo(project_id: int, company_id: int, apollo_titles: list, project_name: str):
    """Extract contacts from websites + Apollo enrich for a project's targets."""
    from app.db import async_session_maker
    from app.services.pipeline_service import pipeline_service
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select

    logger.info(f"--- Contacts & Apollo for {project_name} (project_id={project_id}) ---")

    async with async_session_maker() as session:
        # Get all target DiscoveredCompanies that haven't been enriched yet
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.company_id == company_id,
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.apollo_enriched_at == None,
            ).order_by(DiscoveredCompany.confidence.desc())
        )
        targets = list(result.scalars().all())
        logger.info(f"{project_name}: {len(targets)} targets need contact enrichment")

        if not targets:
            logger.info(f"{project_name}: No targets to enrich, skipping")
            return {"contacts": {}, "apollo": {}}

        target_ids = [t.id for t in targets]

        # Step 1: Website contact extraction
        logger.info(f"{project_name}: Extracting contacts from websites...")
        contact_stats = await pipeline_service.extract_contacts_batch(
            session=session,
            discovered_company_ids=target_ids,
            company_id=company_id,
        )
        logger.info(f"{project_name} contact extraction: {contact_stats}")

        # Step 2: Apollo enrichment (no credit limit)
        logger.info(f"{project_name}: Running Apollo enrichment with titles={apollo_titles}...")
        apollo_stats = await pipeline_service.enrich_apollo_batch(
            session=session,
            discovered_company_ids=target_ids,
            company_id=company_id,
            max_people=5,
            max_credits=None,  # No limit
            titles=apollo_titles,
        )
        logger.info(f"{project_name} Apollo enrichment: {apollo_stats}")

        return {"contacts": contact_stats, "apollo": apollo_stats}


# ============================================================
# Part D: Google Sheets Export
# ============================================================
async def export_to_sheets(project_id: int, company_id: int, project_name: str) -> str:
    """Export targets + contacts to Google Sheets."""
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    logger.info(f"--- Exporting {project_name} to Google Sheets ---")

    async with async_session_maker() as session:
        # Fetch targets with contacts
        result = await session.execute(text("""
            SELECT
                sr.domain,
                sr.confidence,
                sr.reasoning,
                sr.company_info->>'name' as company_name,
                sr.company_info->>'description' as description,
                sr.company_info->>'services' as services,
                sr.company_info->>'location' as location,
                sr.company_info->>'industry' as industry,
                sr.scores->>'language_match' as language_match,
                sr.scores->>'industry_match' as industry_match,
                sr.scores->>'service_match' as service_match,
                sr.scores->>'company_type' as company_type_score,
                sr.scores->>'geography_match' as geography_match,
                sr.review_status,
                sr.analyzed_at,
                'https://' || sr.domain as url
            FROM search_results sr
            WHERE sr.project_id = :project_id
                AND sr.is_target = true
                AND sr.review_status != 'rejected'
            ORDER BY sr.confidence DESC, sr.analyzed_at DESC
        """), {"project_id": project_id})
        target_rows = result.fetchall()

        # Fetch contacts for these targets
        contacts_result = await session.execute(text("""
            SELECT
                dc.domain,
                ec.first_name,
                ec.last_name,
                ec.email,
                ec.phone,
                ec.job_title,
                ec.linkedin_url,
                ec.source,
                ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :project_id
                AND dc.company_id = :company_id
                AND dc.is_target = true
            ORDER BY dc.domain, ec.is_verified DESC, ec.source
        """), {"project_id": project_id, "company_id": company_id})
        contact_rows = contacts_result.fetchall()

        # Build domain -> contacts mapping
        domain_contacts = {}
        for c in contact_rows:
            domain = c.domain
            if domain not in domain_contacts:
                domain_contacts[domain] = []
            domain_contacts[domain].append(c)

        logger.info(f"{project_name}: {len(target_rows)} targets, contacts for {len(domain_contacts)} domains")

        # Build sheet data — one row per target, multiple contact columns
        headers = [
            "Domain", "URL", "Company Name", "Description", "Services",
            "Location", "Industry", "Confidence",
            "Language", "Industry Match", "Service Match", "Company Type", "Geography",
            "Review Status",
            "Contact 1 Name", "Contact 1 Email", "Contact 1 Phone",
            "Contact 1 Title", "Contact 1 LinkedIn", "Contact 1 Source",
            "Contact 2 Name", "Contact 2 Email", "Contact 2 Phone",
            "Contact 2 Title", "Contact 2 LinkedIn", "Contact 2 Source",
            "Contact 3 Name", "Contact 3 Email", "Contact 3 Phone",
            "Contact 3 Title", "Contact 3 LinkedIn", "Contact 3 Source",
            "Reasoning",
        ]

        data = [headers]
        for row in target_rows:
            services = row.services
            if services:
                try:
                    services_list = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(services_list) if isinstance(services_list, list) else str(services)
                except Exception:
                    pass

            row_data = [
                row.domain,
                row.url,
                row.company_name or "",
                row.description or "",
                services or "",
                row.location or "",
                row.industry or "",
                str(row.confidence or ""),
                str(row.language_match or ""),
                str(row.industry_match or ""),
                str(row.service_match or ""),
                str(row.company_type_score or ""),
                str(row.geography_match or ""),
                row.review_status or "",
            ]

            # Add up to 3 contacts
            contacts = domain_contacts.get(row.domain, [])
            for i in range(3):
                if i < len(contacts):
                    c = contacts[i]
                    name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                    row_data.extend([
                        name,
                        c.email or "",
                        c.phone or "",
                        c.job_title or "",
                        c.linkedin_url or "",
                        str(c.source or ""),
                    ])
                else:
                    row_data.extend(["", "", "", "", "", ""])

            row_data.append(row.reasoning or "")
            data.append(row_data)

        # Create and populate sheet
        title = f"{project_name} Targets + Contacts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        url = google_sheets_service.create_and_populate(
            title=title,
            data=data,
            share_with=SHARE_WITH,
        )

        if url:
            logger.info(f"{project_name}: Exported {len(target_rows)} targets to: {url}")
        else:
            logger.error(f"{project_name}: Google Sheets export failed!")
            # Fallback: save as JSON
            fallback_path = f"/scripts/{project_name.lower()}_targets.json"
            with open(fallback_path, "w", encoding="utf-8") as f:
                json.dump(
                    [dict(zip(headers, r)) for r in data[1:]],
                    f, indent=2, default=str, ensure_ascii=False,
                )
            logger.info(f"Saved fallback JSON to {fallback_path}")
            url = fallback_path

        return url


# ============================================================
# Main orchestrator
# ============================================================
async def main():
    from sqlalchemy import text

    start = datetime.utcnow()
    logger.info("=" * 70)
    logger.info("STARTING ALL-IN-ONE SEARCH + CONTACTS + EXPORT PIPELINE")
    logger.info(f"Time: {start.isoformat()}")
    logger.info("=" * 70)

    results = {}

    # --- Part A: ArchiStruct ---
    try:
        archistruct_job_id = await run_archistruct_search()
        results["archistruct_job"] = archistruct_job_id
        logger.info(f"Part A complete: ArchiStruct job {archistruct_job_id}")
    except Exception as e:
        logger.error(f"Part A FAILED: {e}", exc_info=True)
        results["archistruct_error"] = str(e)

    # --- Part B: Deliryo ---
    try:
        deliryo_jobs = await run_deliryo_search()
        results["deliryo_jobs"] = deliryo_jobs
        logger.info(f"Part B complete: Deliryo jobs {deliryo_jobs}")
    except Exception as e:
        logger.error(f"Part B FAILED: {e}", exc_info=True)
        results["deliryo_error"] = str(e)

    # --- Part C: Contacts + Apollo ---
    logger.info("=" * 70)
    logger.info("PART C: CONTACT EXTRACTION + APOLLO ENRICHMENT")
    logger.info("=" * 70)

    # Get Deliryo company_id
    from app.db import async_session_maker
    deliryo_company_id = None
    async with async_session_maker() as session:
        row = await session.execute(
            text("SELECT company_id FROM projects WHERE id = :pid"),
            {"pid": DELIRYO_PROJECT_ID},
        )
        deliryo_company_id = row.scalar_one()

    try:
        archistruct_contacts = await run_contacts_and_apollo(
            ARCHISTRUCT_PROJECT_ID, ARCHISTRUCT_COMPANY_ID,
            ARCHISTRUCT_APOLLO_TITLES, "ArchiStruct",
        )
        results["archistruct_contacts"] = archistruct_contacts
    except Exception as e:
        logger.error(f"Part C (ArchiStruct contacts) FAILED: {e}", exc_info=True)
        results["archistruct_contacts_error"] = str(e)

    try:
        deliryo_contacts = await run_contacts_and_apollo(
            DELIRYO_PROJECT_ID, deliryo_company_id,
            DELIRYO_APOLLO_TITLES, "Deliryo",
        )
        results["deliryo_contacts"] = deliryo_contacts
    except Exception as e:
        logger.error(f"Part C (Deliryo contacts) FAILED: {e}", exc_info=True)
        results["deliryo_contacts_error"] = str(e)

    # --- Part D: Google Sheets Export ---
    logger.info("=" * 70)
    logger.info("PART D: GOOGLE SHEETS EXPORT")
    logger.info("=" * 70)

    try:
        archistruct_url = await export_to_sheets(
            ARCHISTRUCT_PROJECT_ID, ARCHISTRUCT_COMPANY_ID, "ArchiStruct",
        )
        results["archistruct_sheet"] = archistruct_url
    except Exception as e:
        logger.error(f"Part D (ArchiStruct export) FAILED: {e}", exc_info=True)
        results["archistruct_export_error"] = str(e)

    try:
        deliryo_url = await export_to_sheets(
            DELIRYO_PROJECT_ID, deliryo_company_id, "Deliryo",
        )
        results["deliryo_sheet"] = deliryo_url
    except Exception as e:
        logger.error(f"Part D (Deliryo export) FAILED: {e}", exc_info=True)
        results["deliryo_export_error"] = str(e)

    # --- Summary ---
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")
    logger.info("=" * 70)

    # Save results
    with open("/scripts/run_targets_500_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main())
