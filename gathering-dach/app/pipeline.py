"""
DACH→LATAM Gathering Pipeline
==============================

Phase 1 (FREE, 0 Apollo credits):
  Search Apollo People for employees LOCATED IN LATAM
  working at companies HEADQUARTERED IN DACH/Nordic (<500 employees).
  → Collect unique company domains with confirmed LATAM presence.
  → CHECKPOINT 1: show found companies, wait for approval.

Phase 2 (FREE, 0 Apollo credits):
  Search Apollo People for CEO/CFO at the approved company domains.
  → Collect up to 5000 CEO/CFO contacts.
  → CHECKPOINT 2: show contact count, export to Google Sheets.

Apollo endpoint: /mixed_people/api_search — FREE, no email reveal.
Emails found later via FindyMail (at operator request, separate step).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.apollo import ApolloClient
from app import db

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

LATAM_COUNTRIES = [
    "Mexico", "Colombia", "Brazil", "Argentina", "Peru",
    "Chile", "Ecuador", "Uruguay", "Costa Rica", "Panama",
]

DACH_NORDIC_COUNTRIES = [
    "Germany", "Austria", "Switzerland",
    "Sweden", "Netherlands", "Norway", "Finland",
]

# Iceland excluded from Apollo location filter — too small, would add noise
# User can re-add if needed

EMPLOYEE_RANGES = ["1,10", "11,20", "21,50", "51,100", "101,200", "201,500"]

EXEC_TITLES = [
    "CEO", "CFO",
    "Chief Executive Officer",
    "Chief Financial Officer",
]

PHASE1_MAX_PAGES = 100     # 100 pages × 100 people = 10,000 LATAM employees max
PHASE2_BATCH_SIZE = 50     # domains per Apollo request in phase 2
PHASE2_MAX_PAGES = 10      # per batch; 10 pages × 100 = 1000 execs per 50 domains
TARGET_CONTACTS = 5_000


def _extract_domain(person: dict) -> str:
    org = person.get("organization") or {}
    url = org.get("website_url") or org.get("primary_domain") or ""
    return (
        url.replace("https://www.", "").replace("http://www.", "")
        .replace("https://", "").replace("http://", "")
        .rstrip("/").lower()
    )


def _extract_company_meta(person: dict) -> dict:
    org = person.get("organization") or {}
    return {
        "name": org.get("name", ""),
        "hq_country": org.get("country", ""),
        "employees": org.get("num_employees") or 0,
        "industry": org.get("industry", ""),
    }


# ── Phase 1 ───────────────────────────────────────────────────────────────────

async def run_phase1(
    run_id: int,
    apollo: ApolloClient,
    progress_cb: Optional[Callable] = None,
) -> int:
    """
    Find LATAM employees at DACH companies.
    Returns count of unique company domains found.
    """
    logger.info(f"[run={run_id}] Phase 1 started: LATAM employees at DACH companies")
    db.set_run_state(run_id, "phase1_running")

    total_people = 0
    unique_domains = 0

    for latam_country in LATAM_COUNTRIES:
        logger.info(f"  Searching: employees in {latam_country}")

        async def on_page(page: int, found: int, total: int, country=latam_country):
            if progress_cb:
                await progress_cb({
                    "phase": "phase1",
                    "current_country": country,
                    "page": page,
                    "people_this_country": found,
                    "total_people": total_people + found,
                    "unique_domains": unique_domains,
                })

        people = await apollo.people_search_all(
            max_pages=PHASE1_MAX_PAGES,
            on_page=on_page,
            person_locations=[latam_country],
            organization_locations=DACH_NORDIC_COUNTRIES,
            organization_num_employees_ranges=EMPLOYEE_RANGES,
        )

        total_people += len(people)

        for person in people:
            domain = _extract_domain(person)
            if not domain or "." not in domain:
                continue
            meta = _extract_company_meta(person)
            db.upsert_company(
                run_id=run_id,
                domain=domain,
                name=meta["name"],
                hq_country=meta["hq_country"],
                employees=meta["employees"],
                industry=meta["industry"],
                latam_countries=json.dumps([latam_country]),
                latam_count=1,
            )

        companies = db.get_companies(run_id)
        unique_domains = len(companies)
        logger.info(
            f"  After {latam_country}: {len(people)} people found, "
            f"{unique_domains} unique domains total"
        )

    db.set_run_state(run_id, "phase1_done")
    logger.info(
        f"[run={run_id}] Phase 1 complete: "
        f"{total_people} LATAM employees → {unique_domains} unique DACH companies"
    )
    return unique_domains


# ── Phase 2 ───────────────────────────────────────────────────────────────────

async def run_phase2(
    run_id: int,
    apollo: ApolloClient,
    progress_cb: Optional[Callable] = None,
) -> int:
    """
    Find CEO/CFO at approved company domains.
    Returns count of contacts found.
    """
    companies = db.get_companies(run_id, approved_only=True)
    domains = [c["domain"] for c in companies if c["domain"]]

    logger.info(
        f"[run={run_id}] Phase 2 started: CEO/CFO search at "
        f"{len(domains)} approved domains"
    )
    db.set_run_state(run_id, "phase2_running")

    total_contacts = 0
    batches = [domains[i:i + PHASE2_BATCH_SIZE] for i in range(0, len(domains), PHASE2_BATCH_SIZE)]

    for batch_idx, batch_domains in enumerate(batches):
        if total_contacts >= TARGET_CONTACTS:
            logger.info(f"Reached {TARGET_CONTACTS} contacts, stopping.")
            break

        async def on_page(page: int, found: int, total: int, bi=batch_idx):
            if progress_cb:
                await progress_cb({
                    "phase": "phase2",
                    "batch": bi + 1,
                    "total_batches": len(batches),
                    "page": page,
                    "contacts_this_batch": found,
                    "total_contacts": total_contacts + found,
                })

        people = await apollo.people_search_all(
            max_pages=PHASE2_MAX_PAGES,
            on_page=on_page,
            organization_domains=batch_domains,
            person_titles=EXEC_TITLES,
        )

        for person in people:
            apollo_id = person.get("id", "")
            if not apollo_id:
                continue
            domain = _extract_domain(person)
            db.upsert_contact(
                run_id=run_id,
                apollo_id=apollo_id,
                company_domain=domain,
                first_name=person.get("first_name", ""),
                last_name=person.get("last_name", ""),
                title=person.get("title", ""),
                linkedin_url=person.get("linkedin_url", ""),
            )

        total_contacts = db.count_contacts(run_id)
        logger.info(
            f"  Batch {batch_idx+1}/{len(batches)}: +{len(people)} people | "
            f"total contacts: {total_contacts}"
        )

        await asyncio.sleep(1)  # brief pause between batches

    db.set_run_state(run_id, "phase2_done")
    logger.info(f"[run={run_id}] Phase 2 complete: {total_contacts} CEO/CFO contacts")
    return total_contacts
