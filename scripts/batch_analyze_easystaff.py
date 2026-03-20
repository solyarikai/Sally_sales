#!/usr/bin/env python3
"""Batch analyze EasyStaff Global companies — via negativa approach with CAPS_LOCKED segments."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

# Via negativa prompt — focus on EXCLUDING shit, not complex scoring
PROMPT_V2 = """Analyze this company website. Your PRIMARY job is to EXCLUDE companies that are NOT potential customers for an international freelancer payment platform.

=== EXCLUSION RULES (via negativa) — if ANY match, output NOT_A_MATCH ===

COMPETITORS (they sell what we sell):
- Staffing/recruitment agencies, headhunting firms
- Nearshoring/offshoring providers (Toptal, BairesDev, Andela, Turing)
- EOR/PEO platforms (Deel, Remote.com, Oyster, Papaya Global)
- Freelance marketplaces (Fiverr, Upwork)
- HR tech, payroll providers, workforce management tools
- Any company whose PRODUCT is "hire people" or "find talent" or "staff augmentation"

OFFLINE/IRRELEVANT:
- Restaurant, cafe, hotel, salon, spa, gym, construction, real estate
- Trading, import/export, retail store, wholesale, logistics, shipping
- Oil, gas, mining, metals, manufacturing plant
- Medical, hospital, clinic, pharmacy, dental
- School, university, nursery, government, ministry
- Bank, insurance, law firm, accounting firm (unless tech-focused)
- Car dealer, garage, furniture, textile, jewelry, travel agency

JUNK:
- Aggregator, directory, listing site, job board, classifieds
- News site, blog, forum, domain parked, under construction

=== IF NOT EXCLUDED — assign a segment ===

Pick the BEST matching segment (CAPS_LOCKED constant):
- DIGITAL_AGENCY — web dev, digital marketing, SEO, PPC, performance marketing
- CREATIVE_STUDIO — design, branding, video, photography, visual identity
- SOFTWARE_HOUSE — custom software development, app development
- IT_SERVICES — managed IT, cloud, DevOps, infrastructure, cybersecurity
- MARKETING_AGENCY — advertising, PR, social media management, content marketing
- TECH_STARTUP — SaaS product company, fintech, edtech, healthtech, proptech
- MEDIA_PRODUCTION — video, animation, audio, broadcasting, content creation
- GAME_STUDIO — game development, interactive media, VR/AR
- CONSULTING_FIRM — management consulting, strategy, digital transformation
- ECOMMERCE_COMPANY — online retail, D2C brand with tech/marketing team

Or propose a NEW segment if none fit (same CAPS_LOCKED format).

=== OUTPUT FORMAT (valid JSON) ===

{
  "segment": "CAPS_LOCKED_SEGMENT or NOT_A_MATCH",
  "is_target": true/false,
  "reasoning": "1-2 sentences: what the company does and why this segment (or why excluded)",
  "company_info": {"name": "from website", "description": "what they do", "location": "if found"}
}

IMPORTANT:
- When in doubt → NOT_A_MATCH. False positives are worse than false negatives.
- "name" = company name from THE WEBSITE, not from the search query.
- is_target = true ONLY if segment is NOT "NOT_A_MATCH"
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
                    print(f"  Not found, skipping")
                    continue

                # If at CP2, use re_analyze to reset and re-run with new prompt
                if run.current_phase == "awaiting_targets_ok":
                    print(f"  Re-analyzing (was at CP2, resetting to scraped)...")
                    result = await gathering_service.re_analyze(
                        s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V2,
                        prompt_name="EasyStaff UAE Via Negativa v2"
                    )
                elif run.current_phase == "scraped":
                    print(f"  Analyzing (first run)...")
                    result = await gathering_service.run_analysis(
                        s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V2,
                        prompt_name="EasyStaff UAE Via Negativa v2"
                    )
                else:
                    print(f"  Phase={run.current_phase}, skipping")
                    continue

                print(f"  Analyzed: {result.get('total_analyzed', 0)}")
                print(f"  Targets: {result.get('targets_found', 0)}")
                print(f"  Rejected: {result.get('rejected', 0)}")
                print(f"  Skipped: {result.get('skipped_no_scraped_text', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
