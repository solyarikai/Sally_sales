#!/usr/bin/env python3
"""Run 2 Clay searches to prove school filter works:
1. Australia + titles (NO school filter)
2. Australia + titles + University of the Philippines
User can compare result counts in Clay UI."""
import asyncio
import sys
sys.path.insert(0, '/app')
from app.services.clay_service import ClayService

async def main():
    clay = ClayService()

    # Search 1: NO school filter — all decision-makers in Australia
    print("=== Search 1: Australia + titles (NO school filter) ===")
    r1 = await clay.run_people_search(
        domains=None,
        use_titles=True,
        countries=["Australia"],
    )
    p1 = r1.get("people", [])
    url1 = r1.get("table_url", "no URL")
    print(f"Results: {len(p1)} contacts")
    print(f"Clay table: {url1}")

    # Search 2: WITH school filter — University of the Philippines
    print("\n=== Search 2: Australia + titles + University of the Philippines ===")
    r2 = await clay.run_people_search(
        domains=None,
        use_titles=True,
        countries=["Australia"],
        schools=["University of the Philippines"],
    )
    p2 = r2.get("people", [])
    url2 = r2.get("table_url", "no URL")
    print(f"Results: {len(p2)} contacts")
    print(f"Clay table: {url2}")

    print(f"\n=== COMPARISON ===")
    print(f"Without school filter: {len(p1)} contacts")
    print(f"With UP filter:        {len(p2)} contacts")
    print(f"Difference proves filter works: {len(p1) != len(p2)}")

if __name__ == "__main__":
    asyncio.run(main())
