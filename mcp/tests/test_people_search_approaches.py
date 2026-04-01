"""Test people search approaches — seniorities vs titles vs combined.
Uses FREE /mixed_people/api_search (no credits needed).
Dumps full raw Apollo responses to file.

Run: docker exec mcp-backend python /app/test_people_search_approaches.py
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
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Test companies (known targets from Fashion Italy)
TEST_DOMAINS = ["versace.com", "etro.com", "dondup.com", "gcds.com", "casadei.com"]

# Default C-level seniorities
DEFAULT_SENIORITIES = ["owner", "founder", "c_suite", "vp", "head", "director"]

# TFP-specific titles (from offer analysis)
TFP_TITLES = ["CEO", "CMO", "Head of E-commerce", "VP Retail", "Director of Digital", "Chief Digital Officer"]


async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        key = decrypt_value(row.api_key_encrypted).strip()

    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_people/api_search"

    all_results = {}

    for domain in TEST_DOMAINS:
        print(f"\n{'='*60}")
        print(f"COMPANY: {domain}")
        print(f"{'='*60}")

        company_results = {}

        # Approach A: seniorities only (default C-level)
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(url, headers=hdr, json={
                "q_organization_domains": domain,
                "person_seniorities": DEFAULT_SENIORITIES,
                "per_page": 20,
            })
            d = resp.json()
            people_a = d.get("people", [])
            print(f"\n  A: SENIORITIES ONLY ({DEFAULT_SENIORITIES})")
            print(f"    Found: {len(people_a)}")
            with_email = [p for p in people_a if p.get("has_email")]
            print(f"    With email: {len(with_email)}")
            for p in people_a[:5]:
                print(f"    - {p.get('first_name','')} {p.get('last_name','')} | {p.get('title','?')} | email={p.get('has_email')}")
            company_results["A_seniorities"] = {"count": len(people_a), "with_email": len(with_email),
                                                 "raw": people_a[:5]}

        await asyncio.sleep(0.5)

        # Approach B: person_titles only (offer-specific)
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(url, headers=hdr, json={
                "q_organization_domains": domain,
                "person_titles": TFP_TITLES,
                "per_page": 20,
            })
            d = resp.json()
            people_b = d.get("people", [])
            print(f"\n  B: TITLES ONLY ({TFP_TITLES[:3]}...)")
            print(f"    Found: {len(people_b)}")
            with_email = [p for p in people_b if p.get("has_email")]
            print(f"    With email: {len(with_email)}")
            for p in people_b[:5]:
                print(f"    - {p.get('first_name','')} {p.get('last_name','')} | {p.get('title','?')} | email={p.get('has_email')}")
            company_results["B_titles"] = {"count": len(people_b), "with_email": len(with_email),
                                           "raw": people_b[:5]}

        await asyncio.sleep(0.5)

        # Approach C: seniorities + titles combined (AND?)
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(url, headers=hdr, json={
                "q_organization_domains": domain,
                "person_seniorities": DEFAULT_SENIORITIES,
                "person_titles": TFP_TITLES,
                "per_page": 20,
            })
            d = resp.json()
            people_c = d.get("people", [])
            print(f"\n  C: SENIORITIES + TITLES COMBINED")
            print(f"    Found: {len(people_c)}")
            with_email = [p for p in people_c if p.get("has_email")]
            print(f"    With email: {len(with_email)}")
            for p in people_c[:5]:
                print(f"    - {p.get('first_name','')} {p.get('last_name','')} | {p.get('title','?')} | email={p.get('has_email')}")
            company_results["C_combined"] = {"count": len(people_c), "with_email": len(with_email),
                                             "raw": people_c[:5]}

        await asyncio.sleep(0.5)

        # Approach D: NO filters (just domain, get everyone)
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(url, headers=hdr, json={
                "q_organization_domains": domain,
                "per_page": 20,
            })
            d = resp.json()
            people_d = d.get("people", [])
            print(f"\n  D: NO FILTERS (all people)")
            print(f"    Found: {len(people_d)}")
            with_email = [p for p in people_d if p.get("has_email")]
            print(f"    With email: {len(with_email)}")
            for p in people_d[:5]:
                print(f"    - {p.get('first_name','')} {p.get('last_name','')} | {p.get('title','?')} | email={p.get('has_email')}")
            company_results["D_no_filter"] = {"count": len(people_d), "with_email": len(with_email),
                                              "raw": people_d[:5]}

        all_results[domain] = company_results

    # Save FULL raw response for first company
    print(f"\n\n{'='*60}")
    print("FULL RAW APOLLO RESPONSE — first person from versace.com approach A")
    print(f"{'='*60}")
    if all_results.get("versace.com", {}).get("A_seniorities", {}).get("raw"):
        print(json.dumps(all_results["versace.com"]["A_seniorities"]["raw"][0], indent=2))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Domain':<20} {'A:Senior':>10} {'B:Title':>10} {'C:Both':>10} {'D:None':>10}")
    print("-" * 65)
    for domain, res in all_results.items():
        a = res.get("A_seniorities", {}).get("with_email", 0)
        b = res.get("B_titles", {}).get("with_email", 0)
        c = res.get("C_combined", {}).get("with_email", 0)
        d = res.get("D_no_filter", {}).get("with_email", 0)
        print(f"{domain:<20} {a:>10} {b:>10} {c:>10} {d:>10}")

    # Save all
    outfile = f"{TMP}/people_approaches_{TIMESTAMP}.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved: {outfile}")

asyncio.run(main())
