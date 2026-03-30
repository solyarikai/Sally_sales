"""Round 2: Refined exploration prompts — targeting OnSocial accuracy.

Uses cached scrape data from round 1. Tests 5 new prompt variations
focused on:
1. Better buyer/seller for data/API products
2. Including brands that DO influencer marketing as targets
3. Not over-including (recruitment agencies, unrelated media)

Run:
    cd mcp && python3 tests/test_exploration_round2.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import httpx

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and len(v) > 3:
                os.environ.setdefault(k, v)

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
CACHE_DIR = Path(__file__).parent / "tmp" / "exploration_cache"
TMP_DIR = Path(__file__).parent / "tmp"

# ═══════════════════════════════════════════════════════════════
# GROUND TRUTH — Opus-level manual review
# ═══════════════════════════════════════════════════════════════
# For each company: True = IS a target buyer, False = NOT

GROUND_TRUTH = {
    "EasyStaff IT consulting Miami": {
        # ALL IT firms in Miami are buyers of payroll (they hire contractors)
        "synergybc.com": True,    # IT staffing/consulting → hires contractors → needs payroll
        "smxusa.com": True,       # IT solutions → needs payroll for team
        "koombea.com": True,      # Software dev agency → hires contractors globally
        "flatiron.software": True, # AI software dev → hires devs
        "therocketcode.com": True, # Software dev → hires contractors
        "avalith.net": True,      # Software dev outsourcing → manages contractors
        "bluecoding.com": True,   # Nearshore staffing → pays contractors
        "shokworks.io": True,     # AI solutions → hires devs
    },
    "TFP Fashion brands Italy": {
        # Fashion brands with e-commerce = targets (have old stock/returns to monetize)
        "trussardi.com": True,     # Italian fashion brand with e-commerce
        "marni.com": True,         # Italian fashion brand with e-commerce
        "elisabettafranchi.com": True, # Italian fashion brand
        "ermannoscervino.com": True,   # Italian fashion brand
        "patriziapepe.com": True,      # Italian fashion brand
        "kiton.com": True,             # Italian luxury brand
        "herno.com": True,             # Italian outerwear brand
        "soeur.fr": False,             # French brand, not Italian (wrong geo)
        "fabianafilippi.com": True,    # Italian fashion brand
        "giuseppezanotti.com": True,   # Italian luxury footwear brand
    },
    "OnSocial Creator platforms UK": {
        # OnSocial sells creator DATA/ANALYTICS to companies that DO influencer marketing
        "thenewgen.com": True,     # Creative agency connecting brands with creators → buys data to find creators
        "sixteenth.com": True,     # Creator talent management → buys analytics on creators
        "seenconnects.com": True,  # Influencer marketing agency → core buyer
        "found.co.uk": False,      # Digital marketing (PPC/SEO) → not influencer-focused
        "musetheagency.com": True, # Talent management for creators → buys data
        "unravelapp.com": False,   # Travel booking app → unrelated
        "inthestyle.com": True,    # Fast fashion brand using influencer marketing → buys data to find influencers
        "dexerto.media": False,    # Gaming/pop culture media → not a buyer of influencer data tools
        "majorplayers.co.uk": False, # Recruitment agency for creative roles → doesn't DO influencer marketing
        "lindafarrow.com": False,    # Luxury eyewear brand → not focused on influencer marketing tech
    },
}

# Correct totals per segment
EXPECTED = {
    "EasyStaff IT consulting Miami": {"targets": 8, "total": 8},
    "TFP Fashion brands Italy": {"targets": 9, "total": 10},
    "OnSocial Creator platforms UK": {"targets": 5, "total": 10},
}

# ═══════════════════════════════════════════════════════════════
# NEW PROMPTS — round 2 refinements
# ═══════════════════════════════════════════════════════════════

PROMPTS = {
    "v6_two_step_structured": """For each company, follow these 2 steps:

STEP 1 — What does this company do? (one sentence)
STEP 2 — Would they PAY for our product? Answer: BUYER, COMPETITOR, or UNRELATED.

OUR PRODUCT: {offer}
TARGET SEGMENT: {query}

BUYER = company whose daily work involves {query} — they'd pay for our product to do their job better.
COMPETITOR = company selling the EXACT same type of product as ours.
UNRELATED = no connection to the target segment.

CRITICAL: Our product SERVES companies that DO {query}. Companies active in that space are BUYERS.
- An agency in our target market = BUYER (uses our product for their clients)
- A brand that does the activity our product supports = BUYER (uses our product internally)
- A platform that manages the same things our product provides data about = BUYER (integrates our data)
- ONLY a company selling the same type of tool/data/service = COMPETITOR

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "what_they_do": "1 sentence", "reasoning": "buyer/competitor/unrelated because..."}}]

Companies:
{companies}""",

    "v7_ecosystem_buyer": """Classify: is this company part of the ECOSYSTEM that buys our product?

OUR PRODUCT: {offer}
TARGET: {query}

Think of it as an ECOSYSTEM. Our product fits into a market where multiple types of companies operate:
- AGENCIES that do the work → they buy tools to do it better → TARGET
- PLATFORMS that enable the work → they integrate data/tools → TARGET
- BRANDS that commission the work → they buy tools to evaluate results → TARGET
- DIRECT COMPETITORS selling the same tool → NOT TARGET
- COMPLETELY DIFFERENT industry → NOT TARGET

The ecosystem test: "Does this company's revenue depend on the same activity our product supports?"
If YES → TARGET. If NO → NOT TARGET.

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "ecosystem fit: yes/no because..."}}]

Companies:
{companies}""",

    "v8_pain_point": """For each company: does our product solve a PAIN POINT they have?

OUR PRODUCT: {offer}
SEARCHING FOR: {query}

A company is a TARGET if they have a problem our product solves:
- They need to {query} better, faster, or cheaper
- They currently do this manually or with inferior tools
- They would see ROI from adopting our product

A company is NOT a target if:
- They sell the same solution (competitor)
- They have zero need for our product (different industry entirely)
- They're in a tangentially related field but wouldn't actually buy our product

Think about each company's DAILY OPERATIONS. Would they use our product in their workflow?

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "pain point: ..."}}]

Companies:
{companies}""",

    "v9_negativa_refined": """EXCLUDE companies that should NOT be contacted. Keep everything else.

WE SELL: {offer}
TARGET SEGMENT: {query}

EXCLUDE ONLY IF one of these is true:
1. DIRECT COMPETITOR: sells the SAME type of product (same category, same buyer)
2. COMPLETELY UNRELATED: zero overlap with the target segment or its supply chain
3. WRONG GEOGRAPHY or WRONG INDUSTRY: explicitly outside the search criteria

INCLUDE if ANY of these is true:
- Company is an AGENCY that does work in the target segment → BUYER of our tools
- Company is a PLATFORM that operates in the target space → BUYER of our data/integration
- Company is a BRAND that actively engages in the activity our product supports → BUYER
- Company manages TALENT/PEOPLE in the target space → BUYER of our analytics
- Company creates CONTENT in the target space → potential BUYER

DO NOT confuse "adjacent" with "competitor". A company that works WITH the same market is a CUSTOMER.
Only a company selling the EXACT SAME product is a competitor.

A recruitment agency that places people in the industry ≠ buyer (they recruit, not operate).
A general digital marketing agency (PPC/SEO) ≠ buyer (unless specifically in the target segment).
A media company covering the industry ≠ buyer (they report, not operate).

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",

    "v10_minimal_precise": """Which companies would be CUSTOMERS of our product?

Product: {offer}
Market: {query}

CUSTOMER = company that DOES {query} as part of their business and would PAY for our product.
NOT CUSTOMER = competitor (same product), unrelated industry, or only tangentially connected.

Rules:
- Agencies/platforms DOING the work in our target market = CUSTOMERS
- Brands that ACTIVELY engage in the target activity = CUSTOMERS
- Companies that RECRUIT for the industry but don't DO it = NOT customers
- General marketing/media companies without specific focus = NOT customers
- Travel, food, unrelated verticals = NOT customers

Return JSON:
[{{"domain":"...","is_target":true/false,"segment":"CAPS","reasoning":"..."}}]

Companies:
{companies}""",
}

MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o"]


async def load_cached_scrapes():
    """Load cached scrape data from round 1."""
    segments = {}

    # Load from cache files
    seg_configs = {
        "EasyStaff IT consulting Miami": {
            "query": "IT consulting companies in Miami",
            "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management. Helps companies hire and pay contractors worldwide.",
        },
        "TFP Fashion brands Italy": {
            "query": "Fashion brands in Italy",
            "offer": "The Fashion People — branded resale platform that turns old stock, returns and pre-owned into revenue for fashion brands. Launch in 2 weeks, 20+ EU countries.",
        },
        "OnSocial Creator platforms UK": {
            "query": "Influencer marketing platforms and creator economy companies in UK",
            "offer": "OnSocial — AI-powered creator data solution. Products: Creator Discovery (find influencers by audience filters), Creator Analytics (deep metrics + audience insights), Social Data API (programmatic access), Sponsored Posts tracking. Target: platforms, agencies, brands, tech companies that DO influencer marketing and need DATA about creators.",
        },
    }

    for seg_name, config in seg_configs.items():
        companies = []
        gt = GROUND_TRUTH.get(seg_name, {})
        for domain in gt.keys():
            cache_key = domain.replace(".", "_").replace("/", "_")
            cache_file = CACHE_DIR / f"scrape_{cache_key}.json"
            if cache_file.exists():
                data = json.loads(cache_file.read_text())
                companies.append({
                    "domain": domain,
                    "primary_domain": domain,
                    "name": domain.split(".")[0].title(),
                    "website_text": data.get("text", "")[:3000],
                })

        segments[seg_name] = {
            "companies": companies,
            "query": config["query"],
            "offer": config["offer"],
        }

    return segments


async def classify(model, prompt_template, companies, query, offer):
    """Run classification."""
    company_text = ""
    for c in companies:
        name = c.get("name", c.get("domain", "?"))
        domain = c.get("domain", c.get("primary_domain", "?"))
        text = c.get("website_text", "")[:500]
        company_text += f"\n--- {name} ({domain}) ---\n{text}\n"

    prompt = prompt_template.format(offer=offer, query=query, companies=company_text)

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 2000, "temperature": 0},
            )
            data = resp.json()
            if "error" in data:
                return None, data["error"].get("message", "")
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content), None
    except Exception as e:
        return None, str(e)


def score(classifications, ground_truth):
    """Score classifications against ground truth."""
    correct = 0
    total = 0
    false_positives = []
    false_negatives = []

    for cls in classifications:
        domain = cls.get("domain", "")
        if domain in ground_truth:
            expected = ground_truth[domain]
            actual = cls.get("is_target", False)
            total += 1
            if actual == expected:
                correct += 1
            elif actual and not expected:
                false_positives.append(domain)
            elif not actual and expected:
                false_negatives.append(domain)

    return {
        "accuracy": correct / total if total > 0 else 0,
        "correct": correct,
        "total": total,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


async def run_round2():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 90)
    print(f"ROUND 2 — REFINED PROMPTS — {ts}")
    print(f"Models: {MODELS}")
    print(f"Prompts: {list(PROMPTS.keys())}")
    print(f"Total setups: {len(MODELS) * len(PROMPTS)}")
    print("=" * 90)

    segments = await load_cached_scrapes()

    for seg_name, data in segments.items():
        print(f"\n{seg_name}: {len(data['companies'])} companies loaded from cache")
        for c in data["companies"]:
            has_text = "✓" if c.get("website_text") else "✗"
            print(f"  {has_text} {c['domain']}")

    results = []

    for model in MODELS:
        for prompt_key, prompt_template in PROMPTS.items():
            setup = f"{model} × {prompt_key}"
            print(f"\n{'='*50}")
            print(f"  {setup}")
            print(f"{'='*50}")

            seg_scores = {}

            for seg_name, data in segments.items():
                if not data["companies"]:
                    print(f"  {seg_name}: SKIP (no cached data)")
                    continue

                classifications, err = await classify(
                    model, prompt_template, data["companies"],
                    data["query"], data["offer"],
                )

                if err:
                    print(f"  {seg_name}: ERROR — {err}")
                    seg_scores[seg_name] = {"accuracy": 0, "error": err}
                    continue

                gt = GROUND_TRUTH.get(seg_name, {})
                sc = score(classifications, gt)
                seg_scores[seg_name] = sc

                targets = [c for c in classifications if c.get("is_target")]
                target_domains = set(c.get("domain", "") for c in targets)

                print(f"  {seg_name}: accuracy={sc['accuracy']*100:.0f}% ({sc['correct']}/{sc['total']}), targets={len(targets)}/{len(classifications)}")
                if sc["false_positives"]:
                    print(f"    FP (shouldn't be target): {sc['false_positives']}")
                if sc["false_negatives"]:
                    print(f"    FN (missed target): {sc['false_negatives']}")

            results.append({
                "model": model,
                "prompt": prompt_key,
                "scores": {k: {**v, "false_positives": v.get("false_positives", []), "false_negatives": v.get("false_negatives", [])} for k, v in seg_scores.items()},
            })

    # Summary table
    print("\n" + "=" * 90)
    print("ACCURACY SUMMARY (correct/total against ground truth)")
    print("=" * 90)
    print(f"{'Setup':<45} {'EasyStaff':>12} {'Fashion':>12} {'OnSocial':>12} {'Avg':>8}")
    print("-" * 95)

    best_setup = None
    best_avg = -1

    for r in results:
        setup = f"{r['model']} × {r['prompt']}"
        accs = {}
        for seg_name in ["EasyStaff IT consulting Miami", "TFP Fashion brands Italy", "OnSocial Creator platforms UK"]:
            s = r["scores"].get(seg_name, {})
            if "error" in s:
                accs[seg_name] = "ERR"
            elif s.get("accuracy") is not None:
                accs[seg_name] = f"{s['correct']}/{s['total']}={s['accuracy']*100:.0f}%"
            else:
                accs[seg_name] = "—"

        avg_acc = 0
        count = 0
        for seg_name in ["EasyStaff IT consulting Miami", "TFP Fashion brands Italy", "OnSocial Creator platforms UK"]:
            s = r["scores"].get(seg_name, {})
            if s.get("accuracy") is not None:
                avg_acc += s["accuracy"]
                count += 1
        avg_acc = avg_acc / count if count > 0 else 0

        es = accs.get("EasyStaff IT consulting Miami", "—")
        tfp = accs.get("TFP Fashion brands Italy", "—")
        ons = accs.get("OnSocial Creator platforms UK", "—")
        print(f"{setup:<45} {es:>12} {tfp:>12} {ons:>12} {avg_acc*100:>7.0f}%")

        if avg_acc > best_avg:
            best_avg = avg_acc
            best_setup = setup

    print(f"\nBEST: {best_setup} ({best_avg*100:.0f}%)")

    # Save results
    results_file = TMP_DIR / f"{ts}_exploration_round2.json"
    results_file.write_text(json.dumps({
        "timestamp": ts,
        "ground_truth": {k: {d: v for d, v in gt.items()} for k, gt in GROUND_TRUTH.items()},
        "results": results,
        "best_setup": best_setup,
        "best_accuracy": best_avg,
    }, indent=2, default=str))
    print(f"\nSaved: {results_file.name}")


if __name__ == "__main__":
    if not OPENAI_KEY:
        print("ERROR: Set OPENAI_API_KEY")
        sys.exit(1)
    asyncio.run(run_round2())
