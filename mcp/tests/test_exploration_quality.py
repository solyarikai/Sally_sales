"""Test exploration phase quality — measures target conversion rate and contact yield.

Goal: For "IT consulting in Miami, 10-200 employees" (EasyStaff offer):
- Find 100+ target contacts (up to 3 per company)
- From NEW companies (not in blacklist)
- Each contact from a REAL target company for EasyStaff payroll

Run:
    cd mcp && python3 tests/test_exploration_quality.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Load mcp/.env
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and len(v) > 3:
                os.environ.setdefault(k, v)

MCP_URL = os.environ.get("MCP_URL", "http://46.62.210.24:8002")

# Keys
APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
APIFY_PROXY = os.environ.get("APIFY_PROXY_PASSWORD", "")


async def test_exploration():
    """Test the full exploration + pipeline for IT consulting in Miami."""
    print("=" * 60)
    print("EXPLORATION QUALITY TEST")
    print("Segment: IT consulting companies in Miami")
    print("Offer: EasyStaff payroll (target: 10-200 employees)")
    print("Goal: 100+ target contacts, up to 3 per company")
    print("=" * 60)

    # Step 1: Infer company size from offer
    print("\n--- Step 1: Infer target company size from offer ---")
    start = time.time()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": """EasyStaff is a global platform for payroll, freelance connections, and invoice management.
They help companies hire and pay contractors worldwide.

What size companies would buy this? Return JSON: {"min": N, "max": N, "apollo_range": "N,N", "reasoning": "..."}"""}],
                "max_tokens": 150,
                "temperature": 0,
            },
        )
        data = resp.json()
        size_result = data["choices"][0]["message"]["content"]
        print(f"  Size inference: {size_result}")
        print(f"  Time: {time.time() - start:.1f}s")

    # Step 2: Initial Apollo search (1 credit)
    print("\n--- Step 2: Initial Apollo search (1 credit) ---")
    start = time.time()

    initial_filters = {
        "q_organization_keyword_tags": ["IT consulting", "technology consulting", "IT services"],
        "organization_locations": ["Miami, Florida, United States"],
        "organization_num_employees_ranges": ["11,50", "51,200"],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_companies/search", headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
            json={"per_page": 25, "page": 1, **initial_filters},
        )
        search_data = resp.json()
        companies = search_data.get("accounts") or search_data.get("organizations") or []

    print(f"  Companies found: {len(companies)}")
    print(f"  Time: {time.time() - start:.1f}s")
    print(f"  Credits used: 1")

    if not companies:
        print("  ERROR: No companies found!")
        return

    for c in companies[:5]:
        print(f"    - {c.get('name', '?')} ({c.get('primary_domain', '?')}) — {c.get('estimated_num_employees', '?')} emp")

    # Step 3: Scrape top company websites (free)
    print(f"\n--- Step 3: Scrape top {min(15, len(companies))} websites (free) ---")
    start = time.time()
    scraped = []

    for c in companies[:15]:
        domain = c.get("primary_domain") or c.get("domain", "")
        if not domain:
            continue
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                resp = await client.get(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    import re
                    text = re.sub(r"<[^>]+>", " ", resp.text[:5000])
                    text = re.sub(r"\s+", " ", text).strip()[:2000]
                    scraped.append({**c, "website_text": text})
        except:
            pass

    print(f"  Scraped: {len(scraped)}/{min(15, len(companies))}")
    print(f"  Time: {time.time() - start:.1f}s")

    # Step 4: GPT classifies targets (free)
    print("\n--- Step 4: GPT-4o-mini classifies targets ---")
    start = time.time()

    classify_prompt = """Classify these companies as TARGET or NOT for this query:
"IT consulting companies in Miami, 10-200 employees"
Our offer: EasyStaff — payroll and contractor management platform.

TARGET = IT consulting firm, staffing agency, technology services company that would benefit from contractor payroll.
NOT = competitor (payroll/HR platform), SaaS product company, non-IT company, wrong size.

For each company, return JSON array:
[{"domain": "...", "is_target": true/false, "confidence": 0.0-1.0, "reasoning": "1 sentence"}]

Companies:
"""
    for c in scraped:
        classify_prompt += f"- {c.get('name', '?')} ({c.get('primary_domain', '?')}): {c.get('website_text', '')[:150]}\n"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": classify_prompt}],
                  "max_tokens": 2000, "temperature": 0},
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        clean = content.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        classifications = json.loads(clean)

    targets = [c for c in classifications if c.get("is_target") and c.get("confidence", 0) >= 0.6]
    non_targets = [c for c in classifications if not c.get("is_target")]

    print(f"  Targets: {len(targets)}/{len(classifications)}")
    print(f"  Conversion rate: {len(targets)/len(classifications)*100:.0f}%")
    print(f"  Time: {time.time() - start:.1f}s")
    for t in targets:
        print(f"    ✓ {t['domain']} ({t['confidence']:.0%}): {t['reasoning']}")
    for n in non_targets[:3]:
        print(f"    ✗ {n['domain']}: {n.get('reasoning', '?')}")

    # Step 5: Enrich top 5 targets (5 credits)
    print(f"\n--- Step 5: Enrich top {min(5, len(targets))} targets (5 credits max) ---")
    start = time.time()
    enriched = []

    for t in targets[:5]:
        domain = t.get("domain", "")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.apollo.io/api/v1/organizations/enrich", headers={"X-Api-Key": APOLLO_KEY},
                    params={"domain": domain},
                )
                org = resp.json().get("organization", {})
                if org:
                    enriched.append({"domain": domain, "org": org})
                    kw = org.get("keywords") or org.get("keyword_tags") or []
                    if isinstance(kw, str):
                        kw = kw.split(",")[:10]
                    print(f"  ✓ {domain}: industry={org.get('industry')}, keywords={kw[:5]}")
        except Exception as e:
            print(f"  ✗ {domain}: {e}")

    print(f"  Enriched: {len(enriched)}")
    print(f"  Credits used: {len(enriched)}")
    print(f"  Time: {time.time() - start:.1f}s")

    # Step 6: Extract common labels
    print("\n--- Step 6: Extract common labels ---")
    from collections import Counter
    kw_counter = Counter()
    ind_counter = Counter()

    for e in enriched:
        org = e["org"]
        ind = org.get("industry")
        if ind:
            ind_counter[ind] += 1
        kw = org.get("keywords") or org.get("keyword_tags") or []
        if isinstance(kw, str):
            kw = [k.strip() for k in kw.split(",")]
        for k in kw:
            if k and len(k) > 2:
                kw_counter[k.lower()] += 1

    common_kw = [k for k, v in kw_counter.most_common(15) if v >= 2]
    common_ind = [k for k, v in ind_counter.most_common(5) if v >= 2]

    print(f"  Common industries: {common_ind}")
    print(f"  Common keywords: {common_kw}")

    # Step 7: Build optimized filters
    print("\n--- Step 7: Optimized filters ---")
    optimized = dict(initial_filters)
    existing_kw = set(optimized.get("q_organization_keyword_tags", []))
    new_kw = [k for k in common_kw if k not in existing_kw][:5]
    if new_kw:
        optimized["q_organization_keyword_tags"] = list(existing_kw) + new_kw
    print(f"  Original keywords: {initial_filters.get('q_organization_keyword_tags')}")
    print(f"  Added keywords: {new_kw}")
    print(f"  Full optimized: {json.dumps(optimized, indent=2)}")

    # Step 8: Full search with optimized filters (estimate)
    print("\n--- Step 8: Full search with optimized filters ---")
    start = time.time()

    # Search 4 pages to get ~100 companies
    all_companies = []
    for page in range(1, 5):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.apollo.io/api/v1/mixed_companies/search", headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
                json={"per_page": 25, "page": page, **optimized},
            )
            data = resp.json()
            page_companies = data.get("accounts") or data.get("organizations") or []
            all_companies.extend(page_companies)
            total_available = data.get("pagination", {}).get("total_entries", 0)
            if not page_companies:
                break

    print(f"  Companies gathered: {len(all_companies)}")
    print(f"  Total available in Apollo: {total_available}")
    print(f"  Credits used: {min(4, len(all_companies)//25 + 1)}")
    print(f"  Time: {time.time() - start:.1f}s")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    total_credits = 1 + len(enriched) + min(4, len(all_companies)//25 + 1)
    print(f"  Total Apollo credits: {total_credits}")
    print(f"  Companies in pipeline: {len(all_companies)}")
    print(f"  Initial target rate: {len(targets)/len(classifications)*100:.0f}%")
    print(f"  Estimated targets: ~{int(len(all_companies) * len(targets)/max(1,len(classifications)))}")
    print(f"  Estimated contacts (3 per company): ~{int(len(all_companies) * len(targets)/max(1,len(classifications))) * 3}")
    print(f"  Optimized keywords added: {new_kw}")


if __name__ == "__main__":
    if not APOLLO_KEY:
        print("ERROR: Set APOLLO_API_KEY")
        sys.exit(1)
    if not OPENAI_KEY:
        print("ERROR: Set OPENAI_API_KEY")
        sys.exit(1)
    asyncio.run(test_exploration())
