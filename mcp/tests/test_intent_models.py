"""Test 20+ model×prompt setups for intent parsing (user prompt → Apollo filters).

This is THE bottleneck: if initial Apollo filters are wrong, everything downstream fails.
Tests which model+prompt combo best maps natural language to real Apollo taxonomy values.

Ground truth: for each segment, we know what Apollo industries + keywords should be returned.
Score = how many valid industries matched + keyword quality + no hallucinated industries.

Run:
    cd mcp && python3 tests/test_intent_models.py
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
TMP_DIR.mkdir(exist_ok=True)

# Load Apollo taxonomy
TAX_PATH = Path(__file__).parent.parent / "apollo_filters" / "apollo_taxonomy.json"
VALID_INDUSTRIES = set()
INDUSTRIES_LIST = ""
if TAX_PATH.exists():
    _td = json.loads(TAX_PATH.read_text())
    VALID_INDUSTRIES = {i.lower() for i in _td.get("industries", [])}
    INDUSTRIES_LIST = ", ".join(_td.get("industries", []))

# ═══════════════════════════════════════════════════════════════
# GROUND TRUTH — what Apollo filters SHOULD be generated
# ═══════════════════════════════════════════════════════════════

TEST_SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management",
        # Must-have industries (from Apollo taxonomy)
        "required_industries": ["information technology & services"],
        # Good-to-have industries
        "bonus_industries": ["computer software", "management consulting", "outsourcing/offshoring"],
        # Must-have keywords (free-text, case-insensitive partial match)
        "required_keywords_contain": ["consulting", "IT"],
        # Geo must contain
        "geo_must_contain": "miami",
        # Industries that should NOT appear (would indicate confusion)
        "forbidden_industries": ["apparel & fashion", "real estate", "banking"],
    },
    {
        "name": "TFP Fashion brands Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands, turns old stock and returns into revenue",
        "required_industries": ["apparel & fashion"],
        "bonus_industries": ["luxury goods & jewelry", "retail", "design", "textiles"],
        "required_keywords_contain": ["fashion"],
        "geo_must_contain": "italy",
        "forbidden_industries": ["information technology & services", "real estate"],
    },
    {
        "name": "OnSocial Creator platforms UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution for influencer marketing: discovery, analytics, social data API",
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

# ═══════════════════════════════════════════════════════════════
# MODELS TO TEST
# ═══════════════════════════════════════════════════════════════

MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o3-mini",
]

# ═══════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ═══════════════════════════════════════════════════════════════

PROMPTS = {
    "p1_taxonomy_strict": {
        "system": """You translate business queries into Apollo.io search filters.

APOLLO INDUSTRIES — use ONLY exact values from this list:
{industries}

Return ONLY valid JSON:
{{
  "segments": [{{
    "label": "CAPS_LABEL",
    "apollo_industries": ["exact industry from list above"],
    "apollo_keywords": ["free-text keyword1", "keyword2"],
    "geo": "City, State, Country"
  }}]
}}

Rules:
- apollo_industries: MUST be exact strings from the list. Pick 2-4 most relevant.
- apollo_keywords: free-text search terms, 3-7 tags, BROAD industry terms + synonyms
- geo: full location string""",
        "user": "Generate Apollo search filters for: {query}\nContext (what we sell): {offer}",
    },

    "p2_map_then_expand": {
        "system": """You are an Apollo.io filter expert. Your job:
1. MAP the user's query to the closest Apollo industry categories
2. ADD relevant keyword tags for free-text search
3. SET the geographic filter

VALID APOLLO INDUSTRIES (pick from this list ONLY):
{industries}

Return JSON:
{{
  "segments": [{{
    "label": "CAPS_LABEL",
    "apollo_industries": ["industry1", "industry2"],
    "apollo_keywords": ["keyword1", "keyword2", "keyword3"],
    "geo": "Location"
  }}]
}}

IMPORTANT:
- Industries must be EXACT matches from the list
- Pick the PRIMARY industry + 2-3 adjacent industries that would contain target companies
- Keywords should be what target companies would list on their profiles
- Think: "What would the target company call themselves on LinkedIn?"
""",
        "user": "Query: {query}\nOur product: {offer}",
    },

    "p3_buyer_focused": {
        "system": """Map this B2B query to Apollo.io filters. The goal is to find companies that would BUY our product.

APOLLO INDUSTRY LIST (use ONLY these exact strings):
{industries}

Think about WHO would buy our product:
- What industries are they in? (from the list above)
- What keywords describe their business? (free-text, broad)
- Where are they located?

Return JSON:
{{
  "segments": [{{
    "label": "CAPS_LABEL",
    "apollo_industries": ["exact industry 1", "exact industry 2"],
    "apollo_keywords": ["keyword1", "keyword2"],
    "geo": "Location"
  }}]
}}""",
        "user": "Find: {query}\nWe sell: {offer}",
    },

    "p4_minimal": {
        "system": """Apollo.io filter generator. Map query to filters.

Industries (EXACT values only): {industries}

JSON output:
{{"segments":[{{"label":"CAPS","apollo_industries":["from list"],"apollo_keywords":["free text"],"geo":"location"}}]}}""",
        "user": "{query} | Product: {offer}",
    },
}

# ═══════════════════════════════════════════════════════════════
# SCORING
# ═══════════════════════════════════════════════════════════════

def score_result(result, test_case):
    """Score a parsed result against ground truth. Returns 0-100."""
    if not result or not result.get("segments"):
        return {"total": 0, "details": "no segments returned"}

    seg = result["segments"][0]  # Take first segment
    industries = [i.lower() for i in seg.get("apollo_industries", [])]
    keywords = [k.lower() for k in seg.get("apollo_keywords", [])]
    geo = (seg.get("geo", "") or "").lower()

    points = 0
    max_points = 0
    details = []

    # 1. Required industries (30 pts each)
    for req in test_case["required_industries"]:
        max_points += 30
        if req.lower() in industries:
            points += 30
            details.append(f"✓ required industry '{req}'")
        else:
            details.append(f"✗ MISSING required industry '{req}'")

    # 2. Bonus industries (10 pts each, max 30)
    bonus_earned = 0
    for bon in test_case.get("bonus_industries", []):
        if bon.lower() in industries and bonus_earned < 30:
            bonus_earned += 10
            details.append(f"✓ bonus industry '{bon}'")
    max_points += 30
    points += bonus_earned

    # 3. All industries valid (from taxonomy) — 10 pts
    max_points += 10
    invalid = [i for i in industries if i not in VALID_INDUSTRIES]
    if not invalid:
        points += 10
        details.append(f"✓ all {len(industries)} industries valid")
    else:
        details.append(f"✗ INVALID industries: {invalid}")

    # 4. No forbidden industries — 10 pts
    max_points += 10
    forbidden_found = [i for i in industries if i in [f.lower() for f in test_case.get("forbidden_industries", [])]]
    if not forbidden_found:
        points += 10
        details.append("✓ no forbidden industries")
    else:
        details.append(f"✗ FORBIDDEN industries present: {forbidden_found}")

    # 5. Required keyword patterns (10 pts each)
    for kw_pattern in test_case.get("required_keywords_contain", []):
        max_points += 10
        if any(kw_pattern.lower() in k for k in keywords):
            points += 10
            details.append(f"✓ keyword contains '{kw_pattern}'")
        else:
            details.append(f"✗ MISSING keyword '{kw_pattern}'")

    # 6. Geo match — 10 pts
    max_points += 10
    geo_target = test_case.get("geo_must_contain", "").lower()
    if geo_target and geo_target in geo:
        points += 10
        details.append(f"✓ geo contains '{geo_target}'")
    elif geo_target:
        details.append(f"✗ geo '{geo}' missing '{geo_target}'")

    pct = int(points / max_points * 100) if max_points > 0 else 0
    return {
        "total": pct,
        "points": points,
        "max_points": max_points,
        "industries": industries,
        "keywords": keywords,
        "geo": geo,
        "invalid_industries": invalid,
        "details": details,
    }


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def call_openai(model, system_prompt, user_prompt):
    """Call OpenAI API. Returns parsed JSON or None."""
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0,
        }

        # o3-mini doesn't support system messages the same way
        if model.startswith("o"):
            body.pop("temperature", None)

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json=body,
            )
            data = resp.json()
            if "error" in data:
                return None, data["error"].get("message", str(data["error"]))
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content), None
    except Exception as e:
        return None, str(e)


async def run_all():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = TMP_DIR / f"{ts}_intent_model_test.log"
    results_file = TMP_DIR / f"{ts}_intent_model_test.json"

    lines = []
    def log(msg):
        print(msg)
        lines.append(msg)

    log("=" * 100)
    log(f"INTENT PARSER MODEL TEST — {ts}")
    log(f"Models: {MODELS}")
    log(f"Prompts: {list(PROMPTS.keys())}")
    log(f"Segments: {[s['name'] for s in TEST_SEGMENTS]}")
    log(f"Total setups: {len(MODELS) * len(PROMPTS)} × {len(TEST_SEGMENTS)} segments = {len(MODELS) * len(PROMPTS) * len(TEST_SEGMENTS)} calls")
    log(f"Apollo taxonomy: {len(VALID_INDUSTRIES)} industries")
    log("=" * 100)

    all_results = []
    setup_scores = {}  # setup_name -> list of scores

    for model in MODELS:
        for pk, pt in PROMPTS.items():
            setup = f"{model} × {pk}"
            log(f"\n{'='*60}")
            log(f"  {setup}")
            log(f"{'='*60}")

            scores = []

            for tc in TEST_SEGMENTS:
                sys_prompt = pt["system"].format(industries=INDUSTRIES_LIST)
                usr_prompt = pt["user"].format(query=tc["query"], offer=tc["offer"])

                t0 = time.time()
                result, err = await call_openai(model, sys_prompt, usr_prompt)
                elapsed = time.time() - t0

                if err:
                    log(f"  {tc['name']}: ERROR ({elapsed:.1f}s) — {err[:100]}")
                    scores.append(0)
                    all_results.append({
                        "model": model, "prompt": pk, "segment": tc["name"],
                        "error": err, "score": 0, "time": elapsed,
                    })
                    continue

                sc = score_result(result, tc)
                scores.append(sc["total"])

                status = "✅" if sc["total"] >= 90 else "⚠️" if sc["total"] >= 70 else "❌"
                log(f"  {status} {tc['name']}: {sc['total']}% ({sc['points']}/{sc['max_points']}pts) [{elapsed:.1f}s]")
                log(f"     industries: {sc['industries']}")
                log(f"     keywords: {sc['keywords']}")
                log(f"     geo: {sc['geo']}")
                if sc.get("invalid_industries"):
                    log(f"     ⚠ INVALID: {sc['invalid_industries']}")
                for d in sc["details"]:
                    if "✗" in d:
                        log(f"     {d}")

                all_results.append({
                    "model": model, "prompt": pk, "segment": tc["name"],
                    "score": sc["total"], "points": sc["points"], "max": sc["max_points"],
                    "industries": sc["industries"], "keywords": sc["keywords"],
                    "geo": sc["geo"], "invalid": sc.get("invalid_industries", []),
                    "details": sc["details"], "time": elapsed,
                })

            avg = sum(scores) / len(scores) if scores else 0
            setup_scores[setup] = {"avg": avg, "scores": scores, "model": model, "prompt": pk}
            log(f"  AVG: {avg:.0f}%")

    # ═══════════════ SUMMARY TABLE ═══════════════
    log("\n" + "=" * 100)
    log("SUMMARY — Average score across all segments")
    log("=" * 100)

    header = f"{'Setup':<40}"
    for tc in TEST_SEGMENTS:
        short = tc["name"][:12]
        header += f" {short:>12}"
    header += f" {'AVG':>8}"
    log(header)
    log("-" * (40 + 13 * len(TEST_SEGMENTS) + 9))

    # Sort by avg score descending
    sorted_setups = sorted(setup_scores.items(), key=lambda x: -x[1]["avg"])

    for setup, data in sorted_setups:
        row = f"{setup:<40}"
        for i, tc in enumerate(TEST_SEGMENTS):
            sc = data["scores"][i] if i < len(data["scores"]) else 0
            row += f" {sc:>11}%"
        row += f" {data['avg']:>7.0f}%"
        log(row)

    best_setup = sorted_setups[0][0] if sorted_setups else "none"
    best_avg = sorted_setups[0][1]["avg"] if sorted_setups else 0
    log(f"\nBEST: {best_setup} ({best_avg:.0f}%)")

    # Top 3
    log("\nTOP 3:")
    for i, (setup, data) in enumerate(sorted_setups[:3]):
        log(f"  {i+1}. {setup} — {data['avg']:.0f}%")

    # Save everything
    log_file.write_text("\n".join(lines))
    results_file.write_text(json.dumps({
        "timestamp": ts,
        "models": MODELS,
        "prompts": list(PROMPTS.keys()),
        "segments": [s["name"] for s in TEST_SEGMENTS],
        "total_setups": len(MODELS) * len(PROMPTS),
        "results": all_results,
        "summary": {k: {"avg": v["avg"], "scores": v["scores"]} for k, v in sorted_setups},
        "best_setup": best_setup,
        "best_score": best_avg,
    }, indent=2, default=str))

    log(f"\nLog: {log_file.name}")
    log(f"Results: {results_file.name}")


if __name__ == "__main__":
    if not OPENAI_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)
    asyncio.run(run_all())
