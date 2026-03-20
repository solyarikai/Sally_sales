#!/usr/bin/env python3
"""Batch analyze all scraped EasyStaff Global companies via gathering pipeline."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT = """EasyStaff Global: international freelancer/contractor payment platform.

We are looking for companies in UAE (Dubai, Abu Dhabi, Sharjah) that:
1. Are digital agencies, tech companies, IT services, marketing agencies, software houses, creative studios
2. Have 5-200 employees
3. Likely hire freelancers or remote contractors
4. Are NOT staffing agencies, recruitment firms, or outsourcing providers (those are competitors)

GOOD: Digital agency with 20 employees doing web development (likely has freelancers)
GOOD: SaaS startup with 15 people (likely has remote contractors)
GOOD: Marketing agency with 30 employees (likely outsources to freelancers)
BAD: Staffing agency (competitor)
BAD: Construction company (no freelancers)
BAD: Restaurant, hotel, retail store (offline business)
BAD: Government entity"""


async def main():
    from app.db import async_session_maker, init_db
    from app.services.gathering_service import gathering_service

    await init_db()

    for run_id in [1, 3, 4, 5]:  # Skip run 2 (no real domains)
        print(f"=== Analyzing Run #{run_id} ===")
        async with async_session_maker() as s:
            try:
                result = await gathering_service.run_analysis(
                    s, run_id, model="gpt-4o-mini", prompt_text=PROMPT,
                    prompt_name="EasyStaff UAE Digital Agencies ICP v1"
                )
                print(f"  Analyzed: {result.get('total_analyzed', 0)}")
                print(f"  Targets: {result.get('targets_found', 0)}")
                print(f"  Rejected: {result.get('rejected', 0)}")
                print(f"  Skipped (no text): {result.get('skipped_no_scraped_text', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
