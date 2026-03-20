#!/usr/bin/env python3
"""EasyStaff Dubai analysis — V5 via negativa with all Opus review fixes."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT_V5 = """Analyze this company website for an international freelancer payment platform targeting UAE-based companies.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

GEOGRAPHY (NOT UAE = reject):
- Company must be BASED IN UAE with CLEAR evidence: Dubai/Abu Dhabi/Sharjah/UAE address on the website
- Non-UAE domains (.in, .ir, .pk, .com.au, .sd, .ch, .ca) WITHOUT explicit UAE address = NOT_A_MATCH
- If website says "India", "Pakistan", "Oman", "Lebanon", "Singapore", "Canada" as location = NOT_A_MATCH
- If you cannot find a CLEAR UAE address or "Dubai/Abu Dhabi/UAE" on the website = NOT_A_MATCH
- Oman is NOT UAE (different country). Lebanon is NOT UAE. Singapore is NOT UAE.

ENTITY TYPE SIGNALS (non-UAE company types = reject):
- "Pvt Ltd", "Private Limited" in company name = Indian/Pakistani entity = NOT_A_MATCH
- "LLP" (Limited Liability Partnership) = likely Indian/UK entity = NOT_A_MATCH unless explicit UAE address
- "Pte Ltd" = Singapore entity = NOT_A_MATCH
- "GmbH" = German/Swiss entity = NOT_A_MATCH unless explicit UAE office
- "Inc" with no UAE address = likely US = NOT_A_MATCH

SOLO/TINY (not a company = reject):
- Only ONE person named/visible on entire website = solo consultant = NOT_A_MATCH
- "Fractional CxO", "Fractional leadership", "Interim CEO/COO/CTO" = IS a freelancer, not a hirer = NOT_A_MATCH
- Personal brand website ("I help CEOs", "Book a call with me") = NOT_A_MATCH
- IFZA/RAKEZ/SHAMS free zone with no team page or employees = likely 1-person setup = NOT_A_MATCH
- Company name IS a person's name (e.g. "John Smith Consulting") = solo = NOT_A_MATCH

INVESTMENT/HOLDING (not freelancer hirers = reject):
- Investment firms, holding companies, venture capital, private equity, angel investors = NOT_A_MATCH
- Venture studios, accelerators, incubators = NOT_A_MATCH
- M&A advisory, capital raising, investment banking = NOT_A_MATCH
- Asset managers, fund managers, family offices = NOT_A_MATCH
- Sovereign wealth funds, government investment vehicles = NOT_A_MATCH

GOVERNMENT/TOO LARGE (reject):
- Government entities, ministries, municipalities = NOT_A_MATCH
- Government subsidiaries (DEWA, Mubadala, ADNOC, etc.) = NOT_A_MATCH
- Companies with 1000+ employees = too large, has internal HR = NOT_A_MATCH

COMPETITORS (they sell what we sell = reject):
- Staffing/recruitment agencies, headhunting, outsourcing providers = NOT_A_MATCH
- EOR/PEO platforms, freelance marketplaces, HR tech = NOT_A_MATCH
- "Staff augmentation", "talent acquisition", "workforce solutions" = NOT_A_MATCH

OFFLINE/IRRELEVANT (reject):
- Restaurant, hotel, construction, real estate, trading, logistics, oil/gas, medical, school
- Bank, insurance, law firm, car dealer, furniture, jewelry, travel agency
- Computer/hardware STORES (selling equipment, not services) = NOT_A_MATCH
- Rewards/loyalty platforms = NOT_A_MATCH
- E-commerce RESELLERS (selling products, not providing agency services) = NOT_A_MATCH

JUNK (reject):
- Aggregator, directory, job board, news, blog, parked domain

=== IF NOT EXCLUDED — assign a segment ===

CAPS_LOCKED segments:
- DIGITAL_AGENCY — web dev, digital marketing, SEO, PPC
- CREATIVE_STUDIO — design, branding, video, photography
- SOFTWARE_HOUSE — custom software, app development
- IT_SERVICES — managed IT, cloud, DevOps, cybersecurity
- MARKETING_AGENCY — advertising, PR, social media, content
- TECH_STARTUP — SaaS, fintech, edtech, healthtech product company
- MEDIA_PRODUCTION — video, animation, audio, broadcasting
- GAME_STUDIO — game development, VR/AR
- CONSULTING_FIRM — management/strategy consulting (MUST have visible TEAM of 3+, NOT solo)
- ECOMMERCE_COMPANY — online retail with tech/marketing team

=== OUTPUT FORMAT (valid JSON) ===

{
  "segment": "CAPS_LOCKED_SEGMENT or NOT_A_MATCH",
  "is_target": true/false,
  "reasoning": "1-2 sentences: company location, what they do, why this segment or why excluded",
  "company_info": {"name": "from website", "description": "what they do", "location": "city, country"}
}

CRITICAL: When in doubt → NOT_A_MATCH. False positives cost real money.
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
                        s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V5,
                        prompt_name="EasyStaff UAE Via Negativa v5"
                    )
                elif run.current_phase == "scraped":
                    print(f"  Analyzing...")
                    result = await gathering_service.run_analysis(
                        s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V5,
                        prompt_name="EasyStaff UAE Via Negativa v5"
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
