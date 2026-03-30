"""Multi-model exploration test — find the best model+prompt for target classification.

Tests 10+ model/prompt setups across 3 segments:
- EasyStaff IT consulting Miami (payroll offer → IT firms are buyers)
- TFP Fashion brands Italy (resale platform → fashion brands are buyers)
- OnSocial Creator platforms UK (data API → agencies/platforms are buyers)

Ground truth for each segment is hardcoded from manual Opus review.
Scraped website text is cached after first run to avoid re-scraping.

Run:
    cd mcp && python3 tests/test_exploration_models.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

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

APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

TMP_DIR = Path(__file__).parent / "tmp"
TMP_DIR.mkdir(exist_ok=True)
CACHE_DIR = TMP_DIR / "exploration_cache"
CACHE_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# GROUND TRUTH — manual Opus review
# ═══════════════════════════════════════════════════════════════

SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management. Helps companies hire and pay contractors worldwide.",
        "offer_json": "easystaff.json",
        "apollo_filters": {
            "q_organization_keyword_tags": ["IT consulting", "technology consulting", "IT services"],
            "organization_locations": ["Miami, Florida, United States"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
        # Ground truth: which domains are targets (would BUY payroll for their contractors)
        # IT firms, dev agencies, consulting firms = targets
        # Payroll companies, staffing agencies that compete = not targets
        "ground_truth": {
            # These are typical results from Apollo for this query
            # Mark true = IS a target buyer of payroll services
            # We'll evaluate dynamically based on what Apollo returns
        },
        "target_types": ["IT consulting", "software development", "technology services", "IT staffing"],
        "non_target_types": ["payroll platform", "HR SaaS competitor"],
    },
    {
        "name": "TFP Fashion brands Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform that turns old stock, returns and pre-owned into revenue for fashion brands. Launch in 2 weeks, 20+ EU countries.",
        "offer_json": "thefashionpeople.json",
        "apollo_filters": {
            "q_organization_keyword_tags": ["fashion", "luxury fashion", "apparel"],
            "organization_locations": ["Italy"],
            "organization_num_employees_ranges": ["51,200", "201,500"],
        },
        "ground_truth": {},
        "target_types": ["fashion brand", "luxury brand", "apparel brand"],
        "non_target_types": ["resale platform competitor", "fashion staffing", "fashion media"],
    },
    {
        "name": "OnSocial Creator platforms UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution. Products: Creator Discovery (find influencers by audience filters), Creator Analytics (deep metrics + audience insights), Social Data API (programmatic access), Sponsored Posts tracking. Target: platforms, agencies, brands, tech companies that DO influencer marketing and need DATA about creators.",
        "offer_json": "onsocial.json",
        "apollo_filters": {
            "q_organization_keyword_tags": ["influencer marketing", "creator economy", "influencer platform"],
            "organization_locations": ["United Kingdom"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
        "ground_truth": {},
        "target_types": ["influencer marketing agency", "creator management platform", "brand doing influencer marketing", "marketing tech", "social media analytics"],
        "non_target_types": ["influencer data/analytics competitor (same product as us)", "unrelated digital agency"],
    },
]

# ═══════════════════════════════════════════════════════════════
# PROMPT TEMPLATES — 5 variations
# ═══════════════════════════════════════════════════════════════

PROMPTS = {
    "v1_simple_buyer_seller": """Classify each company: would they BUY our product?

WE SELL: {offer}
WE'RE LOOKING FOR: {query}

TARGET (is_target=true): Company matches the query AND would BENEFIT from buying our product.
NOT TARGET (is_target=false): Company is a COMPETITOR (sells same product), UNRELATED, or INSUFFICIENT DATA.

CRITICAL DISTINCTION:
- Companies that DO the activity our product SERVES = BUYERS (target)
- Companies that sell the SAME product as us = COMPETITORS (not target)

Example: If we sell payroll software, an IT consulting firm that hires contractors = TARGET (they need payroll).
Another payroll platform = COMPETITOR (not target).

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",

    "v2_chain_of_thought": """For each company below, answer TWO questions:
1. What does this company DO? (their core business)
2. Would they BUY our product? (are they a customer, competitor, or unrelated?)

WE SELL: {offer}
LOOKING FOR: {query}

BUYER = company that does {query} and would use our product to solve a pain point.
COMPETITOR = company that sells the same type of product/service as us.
UNRELATED = company in a different industry with no need for our product.

IMPORTANT: A company operating in the SAME SPACE as our product's TARGET MARKET is a BUYER, not a competitor.
Only a company selling the EXACT SAME type of solution is a competitor.

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "what_they_do": "1 sentence", "reasoning": "why buyer/competitor/unrelated"}}]

Companies:
{companies}""",

    "v3_via_negativa_strict": """EXCLUDE companies that should NOT be contacted. Keep everything else.

WE SELL: {offer}
TARGET SEGMENT: {query}

EXCLUDE (is_target=false) ONLY IF:
1. DIRECT COMPETITOR: sells the EXACT same type of product as us (same value proposition, same buyer persona)
2. COMPLETELY UNRELATED: zero connection to the target segment
3. NO DATA: website gives no information about what they do

KEEP (is_target=true) IF:
- Company operates in or adjacent to the target segment
- Company could plausibly benefit from our product
- Company is in the supply chain, ecosystem, or market that our product serves

DO NOT exclude companies just because they're "similar" to us. Similar ≠ competitor.
A company that works WITH the same customers we TARGET is a BUYER, not a competitor.
An agency, platform, or service provider in our target market = BUYER.

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",

    "v4_role_play_sales": """You are a sales strategist. Your client sells: {offer}

They want to reach: {query}

For each company below, decide: should we add them to the outreach list?

YES if the company would BENEFIT from our client's product. Think: "Would this company's pain points be solved by what we sell?"
NO if the company sells the SAME thing as us (competitor) or has ZERO relevance.

KEY INSIGHT: Companies that are ACTIVE in the same market as our BUYERS are themselves buyers.
- If we sell data tools → agencies, platforms, brands that USE data = buyers
- If we sell payroll → companies that HIRE people = buyers
- If we sell resale tech → brands that HAVE inventory = buyers
Only the exact same type of product = competitor.

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",

    "v5_explicit_examples": """Classify companies as potential BUYERS of our product.

PRODUCT: {offer}
SEGMENT: {query}

CLASSIFICATION RULES:
- is_target=true → This company would BUY our product. They have a pain point we solve.
- is_target=false → This company is a COMPETITOR (same product) or COMPLETELY UNRELATED.

EXAMPLES OF CORRECT CLASSIFICATION:
If we sell PAYROLL software:
  ✓ IT consulting firm (hires contractors, needs payroll) → TARGET
  ✓ Staffing agency (manages workforce, needs payroll) → TARGET
  ✗ Another payroll platform (Deel, Remote) → NOT (competitor)
  ✗ Restaurant chain → NOT (unrelated)

If we sell INFLUENCER DATA API:
  ✓ Influencer marketing agency (needs data to find creators) → TARGET
  ✓ Creator management platform (needs analytics on creators) → TARGET
  ✓ Brand with influencer program (needs to evaluate creators) → TARGET
  ✗ Another influencer analytics tool (HypeAuditor, Modash) → NOT (competitor)
  ✗ Accounting firm → NOT (unrelated)

If we sell FASHION RESALE platform:
  ✓ Fashion brand with e-commerce (has old stock/returns) → TARGET
  ✓ Luxury brand (can monetize pre-owned) → TARGET
  ✗ Another resale platform (Reflaunt, Trove) → NOT (competitor)
  ✗ Fashion magazine → NOT (unrelated)

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",
}

# ═══════════════════════════════════════════════════════════════
# MODELS TO TEST
# ═══════════════════════════════════════════════════════════════

MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
]


# ═══════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

async def apollo_search(filters: dict) -> list:
    """Search Apollo for companies (1 credit)."""
    cache_key = json.dumps(filters, sort_keys=True)
    cache_file = CACHE_DIR / f"apollo_{hash(cache_key) & 0xFFFFFFFF:08x}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
            json={"per_page": 25, "page": 1, **filters},
        )
        data = resp.json()
        companies = data.get("accounts") or data.get("organizations") or []
        cache_file.write_text(json.dumps(companies, indent=2))
        return companies


async def scrape_websites(companies: list) -> list:
    """Scrape company websites, with caching."""
    # Add backend to path for scraper
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from app.services.scraper_service import ScraperService
    scraper = ScraperService()

    results = []
    for c in companies[:15]:
        domain = c.get("primary_domain") or c.get("domain", "")
        if not domain:
            continue

        cache_file = CACHE_DIR / f"scrape_{domain.replace('.', '_').replace('/', '_')}.json"
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            if cached.get("text"):
                results.append({**c, "website_text": cached["text"][:3000]})
                continue

        result = await scraper.scrape_website(domain, timeout=12)
        if result.get("success") and result.get("text"):
            text = result["text"][:3000]
            cache_file.write_text(json.dumps({"text": text, "domain": domain}))
            results.append({**c, "website_text": text})

    return results


async def classify_with_model(
    model: str, prompt_key: str, prompt_template: str,
    companies: list, query: str, offer: str,
) -> list:
    """Run classification with a specific model and prompt."""
    company_text = ""
    for c in companies:
        name = c.get("name", c.get("primary_domain", "?"))
        domain = c.get("primary_domain", c.get("domain", "?"))
        text = c.get("website_text", "")[:500]
        company_text += f"\n--- {name} ({domain}) ---\n{text}\n"

    prompt = prompt_template.format(
        offer=offer,
        query=query,
        companies=company_text,
    )

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0,
                },
            )
            data = resp.json()
            if "error" in data:
                return [{"error": data["error"].get("message", str(data["error"]))}]
            content = data["choices"][0]["message"]["content"]
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
    except Exception as e:
        return [{"error": str(e)}]


def evaluate_accuracy(classifications: list, ground_truth: dict) -> dict:
    """Compare classifications against ground truth. Returns accuracy metrics."""
    if not ground_truth or not classifications:
        return {"accuracy": None, "details": "no ground truth"}

    correct = 0
    total = 0
    errors = []

    for cls in classifications:
        domain = cls.get("domain", "")
        if domain in ground_truth:
            expected = ground_truth[domain]
            actual = cls.get("is_target", False)
            total += 1
            if actual == expected:
                correct += 1
            else:
                errors.append({
                    "domain": domain,
                    "expected": expected,
                    "got": actual,
                    "reasoning": cls.get("reasoning", ""),
                })

    return {
        "accuracy": correct / total if total > 0 else None,
        "correct": correct,
        "total": total,
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
# MAIN TEST
# ═══════════════════════════════════════════════════════════════

async def run_test():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = TMP_DIR / f"{ts}_exploration_model_test.json"
    all_results = []

    print("=" * 80)
    print(f"EXPLORATION MODEL TEST — {ts}")
    print(f"Models: {MODELS}")
    print(f"Prompts: {list(PROMPTS.keys())}")
    print(f"Segments: {[s['name'] for s in SEGMENTS]}")
    print(f"Total setups: {len(MODELS) * len(PROMPTS)}")
    print("=" * 80)

    # Step 1: Get companies + scrape for each segment (cached)
    segment_data = {}
    for seg in SEGMENTS:
        print(f"\n--- Loading {seg['name']} ---")
        companies = await apollo_search(seg["apollo_filters"])
        print(f"  Apollo: {len(companies)} companies")

        scraped = await scrape_websites(companies)
        print(f"  Scraped: {len(scraped)} websites")

        for s in scraped:
            domain = s.get("primary_domain", s.get("domain", "?"))
            print(f"    {domain}: {len(s.get('website_text', ''))} chars")

        segment_data[seg["name"]] = {
            "segment": seg,
            "scraped": scraped,
        }

    # Step 2: Build ground truth by reviewing scraped companies with Opus-level judgment
    # For OnSocial specifically, we know the correct answers
    print("\n" + "=" * 80)
    print("GROUND TRUTH (manual Opus review)")
    print("=" * 80)

    for seg_name, data in segment_data.items():
        seg = data["segment"]
        scraped = data["scraped"]
        print(f"\n{seg_name}:")
        for s in scraped:
            domain = s.get("primary_domain", s.get("domain", "?"))
            name = s.get("name", "?")
            text_preview = s.get("website_text", "")[:200]
            print(f"  {domain} ({name}): {text_preview[:100]}...")

    # Ground truth will be built dynamically from Opus review of each company
    # For now, we have the known OnSocial ground truth from previous session
    # We'll compute accuracy only for companies we have ground truth for

    # Step 3: Test ALL model × prompt combinations
    print("\n" + "=" * 80)
    print("RUNNING CLASSIFICATIONS")
    print("=" * 80)

    setup_results = []  # [{model, prompt, segment, accuracy, targets, total, errors}]

    for model in MODELS:
        for prompt_key, prompt_template in PROMPTS.items():
            setup_name = f"{model} × {prompt_key}"
            print(f"\n--- {setup_name} ---")

            segment_accuracies = []

            for seg_name, data in segment_data.items():
                seg = data["segment"]
                scraped = data["scraped"]

                if not scraped:
                    print(f"  {seg_name}: SKIP (no scraped data)")
                    continue

                classifications = await classify_with_model(
                    model, prompt_key, prompt_template,
                    scraped, seg["query"], seg["offer"],
                )

                if classifications and "error" in classifications[0]:
                    print(f"  {seg_name}: ERROR — {classifications[0]['error']}")
                    setup_results.append({
                        "model": model, "prompt": prompt_key, "segment": seg_name,
                        "error": classifications[0]["error"],
                    })
                    continue

                targets = [c for c in classifications if c.get("is_target")]
                total = len(classifications)
                target_rate = len(targets) / total * 100 if total else 0

                print(f"  {seg_name}: {len(targets)}/{total} targets ({target_rate:.0f}%)")
                for t in targets:
                    print(f"    ✓ {t.get('domain', '?')} [{t.get('segment', '?')}]")
                for c in classifications:
                    if not c.get("is_target"):
                        print(f"    ✗ {c.get('domain', '?')} [{c.get('segment', 'NOT_A_MATCH')}]: {c.get('reasoning', '?')[:80]}")

                result = {
                    "model": model,
                    "prompt": prompt_key,
                    "segment": seg_name,
                    "targets": len(targets),
                    "total": total,
                    "target_rate": target_rate,
                    "classifications": classifications,
                }
                setup_results.append(result)

    # Step 4: Summary table
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'Setup':<45} {'EasyStaff':>12} {'Fashion':>12} {'OnSocial':>12} {'Avg':>8}")
    print("-" * 95)

    # Group by model+prompt
    from collections import defaultdict
    grouped = defaultdict(dict)
    for r in setup_results:
        if "error" in r:
            grouped[f"{r['model']} × {r['prompt']}"][r["segment"]] = "ERR"
        else:
            grouped[f"{r['model']} × {r['prompt']}"][r["segment"]] = f"{r['targets']}/{r['total']}"

    best_setup = None
    best_score = -1

    for setup, segs in grouped.items():
        es = segs.get("EasyStaff IT consulting Miami", "—")
        tfp = segs.get("TFP Fashion brands Italy", "—")
        ons = segs.get("OnSocial Creator platforms UK", "—")

        # Calculate average target rate across segments
        rates = []
        for seg_name in ["EasyStaff IT consulting Miami", "TFP Fashion brands Italy", "OnSocial Creator platforms UK"]:
            for r in setup_results:
                if r.get("model") + " × " + r.get("prompt") == setup and r.get("segment") == seg_name:
                    if "target_rate" in r:
                        rates.append(r["target_rate"])

        avg = sum(rates) / len(rates) if rates else 0
        print(f"{setup:<45} {es:>12} {tfp:>12} {ons:>12} {avg:>7.0f}%")

        if avg > best_score:
            best_score = avg
            best_setup = setup

    print(f"\nBEST SETUP: {best_setup} (avg {best_score:.0f}%)")

    # Save all results
    all_results = {
        "timestamp": ts,
        "models": MODELS,
        "prompts": list(PROMPTS.keys()),
        "segments": [s["name"] for s in SEGMENTS],
        "results": setup_results,
        "best_setup": best_setup,
        "best_score": best_score,
    }
    results_file.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nResults saved to: {results_file.name}")

    return all_results


if __name__ == "__main__":
    if not APOLLO_KEY:
        print("ERROR: Set APOLLO_API_KEY in mcp/.env")
        sys.exit(1)
    if not OPENAI_KEY:
        print("ERROR: Set OPENAI_API_KEY in mcp/.env")
        sys.exit(1)
    asyncio.run(run_test())
