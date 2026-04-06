"""
DACH→LATAM Gathering Pipeline
==============================

Phase 1 (FREE, 0 Apollo credits):
  Puppeteer scraper searches Apollo Companies UI for DACH/Nordic companies
  (10–500 employees) with keywords indicating LATAM/international team presence:
  "LATAM", "Latin America", "nearshore", "remote team", etc.
  → Collect unique company domains.
  → CHECKPOINT 1: show found companies, wait for approval.

Phase 2 (FREE, 0 Apollo credits):
  Search Apollo People for CFO→CEO→COO at the approved company domains.
  → Priority: Tier1 (CFO/VP Finance) → Tier2 (CEO/Founder) → Tier3 (COO/Ops)
  → Max 2 contacts per company; prefer breadth over depth.
  → Collect up to 5000 contacts.
  → CHECKPOINT 2: show contact count, export to Google Sheets.

Apollo endpoint: /mixed_people/api_search — FREE, no email reveal.
Emails found later via FindyMail (at operator request, separate step).
"""
import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional

from app.apollo import ApolloClient
from app import db

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

PHASE2_BATCH_SIZE = 50     # domains per Apollo request in phase 2
PHASE2_MAX_PAGES = 10      # per batch; 10 pages × 100 = 1000 execs per 50 domains
MAX_CONTACTS_PER_COMPANY = 2  # hard ceiling; prefer breadth over depth
TARGET_CONTACTS = 5_000

# Phase 2 title priorities — searched together, selected per company
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


# ── Phase 1 ───────────────────────────────────────────────────────────────────

async def run_phase1(
    run_id: int,
    progress_cb: Optional[Callable] = None,
) -> int:
    """
    Scrape Apollo Companies UI for DACH companies with LATAM/international keywords.
    Returns count of unique company domains found.
    """
    from app.scraper import scrape_dach_companies, SEARCH_LOCATIONS, LATAM_KEYWORDS

    logger.info(
        f"[run={run_id}] Phase 1 started: Puppeteer scrape of DACH companies | "
        f"locations={SEARCH_LOCATIONS} | keywords={LATAM_KEYWORDS}"
    )
    db.set_run_state(run_id, "phase1_running")

    companies = await scrape_dach_companies(on_progress=progress_cb)

    for company in companies:
        domain = company["domain"]
        if not domain or "." not in domain:
            continue
        db.upsert_company(
            run_id=run_id,
            domain=domain,
            name=company.get("name", ""),
            hq_country=company.get("hq_country", ""),
            employees=company.get("employees") or 0,
            industry=company.get("industry", ""),
            latam_countries=json.dumps([company.get("hq_country", "")]),
            latam_count=1,
        )

    unique_domains = len(db.get_companies(run_id))
    db.set_run_state(run_id, "phase1_done")
    logger.info(
        f"[run={run_id}] Phase 1 complete: {unique_domains} unique DACH companies"
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
