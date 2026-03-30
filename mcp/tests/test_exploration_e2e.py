"""E2E test of exploration_service._classify_targets with the updated prompt.

Tests the ACTUAL function from exploration_service.py (not a copy of the prompt).
Verifies accuracy against ground truth for all 3 segments.

Run:
    cd mcp && python3 tests/test_exploration_e2e.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

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
CACHE_DIR = Path(__file__).parent / "tmp" / "exploration_cache"
TMP_DIR = Path(__file__).parent / "tmp"

GROUND_TRUTH = {
    "EasyStaff IT consulting Miami": {
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management. Helps companies hire and pay contractors worldwide.",
        "expected": {
            "synergybc.com": True, "smxusa.com": True, "koombea.com": True,
            "flatiron.software": True, "therocketcode.com": True, "avalith.net": True,
            "bluecoding.com": True, "shokworks.io": True,
        },
    },
    "TFP Fashion brands Italy": {
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform that turns old stock, returns and pre-owned into revenue for fashion brands.",
        "expected": {
            "trussardi.com": True, "marni.com": True, "elisabettafranchi.com": True,
            "ermannoscervino.com": True, "patriziapepe.com": True, "kiton.com": True,
            "herno.com": True, "soeur.fr": False, "fabianafilippi.com": True,
            "giuseppezanotti.com": True,
        },
    },
    "OnSocial Creator platforms UK": {
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution. Creator Discovery, Creator Analytics, Social Data API, Sponsored Posts tracking. Target: platforms, agencies, brands that DO influencer marketing.",
        "expected": {
            "thenewgen.com": True, "sixteenth.com": True, "seenconnects.com": True,
            "found.co.uk": False, "musetheagency.com": True, "unravelapp.com": False,
            "inthestyle.com": True, "dexerto.media": False, "majorplayers.co.uk": False,
            "lindafarrow.com": False,
        },
    },
}


async def main():
    from app.services.exploration_service import _classify_targets

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"E2E EXPLORATION TEST — {ts}")
    print(f"Testing actual _classify_targets() from exploration_service.py")
    print("=" * 80)

    total_correct = 0
    total_total = 0

    for seg_name, config in GROUND_TRUTH.items():
        print(f"\n--- {seg_name} ---")

        # Load cached scrape data
        companies = []
        for domain in config["expected"]:
            cache_file = CACHE_DIR / f"scrape_{domain.replace('.', '_').replace('/', '_')}.json"
            if cache_file.exists():
                data = json.loads(cache_file.read_text())
                companies.append({
                    "domain": domain,
                    "primary_domain": domain,
                    "name": domain.split(".")[0].title(),
                    "scraped_text": data.get("text", "")[:3000],
                })
            else:
                print(f"  WARN: no cache for {domain}")

        if not companies:
            print(f"  SKIP — no cached data")
            continue

        print(f"  Companies: {len(companies)}")

        # Call the ACTUAL function
        targets = await _classify_targets(
            companies, config["query"], config["offer"], OPENAI_KEY
        )

        target_domains = set()
        for t in targets:
            d = t.get("domain", t.get("primary_domain", ""))
            if not d and "classification" in t:
                d = t["classification"].get("domain", "")
            target_domains.add(d)

        # Score against ground truth
        correct = 0
        total = 0
        fp = []
        fn = []

        for domain, expected in config["expected"].items():
            actual = domain in target_domains
            total += 1
            if actual == expected:
                correct += 1
            elif actual and not expected:
                fp.append(domain)
            else:
                fn.append(domain)

        accuracy = correct / total if total else 0
        total_correct += correct
        total_total += total

        status = "PASS" if accuracy >= 0.9 else "FAIL"
        print(f"  {status}: {correct}/{total} ({accuracy*100:.0f}%) — targets={len(target_domains)}/{len(companies)}")

        if fp:
            print(f"  False positives: {fp}")
        if fn:
            print(f"  False negatives: {fn}")

        for t in targets:
            d = t.get("domain", t.get("primary_domain", ""))
            cls = t.get("classification", {})
            seg = cls.get("segment", "?")
            print(f"    ✓ {d} [{seg}]")

    # Overall
    overall = total_correct / total_total if total_total else 0
    print(f"\n{'='*80}")
    print(f"OVERALL: {total_correct}/{total_total} ({overall*100:.0f}%)")
    status = "ALL PASS" if overall >= 0.95 else "NEEDS WORK"
    print(f"STATUS: {status}")

    # Save
    out = TMP_DIR / f"{ts}_exploration_e2e.json"
    out.write_text(json.dumps({
        "timestamp": ts, "overall_accuracy": overall,
        "correct": total_correct, "total": total_total,
    }, indent=2))
    print(f"Saved: {out.name}")


if __name__ == "__main__":
    asyncio.run(main())
