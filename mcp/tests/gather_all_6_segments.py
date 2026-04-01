"""Gather 5 pages for all 6 segments using industry_first approach.
Stores results + extends industry map from any new industries found.
Run: docker exec mcp-backend python /app/gather_all_6_segments.py
"""
import asyncio, httpx, sys, json, time, os
from datetime import datetime
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select, text

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TMP = "/app/tests/tmp"
os.makedirs(TMP, exist_ok=True)

SEGMENTS = [
    {
        "id": "tfp_fashion_italy",
        "query": "Fashion brands in Italy",
        "offer": "Branded resale platform for fashion brands",
        "location": ["Italy"],
        "size": ["11,50", "51,200"],
        "industry_tag_ids": ["5567cd82736964540d0b0000", "5567cda97369644cfd3e0000"],
        "keywords_fallback": ["fashion design", "fashion brand", "italian fashion"],
    },
    {
        "id": "es_it_miami",
        "query": "IT consulting companies in Miami",
        "offer": "Payroll for companies hiring internationally",
        "location": ["Miami, Florida, United States"],
        "size": ["11,50", "51,200"],
        "industry_tag_ids": ["5567cd4773696439b10b0000", "5567cdd47369643dbf260000"],
        "keywords_fallback": ["IT consulting", "software development", "managed IT services"],
    },
    {
        "id": "es_video_london",
        "query": "Video production companies in London",
        "offer": "Payroll for companies hiring internationally",
        "location": ["London, England, United Kingdom"],
        "size": ["11,50", "51,200"],
        "industry_tag_ids": ["5567cd467369644d39040000", "5567e0ea7369640d2ba31600"],
        "keywords_fallback": ["video production", "film production", "content creation"],
    },
    {
        "id": "es_it_us",
        "query": "IT consulting companies in US",
        "offer": "Payroll for companies hiring internationally",
        "location": ["United States"],
        "size": ["11,50", "51,200"],
        "industry_tag_ids": ["5567cd4773696439b10b0000", "5567cdd47369643dbf260000"],
        "keywords_fallback": ["IT consulting", "software development"],
    },
    {
        "id": "es_video_uk",
        "query": "Video production companies in UK",
        "offer": "Payroll for companies hiring internationally",
        "location": ["United Kingdom"],
        "size": ["11,50", "51,200"],
        "industry_tag_ids": ["5567cd467369644d39040000", "5567e0ea7369640d2ba31600"],
        "keywords_fallback": ["video production", "film production"],
    },
    {
        "id": "onsocial_uk",
        "query": "Social media influencer agencies in UK",
        "offer": "AI social media management platform",
        "location": ["United Kingdom"],
        "size": ["1,10", "11,50", "51,200"],
        "industry_tag_ids": ["5567cd467369644d39040000", "5567ce5973696453d9780000"],
        "keywords_fallback": ["influencer marketing", "social media agency"],
    },
]


async def get_key(user_id=181):
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == user_id))
        row = r.scalar_one_or_none()
        return decrypt_value(row.api_key_encrypted).strip() if row else None


async def search_pages(key, params, pages=5):
    """Search N pages, return unique companies + extend industry map."""
    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_companies/search"
    all_orgs = []
    domains = set()
    page_counts = []
    new_industries = {}
    t0 = time.time()

    for page in range(1, pages + 1):
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=hdr, json={**params, "page": page, "per_page": 100})
            d = resp.json()
            orgs = d.get("organizations", []) or d.get("accounts", [])
            total = d.get("pagination", {}).get("total_entries", 0)
            for o in orgs:
                dom = o.get("primary_domain") or (o.get("website_url") or "").replace("https://","").replace("http://","").split("/")[0]
                if dom and dom not in domains:
                    domains.add(dom)
                    all_orgs.append({
                        "name": o.get("name", "?"),
                        "domain": dom,
                        "industry": o.get("industry"),
                        "industry_tag_id": o.get("industry_tag_id"),
                        "employees": o.get("estimated_num_employees"),
                        "description": (o.get("short_description") or "")[:100],
                    })
                    # Track new industries for map extension
                    itid = o.get("industry_tag_id")
                    iname = o.get("industry")
                    if itid and iname and itid not in new_industries:
                        new_industries[itid] = {"name": iname, "domain": dom}
            page_counts.append(len(orgs))
        await asyncio.sleep(0.35)

    elapsed = time.time() - t0

    # Extend industry map with any new discoveries
    if new_industries:
        try:
            async with async_session_maker() as s:
                for tid, info in new_industries.items():
                    await s.execute(text(
                        "INSERT INTO apollo_industry_map (tag_id, industry_name, sample_domain) "
                        "VALUES (:tid, :name, :domain) "
                        "ON CONFLICT (tag_id) DO UPDATE SET updated_at = now()"
                    ), {"tid": tid, "name": info["name"], "domain": info["domain"]})
                await s.commit()
                # Check how many are new
                count = await s.execute(text("SELECT count(*) FROM apollo_industry_map"))
                total_map = count.scalar()
                print(f"    Industry map: {len(new_industries)} checked, total in DB: {total_map}")
        except Exception as e:
            print(f"    Industry map extend error: {e}")

    return {
        "companies": all_orgs,
        "unique": len(all_orgs),
        "pages": page_counts,
        "credits": pages,
        "seconds": round(elapsed, 1),
        "apollo_total": total,
        "new_industries": {k: v["name"] for k, v in new_industries.items()},
    }


async def main():
    key = await get_key()
    if not key:
        print("No key"); return

    print(f"{'='*70}")
    print(f"ALL 6 SEGMENTS — INDUSTRY_FIRST — {TIMESTAMP}")
    print(f"{'='*70}")

    all_results = {}

    for seg in SEGMENTS:
        print(f"\n--- {seg['id']}: {seg['query']} ---")

        # Primary: industry_tag_ids
        print(f"  Industry search (primary)...")
        r_ind = await search_pages(key, {
            "organization_industry_tag_ids": seg["industry_tag_ids"],
            "organization_locations": seg["location"],
            "organization_num_employees_ranges": seg["size"],
        }, pages=5)
        print(f"    → {r_ind['unique']} unique, pages={r_ind['pages']}, {r_ind['seconds']}s, {r_ind['credits']} credits")

        # For comparison: keywords only
        print(f"  Keywords search (fallback)...")
        r_kw = await search_pages(key, {
            "q_organization_keyword_tags": seg["keywords_fallback"],
            "organization_locations": seg["location"],
            "organization_num_employees_ranges": seg["size"],
        }, pages=5)
        print(f"    → {r_kw['unique']} unique, pages={r_kw['pages']}, {r_kw['seconds']}s, {r_kw['credits']} credits")

        all_results[seg["id"]] = {
            "industry": {"unique": r_ind["unique"], "credits": r_ind["credits"], "seconds": r_ind["seconds"], "pages": r_ind["pages"], "apollo_total": r_ind["apollo_total"]},
            "keywords": {"unique": r_kw["unique"], "credits": r_kw["credits"], "seconds": r_kw["seconds"], "pages": r_kw["pages"], "apollo_total": r_kw["apollo_total"]},
            "samples_industry": [c["name"] for c in r_ind["companies"][:10]],
            "samples_keywords": [c["name"] for c in r_kw["companies"][:10]],
        }

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Segment':<25} {'Ind.Uniq':>9} {'Kw.Uniq':>9} {'Ind.Total':>10} {'Kw.Total':>10}")
    print("-" * 70)
    for sid, r in all_results.items():
        print(f"{sid:<25} {r['industry']['unique']:>9} {r['keywords']['unique']:>9} {r['industry']['apollo_total']:>10} {r['keywords']['apollo_total']:>10}")

    # Save
    outfile = f"{TMP}/all_segments_{TIMESTAMP}.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved: {outfile}")

asyncio.run(main())
