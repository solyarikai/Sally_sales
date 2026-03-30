"""Final round: push for 100% accuracy on all segments.

The v9/v10 prompts get 97% — only missing inthestyle.com (fast fashion brand
that does influencer marketing but website text doesn't show this).

Tests 3 final prompt variants that add "e-commerce/DTC brands = potential buyers
of data tools" without breaking other segments.

Run:
    cd mcp && python3 tests/test_exploration_final.py
"""
import asyncio
import json
import os
import sys
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

GROUND_TRUTH = {
    "EasyStaff IT consulting Miami": {
        "synergybc.com": True, "smxusa.com": True, "koombea.com": True,
        "flatiron.software": True, "therocketcode.com": True, "avalith.net": True,
        "bluecoding.com": True, "shokworks.io": True,
    },
    "TFP Fashion brands Italy": {
        "trussardi.com": True, "marni.com": True, "elisabettafranchi.com": True,
        "ermannoscervino.com": True, "patriziapepe.com": True, "kiton.com": True,
        "herno.com": True, "soeur.fr": False, "fabianafilippi.com": True,
        "giuseppezanotti.com": True,
    },
    "OnSocial Creator platforms UK": {
        "thenewgen.com": True, "sixteenth.com": True, "seenconnects.com": True,
        "found.co.uk": False, "musetheagency.com": True, "unravelapp.com": False,
        "inthestyle.com": True, "dexerto.media": False, "majorplayers.co.uk": False,
        "lindafarrow.com": False,
    },
}

SEGMENTS = {
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

# ═══════════════════════════════════════════════════════════════
# FINAL PROMPTS — tuned for the inthestyle.com edge case
# ═══════════════════════════════════════════════════════════════

PROMPTS = {
    # v9 from round 2 (97% baseline) — unchanged for comparison
    "v9_baseline": """EXCLUDE companies that should NOT be contacted. Keep everything else.

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

    # v11: adds e-commerce/DTC brand clause
    "v11_brand_inclusive": """EXCLUDE companies that should NOT be contacted. Keep everything else.

WE SELL: {offer}
TARGET SEGMENT: {query}

EXCLUDE ONLY IF one of these is true:
1. DIRECT COMPETITOR: sells the SAME type of product (same category, same buyer)
2. COMPLETELY UNRELATED: zero overlap with the target segment or its supply chain
3. WRONG GEOGRAPHY or WRONG INDUSTRY: explicitly outside the search criteria

INCLUDE if ANY of these is true:
- Company is an AGENCY that does work in the target segment → BUYER of our tools
- Company is a PLATFORM that operates in the target space → BUYER of our data
- Company is a BRAND/RETAILER/E-COMMERCE that likely uses the activity our product supports in their marketing → BUYER (brands are end-customers of marketing tools and data)
- Company manages TALENT/PEOPLE in the target space → BUYER of our analytics

KEY INSIGHT about BRANDS: E-commerce brands, DTC companies, and retailers with strong social media presence ARE buyers of marketing data and tools. They run campaigns, work with agencies, and need data to evaluate results. Include them.

DO NOT confuse "adjacent" with "competitor". Only the EXACT same product = competitor.

EXCLUDE these specifically:
- Recruitment/staffing agencies that place people but don't DO the marketing work
- General PPC/SEO agencies not specifically in the target vertical
- Media companies that report ON the industry but don't participate IN it
- Unrelated verticals (travel, food, finance) unless they explicitly do the target activity

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",

    # v12: system prompt approach
    "v12_system_plus_user": """You are classifying companies for a sales team. Your job: identify which companies would BUY our product.

OUR PRODUCT: {offer}

TARGET MARKET: {query}

WHO BUYS our product (mark is_target=true):
1. AGENCIES in the target space — they use our tools for client campaigns
2. PLATFORMS in the target space — they integrate our data
3. BRANDS & RETAILERS — especially e-commerce and DTC brands that actively use the marketing channel our product supports. Brands are the END BUYERS in any marketing ecosystem.
4. TALENT MANAGEMENT — they need data about the talent they manage

WHO DOES NOT BUY (mark is_target=false):
1. COMPETITORS — companies selling the exact same type of product
2. UNRELATED — companies in completely different industries (travel, food, luxury goods not in segment)
3. RECRUITERS — staffing/recruitment agencies that place people but don't execute marketing
4. GENERAL MARKETERS — PPC/SEO agencies without specific focus on the target vertical
5. MEDIA/PRESS — outlets that cover the industry but don't participate as buyers

Think: "Would this company's marketing team or product team use our product?" If yes → target.

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
{companies}""",
}

MODELS = ["gpt-4o-mini", "gpt-4o"]


async def load_cached():
    results = {}
    for seg_name, config in SEGMENTS.items():
        companies = []
        for domain in GROUND_TRUTH.get(seg_name, {}):
            cache_file = CACHE_DIR / f"scrape_{domain.replace('.', '_').replace('/', '_')}.json"
            if cache_file.exists():
                data = json.loads(cache_file.read_text())
                companies.append({
                    "domain": domain, "primary_domain": domain,
                    "name": domain.split(".")[0].title(),
                    "website_text": data.get("text", "")[:3000],
                })
        results[seg_name] = {"companies": companies, **config}
    return results


async def classify(model, prompt_template, companies, query, offer):
    company_text = ""
    for c in companies:
        name = c.get("name", c.get("domain", "?"))
        domain = c.get("domain", "?")
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
    correct = 0
    total = 0
    fp, fn = [], []
    for cls in classifications:
        domain = cls.get("domain", "")
        if domain in ground_truth:
            expected = ground_truth[domain]
            actual = cls.get("is_target", False)
            total += 1
            if actual == expected:
                correct += 1
            elif actual and not expected:
                fp.append(domain)
            else:
                fn.append(domain)
    return {"accuracy": correct / total if total else 0, "correct": correct, "total": total,
            "fp": fp, "fn": fn}


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"FINAL ROUND — {ts}")
    print(f"Setups: {len(MODELS) * len(PROMPTS)}")

    segments = await load_cached()
    results = []

    for model in MODELS:
        for pk, pt in PROMPTS.items():
            setup = f"{model} × {pk}"
            print(f"\n--- {setup} ---")

            seg_scores = {}
            for seg_name, data in segments.items():
                cls, err = await classify(model, pt, data["companies"], data["query"], data["offer"])
                if err:
                    print(f"  {seg_name}: ERR {err}")
                    seg_scores[seg_name] = {"accuracy": 0, "error": err}
                    continue

                gt = GROUND_TRUTH[seg_name]
                sc = score(cls, gt)
                seg_scores[seg_name] = sc

                status = "✅" if sc["accuracy"] == 1.0 else "❌" if sc["accuracy"] < 0.9 else "⚠️"
                print(f"  {status} {seg_name}: {sc['correct']}/{sc['total']} ({sc['accuracy']*100:.0f}%)", end="")
                if sc["fp"]:
                    print(f"  FP:{sc['fp']}", end="")
                if sc["fn"]:
                    print(f"  FN:{sc['fn']}", end="")
                print()

            results.append({"model": model, "prompt": pk, "scores": seg_scores})

    # Summary
    print(f"\n{'='*95}")
    print(f"{'Setup':<45} {'EasyStaff':>10} {'Fashion':>10} {'OnSocial':>10} {'Avg':>8}")
    print("-" * 85)

    best_setup, best_avg = None, -1
    for r in results:
        setup = f"{r['model']} × {r['prompt']}"
        accs = []
        vals = {}
        for seg in ["EasyStaff IT consulting Miami", "TFP Fashion brands Italy", "OnSocial Creator platforms UK"]:
            s = r["scores"].get(seg, {})
            a = s.get("accuracy", 0)
            accs.append(a)
            vals[seg] = f"{s.get('correct',0)}/{s.get('total',0)}={a*100:.0f}%"
        avg = sum(accs) / len(accs)
        print(f"{setup:<45} {vals.get('EasyStaff IT consulting Miami','—'):>10} {vals.get('TFP Fashion brands Italy','—'):>10} {vals.get('OnSocial Creator platforms UK','—'):>10} {avg*100:>7.0f}%")
        if avg > best_avg:
            best_avg = avg
            best_setup = setup

    print(f"\nBEST: {best_setup} ({best_avg*100:.0f}%)")

    # Save
    out = TMP_DIR / f"{ts}_exploration_final.json"
    out.write_text(json.dumps({"timestamp": ts, "results": results, "best": best_setup, "best_avg": best_avg}, indent=2, default=str))
    print(f"Saved: {out.name}")


if __name__ == "__main__":
    asyncio.run(main())
