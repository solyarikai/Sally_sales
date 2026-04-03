"""Test industry selection specifically — find the prompt+model that gets all 3 segments right.

Golden filters (from GOLDEN_FILTERS.md):
  EasyStaff: information technology & services, management consulting
  Fashion:   apparel & fashion, luxury goods & jewelry, retail
  OnSocial:  marketing & advertising (NOT internet, NOT information services)

KPI: match golden industries. Every extra broad/wrong industry = penalty.

Run:
    cd mcp && python3 -u tests/test_industry_selection.py
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
TMP_DIR = Path(__file__).parent / "tmp"

# Load industry list
TAX_PATH = Path(__file__).parent.parent / "apollo_filters" / "apollo_taxonomy.json"
INDUSTRIES = json.loads(TAX_PATH.read_text()).get("industries", [])

# Golden truth — correct industries per segment
GOLDEN = {
    "IT consulting companies in Miami": {
        "must_have": ["information technology & services"],
        "good": ["management consulting", "computer software", "outsourcing/offshoring"],
        "bad": ["apparel & fashion", "real estate", "banking"],
    },
    "Fashion brands in Italy": {
        "must_have": ["apparel & fashion"],
        "good": ["luxury goods & jewelry", "retail", "textiles", "design"],
        "bad": ["information technology & services", "internet", "real estate"],
    },
    "Influencer marketing platforms and creator economy companies in UK": {
        "must_have": ["marketing & advertising"],
        "good": ["online media", "media production", "entertainment"],
        "bad": ["internet", "information services", "information technology & services", "computer software", "consumer services"],
    },
}

SEGMENTS = [
    ("IT consulting companies in Miami", "EasyStaff payroll platform"),
    ("Fashion brands in Italy", "The Fashion People resale platform"),
    ("Influencer marketing platforms and creator economy companies in UK", "OnSocial creator data API"),
]

MODELS = ["gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o-mini", "gpt-4o"]

PROMPTS = {
    "p1_linkedin_test": """Pick 2-4 Apollo industries for this search.
ONLY pick industries where the target companies would LIST THEMSELVES on LinkedIn.

Industries list: {industries}
Search: {query}
We sell: {offer}

Test each industry: "Would a {query_short} company pick THIS as their LinkedIn industry?" If no → skip.

Return JSON: {{"industries": ["exact name 1", "exact name 2"]}}""",

    "p2_specific_over_broad": """Pick Apollo industries for: {query}
We sell: {offer}

Available: {industries}

Pick the MOST SPECIFIC industries. Prefer narrow industries over broad ones.
If the segment is niche, 1-2 specific industries is better than 3-4 broad ones.
Never pick generic industries that contain millions of unrelated companies.

Return JSON: {{"industries": ["exact name 1"]}}""",

    "p3_would_they_say": """I'm searching Apollo for: {query}

Available industries: {industries}

For each industry ask: "If I met someone from a {query_short} company and asked 'what industry are you in?', would they say THIS?"

Only include industries they would actually SAY. Not industries that technically contain them.

Return JSON: {{"industries": ["exact name"]}}""",

    "p4_exclusion_first": """Pick Apollo industries for: {query}
We sell: {offer}

Available: {industries}

FIRST: eliminate all industries that are clearly wrong (different business entirely).
THEN: from remaining, pick 2-4 that are MOST DIRECTLY relevant.
IMPORTANT: "internet", "information services", "consumer services" are generic catch-alls — only include if the segment IS specifically about internet/information/consumer services.

Return JSON: {{"industries": ["exact name"]}}""",

    "p5_core_plus_adjacent": """Map this search to Apollo industries: {query}
We sell: {offer}

Available: {industries}

Step 1: What is the ONE core industry? (the single best match)
Step 2: Are there 1-2 adjacent industries where MANY target companies also list themselves? Only add if >30% of target companies would be there.

Return JSON: {{"industries": ["core", "adjacent_if_any"]}}""",
}


def score(industries, golden):
    points = 0
    max_pts = 0
    details = []

    for m in golden["must_have"]:
        max_pts += 30
        if m in industries:
            points += 30
            details.append(f"✓ must-have '{m}'")
        else:
            details.append(f"✗ MISSING must-have '{m}'")

    bonus = 0
    for g in golden["good"]:
        if g in industries:
            bonus += 10
            details.append(f"✓ good '{g}'")
    points += min(bonus, 20)
    max_pts += 20

    max_pts += 20
    bad_found = [b for b in golden["bad"] if b in industries]
    if not bad_found:
        points += 20
        details.append("✓ no bad industries")
    else:
        details.append(f"✗ BAD: {bad_found}")

    return {"score": int(points / max_pts * 100) if max_pts else 0, "details": details}


async def call_gpt(model, prompt):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 300, "temperature": 0},
            )
            data = resp.json()
            if "error" in data:
                return None, str(data["error"])[:100]
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            import re
            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                content = m.group(0)
            return json.loads(content), None
    except Exception as e:
        return None, str(e)[:100]


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log(f"INDUSTRY SELECTION TEST — {ts}")
    log(f"Models: {MODELS} | Prompts: {list(PROMPTS.keys())}")
    log(f"Total: {len(MODELS) * len(PROMPTS)} setups × 3 segments = {len(MODELS) * len(PROMPTS) * 3} calls")

    results = []

    for model in MODELS:
        for pk, pt in PROMPTS.items():
            setup = f"{model} × {pk}"
            scores = []

            for query, offer in SEGMENTS:
                query_short = query.split(" in ")[0]
                prompt = pt.format(
                    query=query, offer=offer, industries=json.dumps(INDUSTRIES),
                    query_short=query_short,
                )
                result, err = await call_gpt(model, prompt)

                if err:
                    scores.append(0)
                    continue

                industries = [i.lower() for i in (result or {}).get("industries", [])]
                golden = GOLDEN[query]
                sc = score(industries, golden)
                scores.append(sc["score"])

                if sc["score"] < 100:
                    log(f"  {setup} | {query[:35]}: {sc['score']}% ind={industries}")
                    for d in sc["details"]:
                        if "✗" in d:
                            log(f"    {d}")

            avg = sum(scores) / len(scores) if scores else 0
            results.append({"setup": setup, "avg": avg, "scores": scores})

    # Summary
    log(f"\n{'='*70}")
    sorted_r = sorted(results, key=lambda x: -x["avg"])
    log(f"{'Setup':<40} {'ES':>6} {'TFP':>6} {'OnS':>6} {'AVG':>6}")
    log("-" * 65)
    for r in sorted_r:
        s = r["scores"]
        log(f"{r['setup']:<40} {s[0] if len(s)>0 else 0:>5}% {s[1] if len(s)>1 else 0:>5}% {s[2] if len(s)>2 else 0:>5}% {r['avg']:>5.0f}%")

    log(f"\nBEST: {sorted_r[0]['setup']} ({sorted_r[0]['avg']:.0f}%)")

    # Save
    log_file = TMP_DIR / f"{ts}_industry_selection.log"
    log_file.write_text("\n".join(lines))
    results_file = TMP_DIR / f"{ts}_industry_selection.json"
    results_file.write_text(json.dumps({"ts": ts, "results": results}, indent=2, default=str))
    log(f"Saved: {log_file.name}")


if __name__ == "__main__":
    asyncio.run(main())
