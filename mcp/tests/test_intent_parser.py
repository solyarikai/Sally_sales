"""Test intent parser — verifies user queries map to REAL Apollo taxonomy values.

Run:
    cd mcp && python3 tests/test_intent_parser.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and len(v) > 3:
                os.environ.setdefault(k, v)

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Load taxonomy for validation
TAX_PATH = Path(__file__).parent.parent / "apollo_filters" / "apollo_taxonomy.json"
VALID_INDUSTRIES = set()
if TAX_PATH.exists():
    VALID_INDUSTRIES = set(json.loads(TAX_PATH.read_text()).get("industries", []))

TEST_CASES = [
    {
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — payroll and contractor management platform",
        "expected_industries": ["information technology & services"],  # at minimum
        "expected_geo_contains": "Miami",
    },
    {
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands",
        "expected_industries": ["apparel & fashion"],
        "expected_geo_contains": "Italy",
    },
    {
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data and analytics for influencer marketing",
        "expected_industries": ["marketing & advertising"],
        "expected_geo_contains": "United Kingdom",
    },
    {
        "query": "SaaS companies in Germany",
        "offer": "Payment processing platform",
        "expected_industries": ["computer software", "internet"],
        "expected_geo_contains": "Germany",
    },
    {
        "query": "Real estate agencies in Dubai",
        "offer": "CRM for real estate",
        "expected_industries": ["real estate"],
        "expected_geo_contains": "Dubai",
    },
]


async def main():
    from app.services.intent_parser import parse_gathering_intent, _APOLLO_INDUSTRIES

    print(f"Apollo taxonomy loaded: {len(_APOLLO_INDUSTRIES)} industries")
    print(f"Valid industries sample: {_APOLLO_INDUSTRIES[:5]}...")
    print()

    all_pass = True

    for tc in TEST_CASES:
        print(f"--- Query: {tc['query']} ---")
        result = await parse_gathering_intent(
            query=tc["query"],
            user_offer=tc["offer"],
            openai_key=OPENAI_KEY,
        )

        if not result or not result.get("segments"):
            print(f"  FAIL: no segments returned")
            all_pass = False
            continue

        for seg in result["segments"]:
            label = seg.get("label", "?")
            industries = seg.get("apollo_industries", [])
            keywords = seg.get("apollo_keywords", [])
            geo = seg.get("geo", "")

            print(f"  Segment: {label}")
            print(f"  Industries: {industries}")
            print(f"  Keywords: {keywords}")
            print(f"  Geo: {geo}")

            # Check industries are from taxonomy
            invalid = [i for i in industries if i.lower() not in {v.lower() for v in VALID_INDUSTRIES}]
            if invalid:
                print(f"  WARN: Industries NOT in taxonomy: {invalid}")

            valid_count = len(industries) - len(invalid)
            print(f"  Valid industries: {valid_count}/{len(industries)}")

            # Check expected industries present
            for exp in tc.get("expected_industries", []):
                found = any(exp.lower() in i.lower() for i in industries)
                if found:
                    print(f"  ✓ Expected '{exp}' found")
                else:
                    print(f"  ✗ Expected '{exp}' NOT found")
                    all_pass = False

            # Check geo
            if tc.get("expected_geo_contains"):
                if tc["expected_geo_contains"].lower() in geo.lower():
                    print(f"  ✓ Geo contains '{tc['expected_geo_contains']}'")
                else:
                    print(f"  ✗ Geo '{geo}' missing '{tc['expected_geo_contains']}'")
                    all_pass = False

        print()

    print("=" * 60)
    print(f"{'ALL PASS' if all_pass else 'SOME FAILURES'}")


if __name__ == "__main__":
    asyncio.run(main())
