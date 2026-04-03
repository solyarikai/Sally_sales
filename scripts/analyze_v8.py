#!/usr/bin/env python3
"""V8 analysis — fixes all 6 GPT suck patterns from Opus review."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT_V8 = """Analyze this company website. Is this a SERVICE BUSINESS that delivers projects using freelancers or remote contractors?

=== WHAT WE'RE LOOKING FOR ===
Companies that DO CLIENT WORK (agencies, studios, consultancies) and likely hire freelancers to deliver it.
NOT product companies. NOT platforms. NOT tools. SERVICE businesses.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

SAAS / PRODUCT COMPANIES (they BUILD a product, not deliver services):
- Company sells a software product, tool, platform, or app = NOT_A_MATCH
- "Sign up", "Start free trial", "Pricing plans", "API documentation" = product company = NOT_A_MATCH
- Cybersecurity TOOLS (scanners, firewalls, email security products) = NOT_A_MATCH
- Chatbot platforms, automation tools, analytics dashboards = NOT_A_MATCH
- Ad networks, push notification platforms, media buying tools = NOT_A_MATCH
- EXCEPTION: if the company ALSO provides consulting/implementation services alongside their product, it's OK

SOLO / ONE PERSON:
- Only ONE person visible on entire website = NOT_A_MATCH
- "Fractional CxO", personal brand, solo advisor, blogger, influencer = NOT_A_MATCH
- Company name IS a person's name = NOT_A_MATCH
- No team page, no "about us" with multiple people = RED FLAG

TEMPLATE / PLACEHOLDER SITES:
- Generic template with stock photos, no real portfolio, no real clients = NOT_A_MATCH
- "Lorem ipsum" or obviously placeholder content = NOT_A_MATCH
- Domain parked, under construction = NOT_A_MATCH

COMPETITORS (they provide WORKERS to other companies):
- Staffing, recruitment, headhunting, outsourcing = NOT_A_MATCH
- "IT staffing", "staff augmentation", "talent acquisition" = NOT_A_MATCH
- EOR/PEO platforms, freelance marketplaces, HR tech = NOT_A_MATCH

GOVERNMENT CONTRACTORS:
- Companies primarily serving government clients = NOT_A_MATCH
- Defense, military, security clearance work = NOT_A_MATCH
- Saudi Vision 2030 megaproject contractors = NOT_A_MATCH
- Government-backed entities, sovereign fund subsidiaries = NOT_A_MATCH

HARDWARE / PHYSICAL:
- IT hardware distributors, network equipment, printers = NOT_A_MATCH
- Construction, real estate, interior design, architecture = NOT_A_MATCH
- Restaurant, hotel, retail, medical, school = NOT_A_MATCH
- Outdoor advertising infrastructure (billboards, DOOH) = NOT_A_MATCH
- Print/publishing companies = NOT_A_MATCH

HOLDING / INVESTMENT:
- VC, PE, holding companies, M&A advisory, accelerators = NOT_A_MATCH

COMPANY FORMATION / LEGAL:
- Business setup, visa, PRO services = NOT_A_MATCH

MARKETPLACE / AGGREGATOR:
- Job boards, directories, listing sites, news sites = NOT_A_MATCH
- White-label reseller platforms = NOT_A_MATCH
- UGC marketplaces = NOT_A_MATCH

=== IF NOT EXCLUDED — this is a service business. Assign segment: ===

DIGITAL_AGENCY — web dev, digital marketing, SEO, PPC, performance marketing
CREATIVE_STUDIO — design, branding, video, photography, visual identity
SOFTWARE_HOUSE — custom software development, app development as a service
IT_SERVICES — managed IT, cloud consulting, DevOps as a service, cybersecurity consulting
MARKETING_AGENCY — advertising, PR, social media management, content marketing
TECH_STARTUP — tech company that provides services (not just a product)
MEDIA_PRODUCTION — video production, animation, audio, broadcasting
GAME_STUDIO — game development as a service, interactive media
CONSULTING_FIRM — management/strategy/digital transformation consulting (with TEAM, not solo)
ECOMMERCE_COMPANY — e-commerce agency services (not product reseller)

=== OUTPUT (valid JSON) ===

{"segment": "CAPS_LOCKED or NOT_A_MATCH", "is_target": true/false, "reasoning": "Does [what] as a service. Likely hires freelancers because [why].", "company_info": {"name": "from website", "description": "what they do", "location": "if found"}}

CRITICAL: When in doubt -> NOT_A_MATCH. A product company is NOT a target even if it's in tech.
"""


async def main():
    from app.db import async_session_maker, init_db
    from app.services.gathering_service import gathering_service
    from app.models.gathering import GatheringRun
    from sqlalchemy import update

    await init_db()

    # Reset all new city runs to scraped for re-analysis
    async with async_session_maker() as s:
        await s.execute(
            update(GatheringRun)
            .where(GatheringRun.id.in_([75, 76, 77, 78, 79, 80]))
            .values(current_phase='scraped')
        )
        from app.models.gathering import ApprovalGate
        await s.execute(
            update(ApprovalGate)
            .where(ApprovalGate.gathering_run_id.in_([75, 76, 77, 78, 79, 80]), ApprovalGate.status == 'pending')
            .values(status='rejected', decision_note='re-analyzing with V8')
        )
        from app.models.gathering import AnalysisRun
        await s.execute(
            update(AnalysisRun)
            .where(AnalysisRun.status == 'running')
            .values(status='failed')
        )
        await s.commit()

    for run_id in [75, 76, 77, 78, 79, 80]:
        async with async_session_maker() as s:
            run = await s.get(GatheringRun, run_id)
            if not run:
                continue
            city = run.notes.split(':')[0] if run.notes else f'Run {run_id}'
            print(f"\n=== V8: {city} (run #{run_id}) ===")
            try:
                result = await gathering_service.re_analyze(
                    s, run_id, model="gpt-4o-mini", prompt_text=PROMPT_V8,
                    prompt_name="EasyStaff Global v8 (service business focus)"
                )
                print(f"  Analyzed: {result.get('total_analyzed', 0)}")
                print(f"  Targets: {result.get('targets_found', 0)}")
                print(f"  Skipped: {result.get('skipped_no_scraped_text', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()

    print("\n=== V8 COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
