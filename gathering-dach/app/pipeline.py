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

# Phase 2 title priorities — searched together, then selected per company
# Tier 1 (highest): CFO-track — controls money, feels freelancer payment pain directly
TITLES_TIER1 = [
    "CFO", "Chief Financial Officer", "VP Finance", "Head of Finance",
    "VP of Finance", "Director of Finance",
]
# Tier 2: CEO-track — decision maker for smaller companies
TITLES_TIER2 = [
    "CEO", "Chief Executive Officer", "Founder", "Co-Founder",
    "Managing Director", "Owner",
]
# Tier 3: Operations — if no finance or CEO found
TITLES_TIER3 = [
    "COO", "Chief Operating Officer", "Head of Operations",
    "VP Operations", "VP of Operations", "Director of Operations",
]

# All titles searched in one Apollo call per batch
ALL_EXEC_TITLES = TITLES_TIER1 + TITLES_TIER2 + TITLES_TIER3

PHASE1_MAX_PAGES = 100     # 100 pages × 100 people = 10,000 LATAM employees max
PHASE2_BATCH_SIZE = 50     # domains per Apollo request in phase 2
PHASE2_MAX_PAGES = 10      # per batch; 10 pages × 100 = 1000 execs per 50 domains
MAX_CONTACTS_PER_COMPANY = 2  # hard ceiling, but prefer breadth over depth
TARGET_CONTACTS = 5_000


def _title_tier(title: str) -> int:
    """Return priority tier for a title (1=highest). 99 = unknown."""
    t = (title or "").lower()
    for keyword in ["cfo", "chief financial", "vp finance", "head of finance",
                    "vp of finance", "director of finance"]:
        if keyword in t:
            return 1
    for keyword in ["ceo", "chief executive", "founder", "co-founder",
                    "managing director", "owner"]:
        if keyword in t:
            return 2
    for keyword in ["coo", "chief operating", "head of operations",
                    "vp operations", "vp of operations", "director of operations"]:
        if keyword in t:
            return 3
    return 99


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
    Find CFO/CEO/COO at approved company domains with priority selection.

    Per company:
      - Take Tier 1 (CFO) if found
      - Else take Tier 2 (CEO/Founder) if found
      - Else take Tier 3 (COO/Operations)
      - Max MAX_CONTACTS_PER_COMPANY, but prefer 1 contact from more companies.

    Returns count of contacts saved.
    """
    companies = db.get_companies(run_id, approved_only=True)
    domains = [c["domain"] for c in companies if c["domain"]]

    logger.info(
        f"[run={run_id}] Phase 2 started: priority CFO→CEO→COO at "
        f"{len(domains)} approved domains"
    )
    db.set_run_state(run_id, "phase2_running")

    total_contacts = 0
    batches = [domains[i:i + PHASE2_BATCH_SIZE] for i in range(0, len(domains), PHASE2_BATCH_SIZE)]

    for batch_idx, batch_domains in enumerate(batches):
        if total_contacts >= TARGET_CONTACTS:
            logger.info(f"Reached {TARGET_CONTACTS} contacts — stopping.")
            break

        async def on_page(page: int, found: int, total: int, bi=batch_idx):
            if progress_cb:
                await progress_cb({
                    "phase": "phase2",
                    "batch": bi + 1,
                    "total_batches": len(batches),
                    "page": page,
                    "total_contacts": total_contacts,
                })

        # Fetch ALL exec titles in one pass per batch
        people = await apollo.people_search_all(
            max_pages=PHASE2_MAX_PAGES,
            on_page=on_page,
            organization_domains=batch_domains,
            person_titles=ALL_EXEC_TITLES,
        )

        # Group candidates by domain, sort each group by tier
        by_domain: Dict[str, List[dict]] = {}
        for person in people:
            domain = _extract_domain(person)
            if not domain:
                continue
            by_domain.setdefault(domain, []).append(person)

        for domain, candidates in by_domain.items():
            # Sort by tier (1 best) then by completeness (has linkedin)
            candidates.sort(
                key=lambda p: (
                    _title_tier(p.get("title", "")),
                    0 if p.get("linkedin_url") else 1,
                )
            )

            saved_for_domain = 0
            best_tier_saved = 99  # track which tier we already saved

            for person in candidates:
                if saved_for_domain >= MAX_CONTACTS_PER_COMPANY:
                    break

                tier = _title_tier(person.get("title", ""))

                # Priority rule: only move to next tier if nothing saved yet from better tier
                # AND only take 2nd contact if same tier as the first saved
                if saved_for_domain > 0 and tier > best_tier_saved:
                    break  # don't mix tiers — 1 CFO is better than 1 CFO + 1 COO

                apollo_id = person.get("id", "")
                if not apollo_id:
                    continue

                db.upsert_contact(
                    run_id=run_id,
                    apollo_id=apollo_id,
                    company_domain=domain,
                    first_name=person.get("first_name", ""),
                    last_name=person.get("last_name", ""),
                    title=person.get("title", ""),
                    linkedin_url=person.get("linkedin_url", ""),
                )
                saved_for_domain += 1
                best_tier_saved = min(best_tier_saved, tier)

        total_contacts = db.count_contacts(run_id)
        logger.info(
            f"  Batch {batch_idx+1}/{len(batches)}: "
            f"{len(people)} candidates → {total_contacts} contacts total"
        )

        await asyncio.sleep(1)

    db.set_run_state(run_id, "phase2_done")
    logger.info(f"[run={run_id}] Phase 2 complete: {total_contacts} contacts")
    return total_contacts
