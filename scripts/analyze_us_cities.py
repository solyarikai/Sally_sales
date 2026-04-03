#!/usr/bin/env python3
"""Analyze NYC + LA companies with US-adapted V6 prompt."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT_US = """Analyze this company website for an international freelancer payment platform.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

GEOGRAPHY: Company must be based in the United States (New York, Los Angeles, or other US city).
If website shows a non-US location with no US address, output NOT_A_MATCH.

SOLO/TINY: Only ONE person on website = NOT_A_MATCH. Need companies with teams (3+ people).
"Fractional CxO", personal brand, solo advisor = NOT_A_MATCH.

COMPETITORS: Staffing, recruitment, headhunting, outsourcing, EOR/PEO, freelance marketplace, HR tech = NOT_A_MATCH.
"Staff augmentation", "talent acquisition" = NOT_A_MATCH.

INTERIOR DESIGN / ARCHITECTURE: Interior design, architecture, fit-out = NOT_A_MATCH.

COMPANY FORMATION: Business setup, visa, legal = NOT_A_MATCH.

INVESTMENT: VC, PE, holding, M&A advisory, fund management = NOT_A_MATCH.

GOVERNMENT: Government entities, 1000+ employees = NOT_A_MATCH.

OFFLINE: Restaurant, hotel, construction, real estate, retail, medical, school, bank, oil/gas = NOT_A_MATCH.

JUNK: Aggregator, directory, job board, news, blog, parked domain, template site = NOT_A_MATCH.

=== IF NOT EXCLUDED — assign segment ===

CAPS_LOCKED:
- DIGITAL_AGENCY — web dev, digital marketing, SEO, PPC
- CREATIVE_STUDIO — design, branding, video, photography
- SOFTWARE_HOUSE — custom software, app development
- IT_SERVICES — managed IT, cloud, DevOps, cybersecurity
- MARKETING_AGENCY — advertising, PR, social media, content
- TECH_STARTUP — SaaS, fintech, edtech, healthtech product company
- MEDIA_PRODUCTION — video, animation, audio, broadcasting
- GAME_STUDIO — game development, VR/AR
- CONSULTING_FIRM — management/strategy consulting (MUST have team, NOT solo)
- ECOMMERCE_COMPANY — online retail with tech/marketing team

=== OUTPUT FORMAT (valid JSON) ===

{
  "segment": "CAPS_LOCKED_SEGMENT or NOT_A_MATCH",
  "is_target": true/false,
  "reasoning": "Company is based in [city, state]. They do [what]. This matches [segment] because [why].",
  "company_info": {"name": "from website", "description": "what they do", "location": "city, state"}
}

When in doubt -> NOT_A_MATCH.
"""


async def main():
    from app.db import async_session_maker, init_db
    from app.services.gathering_service import gathering_service
    from app.models.gathering import GatheringRun
    from sqlalchemy import update

    await init_db()

    for run_id in [56, 63]:
        print(f"=== Run #{run_id} ===")
        async with async_session_maker() as s:
            run = await s.get(GatheringRun, run_id)
            if not run:
                continue
            if run.current_phase == "awaiting_targets_ok":
                result = await gathering_service.re_analyze(
                    s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_US,
                    prompt_name="EasyStaff US Cities v2"
                )
            elif run.current_phase == "scraped":
                result = await gathering_service.run_analysis(
                    s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_US,
                    prompt_name="EasyStaff US Cities v2"
                )
            else:
                print(f"  Phase={run.current_phase}, skipping")
                continue
            print(f"  Analyzed: {result.get('total_analyzed', 0)}")
            print(f"  Targets: {result.get('targets_found', 0)}")
            print(f"  Skipped: {result.get('skipped_no_scraped_text', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
