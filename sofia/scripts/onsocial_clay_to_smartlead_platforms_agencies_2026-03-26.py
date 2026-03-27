#!/usr/bin/env python3
"""
OnSocial Clay→SmartLead Pipeline (Platforms + Agencies, 2026-03-26)

Full pipeline: Clay discovery → GPT classification → Apollo People Search →
FindyMail email enrichment → SmartLead upload with regional social_proof.

Steps 0-8: backend API on Hetzner (with checkpoints + Claude Code review).
Steps 9-12: Apollo + FindyMail + SmartLead (local on Hetzner).

Segments: INFLUENCER_PLATFORMS, IM_FIRST_AGENCIES (4 geo tiers each).

Usage (run on Hetzner via SSH):

  cd ~/magnum-opus-project/repo

  # Full pipeline from scratch
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --segment platforms_tier12

  # Resume from specific step
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --from-step scrape --run-id 150

  # Re-analyze with different prompt
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --re-analyze --run-id 150 --prompt-file prompts/v2.txt

  # Dry run
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --dry-run --segment platforms_tier12

Env vars: APOLLO_API_KEY, FINDYMAIL_API_KEY, SMARTLEAD_API_KEY
Backend must be running on localhost:8001 (Hetzner)
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# ── PATHS ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
SOFIA_DIR = SCRIPT_DIR.parent
STATE_DIR = SOFIA_DIR.parent / "state" / "onsocial" / "v4"
STATE_DIR.mkdir(parents=True, exist_ok=True)

CSV_DIR = SOFIA_DIR / "output" / "OnSocial" / "v4"
CSV_DIR.mkdir(parents=True, exist_ok=True)

# State files
TARGETS_FILE = STATE_DIR / "targets.json"
CONTACTS_FILE = STATE_DIR / "contacts.json"
CONTACTS_CACHE = STATE_DIR / "contacts_cache.json"
ENRICHED_FILE = STATE_DIR / "enriched.json"
FINDYMAIL_PROGRESS = STATE_DIR / "findymail_progress.json"
UPLOAD_LOG = STATE_DIR / "upload_log.json"
RUN_STATE = STATE_DIR / "run_state.json"  # tracks current run_id + phase

# ── API CONFIG ────────────────────────────────────────────────────────────────
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://localhost:8000")
BACKEND_HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
APOLLO_BASE = "https://api.apollo.io/api/v1"

FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
FINDYMAIL_BASE = "https://app.findymail.com"
FINDYMAIL_CONCURRENT = 5

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"

SMARTLEAD_EMAIL_ACCOUNTS = [
    2718958, 2718959, 2718960, 2718961, 2718962,
    2718963, 2718964, 2718965, 2718966, 2718967,
    2718968, 2718969, 2718970, 2718971,
]

PROJECT_ID = 42
MAX_CONTACTS_PER_COMPANY = 3
SENIORITIES = ["owner", "founder", "c_suite", "vp", "head", "director"]

# ── SOCIAL PROOF BY REGION ────────────────────────────────────────────────────

SOCIAL_PROOF = {
    "INFLUENCER_PLATFORMS": {
        "United Kingdom": "Whalar and Billion Dollar Boy",
        "Germany": "Zalando and Intermate",
        "France": "Kolsquare, Skeepers, and Favikon",
        "India": "Phyllo and KlugKlug",
        "Australia": "TRIBEGroup",
        "Spain": "SAMY Alliance",
        "United Arab Emirates": "ArabyAds and Sociata",
        "Saudi Arabia": "ArabyAds and Sociata",
        "Egypt": "ArabyAds and Sociata",
        "Turkey": "ArabyAds and Sociata",
        "Israel": "ArabyAds and Sociata",
        "Brazil": "Modash and Captiv8",
        "Mexico": "Modash and Captiv8",
        "Colombia": "Modash and Captiv8",
        "Argentina": "Modash and Captiv8",
        "_default": "Modash, Captiv8, and Lefty",
    },
    "IM_FIRST_AGENCIES": {
        "United Kingdom": "Whalar and Billion Dollar Boy",
        "Germany": "Linkster and Gocomo",
        "France": "Ykone and Skeepers",
        "India": "Qoruz and Tonic Worldwide",
        "Australia": "TRIBEGroup",
        "Spain": "SAMY Alliance",
        "United Arab Emirates": "ArabyAds and Sociata",
        "Saudi Arabia": "ArabyAds and Sociata",
        "Egypt": "ArabyAds and Sociata",
        "Turkey": "ArabyAds and Sociata",
        "Israel": "ArabyAds and Sociata",
        "Brazil": "Viral Nation and Captiv8",
        "Mexico": "Viral Nation and Captiv8",
        "Colombia": "Viral Nation and Captiv8",
        "Argentina": "Viral Nation and Captiv8",
        "_default": "Viral Nation and Obviously",
    },
}

# ── TITLES BY SEGMENT ─────────────────────────────────────────────────────────

TITLES = {
    "INFLUENCER_PLATFORMS": [
        "CTO", "VP Engineering", "VP of Engineering", "Head of Engineering",
        "Head of Product", "Chief Product Officer", "VP Product",
        "Director of Engineering", "Director of Product",
        "Co-Founder", "Founder", "CEO", "COO",
    ],
    "IM_FIRST_AGENCIES": [
        "CEO", "Founder", "Co-Founder", "Managing Director", "Managing Partner",
        "Head of Influencer Marketing", "Director of Influencer",
        "Head of Influencer", "VP Strategy", "Head of Partnerships",
        "Director of Client Services", "Head of Strategy",
        "General Manager", "Partner", "Owner",
    ],
}

# ── CLAY FILTER CONFIGS ──────────────────────────────────────────────────────

CLAY_FILTERS = {
    "platforms_tier12": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "These are platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools. "
                "Examples: Modash, Captiv8, Lefty, Kolsquare, Skeepers, Favikon, Phyllo, KlugKlug, The Shelf, impact.com. "
                "NOT: recruitment agencies, PR agencies, generic SMM agencies, web design, SEO/PPC agencies, consulting, fintech. "
                "Key characteristic: company HAS its own technology product (platform/SaaS/API) for influencer/creator data or analytics."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": [
                "United States", "United Kingdom", "Germany", "Netherlands", "France",
                "Canada", "Australia", "Spain", "Italy", "Sweden", "Denmark", "Belgium",
                "United Arab Emirates", "Saudi Arabia", "Egypt", "Turkey", "Israel",
            ],
            "minimum_member_count": 10,
            "maximum_member_count": 5000,
            "max_results": 5000,
        },
    },
    "platforms_tier34": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, social listening, UGC, creator data APIs. "
                "Examples: Modash, Captiv8, Phyllo, KlugKlug. "
                "NOT: recruitment, PR, web design, SEO, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services"],
            "country_names": ["India", "Brazil", "Mexico", "Colombia", "Argentina"],
            "minimum_member_count": 10,
            "maximum_member_count": 5000,
            "max_results": 2000,
        },
    },
    "agencies_tier12": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in launching campaigns with influencers, managing creator contracts, TikTok/Instagram/YouTube campaigns. "
                "Examples: Viral Nation, Obviously, Ykone, Billion Dollar Boy, SAMY Alliance, TRIBEGroup, Whalar, Intermate, Brighter Click. "
                "NOT: PR agencies, generic digital agencies, SEO/PPC, marketing holdings (WPP, Omnicom, HAVAS, Publicis, Mindshare), "
                "freelancers, agencies under 10 people, web studios, consulting firms. "
                "Key: influencer marketing or creator marketing explicitly stated as core service. Size 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": [
                "United States", "United Kingdom", "Germany", "Netherlands", "France",
                "Australia", "Canada", "Spain", "Belgium", "Denmark",
                "United Arab Emirates", "Saudi Arabia", "Egypt", "Turkey", "Israel",
            ],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 5000,
        },
    },
    "agencies_tier34": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube. "
                "Examples: Viral Nation, Qoruz, Tonic Worldwide, SAMY Alliance. "
                "NOT: PR, digital agencies, SEO/PPC, holdings, freelancers, <10 people, web studios. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["India", "Brazil", "Mexico", "Colombia", "Argentina"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 2000,
        },
    },
}

# ── CLASSIFICATION PROMPT ─────────────────────────────────────────────────────
# Used in Step 5 (Analyze). Same logic as GOD_pipeline CLASSIFICATION_PROMPT.
# Can be overridden with --prompt-file.

DEFAULT_ANALYSIS_PROMPT = """\
You classify companies as potential customers of OnSocial — a B2B API
that provides creator/influencer data for Instagram, TikTok, and YouTube
(audience demographics, engagement analytics, fake follower detection,
creator search).

Companies that need OnSocial are those whose CORE business involves
working with social media creators.

== STEP 1: INSTANT DISQUALIFIERS ==
- website_content is EMPTY and no description → "OTHER | No data available"
- Domain is parked / for sale / dead → "OTHER | Domain inactive"
- 5000+ employees → "OTHER | Enterprise, too large"
- <10 employees → "OTHER | Too small"

If none triggered → continue to Step 2.

== STEP 2: SEGMENTS ==

INFLUENCER_PLATFORMS
  Builds SaaS / software / tools for influencer marketing: analytics,
  creator discovery, campaign management, creator CRM, UGC content
  platforms, creator marketplaces, creator monetization tools, social
  commerce, live shopping platforms, social listening with creator focus.
  KEY TEST: they have a PRODUCT (software/platform/API) that brands or
  agencies use to find, analyze, manage, or pay creators.

IM_FIRST_AGENCIES
  Agency where influencer/creator campaigns are THE primary business,
  not a side service. 10-500 employees. Includes: influencer-first
  agencies, MCN (multi-channel networks), creator talent management,
  gaming influencer agencies, UGC production agencies.
  KEY TEST: 60%+ of their visible offering (homepage, case studies,
  team titles) is about creator/influencer work.

OTHER
  Everything that does NOT fit above. Includes: generic digital agencies,
  PR firms, SEO/PPC shops, web development, e-commerce brands (unless
  they BUILD creator tools), consulting, recruitment, fintech, etc.

== STEP 3: CONFLICT RESOLUTION ==
- Company does BOTH agency work AND has a SaaS product → INFLUENCER_PLATFORMS
  (product companies are higher-value targets)
- Company is a "full-service digital agency" that also does IM → OTHER
  (not IM-first, IM is a side service)
- Company description mentions "influencer" but core is PR → OTHER
- Company is an affiliate network without creator focus → OTHER

== OUTPUT FORMAT (strict) ==
SEGMENT | confidence (0.0-1.0) | one-line reasoning

Examples:
INFLUENCER_PLATFORMS | 0.92 | SaaS platform for influencer discovery and analytics
IM_FIRST_AGENCIES | 0.85 | Agency specializing in TikTok creator campaigns, 50 employees
OTHER | 0.95 | Generic digital marketing agency, IM is one of 8 services listed
"""


# ── HELPERS ───────────────────────────────────────────────────────────────────

def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def save_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → CSV: {path.name} ({len(rows)} rows)")

def normalize_company(name: str) -> str:
    for suffix in [" Inc", " Inc.", " LLC", " Ltd", " Ltd.", " GmbH", " Corp", " Corp.", " S.A.", " S.L."]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def tag() -> str:
    return datetime.now().strftime("%b%d")

def api(method: str, path: str, **kwargs) -> dict:
    """Call backend API."""
    url = f"{BACKEND_BASE}/api{path}"
    r = getattr(httpx, method)(url, headers=BACKEND_HEADERS, timeout=300, **kwargs)
    if r.status_code >= 400:
        print(f"  API ERROR {r.status_code}: {r.text[:500]}")
        sys.exit(1)
    return r.json()

def get_social_proof(country: str, segment: str) -> str:
    table = SOCIAL_PROOF.get(segment, SOCIAL_PROOF["INFLUENCER_PLATFORMS"])
    return table.get(country, table["_default"])

def save_state(run_id: int, phase: str, gate_id: int = None, config_key: str = ""):
    save_json(RUN_STATE, {"run_id": run_id, "phase": phase, "gate_id": gate_id,
                           "config_key": config_key, "updated_at": ts()})

def load_state() -> dict:
    return load_json(RUN_STATE) or {}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: START GATHERING (Clay)
# ══════════════════════════════════════════════════════════════════════════════

def step0_start(config_key: str, project_id: int = PROJECT_ID) -> int:
    """Start Clay gathering via backend API. Returns run_id."""
    config = CLAY_FILTERS[config_key]
    print(f"\n{'='*60}")
    print(f"STEP 0: Clay Gathering — {config_key}")
    print(f"  Segment: {config['segment']}")
    print(f"  Countries: {', '.join(config['filters'].get('country_names', []))}")
    print(f"  Max results: {config['filters'].get('max_results', 5000)}")
    print(f"{'='*60}")

    result = api("post", "/pipeline/gathering/start", json={
        "project_id": project_id,
        "source_type": "clay.companies.emulator",
        "filters": config["filters"],
        "triggered_by": "operator",
        "input_mode": "structured",
        "notes": f"v4 pipeline — {config_key}",
    })

    run_id = result["id"]
    print(f"\n  Run created: #{run_id}")
    print(f"  Status: {result['status']} / {result['current_phase']}")
    save_state(run_id, "started", config_key=config_key)
    return run_id


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1-2: BLACKLIST → CP1
# ══════════════════════════════════════════════════════════════════════════════

def step2_blacklist(run_id: int) -> dict:
    """Run blacklist check → creates CP1 gate."""
    print(f"\n{'='*60}")
    print(f"STEP 2: Blacklist Check (run #{run_id})")
    print(f"{'='*60}")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/blacklist-check")
    print(f"  Phase: {result.get('current_phase', '?')}")

    # Get pending gate
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        save_state(run_id, "awaiting_scope_ok", gate_id=gate_id)
        print(f"\n  ★ CHECKPOINT 1 — gate #{gate_id}")
        print(f"  Scope: {json.dumps(gate.get('scope', {}), indent=2)[:1000]}")
        return {"gate_id": gate_id, "scope": gate.get("scope", {})}
    return {}


def approve_gate(gate_id: int, note: str = "Approved by Claude Code") -> dict:
    """Approve a checkpoint gate."""
    result = api("post", f"/pipeline/gathering/approval-gates/{gate_id}/approve",
                 json={"decision_note": note})
    print(f"  Gate #{gate_id} approved")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3-4: PRE-FILTER + SCRAPE
# ══════════════════════════════════════════════════════════════════════════════

def step3_prefilter(run_id: int) -> dict:
    print(f"\n{'='*60}")
    print(f"STEP 3: Pre-filter (run #{run_id})")
    print(f"{'='*60}")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/pre-filter")
    print(f"  Phase: {result.get('current_phase', '?')}")
    save_state(run_id, "pre_filtered")
    return result


def step4_scrape(run_id: int) -> dict:
    print(f"\n{'='*60}")
    print(f"STEP 4: Scrape websites (run #{run_id})")
    print(f"  This may take 10-30 minutes...")
    print(f"{'='*60}")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/scrape")
    print(f"  Phase: {result.get('current_phase', '?')}")
    save_state(run_id, "scraped")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: ANALYZE (GPT) → CP2  — with re-analyze loop
# ══════════════════════════════════════════════════════════════════════════════

def step5_analyze(run_id: int, prompt_text: str, model: str = "gpt-4o-mini") -> dict:
    """Run GPT analysis. Returns gate info for CP2."""
    print(f"\n{'='*60}")
    print(f"STEP 5: Analyze (run #{run_id})")
    print(f"  Model: {model}")
    print(f"  Prompt: {prompt_text[:100]}...")
    print(f"{'='*60}")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/analyze",
                 params={"prompt_text": prompt_text, "model": model})

    target_rate = result.get("target_rate", 0)
    targets_count = result.get("targets_count", 0)
    total_analyzed = result.get("total_analyzed", 0)

    print(f"\n  Analyzed: {total_analyzed}")
    print(f"  Targets: {targets_count} ({target_rate*100:.1f}%)")

    # Get CP2 gate
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        save_state(run_id, "awaiting_targets_ok", gate_id=gate_id)

        # Output for Claude Code review
        print(f"\n  ★ CHECKPOINT 2 — gate #{gate_id}")
        print(f"  Target rate: {target_rate*100:.1f}%")
        print(f"  Review targets and decide:")
        print(f"    - approve: target rate OK, proceed to FindyMail")
        print(f"    - re-analyze: try different prompt")
        print(f"    - cancel: abort this run")

        return {
            "gate_id": gate_id,
            "target_rate": target_rate,
            "targets_count": targets_count,
            "total_analyzed": total_analyzed,
        }
    return {"target_rate": target_rate, "targets_count": targets_count}


def step5_reanalyze(run_id: int, prompt_text: str, model: str = "gpt-4o-mini") -> dict:
    """Re-run analysis with different prompt (no re-scrape needed)."""
    print(f"\n{'='*60}")
    print(f"STEP 5 (RE-ANALYZE): run #{run_id}")
    print(f"  New prompt: {prompt_text[:100]}...")
    print(f"{'='*60}")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/re-analyze",
                 params={"prompt_text": prompt_text, "model": model})

    target_rate = result.get("target_rate", 0)
    targets_count = result.get("targets_count", 0)

    print(f"\n  New target rate: {target_rate*100:.1f}%")
    print(f"  Targets: {targets_count}")

    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate_id = pending[0]["id"]
        save_state(run_id, "awaiting_targets_ok", gate_id=gate_id)
        return {"gate_id": gate_id, "target_rate": target_rate, "targets_count": targets_count}
    return {"target_rate": target_rate, "targets_count": targets_count}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6-8: VERIFY (FindyMail via backend) → CP3
# ══════════════════════════════════════════════════════════════════════════════

def step6_prepare_verify(run_id: int) -> dict:
    """Prepare FindyMail verification → creates CP3 with cost estimate."""
    print(f"\n{'='*60}")
    print(f"STEP 6: Prepare Verification (run #{run_id})")
    print(f"{'='*60}")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/prepare-verification")

    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        scope = gate.get("scope", {})
        save_state(run_id, "awaiting_verify_ok", gate_id=gate_id)

        print(f"\n  ★ CHECKPOINT 3 — gate #{gate_id}")
        print(f"  Emails to verify: {scope.get('emails_to_verify', '?')}")
        print(f"  Estimated cost: ${scope.get('estimated_cost_usd', '?')}")
        return {"gate_id": gate_id, "scope": scope}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: EXPORT TARGETS FROM DB
# ══════════════════════════════════════════════════════════════════════════════

def step9_export_targets(project_id: int, force: bool = False) -> list[dict]:
    """Export approved targets from backend DB."""
    print(f"\n{'='*60}")
    print(f"STEP 9: Export Targets (project_id={project_id})")
    print(f"{'='*60}")

    if TARGETS_FILE.exists() and not force:
        targets = load_json(TARGETS_FILE)
        print(f"  Loaded from cache: {len(targets)} targets")
        return targets

    # Try API first
    try:
        r = httpx.get(
            f"{BACKEND_BASE}/api/pipeline/gathering/targets/",
            params={"project_id": project_id, "is_target": True},
            headers=BACKEND_HEADERS, timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            targets = data if isinstance(data, list) else data.get("items", data.get("targets", []))
        else:
            targets = _export_targets_db(project_id)
    except Exception:
        targets = _export_targets_db(project_id)

    if not targets:
        print("  No targets found. Complete backend pipeline first (Steps 0-8).")
        sys.exit(1)

    save_json(TARGETS_FILE, targets)
    segments = {}
    for t in targets:
        seg = t.get("segment", t.get("analysis_segment", "UNKNOWN"))
        segments[seg] = segments.get(seg, 0) + 1
    print(f"  Exported: {len(targets)} targets")
    for seg, cnt in sorted(segments.items()):
        print(f"    {seg}: {cnt}")
    return targets


def _export_targets_db(project_id: int) -> list[dict]:
    """Fallback: export via psql on Hetzner."""
    import subprocess
    sql = (
        f"SELECT domain, name, country, employee_count, analysis_segment, analysis_confidence "
        f"FROM discovered_companies WHERE project_id={project_id} AND is_target=true"
    )
    cmd = f'docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -F \'|\' -c "{sql}"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        targets = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                targets.append({
                    "domain": parts[0].strip(),
                    "company_name": parts[1].strip(),
                    "country": parts[2].strip(),
                    "employees": parts[3].strip(),
                    "segment": parts[4].strip(),
                    "confidence": parts[5].strip() if len(parts) > 5 else "",
                })
        return targets
    except Exception as e:
        print(f"  DB export error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: APOLLO PEOPLE SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def search_people(domain: str, titles: list[str]) -> list[dict]:
    try:
        r = httpx.post(
            f"{APOLLO_BASE}/mixed_people/api_search",
            headers={"Content-Type": "application/json", "X-Api-Key": APOLLO_API_KEY},
            json={
                "q_organization_domains": domain,
                "person_titles": titles,
                "person_seniorities": SENIORITIES,
                "page": 1, "per_page": 25,
            },
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            people = data.get("people", [])
            # api_search returns obfuscated data — extract what we can
            # Full names need bulk_match (paid). We get: first_name, title, org, linkedin
            return people
        elif r.status_code == 429:
            print(f"  Rate limit — waiting 60s...")
            time.sleep(60)
            return search_people(domain, titles)
        return []
    except Exception as e:
        print(f"  ERROR search {domain}: {e}")
        return []


def step10_people_search(targets: list[dict], max_companies: int = 500,
                         force: bool = False) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"STEP 10: Apollo People Search")
    print(f"{'='*60}")

    if CONTACTS_FILE.exists() and not force:
        contacts = load_json(CONTACTS_FILE)
        print(f"  Loaded from cache: {len(contacts)} contacts")
        return contacts

    if not APOLLO_API_KEY:
        print("  ERROR: APOLLO_API_KEY not set")
        sys.exit(1)

    cache = load_json(CONTACTS_CACHE) or {}
    all_contacts = []
    processed = 0

    for i, t in enumerate(targets[:max_companies], 1):
        domain = t.get("domain", "").strip()
        if not domain:
            continue
        segment = t.get("segment", t.get("analysis_segment", "UNKNOWN"))
        company_name = normalize_company(t.get("company_name", t.get("name", domain)))
        country = t.get("country", "")
        titles = TITLES.get(segment, TITLES["INFLUENCER_PLATFORMS"])

        if domain in cache:
            all_contacts.extend(cache[domain])
            continue

        print(f"  [{i}/{min(max_companies, len(targets))}] {domain} ({segment})")
        people = search_people(domain, titles)
        if not people:
            cache[domain] = []
            processed += 1
            if processed % 50 == 0:
                save_json(CONTACTS_CACHE, cache)
            time.sleep(0.3)
            continue

        domain_contacts = []
        for person in people[:MAX_CONTACTS_PER_COMPANY]:
            contact = {
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "email": person.get("email", "") or "",
                "title": person.get("title", ""),
                "company_name": company_name,
                "domain": domain,
                "segment": segment,
                "linkedin_url": person.get("linkedin_url", "") or "",
                "country": country,
                "employees": t.get("employees", t.get("employee_count", "")),
                "social_proof": get_social_proof(country, segment),
            }
            domain_contacts.append(contact)
            all_contacts.append(contact)
            status = "✓" if contact["email"] else "○"
            print(f"    {status} {contact['first_name']} {contact['last_name']} ({contact['title']})")

        cache[domain] = domain_contacts
        processed += 1
        if processed % 50 == 0:
            save_json(CONTACTS_CACHE, cache)
        time.sleep(0.3)

    save_json(CONTACTS_CACHE, cache)
    save_json(CONTACTS_FILE, all_contacts)

    with_email = sum(1 for c in all_contacts if c["email"])
    print(f"\n  Total: {len(all_contacts)} contacts ({with_email} with email)")
    save_csv(CSV_DIR / f"apollo_contacts_{tag()}.csv", all_contacts)
    return all_contacts


# ══════════════════════════════════════════════════════════════════════════════
# STEP 11: FINDYMAIL
# ══════════════════════════════════════════════════════════════════════════════

async def find_email(client: httpx.AsyncClient, linkedin_url: str) -> dict:
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers={"Authorization": f"Bearer {FINDYMAIL_API_KEY}", "Content-Type": "application/json"},
            json={"linkedin_url": url}, timeout=60.0,
        )
        if r.status_code == 200:
            data = r.json()
            contact = data.get("contact", {})
            return {"email": data.get("email") or contact.get("email") or "",
                    "verified": data.get("verified", False) or contact.get("verified", False)}
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return {"email": "", "verified": False}
    except RuntimeError:
        raise
    except Exception:
        return {"email": "", "verified": False}


async def step11_findymail(contacts: list[dict], max_contacts: int = 1500,
                            force: bool = False) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"STEP 11: FindyMail Enrichment")
    print(f"{'='*60}")

    if ENRICHED_FILE.exists() and not force:
        return load_json(ENRICHED_FILE)

    if not FINDYMAIL_API_KEY:
        print("  ERROR: FINDYMAIL_API_KEY not set")
        sys.exit(1)

    already_have = [c for c in contacts if c.get("email")]
    to_enrich = [c for c in contacts if not c.get("email") and c.get("linkedin_url")]
    to_enrich = to_enrich[:max_contacts]

    cost = len(to_enrich) * 0.01
    print(f"  {len(already_have)} already have email")
    print(f"  {len(to_enrich)} to enrich (~${cost:.2f})")
    print(f"\n  ★ CHECKPOINT: ${cost:.2f} for {len(to_enrich)} contacts.")
    if sys.stdin.isatty():
        print("  Enter to continue, Ctrl+C to abort.")
        input()
    else:
        print("  Non-interactive mode — proceeding automatically.")

    done = load_json(FINDYMAIL_PROGRESS) or {}
    sem = asyncio.Semaphore(FINDYMAIL_CONCURRENT)
    found = not_found = 0
    out_of_credits = False
    t0 = time.time()

    async def process_one(row):
        nonlocal found, not_found, out_of_credits
        if out_of_credits:
            return
        li = row.get("linkedin_url", "").strip()
        if not li:
            return
        if li in done:
            res = done[li]
            row["email"] = res.get("email", "")
            if res.get("email"): found += 1
            else: not_found += 1
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await find_email(client, li)
                except RuntimeError:
                    out_of_credits = True
                    return
            row["email"] = res.get("email", "")
            done[li] = res
            if res.get("email"):
                found += 1
                print(f"  ✓ {row.get('first_name','')} {row.get('last_name','')} → {res['email']}")
            else:
                not_found += 1

    for i in range(0, len(to_enrich), 20):
        if out_of_credits:
            print("\n  OUT OF CREDITS")
            break
        await asyncio.gather(*[process_one(r) for r in to_enrich[i:i+20]])
        save_json(FINDYMAIL_PROGRESS, done)

    all_enriched = already_have + to_enrich
    save_json(ENRICHED_FILE, all_enriched)

    with_email = [c for c in all_enriched if c.get("email", "").strip()]
    without_email = [c for c in all_enriched if not c.get("email") and c.get("linkedin_url")]
    save_csv(CSV_DIR / f"with_email_{tag()}.csv", with_email)
    save_csv(CSV_DIR / f"without_email_{tag()}.csv", without_email)

    print(f"\n  Done in {time.time()-t0:.0f}s. With email: {len(with_email)}, without: {len(without_email)}")
    return all_enriched


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12: SMARTLEAD UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def sl_params():
    return {"api_key": SMARTLEAD_API_KEY}

def create_campaign(name: str) -> int:
    r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/create", params=sl_params(), json={
        "name": name, "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
        "send_as_plain_text": True, "stop_lead_settings": "REPLY_TO_AN_EMAIL",
    }, timeout=30)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"  Created campaign: {cid} — {name}")
    return cid

def upload_leads(campaign_id: int, contacts: list[dict]) -> int:
    leads = []
    for c in contacts:
        leads.append({
            "email": c["email"].strip(),
            "first_name": c.get("first_name", ""),
            "last_name": c.get("last_name", ""),
            "company_name": normalize_company(c.get("company_name", "")),
            "linkedin_profile": c.get("linkedin_url", ""),
            "custom_fields": {
                "social_proof": c.get("social_proof", ""),
                "title": c.get("title", ""),
                "country": c.get("country", ""),
                "segment": c.get("segment", ""),
            },
        })
    total = 0
    for i in range(0, len(leads), 100):
        batch = leads[i:i+100]
        r = httpx.post(f"{SMARTLEAD_BASE}/leads", params={**sl_params(), "campaign_id": campaign_id},
                       json={"lead_list": batch}, timeout=60)
        if r.status_code == 200:
            total += len(batch)
        elif r.status_code == 429:
            time.sleep(70)
            r2 = httpx.post(f"{SMARTLEAD_BASE}/leads", params={**sl_params(), "campaign_id": campaign_id},
                            json={"lead_list": batch}, timeout=60)
            if r2.status_code == 200:
                total += len(batch)
        time.sleep(1)
    print(f"  Uploaded: {total}/{len(leads)}")
    return total

def step12_upload(contacts: list[dict]):
    print(f"\n{'='*60}")
    print(f"STEP 12: SmartLead Upload")
    print(f"{'='*60}")

    if not SMARTLEAD_API_KEY:
        print("  ERROR: SMARTLEAD_API_KEY not set")
        sys.exit(1)

    with_email = [c for c in contacts if c.get("email", "").strip()]
    seen = set()
    deduped = []
    for c in with_email:
        e = c["email"].strip().lower()
        if e not in seen:
            seen.add(e)
            deduped.append(c)

    by_segment = {}
    for c in deduped:
        seg = c.get("segment", "UNKNOWN")
        by_segment.setdefault(seg, []).append(c)

    NAMES = {
        "INFLUENCER_PLATFORMS": "INFLUENCER PLATFORMS v4",
        "IM_FIRST_AGENCIES": "IM-FIRST AGENCIES v4",
    }
    log = load_json(UPLOAD_LOG) or {}

    for seg, seg_contacts in sorted(by_segment.items()):
        name = NAMES.get(seg, f"OnSocial {seg} v4")
        print(f"\n  --- {name}: {len(seg_contacts)} leads ---")
        print(f"  ★ CHECKPOINT: Create '{name}'?")
        if sys.stdin.isatty():
            print("  Enter to continue, Ctrl+C to abort.")
            input()
        else:
            print("  Non-interactive mode — proceeding.")

        cid = log.get(seg, {}).get("campaign_id")
        if not cid:
            cid = create_campaign(name)
            httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/email-accounts", params=sl_params(),
                       json={"emailAccountIDs": SMARTLEAD_EMAIL_ACCOUNTS}, timeout=30)
            httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/schedule", params=sl_params(), json={
                "timezone": "America/New_York", "days_of_the_week": [1,2,3,4,5],
                "start_hour": "08:00", "end_hour": "18:00",
                "min_time_btw_emails": 15, "max_new_leads_per_day": 500,
            }, timeout=30)

        uploaded = upload_leads(cid, seg_contacts)
        log[seg] = {"campaign_id": cid, "campaign_name": name,
                     "leads": uploaded, "at": ts()}
        save_json(UPLOAD_LOG, log)

    print(f"\n  ⚠ Campaigns in DRAFTED status. Add v4 sequences + activate manually.")
    print(f"  ⚠ Use {{{{social_proof}}}} variable in sequences.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

STEPS = ["start", "blacklist", "prefilter", "scrape", "analyze", "verify",
         "export", "people", "findymail", "upload"]

def main():
    p = argparse.ArgumentParser(description="OnSocial Clay→SmartLead (Platforms + Agencies)")
    p.add_argument("--project-id", type=int, default=PROJECT_ID)
    p.add_argument("--segment", choices=["platforms_tier12", "platforms_tier34",
                                          "agencies_tier12", "agencies_tier34"])
    p.add_argument("--from-step", choices=STEPS, default="start")
    p.add_argument("--run-id", type=int, help="Resume existing run")
    p.add_argument("--max-companies", type=int, default=500)
    p.add_argument("--max-findymail", type=int, default=1500)
    p.add_argument("--prompt-file", help="Custom analysis prompt file")
    p.add_argument("--re-analyze", action="store_true", help="Re-analyze with new prompt")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print(f"OnSocial v4 Pipeline — {ts()}")
    print(f"State: {STATE_DIR}")

    prompt_text = DEFAULT_ANALYSIS_PROMPT
    if args.prompt_file:
        prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
        print(f"Custom prompt loaded: {args.prompt_file}")

    run_id = args.run_id or load_state().get("run_id")

    # Re-analyze mode
    if args.re_analyze:
        if not run_id:
            print("ERROR: --run-id required for --re-analyze")
            sys.exit(1)
        step5_reanalyze(run_id, prompt_text)
        return

    steps = STEPS[STEPS.index(args.from_step):]

    if args.dry_run:
        config = CLAY_FILTERS.get(args.segment, {})
        filters = config.get("filters", {})
        print(f"\n  DRY RUN — no API calls")
        print(f"  Segment: {args.segment} ({config.get('segment', '?')})")
        print(f"  Countries: {', '.join(filters.get('country_names', []))}")
        print(f"  Max results: {filters.get('max_results', '?')}")
        print(f"  Employees: {filters.get('minimum_member_count', '?')}-{filters.get('maximum_member_count', '?')}")
        print(f"  Steps: {' → '.join(steps)}")
        print(f"  Prompt: {prompt_text[:80]}...")
        return

    # Steps 0-8: Backend API
    if "start" in steps:
        if not args.segment:
            print("ERROR: --segment required for start")
            sys.exit(1)
        run_id = step0_start(args.segment, args.project_id)
        # Wait for Clay to finish gathering
        print("\n  Waiting for Clay gathering to complete...")
        while True:
            time.sleep(10)
            r = httpx.get(f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
                          headers=BACKEND_HEADERS, timeout=30)
            phase = r.json().get("current_phase", "")
            if phase != "gather":
                print(f"  Phase: {phase}")
                break
            print("  ..still gathering")

    if "blacklist" in steps and run_id:
        cp1 = step2_blacklist(run_id)
        if cp1.get("gate_id"):
            print("\n  >>> Claude Code will review CP1 and decide <<<")
            print("  Pausing. Run with --from-step prefilter --run-id", run_id, "after approval.")
            return

    if "prefilter" in steps and run_id:
        step3_prefilter(run_id)

    if "scrape" in steps and run_id:
        step4_scrape(run_id)

    if "analyze" in steps and run_id:
        cp2 = step5_analyze(run_id, prompt_text)
        if cp2.get("gate_id"):
            print(f"\n  >>> Claude Code will review CP2 (target rate: {cp2.get('target_rate', 0)*100:.1f}%) <<<")
            print(f"  If OK: approve gate, then --from-step verify --run-id {run_id}")
            print(f"  If bad: --re-analyze --run-id {run_id} --prompt-file new_prompt.txt")
            return

    if "verify" in steps and run_id:
        cp3 = step6_prepare_verify(run_id)
        if cp3.get("gate_id"):
            print("\n  >>> Claude Code will review CP3 (cost) <<<")
            print(f"  After approval: --from-step export --run-id {run_id}")
            return

    # Steps 9-12: Local execution
    if "export" in steps:
        targets = step9_export_targets(args.project_id, force=args.force)
    else:
        targets = load_json(TARGETS_FILE) or []

    if "people" in steps:
        contacts = step10_people_search(targets, max_companies=args.max_companies, force=args.force)
    else:
        contacts = load_json(CONTACTS_FILE) or load_json(ENRICHED_FILE) or []

    if "findymail" in steps:
        contacts = asyncio.run(step11_findymail(contacts, max_contacts=args.max_findymail, force=args.force))
    else:
        contacts = load_json(ENRICHED_FILE) or contacts

    if "upload" in steps:
        step12_upload(contacts)


if __name__ == "__main__":
    main()
