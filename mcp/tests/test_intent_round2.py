"""Round 2: Push intent parsing past 90%. Fix o3-mini, add refined prompts.

Analysis of round 1 gap:
- 90% ceiling because models pick only 2 industries (need 3-4 for bonus points)
- Offer text leaks into keywords (payroll keywords when searching for IT consulting)
- o3-mini needs max_completion_tokens not max_tokens

Run:
    cd mcp && python3 tests/test_intent_round2.py
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

TAX_PATH = Path(__file__).parent.parent / "apollo_filters" / "apollo_taxonomy.json"
VALID_INDUSTRIES = set()
INDUSTRIES_LIST = ""
if TAX_PATH.exists():
    _td = json.loads(TAX_PATH.read_text())
    VALID_INDUSTRIES = {i.lower() for i in _td.get("industries", [])}
    INDUSTRIES_LIST = ", ".join(_td.get("industries", []))

TEST_SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management",
        "required_industries": ["information technology & services"],
        "bonus_industries": ["computer software", "management consulting", "outsourcing/offshoring"],
        "required_keywords_contain": ["consulting", "IT"],
        "geo_must_contain": "miami",
        "forbidden_industries": ["apparel & fashion", "real estate", "banking"],
    },
    {
        "name": "TFP Fashion brands Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands",
        "required_industries": ["apparel & fashion"],
        "bonus_industries": ["luxury goods & jewelry", "retail", "design", "textiles"],
        "required_keywords_contain": ["fashion"],
        "geo_must_contain": "italy",
        "forbidden_industries": ["information technology & services", "real estate"],
    },
    {
        "name": "OnSocial Creator platforms UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution for influencer marketing",
        "required_industries": ["marketing & advertising"],
        "bonus_industries": ["internet", "online media", "media production", "entertainment"],
        "required_keywords_contain": ["influencer"],
        "geo_must_contain": "united kingdom",
        "forbidden_industries": ["apparel & fashion", "real estate", "accounting"],
    },
    {
        "name": "Crypto payments MENA",
        "query": "Fintech and cryptocurrency companies in UAE and Saudi Arabia",
        "offer": "Inxy — crypto payment processing platform for merchants",
        "required_industries": ["financial services"],
        "bonus_industries": ["internet", "banking", "computer software", "information technology & services"],
        "required_keywords_contain": ["crypto", "fintech"],
        "geo_must_contain": "arab",
        "forbidden_industries": ["apparel & fashion", "real estate"],
    },
    {
        "name": "Dev agencies Eastern Europe",
        "query": "Software development agencies and IT outsourcing companies in Poland and Ukraine",
        "offer": "Recruitment platform for tech companies",
        "required_industries": ["information technology & services"],
        "bonus_industries": ["computer software", "outsourcing/offshoring"],
        "required_keywords_contain": ["software", "development"],
        "geo_must_contain": "poland",
        "forbidden_industries": ["apparel & fashion", "real estate"],
    },
]

MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1-nano", "o3-mini"]

PROMPTS = {
    "p5_taxonomy_force_3plus": {
        "system": """Map this business query to Apollo.io filters.

APOLLO INDUSTRIES (use ONLY exact values from this list):
{industries}

CRITICAL RULES:
- apollo_industries: MUST pick 3-4 industries from the list. The PRIMARY industry + 2-3 ADJACENT industries where target companies might also be listed.
- apollo_keywords: 3-5 free-text terms describing the TARGET COMPANIES (not our product). What would they call themselves?
- Separate the user's SEGMENT query from their PRODUCT/OFFER. Keywords = what target companies do, NOT what we sell.

Return JSON:
{{"segments":[{{"label":"CAPS","apollo_industries":["industry1","industry2","industry3"],"apollo_keywords":["target_keyword1","target_keyword2"],"geo":"Location"}}]}}""",
        "user": "Segment to find: {query}\n(We sell: {offer} — but keywords should describe THEIR business, not ours)",
    },

    "p6_linkedin_perspective": {
        "system": """You are mapping a B2B search query to Apollo.io database filters.

Think: "If I'm looking for these companies on LinkedIn, what INDUSTRIES would they list? What KEYWORDS would their company page use?"

APOLLO INDUSTRIES (choose 3-4 from this EXACT list):
{industries}

Return JSON:
{{"segments":[{{"label":"CAPS","apollo_industries":["industry1","industry2","industry3"],"apollo_keywords":["keyword1","keyword2","keyword3"],"geo":"Location"}}]}}

Rules:
- Industries: pick the PRIMARY + adjacent ones (3-4 total)
- Keywords: what would the TARGET company write on LinkedIn? Not what we sell.
- Example: searching for "IT consulting in Miami" → industries: information technology & services, computer software, management consulting. Keywords: IT consulting, technology consulting, IT services""",
        "user": "Find: {query}\nContext: we sell {offer}",
    },

    "p7_coverage_maximizer": {
        "system": """Translate this query into Apollo.io search filters that MAXIMIZE coverage of target companies.

APOLLO INDUSTRIES (use EXACT strings, pick 3-5 that cover the target space):
{industries}

The goal: find as many relevant companies as possible. More industries = more coverage.
But ALL industries must be relevant to the query. Don't add random ones.

Think in concentric circles:
1. CORE industry (most direct match)
2. ADJACENT industries (where similar companies might be listed)
3. PERIPHERAL industries (where some targets might surprisingly be listed)

Return JSON:
{{"segments":[{{"label":"CAPS","apollo_industries":["core","adjacent1","adjacent2","peripheral"],"apollo_keywords":["broad_keyword1","broad_keyword2","specific_keyword"],"geo":"Location"}}]}}""",
        "user": "Query: {query}\nProduct context: {offer}",
    },

    "p8_structured_reasoning": {
        "system": """Map this query to Apollo.io filters. Think step by step.

Available Apollo Industries:
{industries}

Step 1: What type of companies is the user looking for?
Step 2: Which Apollo industries contain these companies? Pick the PRIMARY + 2-3 ADJACENT.
Step 3: What keywords would these companies use to describe themselves?
Step 4: What is the geographic filter?

IMPORTANT: Keywords should describe the TARGET companies, not the user's product.

Return ONLY the JSON (no reasoning text):
{{"segments":[{{"label":"CAPS","apollo_industries":["i1","i2","i3"],"apollo_keywords":["k1","k2","k3"],"geo":"Location"}}]}}""",
        "user": "Find: {query}\nOur product: {offer}",
    },
}


def score_result(result, test_case):
    if not result or not result.get("segments"):
        return {"total": 0, "details": ["no segments"]}

    seg = result["segments"][0]
    industries = [i.lower() for i in seg.get("apollo_industries", [])]
    keywords = [k.lower() for k in seg.get("apollo_keywords", [])]
    geo = (seg.get("geo", "") or "").lower()

    points, max_points = 0, 0
    details = []

    for req in test_case["required_industries"]:
        max_points += 30
        if req.lower() in industries:
            points += 30
            details.append(f"✓ required '{req}'")
        else:
            details.append(f"✗ MISSING '{req}'")

    bonus = 0
    for bon in test_case.get("bonus_industries", []):
        if bon.lower() in industries and bonus < 30:
            bonus += 10
            details.append(f"✓ bonus '{bon}'")
    max_points += 30
    points += bonus

    max_points += 10
    invalid = [i for i in industries if i not in VALID_INDUSTRIES]
    if not invalid:
        points += 10
        details.append(f"✓ all valid ({len(industries)})")
    else:
        details.append(f"✗ INVALID: {invalid}")

    max_points += 10
    forbidden = [i for i in industries if i in [f.lower() for f in test_case.get("forbidden_industries", [])]]
    if not forbidden:
        points += 10
    else:
        details.append(f"✗ FORBIDDEN: {forbidden}")

    for kp in test_case.get("required_keywords_contain", []):
        max_points += 10
        if any(kp.lower() in k for k in keywords):
            points += 10
        else:
            details.append(f"✗ keyword '{kp}' missing")

    max_points += 10
    gt = test_case.get("geo_must_contain", "").lower()
    if gt and gt in geo:
        points += 10
    elif gt:
        details.append(f"✗ geo '{geo}' missing '{gt}'")

    return {"total": int(points / max_points * 100) if max_points else 0,
            "points": points, "max": max_points, "industries": industries,
            "keywords": keywords, "geo": geo, "invalid": invalid, "details": details}


async def call_openai(model, system_prompt, user_prompt):
    try:
        body = {
            "model": model,
            "messages": [
                {"role": "system" if not model.startswith("o") else "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if model.startswith("o"):
            body["max_completion_tokens"] = 500
        else:
            body["max_tokens"] = 500
            body["temperature"] = 0

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json=body,
            )
            data = resp.json()
            if "error" in data:
                return None, data["error"].get("message", str(data["error"]))[:150]
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            # Try to find JSON in the response
            if not content.startswith("{"):
                import re
                m = re.search(r'\{.*\}', content, re.DOTALL)
                if m:
                    content = m.group(0)
            return json.loads(content), None
    except Exception as e:
        return None, str(e)[:150]


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_lines = []
    all_results = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log(f"INTENT ROUND 2 — {ts}")
    log(f"Models: {MODELS} | Prompts: {list(PROMPTS.keys())}")
    log(f"Setups: {len(MODELS) * len(PROMPTS)} × {len(TEST_SEGMENTS)} = {len(MODELS) * len(PROMPTS) * len(TEST_SEGMENTS)} calls")

    setup_scores = {}

    for model in MODELS:
        for pk, pt in PROMPTS.items():
            setup = f"{model} × {pk}"
            log(f"\n--- {setup} ---")
            scores = []

            for tc in TEST_SEGMENTS:
                sys_p = pt["system"].format(industries=INDUSTRIES_LIST)
                usr_p = pt["user"].format(query=tc["query"], offer=tc["offer"])

                t0 = time.time()
                result, err = await call_openai(model, sys_p, usr_p)
                elapsed = time.time() - t0

                if err:
                    log(f"  ❌ {tc['name']}: ERR ({elapsed:.1f}s) {err[:80]}")
                    scores.append(0)
                    all_results.append({"model": model, "prompt": pk, "seg": tc["name"], "error": err, "score": 0})
                    continue

                sc = score_result(result, tc)
                scores.append(sc["total"])
                icon = "✅" if sc["total"] >= 90 else "⚠️" if sc["total"] >= 70 else "❌"
                log(f"  {icon} {tc['name']}: {sc['total']}% ind={sc['industries']} kw={sc['keywords'][:3]} geo={sc['geo']}")
                for d in sc["details"]:
                    if "✗" in d:
                        log(f"     {d}")

                all_results.append({"model": model, "prompt": pk, "seg": tc["name"],
                                    "score": sc["total"], **sc})

            avg = sum(scores) / len(scores) if scores else 0
            setup_scores[setup] = avg
            log(f"  AVG: {avg:.0f}%")

    # Summary
    log("\n" + "=" * 90)
    sorted_s = sorted(setup_scores.items(), key=lambda x: -x[1])
    log(f"{'Setup':<40} {'AVG':>6}")
    log("-" * 48)
    for s, a in sorted_s:
        log(f"{s:<40} {a:>5.0f}%")

    log(f"\nBEST: {sorted_s[0][0]} ({sorted_s[0][1]:.0f}%)")
    log(f"\nTOP 5:")
    for i, (s, a) in enumerate(sorted_s[:5]):
        log(f"  {i+1}. {s} — {a:.0f}%")

    # Save
    log_file = TMP_DIR / f"{ts}_intent_round2.log"
    log_file.write_text("\n".join(log_lines))
    results_file = TMP_DIR / f"{ts}_intent_round2.json"
    results_file.write_text(json.dumps({
        "ts": ts, "results": all_results,
        "summary": dict(sorted_s), "best": sorted_s[0][0],
    }, indent=2, default=str))
    log(f"\nSaved: {log_file.name}, {results_file.name}")


if __name__ == "__main__":
    asyncio.run(main())
