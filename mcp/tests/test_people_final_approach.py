"""Final people extraction test — seniorities + titles as TWO parallel searches.
Tests the actual production approach on 5 companies.
Dumps raw Apollo responses to files.
Writes all reasoning to PEOPLE_APPROACH_REASONING.md.

Run: docker exec mcp-backend python /app/test_people_final_approach.py
"""
import asyncio, httpx, sys, json, os
from datetime import datetime
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select

TMP = "/app/tests/tmp"
os.makedirs(TMP, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

TEST_DOMAINS = ["versace.com", "etro.com", "dondup.com", "gcds.com", "casadei.com"]
DEFAULT_SENIORITIES = ["owner", "founder", "c_suite", "vp", "head", "director"]
TFP_TITLES = ["CEO", "CMO", "Head of E-commerce", "VP Retail", "Director of Digital", "Chief Digital Officer"]


async def search_people(key, domain, params_extra, label):
    """Call mixed_people/api_search with extra params. Returns raw response."""
    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    base = {"q_organization_domains": domain, "page": 1, "per_page": 25}
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.post("https://api.apollo.io/api/v1/mixed_people/api_search",
                            headers=hdr, json={**base, **params_extra})
        return resp.json()


async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        key = decrypt_value(row.api_key_encrypted).strip()

    all_results = {}
    raw_responses = {}

    for domain in TEST_DOMAINS:
        print(f"\n{'='*60}")
        print(f"{domain}")
        print(f"{'='*60}")

        # Search A: Seniorities (default C-level)
        raw_a = await search_people(key, domain, {"person_seniorities": DEFAULT_SENIORITIES}, "seniorities")
        people_a = raw_a.get("people", [])
        await asyncio.sleep(0.3)

        # Search B: Offer-specific titles
        raw_b = await search_people(key, domain, {"person_titles": TFP_TITLES}, "titles")
        people_b = raw_b.get("people", [])
        await asyncio.sleep(0.3)

        # Save full raw response for first company
        if domain == "versace.com":
            raw_responses["search_A_seniorities"] = raw_a
            raw_responses["search_B_titles"] = raw_b

        # Merge + dedup
        seen = set()
        merged = []
        for p in people_a + people_b:
            pid = p.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                merged.append(p)

        # Filter has_email=true
        with_email = [p for p in merged if p.get("has_email")]

        # Prioritize by title match
        title_lower = [t.lower() for t in TFP_TITLES]
        preferred = []
        others = []
        for p in with_email:
            ptitle = (p.get("title") or "").lower()
            if any(t in ptitle for t in title_lower):
                preferred.append(p)
            else:
                others.append(p)
        final = (preferred + others)[:3]

        print(f"  Search A (seniorities): {len(people_a)} total, {sum(1 for p in people_a if p.get('has_email'))} with email")
        print(f"  Search B (titles):      {len(people_b)} total, {sum(1 for p in people_b if p.get('has_email'))} with email")
        print(f"  Merged + dedup:         {len(merged)} unique, {len(with_email)} with email")
        print(f"  Preferred (title match): {len(preferred)}")
        print(f"  Final top 3:")
        for p in final:
            matched = "★" if any(t in (p.get("title") or "").lower() for t in title_lower) else " "
            print(f"    {matched} {p.get('first_name','')} {p.get('last_name_obfuscated','')} | {p.get('title','?')} | email={p.get('has_email')}")

        # Also show what seniorities search returned (actual titles)
        print(f"  All from seniorities search:")
        for p in people_a[:8]:
            print(f"    {p.get('first_name','')} | {p.get('title','?')} | email={p.get('has_email')}")

        all_results[domain] = {
            "seniorities_count": len(people_a),
            "seniorities_with_email": sum(1 for p in people_a if p.get("has_email")),
            "titles_count": len(people_b),
            "titles_with_email": sum(1 for p in people_b if p.get("has_email")),
            "merged_unique": len(merged),
            "merged_with_email": len(with_email),
            "preferred_count": len(preferred),
            "final_3": [{"name": f"{p.get('first_name','')} {p.get('last_name_obfuscated','')}", "title": p.get("title"), "has_email": p.get("has_email")} for p in final],
            "all_seniority_titles": [p.get("title") for p in people_a],
        }

    # Save raw Apollo responses
    raw_file = f"{TMP}/apollo_raw_people_{TS}.json"
    with open(raw_file, "w") as f:
        json.dump(raw_responses, f, indent=2)
    print(f"\nRaw Apollo responses saved: {raw_file}")

    # Save all results
    results_file = f"{TMP}/people_final_approach_{TS}.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Results saved: {results_file}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY — Seniorities + Titles (two parallel FREE searches)")
    print(f"{'='*60}")
    print(f"{'Domain':<20} {'A:Sen':>6} {'B:Tit':>6} {'Merge':>6} {'Email':>6} {'Pref':>6}")
    for d, r in all_results.items():
        print(f"{d:<20} {r['seniorities_count']:>6} {r['titles_count']:>6} {r['merged_unique']:>6} {r['merged_with_email']:>6} {r['preferred_count']:>6}")

asyncio.run(main())
