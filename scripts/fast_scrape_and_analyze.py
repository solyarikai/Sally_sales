#!/usr/bin/env python3
"""Fast scrape: 50 concurrent, streaming DB commits (no data loss on crash).
Then GPT-4o-mini analysis with v7 prompt (no city filter)."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

COMMIT_EVERY = 50  # Commit to DB every N successful scrapes


async def fast_scrape():
    from app.db import async_session_maker, init_db
    from app.services.scraper_service import scraper_service
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select, update, not_
    from datetime import datetime, timezone

    await init_db()

    # Get all companies needing scrape
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.scraped_text.is_(None),
                DiscoveredCompany.first_found_by >= 75,
                DiscoveredCompany.status != DiscoveredCompanyStatus.REJECTED,
                not_(DiscoveredCompany.domain.like('%_apollo_%')),
                DiscoveredCompany.domain.isnot(None),
                DiscoveredCompany.domain != '',
            )
        )
        companies = result.all()

    total = len(companies)
    print(f"Scraping {total} companies — 50 concurrent, commit every {COMMIT_EVERY}")

    urls = [{'row_id': c.id, 'url': f'https://{c.domain}'} for c in companies]

    # Streaming commit: save each result immediately
    success_count = 0
    batch_buffer = []
    session_holder = [None]  # mutable reference for callback

    async def on_result(result):
        nonlocal success_count, batch_buffer
        if result.get('success') and result.get('text'):
            batch_buffer.append(result)

        if len(batch_buffer) >= COMMIT_EVERY:
            async with async_session_maker() as s:
                for r in batch_buffer:
                    await s.execute(
                        update(DiscoveredCompany)
                        .where(DiscoveredCompany.id == r['row_id'])
                        .values(
                            scraped_text=r['text'][:50000],
                            scraped_at=datetime.now(timezone.utc),
                        )
                    )
                await s.commit()
                success_count += len(batch_buffer)
                print(f"  Committed {success_count}/{total} scraped")
                batch_buffer.clear()

    await scraper_service.scrape_batch(
        urls, timeout=15, max_concurrent=50, delay_between_requests=0.05,
        on_result=on_result,
    )

    # Commit remaining
    if batch_buffer:
        async with async_session_maker() as s:
            for r in batch_buffer:
                await s.execute(
                    update(DiscoveredCompany)
                    .where(DiscoveredCompany.id == r['row_id'])
                    .values(
                        scraped_text=r['text'][:50000],
                        scraped_at=datetime.now(timezone.utc),
                    )
                )
            await s.commit()
            success_count += len(batch_buffer)

    print(f"SCRAPING DONE: {success_count}/{total}")
    return success_count


async def analyze():
    from app.db import async_session_maker, init_db
    from app.services.gathering_service import gathering_service
    from app.models.gathering import GatheringRun

    PROMPT = """Analyze this company website. Is this a service business that likely hires freelancers or remote contractors?

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

SOLO/TINY: Only ONE person on website = NOT_A_MATCH. Need teams of 3+.
"Fractional CxO", personal brand, solo advisor, blogger = NOT_A_MATCH.

COMPETITORS: Staffing, recruitment, outsourcing, EOR/PEO, HR tech = NOT_A_MATCH.
"Staff augmentation", "talent acquisition" = NOT_A_MATCH.

INTERIOR DESIGN / ARCHITECTURE = NOT_A_MATCH.
COMPANY FORMATION / LEGAL / VISA = NOT_A_MATCH.
INVESTMENT / VC / HOLDING / M&A = NOT_A_MATCH.
GOVERNMENT / 1000+ employees = NOT_A_MATCH.
OFFLINE (restaurant, hotel, construction, retail, medical, bank) = NOT_A_MATCH.
Hardware stores, rewards platforms, e-commerce resellers = NOT_A_MATCH.
FAKE / template site / aggregator / directory / job board = NOT_A_MATCH.

=== IF NOT EXCLUDED — assign segment ===

DIGITAL_AGENCY, CREATIVE_STUDIO, SOFTWARE_HOUSE, IT_SERVICES, MARKETING_AGENCY,
TECH_STARTUP, MEDIA_PRODUCTION, GAME_STUDIO, CONSULTING_FIRM, ECOMMERCE_COMPANY

=== OUTPUT (valid JSON) ===

{"segment": "CAPS_LOCKED or NOT_A_MATCH", "is_target": true/false, "reasoning": "Does [what]. Matches [segment] because [why].", "company_info": {"name": "from website", "description": "what they do", "location": "if found"}}

When in doubt -> NOT_A_MATCH.
"""

    await init_db()

    for run_id in [75, 76, 77, 78, 79, 80]:
        async with async_session_maker() as s:
            run = await s.get(GatheringRun, run_id)
            if not run:
                continue
            city = run.notes.split(':')[0] if run.notes else f'Run {run_id}'

            if run.current_phase == 'gathered':
                run.current_phase = 'scraped'
                await s.commit()

            print(f"\n=== GPT: {city} (run #{run_id}) ===")
            try:
                result = await gathering_service.run_analysis(
                    s, run_id, model="gpt-4o-mini", prompt_text=PROMPT,
                    prompt_name="EasyStaff Global v7 (no city filter)"
                )
                print(f"  Analyzed: {result.get('total_analyzed', 0)}")
                print(f"  Targets: {result.get('targets_found', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")


async def main():
    scraped = await fast_scrape()
    if scraped > 0:
        await analyze()
    print("\n=== ALL DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
