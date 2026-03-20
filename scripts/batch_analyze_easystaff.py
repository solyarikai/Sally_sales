#!/usr/bin/env python3
"""EasyStaff Dubai analysis — V3 via negativa with geography + solo consultant filters."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT_V3 = """Analyze this company website for an international freelancer payment platform targeting UAE-based companies.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

GEOGRAPHY (NOT UAE = reject):
- Company must be BASED IN UAE or have a UAE office clearly mentioned on the website
- Non-UAE domains (.in, .ir, .pk, .com.au, .sd) WITHOUT a clear UAE address on the website = NOT_A_MATCH
- Website entirely in a non-English/non-Arabic language with no UAE mentions = NOT_A_MATCH
- If the website says "India", "Pakistan", "Iran" as their location and does NOT mention UAE = NOT_A_MATCH
- If you cannot find a CLEAR UAE address, office, or "Dubai/Abu Dhabi/UAE" mention on the website = NOT_A_MATCH
- "Location not explicitly mentioned" = NOT_A_MATCH (when in doubt about location, reject)

INVESTMENT/HOLDING (not freelancer hirers = reject):
- Investment firms, holding companies, venture capital, private equity = NOT_A_MATCH
- Asset managers, fund managers, family offices = NOT_A_MATCH
- These companies hire bankers, not freelancers

SOLO/TINY (not a company = reject):
- Solo consultant, individual advisor, personal branding website = NOT_A_MATCH
- One person with a personal website offering advisory/coaching = NOT_A_MATCH
- If the website is clearly about ONE person (their photo, "I help CEOs", "Book a call with me") = NOT_A_MATCH
- We need COMPANIES with TEAMS (3+ people), not individuals

COMPETITORS (they sell what we sell = reject):
- Staffing/recruitment agencies, headhunting firms
- Nearshoring/offshoring providers (Toptal, BairesDev, Andela, Turing)
- EOR/PEO platforms (Deel, Remote.com, Oyster, Papaya Global)
- Freelance marketplaces (Fiverr, Upwork)
- HR tech, payroll providers, workforce management tools
- Any company whose PRODUCT is "hire people" or "find talent" or "staff augmentation"

OFFLINE/IRRELEVANT (no freelancers = reject):
- Restaurant, cafe, hotel, salon, spa, gym, construction, real estate
- Trading, import/export, retail store, wholesale, logistics, shipping
- Oil, gas, mining, metals, manufacturing plant
- Medical, hospital, clinic, pharmacy, dental
- School, university, nursery, government, ministry
- Bank, insurance, law firm, accounting firm (unless tech-focused)
- Car dealer, garage, furniture, textile, jewelry, travel agency

JUNK (not a real business site = reject):
- Aggregator, directory, listing site, job board
- News site, blog, forum, domain parked, under construction

=== IF NOT EXCLUDED — assign a segment ===

Pick the BEST matching segment (CAPS_LOCKED):
- DIGITAL_AGENCY — web dev, digital marketing, SEO, PPC, performance marketing
- CREATIVE_STUDIO — design, branding, video, photography, visual identity
- SOFTWARE_HOUSE — custom software development, app development
- IT_SERVICES — managed IT, cloud, DevOps, infrastructure, cybersecurity
- MARKETING_AGENCY — advertising, PR, social media management, content marketing
- TECH_STARTUP — SaaS product, fintech, edtech, healthtech, proptech
- MEDIA_PRODUCTION — video, animation, audio, broadcasting, content creation
- GAME_STUDIO — game development, interactive media, VR/AR
- CONSULTING_FIRM — management consulting, strategy, digital transformation (MUST be a firm with team, NOT solo)
- ECOMMERCE_COMPANY — online retail, D2C brand with tech/marketing team

Or propose a NEW segment (same CAPS_LOCKED format).

=== OUTPUT FORMAT (valid JSON) ===

{
  "segment": "CAPS_LOCKED_SEGMENT or NOT_A_MATCH",
  "is_target": true/false,
  "reasoning": "1-2 sentences: what the company does, WHERE they are based, and why this segment (or why excluded)",
  "company_info": {"name": "from website", "description": "what they do", "location": "city, country"}
}

CRITICAL:
- When in doubt → NOT_A_MATCH. False positives cost real money.
- is_target = true ONLY if segment is NOT "NOT_A_MATCH"
- ALWAYS mention the company's LOCATION in reasoning
- "name" = from THE WEBSITE, not from search query
"""


async def main():
    from app.db import async_session_maker, init_db
    from app.services.gathering_service import gathering_service

    await init_db()

    for run_id in [1, 3, 4, 5]:
        print(f"=== Run #{run_id} ===")
        async with async_session_maker() as s:
            try:
                from app.models.gathering import GatheringRun
                run = await s.get(GatheringRun, run_id)
                if not run:
                    continue

                if run.current_phase == "awaiting_targets_ok":
                    print(f"  Re-analyzing (resetting from CP2)...")
                    result = await gathering_service.re_analyze(
                        s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V3,
                        prompt_name="EasyStaff UAE Via Negativa v4"
                    )
                elif run.current_phase == "scraped":
                    print(f"  Analyzing...")
                    result = await gathering_service.run_analysis(
                        s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V3,
                        prompt_name="EasyStaff UAE Via Negativa v4"
                    )
                else:
                    print(f"  Phase={run.current_phase}, skipping")
                    continue

                print(f"  Analyzed: {result.get('total_analyzed', 0)}")
                print(f"  Targets: {result.get('targets_found', 0)}")
                print(f"  Skipped: {result.get('skipped_no_scraped_text', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
