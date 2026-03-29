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

    # Step 1: Infer company size from offer using offer_analyzer service (not hardcoded)
    print("\n--- Step 1: Infer target company size from offer ---")
    start = time.time()

    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from app.services.offer_analyzer import infer_target_size

    offer_text = "EasyStaff is a global platform for payroll, freelance connections, and invoice management. They help companies hire and pay contractors worldwide."
    size_result = await infer_target_size(offer_text, OPENAI_KEY)
    print(f"  Size inference: {json.dumps(size_result)}")
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

    # Use the proper BeautifulSoup scraper (same as MCP pipeline)
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from app.services.scraper_service import ScraperService
    scraper = ScraperService()

    for c in companies[:15]:
        domain = c.get("primary_domain") or c.get("domain", "")
        if not domain:
            continue
        result = await scraper.scrape_website(domain, timeout=12)
        if result.get("success"):
            text = result["text"][:3000]  # First 3000 chars for classification
            scraped.append({**c, "website_text": text})
            print(f"    ✓ {domain}: {len(result['text'])} chars scraped")
        else:
            print(f"    ✗ {domain}: {result.get('error', '?')}")

    print(f"  Scraped: {len(scraped)}/{min(15, len(companies))}")
    print(f"  Time: {time.time() - start:.1f}s")

    # Step 4: GPT classifies targets (free)
    print("\n--- Step 4: GPT-4o-mini classifies targets ---")
    start = time.time()

    classify_prompt = """VIA NEGATIVA classification: EXCLUDE companies that are NOT targets for EasyStaff.

EasyStaff = payroll & contractor management platform. Helps companies pay freelancers/contractors worldwide.

EXCLUDE (is_target=false) if ANY of these apply:
1. COMPETITOR: payroll/HR/PEO/EOR platform (Deel, Remote, Oyster, Papaya, Gusto, Rippling, ADP, etc.)
2. PRODUCT COMPANY: builds own SaaS/AI product (not services/consulting — they hire FTEs, not contractors)
3. NON-IT: restaurants, real estate, legal, retail, healthcare, finance, construction
4. ENTERPRISE PRODUCT: sells own software PRODUCT to enterprises (not services — they have FTEs, not contractors)
5. INSUFFICIENT DATA: cannot determine what company does — website text is mostly JS code or too short to judge
6. MARKETING/CREATIVE AGENCY: pure marketing, PR, design (no engineering team using contractors)

IMPORTANT DISTINCTIONS:
- "Digital transformation CONSULTING" = IS a target (they're a consulting firm, hire contractors for projects)
- "Enterprise PRODUCT/PLATFORM" = NOT a target (they build own product with FTEs)
- "Consulting services + technology solutions" = IS a target
- "AI-native platform for enterprises" = NOT a target (product company)

KEEP (is_target=true) ONLY if CLEAR EVIDENCE of:
- IT consulting / technology services / software development AGENCY
- Nearshore / offshore staffing that PLACES DEVELOPERS
- IT outsourcing / managed services with CONTRACTOR TEAMS
- Staffing agency focused on TECH TALENT

SEGMENT labels (one per company):
- IT_CONSULTING: traditional IT consulting
- DEV_AGENCY: software development shop / custom dev
- NEARSHORE_STAFFING: nearshore/offshore dev team placement
- IT_OUTSOURCING: managed IT services / outsourcing
- NOT_A_MATCH: excluded by rules above

Return JSON array:
[{"domain": "...", "is_target": true/false, "segment": "...", "reasoning": "what the company does"}]

Companies:
"""
    for c in scraped:
        text = c.get("website_text", "")[:500]
        name = c.get("name", c.get("primary_domain", "?"))
        domain = c.get("primary_domain", c.get("domain", "?"))
        classify_prompt += f"\n--- {name} ({domain}) ---\n{text}\n"

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

    targets = [c for c in classifications if c.get("is_target")]
    non_targets = [c for c in classifications if not c.get("is_target")]

    print(f"  Targets: {len(targets)}/{len(classifications)}")
    print(f"  Conversion rate: {len(targets)/len(classifications)*100:.0f}%")
    print(f"  Time: {time.time() - start:.1f}s")
    for t in targets:
        print(f"    ✓ {t['domain']} [{t.get('segment','?')}]: {t.get('reasoning','?')}")
    for n in non_targets:
        print(f"    ✗ {n['domain']} [{n.get('segment','NOT_A_MATCH')}]: {n.get('reasoning', '?')}")

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

    # Step 9: Save targets for manual Opus verification
    # Opus verification is done by the AGENT (Claude Opus in Claude Code), NOT via API calls.
    # The Anthropic API key is ONLY for testing MCP conversations via test_real_mcp.py.
    print("\n--- Step 9: Targets saved for Opus review ---")
    review_file = Path(__file__).parent / "tmp" / f"{int(time.time())}_targets_for_opus_review.json"
    review_data = {
        "query": "IT consulting companies in Miami, 10-200 employees",
        "offer": "EasyStaff — payroll, contractor management, invoice processing",
        "targets": [],
        "non_targets": [],
    }
    for t in targets:
        domain = t.get("domain", "")
        website_text = ""
        for sc in scraped:
            if sc.get("primary_domain") == domain or sc.get("domain") == domain:
                website_text = sc.get("website_text", "")[:500]
                break
        review_data["targets"].append({
            "domain": domain,
            "name": t.get("name", "?"),
            "gpt_confidence": t.get("confidence", "?"),
            "gpt_reasoning": t.get("reasoning", "?"),
            "website_snippet": website_text,
        })
    for n in non_targets:
        review_data["non_targets"].append({
            "domain": n.get("domain", "?"),
            "gpt_reasoning": n.get("reasoning", "?"),
        })
    review_file.write_text(json.dumps(review_data, indent=2))
    print(f"  Saved to: {review_file.name}")
    print(f"  Run 'cat {review_file}' and review each target in Claude Code session")

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
