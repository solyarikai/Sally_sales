#!/usr/bin/env python3
"""
Migrate Existing TAM Data — Import EasyStaff Global JSON files into the gathering system.

Imports:
  1. uae_god_search_companies.json (5,602 companies) → apollo.people.emulator, strategy_b
  2. dubai_agency_companies_full.json (295 companies) → apollo.people.emulator, strategy_a
  3. uae_20k_companies.json (7,782 companies) → apollo.companies.emulator, industry_tags
  4. uae_god_search_people.json (12,201 people) → ExtractedContacts linked to DiscoveredCompanies

Usage:
  cd backend && python -m scripts.migrate_existing_tam [--dry-run] [--project-id 9]
"""
import asyncio
import json
import hashlib
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from app.db import async_session_maker, init_db
from app.models.gathering import GatheringRun, CompanySourceLink
from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus, ExtractedContact, ContactSource
from app.services.domain_service import normalize_domain

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "easystaff-global" / "data"

# EasyStaff Global project
DEFAULT_PROJECT_ID = 9
DEFAULT_COMPANY_ID = 1


def compute_filter_hash(filters: dict) -> str:
    canonical = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def extract_domain(raw: str) -> str:
    """Extract and normalize domain from URL or raw string."""
    if not raw:
        return ""
    domain = normalize_domain(raw)
    return domain


async def create_gathering_run(
    session, project_id: int, company_id: int,
    source_type: str, source_subtype: str, source_label: str,
    filters: dict, raw_count: int, notes: str,
) -> GatheringRun:
    """Create a historical gathering run record."""
    run = GatheringRun(
        project_id=project_id,
        company_id=company_id,
        source_type=source_type,
        source_label=source_label,
        source_subtype=source_subtype,
        filters=filters,
        filter_hash=compute_filter_hash(filters),
        status="completed",
        started_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        raw_results_count=raw_count,
        triggered_by="migration",
        input_mode="structured",
        notes=notes,
    )
    session.add(run)
    await session.flush()
    logger.info(f"Created GatheringRun #{run.id}: {source_type}/{source_subtype} ({raw_count} raw)")
    return run


async def upsert_company(
    session, project_id: int, company_id: int, domain: str,
    name: str = "", company_info: dict = None, linkedin_url: str = "",
) -> tuple:
    """Upsert DiscoveredCompany by domain. Returns (dc, is_new)."""
    if not domain:
        return None, False

    existing = await session.execute(
        select(DiscoveredCompany).where(
            DiscoveredCompany.company_id == company_id,
            DiscoveredCompany.project_id == project_id,
            DiscoveredCompany.domain == domain,
        )
    )
    dc = existing.scalar_one_or_none()

    if dc:
        # Enrich with better data if available
        if name and not dc.name:
            dc.name = name
        if company_info and not dc.company_info:
            dc.company_info = company_info
        if linkedin_url and not dc.linkedin_company_url:
            dc.linkedin_company_url = linkedin_url
        return dc, False

    dc = DiscoveredCompany(
        company_id=company_id,
        project_id=project_id,
        domain=domain,
        name=name,
        url=f"https://{domain}",
        company_info=company_info,
        linkedin_company_url=linkedin_url,
        status=DiscoveredCompanyStatus.NEW,
    )
    session.add(dc)
    await session.flush()
    return dc, True


async def create_source_link(
    session, dc_id: int, run_id: int, rank: int, source_data: dict,
) -> bool:
    """Create CompanySourceLink. Returns True if new link created."""
    existing = await session.execute(
        select(CompanySourceLink).where(
            CompanySourceLink.discovered_company_id == dc_id,
            CompanySourceLink.gathering_run_id == run_id,
        )
    )
    if existing.scalar_one_or_none():
        return False

    link = CompanySourceLink(
        discovered_company_id=dc_id,
        gathering_run_id=run_id,
        source_rank=rank,
        source_data=source_data,
    )
    session.add(link)
    return True


async def import_god_search_companies(session, project_id: int, company_id: int, dry_run: bool = False):
    """Import uae_god_search_companies.json — Apollo People tab, Strategy B (seniority)."""
    filepath = DATA_DIR / "uae_god_search_companies.json"
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} records from {filepath.name}")

    if dry_run:
        logger.info(f"[DRY RUN] Would create GatheringRun + {len(data)} companies")
        return

    filters = {
        "person_locations": ["Dubai, United Arab Emirates", "Abu Dhabi, United Arab Emirates", "Sharjah, United Arab Emirates"],
        "person_seniorities": ["founder", "c_suite", "owner"],
        "organization_num_employees_ranges": ["1,10", "11,20", "21,50", "51,100", "101,200"],
        "strategy": "B",
        "max_pages": 10,
    }

    run = await create_gathering_run(
        session, project_id, company_id,
        source_type="apollo.people.emulator",
        source_subtype="strategy_b",
        source_label="Apollo People Search — Seniority Strategy",
        filters=filters,
        raw_count=len(data),
        notes="Historical import: UAE agencies, broad seniority x size search",
    )

    new_count = 0
    dup_count = 0

    for i, item in enumerate(data):
        domain = extract_domain(item.get("domain", ""))
        linkedin_url = item.get("linkedin_url", "")
        name = item.get("name", "")

        dc, is_new = await upsert_company(
            session, project_id, company_id, domain,
            name=name, company_info=item, linkedin_url=linkedin_url,
        )
        if not dc:
            continue

        await create_source_link(session, dc.id, run.id, i + 1, item)

        if is_new:
            new_count += 1
        else:
            dup_count += 1

        if (i + 1) % 500 == 0:
            await session.flush()
            logger.info(f"  Progress: {i + 1}/{len(data)} ({new_count} new, {dup_count} dup)")

    run.new_companies_count = new_count
    run.duplicate_count = dup_count
    await session.flush()
    logger.info(f"God search companies: {new_count} new, {dup_count} duplicates")


async def import_keyword_companies(session, project_id: int, company_id: int, dry_run: bool = False):
    """Import dubai_agency_companies_full.json — Apollo People tab, Strategy A (keywords)."""
    filepath = DATA_DIR / "dubai_agency_companies_full.json"
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} records from {filepath.name}")

    if dry_run:
        logger.info(f"[DRY RUN] Would create GatheringRun + {len(data)} companies")
        return

    filters = {
        "person_locations": ["Dubai, United Arab Emirates"],
        "q_organization_name": "32 keywords (marketing agency, digital agency, staffing, etc.)",
        "strategy": "A",
        "max_pages": 10,
    }

    run = await create_gathering_run(
        session, project_id, company_id,
        source_type="apollo.people.emulator",
        source_subtype="strategy_a",
        source_label="Apollo People Search — Keyword Strategy",
        filters=filters,
        raw_count=len(data),
        notes="Historical import: Dubai agency keyword search (32 keywords)",
    )

    new_count = 0
    dup_count = 0

    for i, item in enumerate(data):
        # This file has different structure — company name, location, people
        name = item.get("company", "")
        # Try to extract domain from people's email domains or name
        domain = ""
        people = item.get("people", [])
        for p in people:
            email = p.get("email", "")
            if email and "@" in email and "email_not_unlocked" not in email:
                domain = email.split("@")[1].lower()
                break

        if not domain:
            continue

        dc, is_new = await upsert_company(
            session, project_id, company_id, domain,
            name=name, company_info=item,
        )
        if not dc:
            continue

        await create_source_link(session, dc.id, run.id, i + 1, item)

        if is_new:
            new_count += 1
        else:
            dup_count += 1

    run.new_companies_count = new_count
    run.duplicate_count = dup_count
    await session.flush()
    logger.info(f"Keyword companies: {new_count} new, {dup_count} duplicates")


async def import_companies_tab(session, project_id: int, company_id: int, dry_run: bool = False):
    """Import uae_20k_companies.json — Apollo Companies tab (DOM scrape)."""
    filepath = DATA_DIR / "uae_20k_companies.json"
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} records from {filepath.name}")

    if dry_run:
        logger.info(f"[DRY RUN] Would create GatheringRun + {len(data)} companies")
        return

    filters = {
        "organization_locations": ["United Arab Emirates"],
        "organization_industry_tag_ids": [
            "5567cd4773696439b10b0000",  # IT
            "5567cd467369644d39040000",  # Marketing
            "5567ced173696450cb580000",  # Retail
        ],
        "organization_num_employees_ranges": ["1,10", "11,20", "21,50", "51,100", "101,200"],
        "max_pages": 100,
    }

    run = await create_gathering_run(
        session, project_id, company_id,
        source_type="apollo.companies.emulator",
        source_subtype="industry_tags",
        source_label="Apollo Companies Tab — Industry Tags + Keywords",
        filters=filters,
        raw_count=len(data),
        notes="Historical import: UAE 20K companies, industry tags + keyword search",
    )

    new_count = 0
    dup_count = 0

    for i, item in enumerate(data):
        linkedin_url = item.get("linkedin_url", "")
        name = item.get("name", "")
        # Companies tab often has no domain — store with linkedin_url as identifier
        domain = ""  # Will need RESOLVE phase later
        apollo_id = item.get("id", "")

        # Skip if no name and no linkedin
        if not name and not linkedin_url:
            continue

        # Try to extract domain from linkedin URL for dedup
        if linkedin_url and not domain:
            # Can't derive domain from LinkedIn — store without domain
            pass

        dc, is_new = await upsert_company(
            session, project_id, company_id,
            domain=domain or f"_apollo_{apollo_id}" if apollo_id else "",
            name=name,
            company_info=item,
            linkedin_url=linkedin_url,
        )
        if not dc:
            continue

        await create_source_link(session, dc.id, run.id, i + 1, item)

        if is_new:
            new_count += 1
        else:
            dup_count += 1

        if (i + 1) % 500 == 0:
            await session.flush()
            logger.info(f"  Progress: {i + 1}/{len(data)} ({new_count} new, {dup_count} dup)")

    run.new_companies_count = new_count
    run.duplicate_count = dup_count
    await session.flush()
    logger.info(f"Companies tab: {new_count} new, {dup_count} duplicates")


async def import_people(session, project_id: int, company_id: int, dry_run: bool = False):
    """Import uae_god_search_people.json as ExtractedContacts linked to DiscoveredCompanies."""
    filepath = DATA_DIR / "uae_god_search_people.json"
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} people records from {filepath.name}")

    if dry_run:
        logger.info(f"[DRY RUN] Would import {len(data)} people")
        return

    imported = 0
    skipped = 0

    for i, person in enumerate(data):
        org = person.get("organization", {}) or {}
        website = org.get("website_url", "")
        domain = extract_domain(website)

        if not domain:
            skipped += 1
            continue

        # Find the DiscoveredCompany
        dc_result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.company_id == company_id,
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.domain == domain,
            )
        )
        dc = dc_result.scalar_one_or_none()
        if not dc:
            skipped += 1
            continue

        email = person.get("email", "")
        if not email or "email_not_unlocked" in email:
            email = None

        # Check for existing contact
        if email:
            existing = await session.execute(
                select(ExtractedContact).where(
                    ExtractedContact.discovered_company_id == dc.id,
                    ExtractedContact.email == email,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

        contact = ExtractedContact(
            discovered_company_id=dc.id,
            email=email,
            first_name=person.get("first_name"),
            last_name=person.get("last_name"),
            job_title=person.get("title"),
            linkedin_url=person.get("linkedin_url"),
            source=ContactSource.APOLLO,
            raw_data=person,
        )
        session.add(contact)
        imported += 1

        if (i + 1) % 1000 == 0:
            await session.flush()
            logger.info(f"  People progress: {i + 1}/{len(data)} ({imported} imported, {skipped} skipped)")

    await session.flush()
    logger.info(f"People import: {imported} imported, {skipped} skipped")


async def main():
    dry_run = "--dry-run" in sys.argv
    project_id = DEFAULT_PROJECT_ID
    company_id = DEFAULT_COMPANY_ID

    # Parse --project-id
    for i, arg in enumerate(sys.argv):
        if arg == "--project-id" and i + 1 < len(sys.argv):
            project_id = int(sys.argv[i + 1])

    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Migrating TAM data for project={project_id}, company={company_id}")

    await init_db()

    async with async_session_maker() as session:
        # Import order: largest dataset first, then keyword search (mostly dups), then companies tab
        logger.info("=" * 60)
        logger.info("Step 1/4: God search companies (Strategy B, ~5,602)")
        await import_god_search_companies(session, project_id, company_id, dry_run)

        logger.info("=" * 60)
        logger.info("Step 2/4: Keyword companies (Strategy A, ~295)")
        await import_keyword_companies(session, project_id, company_id, dry_run)

        logger.info("=" * 60)
        logger.info("Step 3/4: Companies tab (Industry tags, ~7,782)")
        await import_companies_tab(session, project_id, company_id, dry_run)

        logger.info("=" * 60)
        logger.info("Step 4/4: People records (~12,201)")
        await import_people(session, project_id, company_id, dry_run)

        if not dry_run:
            await session.commit()
            logger.info("All data committed to database")
        else:
            logger.info("[DRY RUN] No changes made")

    logger.info("Migration complete!")


if __name__ == "__main__":
    asyncio.run(main())
