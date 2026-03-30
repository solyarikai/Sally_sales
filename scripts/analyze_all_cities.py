#!/usr/bin/env python3
"""Analyze all new city companies — NO city filter.
Target = any service business that hires freelancers. City doesn't matter."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT = """Analyze this company website. Is this a service business that likely hires freelancers or remote contractors?

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

SOLO/TINY (RED FLAG):
- Only ONE person on website = NOT_A_MATCH
- "Fractional CxO", personal brand, solo advisor, blogger = NOT_A_MATCH
- No team/about page showing multiple people = RED FLAG
- Company name IS a person's name = NOT_A_MATCH

COMPETITORS (our direct competition — reject aggressively):
- Staffing, recruitment, headhunting, outsourcing providers = NOT_A_MATCH
- "IT staffing", "IT recruitment", "tech recruitment" = NOT_A_MATCH
- EOR/PEO platforms, freelance marketplaces, HR tech = NOT_A_MATCH
- "Staff augmentation", "talent acquisition", "workforce solutions" = NOT_A_MATCH
- Any company that PROVIDES workers to other companies = NOT_A_MATCH

INTERIOR DESIGN / ARCHITECTURE:
- Interior design, architecture, fit-out, renovation = NOT_A_MATCH

COMPANY FORMATION / LEGAL:
- Business setup, visa services, PRO services, trade license = NOT_A_MATCH

INVESTMENT/HOLDING:
- VC, PE, holding, M&A advisory, fund management, angel investors = NOT_A_MATCH
- Sovereign wealth funds, accelerators = NOT_A_MATCH

GOVERNMENT / TOO LARGE:
- Government entities, 1000+ employees = NOT_A_MATCH

OFFLINE / NOT SERVICE BUSINESS:
- Restaurant, hotel, construction, real estate, retail, medical, school, bank, oil/gas = NOT_A_MATCH
- Hardware stores, printer rental, office equipment = NOT_A_MATCH
- Rewards/loyalty platforms = NOT_A_MATCH
- E-commerce product RESELLERS (selling products, not providing services) = NOT_A_MATCH
- DOOH / billboard inventory = NOT_A_MATCH

FAKE/JUNK:
- Template/placeholder site, no real content = NOT_A_MATCH
- Aggregator, directory, job board, news, blog, parked domain = NOT_A_MATCH

=== IF NOT EXCLUDED — assign segment ===

DIGITAL_AGENCY, CREATIVE_STUDIO, SOFTWARE_HOUSE, IT_SERVICES, MARKETING_AGENCY,
TECH_STARTUP, MEDIA_PRODUCTION, GAME_STUDIO, CONSULTING_FIRM, ECOMMERCE_COMPANY

=== OUTPUT (valid JSON) ===

{"segment": "CAPS_LOCKED or NOT_A_MATCH", "is_target": true/false, "reasoning": "Company does [what]. Matches [segment] because [why they hire freelancers].", "company_info": {"name": "from website", "description": "what they do", "location": "if found"}}

CRITICAL: When in doubt -> NOT_A_MATCH. False positives cost real money.
"""


async def main():
    from app.db import async_session_maker, init_db
    from app.services.gathering_service import gathering_service
    from app.models.gathering import GatheringRun
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select, func, not_

    await init_db()

    # Wait for scraping
    while True:
        async with async_session_maker() as s:
            unscraped = await s.execute(
                select(func.count(DiscoveredCompany.id)).where(
                    DiscoveredCompany.project_id == 9,
                    DiscoveredCompany.first_found_by >= 75,
                    DiscoveredCompany.scraped_text.is_(None),
                    DiscoveredCompany.status != DiscoveredCompanyStatus.REJECTED,
                    not_(DiscoveredCompany.domain.like('%_apollo_%')),
                    DiscoveredCompany.domain.isnot(None),
                )
            )
            remaining = unscraped.scalar()
            if remaining == 0:
                break
            print(f"Waiting for scraping... {remaining} remaining")
        await asyncio.sleep(30)

    print("Scraping done. Starting GPT-4o-mini analysis...")

    for run_id in [75, 76, 77, 78, 79, 80]:
        async with async_session_maker() as s:
            run = await s.get(GatheringRun, run_id)
            if not run:
                continue
            city = run.notes.split(':')[0] if run.notes else f'Run {run_id}'

            if run.current_phase == 'gathered':
                run.current_phase = 'scraped'
                await s.commit()

            print(f"\n=== {city} (run #{run_id}) ===")
            try:
                result = await gathering_service.run_analysis(
                    s, run_id, model="gpt-4o-mini", prompt_text=PROMPT,
                    prompt_name="EasyStaff Global Via Negativa v7 (no city filter)"
                )
                print(f"  Analyzed: {result.get('total_analyzed', 0)}")
                print(f"  Targets: {result.get('targets_found', 0)}")
                print(f"  Skipped: {result.get('skipped_no_scraped_text', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
