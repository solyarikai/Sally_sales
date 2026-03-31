#!/usr/bin/env python3
"""
OnSocial Clay Pipeline (IM_FIRST_AGENCIES v4, ALL GEO, 2026-03-31)

Full pipeline: Clay Company Search (description_keywords, no AI mapping) ->
Backend dedup/blacklist/scrape/classify -> Apollo People UI Search ->
FindyMail email enrichment -> SmartLead upload.

Company search: Clay via backend API with description_keywords (direct, FREE - no credits).
People search:  Apollo People tab via apollo_scraper.js (FREE, no credits).

Filters from: sofia/projects/OnSocial/docs/apollo-filters-v4.md (Segment 3)
  - 30 description_keywords (v3 base + v4 new: creator studio, talent management, etc.)
  - 47 description_keywords_exclude
  - Employees: 10-500
  - Industries: 1 (Marketing and Advertising only)
  - ALL GEO (no country_names filter)
  - Target: 1,500-3,000 companies (v4 estimate)

People filters (v4):
  - Management Level: c_suite, vp, director, owner, senior, head, partner, founder
  - Titles: 25 titles (v4: added Head of Creator Partnerships, Director of Creator, etc.)
  - Excluded titles applied as post-filter after scrape

Steps:
  Step 0:     Clay Company Search via backend API (clay.companies.emulator)
  Steps 2-8:  Backend pipeline (dedup -> blacklist -> scrape -> classify)
  Step 9:     Export targets from DB
  Step 10:    Apollo People UI Search (auto via apollo_scraper.js)
  Step 11:    FindyMail email enrichment
  Step 12:    SmartLead upload

Usage (run on Hetzner via SSH):
  cd ~/magnum-opus-project/repo

  # Full pipeline from Clay search
  python3 sofia/scripts/onsocial_clay_imagency_v4_allgeo_2026-03-31.py --from-step start

  # Dry run (print filters, no API calls)
  python3 sofia/scripts/onsocial_clay_imagency_v4_allgeo_2026-03-31.py --dry-run

  # Resume from people search (auto Apollo)
  python3 sofia/scripts/onsocial_clay_imagency_v4_allgeo_2026-03-31.py --from-step people

  # Resume with manual CSV (fallback)
  python3 sofia/scripts/onsocial_clay_imagency_v4_allgeo_2026-03-31.py --from-step people --apollo-csv export.csv

Env vars: FINDYMAIL_API_KEY, SMARTLEAD_API_KEY
Backend must be running on localhost:8000 (Hetzner)
"""

import argparse
import asyncio
import csv
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx


# ══════════════════════════════════════════════════════════════════════════════
# PATHS & CONFIG
# ══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent
SOFIA_DIR = SCRIPT_DIR.parent
REPO_DIR = SOFIA_DIR.parent  # magnum-opus-project/repo on Hetzner

STATE_DIR = SOFIA_DIR.parent / "state" / "onsocial" / "clay_imagency_v4_allgeo"
STATE_DIR.mkdir(parents=True, exist_ok=True)

CSV_DIR = SOFIA_DIR / "output" / "OnSocial" / "clay_imagency_v4_allgeo"
CSV_DIR.mkdir(parents=True, exist_ok=True)

RUN_STATE = STATE_DIR / "run_state.json"
TARGETS_FILE = STATE_DIR / "targets.json"
CONTACTS_FILE = STATE_DIR / "contacts.json"
ENRICHED_FILE = STATE_DIR / "enriched.json"
FINDYMAIL_PROGRESS = STATE_DIR / "findymail_progress.json"
UPLOAD_LOG = STATE_DIR / "upload_log.json"

# Backend
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://localhost:8000")
BACKEND_HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

# API keys
FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
FINDYMAIL_BASE = "https://app.findymail.com"
FINDYMAIL_CONCURRENT = 5

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"

SMARTLEAD_EMAIL_ACCOUNTS = [
    15090446, 15090416, 15090400,  # bhaskar@ (OnSocial)
    12300705, 12300692, 12300668,  # petr@ crona-ai
    11812436, 11812422, 11812388, 11812365, 11812350,  # petr@ crona
    11812334, 11812321, 11812309, 11812296,  # petr@ crona
]

# Project
PROJECT_ID = 42  # OnSocial
PROJECT_CODE = "OS"
SEGMENT_NAME = "IM_FIRST_AGENCIES"
SEGMENT_CODE = "IMAGENCY"


# ══════════════════════════════════════════════════════════════════════════════
# SOCIAL PROOF BY REGION
# ══════════════════════════════════════════════════════════════════════════════

SOCIAL_PROOF = {
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
}


def get_social_proof(country: str) -> str:
    return SOCIAL_PROOF.get(country, SOCIAL_PROOF["_default"])


# ══════════════════════════════════════════════════════════════════════════════
# CLAY FILTERS (from apollo-filters-v4.md, Segment 3 - description_keywords)
# Uses description_keywords for direct Clay search - NO AI/Gemini mapping.
# ══════════════════════════════════════════════════════════════════════════════

CLAY_FILTERS = {
    "description_keywords": [
        # --- Original v3 keywords (12) ---
        "influencer marketing agency",
        "influencer agency",
        "creator agency",
        "influencer management",
        "creator campaigns",
        "influencer marketing",
        "creator partnerships",
        "TikTok agency",
        "influencer talent",
        "creator talent",
        "influencer strategy",
        "UGC agency",
        # --- New v4 keywords (18 adjacent agencies missed by v3) ---
        "creator studio",
        "content studio influencer",
        "branded content studio",
        "creative studio influencer",
        "talent management agency creator",
        "digital talent agency",
        "creator representation",
        "influencer representation",
        "social-first agency",
        "creator-first agency",
        "influencer activation agency",
        "creator activation",
        "micro-influencer agency",
        "nano-influencer agency",
        "influencer seeding agency",
        "gifting agency",
        "creator network agency",
        "influencer collective",
    ],
    "description_keywords_exclude": [
        "SEO agency", "PPC agency", "web design", "software development",
        "recruitment", "HR", "staffing", "healthcare", "legal", "accounting",
        "logistics", "manufacturing", "real estate", "fintech", "insurance",
        "construction", "education", "nonprofit", "government", "defense",
        "food service", "restaurant", "hospitality", "travel agency",
        "freelance", "solo consultant", "print", "media buying only",
        "PR agency", "public relations", "crisis communications",
        "web development", "app development", "branding only",
        "market research", "consulting firm", "management consulting",
        "antivirus", "cybersecurity", "IT infrastructure",
        "modelling agency", "casting agency", "event management only",
        "photography studio only", "video production only",
        "translation agency", "localization agency",
    ],
    "industries": [
        "Marketing and Advertising",
    ],
    # ALL GEO - no country_names filter
    "minimum_member_count": 10,
    "maximum_member_count": 500,
    "max_results": 5000,
}


# ══════════════════════════════════════════════════════════════════════════════
# PEOPLE FILTERS (v4: expanded titles, seniorities, excluded titles)
# ══════════════════════════════════════════════════════════════════════════════

PEOPLE_SENIORITIES = [
    "c_suite", "vp", "director", "owner", "senior", "head", "partner", "founder",
]

PEOPLE_TITLES = [
    "CEO", "Founder", "Co-Founder", "Managing Director", "Managing Partner",
    "Head of Influencer Marketing", "Director of Influencer",
    "Head of Influencer", "VP Strategy", "Head of Partnerships",
    "Director of Client Services", "Head of Strategy",
    "General Manager", "Partner", "Owner",
    "Senior Partner", "Senior Managing Director",
    # v4 additions
    "Head of Creator Partnerships", "Director of Creator",
    "Head of Talent", "Director of Talent",
    "Head of Growth", "Director of Business Development",
    "Head of Operations", "Director of Operations",
]

EXCLUDED_TITLES_PATTERNS = [
    "intern", "junior", "assistant", "student", "freelance",
    "campaign manager", "campaign coordinator",
    "social media manager", "content creator", "designer",
    "account coordinator", "media planner", "media buyer",
    "pr manager", "communications manager",
    "hr", "people", "recruiter", "finance", "accounting",
    "executive assistant", "office manager", "operations coordinator",
    "community manager", "senior community manager",
    "influencer coordinator", "senior influencer coordinator",
    "talent coordinator", "senior talent coordinator",
]


def _title_excluded(title: str) -> bool:
    t = title.lower().strip()
    for pattern in EXCLUDED_TITLES_PATTERNS:
        if pattern in t:
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICATION PROMPT (for Step 5: Analyze)
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_ANALYSIS_PROMPT = """\
You classify companies as potential customers of OnSocial - a B2B API
that provides creator/influencer data for Instagram, TikTok, and YouTube
(audience demographics, engagement analytics, fake follower detection,
creator search).

Companies that need OnSocial are those whose CORE business involves
working with social media creators.

== STEP 1: INSTANT DISQUALIFIERS ==
- website_content is EMPTY and no description -> "OTHER | No data available"
- Domain is parked / for sale / dead -> "OTHER | Domain inactive"
- 5000+ employees -> "OTHER | Enterprise, too large"
- <10 employees -> "OTHER | Too small for agency segment"

If none triggered -> continue to Step 2.

== STEP 2: SEGMENTS ==

IM_FIRST_AGENCIES
  Agency where influencer/creator campaigns are THE primary business,
  not a side service. 10-500 employees.
  KEY TEST: 60%+ of their visible offering is about creator/influencer work.

INFLUENCER_PLATFORMS
  Builds SaaS / software / tools for influencer marketing: analytics,
  creator discovery, campaign management, creator CRM, UGC content
  platforms, creator marketplaces, creator monetization tools, social
  commerce, live shopping platforms, social listening with creator focus.
  KEY TEST: they have a PRODUCT (software/platform/API) that brands or
  agencies use to find, analyze, manage, or pay creators.

AFFILIATE_PERFORMANCE
  Affiliate networks, performance marketing platforms, partnership platforms,
  social commerce tools, creator monetization platforms, link-in-bio tools,
  loyalty/rewards/cashback platforms converging with creator/affiliate space,
  attribution platforms, commission tracking, referral marketing platforms.
  KEY TEST: they OPERATE or BUILD technology for affiliate/performance
  marketing, partner ecosystems, or creator monetization - not just use it.

OTHER
  Everything that does NOT fit above. Includes: generic digital agencies,
  PR firms, SEO/PPC shops, web development, e-commerce brands (unless
  they BUILD creator tools), consulting, recruitment, fintech, etc.

== STEP 3: CONFLICT RESOLUTION ==
- Company is a "full-service digital agency" that also does influencer -> OTHER
  (not influencer-first)
- Company does influencer marketing AND has a SaaS product -> INFLUENCER_PLATFORMS
  (product companies are higher-value targets)
- Company is a PR agency that also does influencer campaigns -> OTHER
- Company is a talent management firm but NOT for creators/influencers -> OTHER
- Company is a modelling/casting agency -> OTHER
- Company says "influencer" but core is event management or experiential -> OTHER

== OUTPUT FORMAT (strict) ==
SEGMENT | confidence (0.0-1.0) | one-line reasoning

Examples:
IM_FIRST_AGENCIES | 0.92 | Influencer-first agency running creator campaigns for brands
IM_FIRST_AGENCIES | 0.85 | Creator talent agency managing influencer partnerships
INFLUENCER_PLATFORMS | 0.88 | SaaS platform for influencer discovery and analytics
OTHER | 0.95 | Generic digital marketing agency, influencer is one of 8 services listed
"""


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def tag() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_company(name: str) -> str:
    if not name:
        return ""
    for suffix in [" Inc.", " Inc", " LLC", " Ltd.", " Ltd", " GmbH", " AG", " S.A.", " B.V.", " Pty"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()


def _normalize_domain(raw: str) -> str:
    d = raw.strip().lower()
    for prefix in ["https://", "http://", "www."]:
        if d.startswith(prefix):
            d = d[len(prefix):]
    d = d.rstrip("/").split("/")[0]
    return d


def api(method: str, path: str, raise_on_error: bool = True, **kwargs) -> dict:
    url = f"{BACKEND_BASE}/api{path}"
    r = getattr(httpx, method)(url, headers=BACKEND_HEADERS, timeout=300, **kwargs)
    if r.status_code >= 400:
        if raise_on_error:
            print(f"  API ERROR {r.status_code}: {r.text[:500]}")
            sys.exit(1)
        return {"_error": r.status_code, "_detail": r.text[:500]}
    return r.json()


def api_long(method: str, path: str, expected_phase: str, run_id: int,
             timeout: int = 3600, poll_interval: int = 30, **kwargs) -> dict:
    url = f"{BACKEND_BASE}/api{path}"
    try:
        r = getattr(httpx, method)(url, headers=BACKEND_HEADERS, timeout=timeout, **kwargs)
        if r.status_code >= 400:
            return {"_error": r.status_code, "_detail": r.text[:500]}
        return r.json()
    except (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
        print(f"  Connection lost ({type(e).__name__}). Polling...")
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll_interval)
            try:
                r2 = httpx.get(f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
                               headers=BACKEND_HEADERS, timeout=30)
                if r2.status_code == 200:
                    phase = r2.json().get("current_phase", "")
                    elapsed = int(time.time() - start)
                    print(f"  [{elapsed}s] Phase: {phase}")
                    if phase == expected_phase or phase.startswith("awaiting_"):
                        return r2.json()
            except Exception:
                print(f"  [{int(time.time()-start)}s] Backend unreachable...")
        return {"_timeout": True}


def save_state(run_id: int, phase: str, gate_id: int = None):
    save_json(RUN_STATE, {"run_id": run_id, "phase": phase, "gate_id": gate_id, "updated_at": ts()})


def load_state() -> dict:
    return load_json(RUN_STATE) or {}


def _checkpoint(message: str) -> bool:
    print(f"\n  * CHECKPOINT: {message}")
    if sys.stdin.isatty():
        print("  [Enter] to continue, [s] to skip, [Ctrl+C] to abort.")
        resp = input("  > ").strip().lower()
        return resp != "s"
    else:
        print("  Non-interactive mode - proceeding.")
        return True


# -- Google Sheets ----

GDRIVE_FOLDERS = {
    "Leads":     "1_1ck-0sn1jXm2px4MCz4o_ZST6J6JfOe",
    "Import":    "1O-rkQK6btZjXzO-p31ZMsrjcLWeacZRV",
    "Targets":   "124SCStl6SHuMPquxyfj0Av5O8U4kNrTj",
    "Ops":       "1K7bVbvVU3LIK5V_cGLwhFKINBdURZLD0",
    "Analytics": "1xRAdlbn2BK3QYBuYtUjgVjhsb2wH5MiV",
    "Archive":   "1uLKLR6NFzJHb_XraE5sfKrSe-HbNja9t",
}

_GSHEETS_TOKEN_PATHS = [
    Path.home() / ".claude" / "google-sheets" / "token.json",
    SOFIA_DIR / ".google-sheets" / "token.json",
    SCRIPT_DIR / ".google-sheets" / "token.json",
]


def _get_gsheets_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    token_path = None
    for p in _GSHEETS_TOKEN_PATHS:
        if p.exists():
            token_path = p
            break
    if not token_path:
        raise FileNotFoundError("Google Sheets token.json not found")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds.expired:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def _resolve_drive_folder(sheet_name: str) -> str | None:
    parts = sheet_name.split(" | ")
    if len(parts) >= 2:
        return GDRIVE_FOLDERS.get(parts[1].strip())
    return None


def _upload_to_sheets(headers: list[str], rows: list[dict], sheet_name: str):
    from googleapiclient.discovery import build
    data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]
    try:
        creds = _get_gsheets_creds()
        sheets_svc = build("sheets", "v4", credentials=creds)
        drive_svc = build("drive", "v3", credentials=creds)
        sheet = sheets_svc.spreadsheets().create(
            body={"properties": {"title": sheet_name}}
        ).execute()
        sid = sheet["spreadsheetId"]
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=sid, range="A1",
            valueInputOption="RAW", body={"values": data}
        ).execute()
        folder_id = _resolve_drive_folder(sheet_name)
        if folder_id:
            f = drive_svc.files().get(fileId=sid, fields="parents").execute()
            old_parents = ",".join(f.get("parents", []))
            drive_svc.files().update(
                fileId=sid, addParents=folder_id, removeParents=old_parents
            ).execute()
        print(f"  -> Sheet: {sheet_name} - https://docs.google.com/spreadsheets/d/{sid}")
    except Exception as e:
        print(f"  ! Sheet upload failed: {e}")


def save_csv(path: Path, rows: list[dict], sheet_name: str = None):
    if not rows:
        return
    if sheet_name:
        safe_name = sheet_name.replace(" | ", "_").replace(" - ", "_").replace(" ", "_").replace("/", "-")
        path = path.parent / f"{safe_name}.csv"
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> CSV: {path.name} ({len(rows)} rows)")
    if sheet_name:
        _upload_to_sheets(fieldnames, rows, sheet_name)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: START GATHERING (Clay with description_keywords)
# ══════════════════════════════════════════════════════════════════════════════

def step0_start() -> int:
    """Start Clay gathering via backend API with description_keywords (no AI mapping)."""
    print(f"\n{'='*60}")
    print(f"STEP 0: Clay Gathering - {SEGMENT_NAME} v4 ALL GEO")
    print(f"  Source: clay.companies.emulator (description_keywords)")
    print(f"  Keywords: {len(CLAY_FILTERS['description_keywords'])} description_keywords")
    print(f"  Excluded: {len(CLAY_FILTERS['description_keywords_exclude'])} keywords")
    print(f"  Industries: {', '.join(CLAY_FILTERS['industries'])}")
    print(f"  Employees: {CLAY_FILTERS['minimum_member_count']}-{CLAY_FILTERS['maximum_member_count']}")
    print(f"  Geo: ALL (no country_names filter)")
    print(f"  Max results: {CLAY_FILTERS['max_results']}")
    print(f"{'='*60}")

    result = api("post", "/pipeline/gathering/start", json={
        "project_id": PROJECT_ID,
        "source_type": "clay.companies.emulator",
        "filters": CLAY_FILTERS,
        "triggered_by": "operator",
        "input_mode": "structured",
        "notes": f"v4 Clay description_keywords - {SEGMENT_NAME} ALL GEO - {len(CLAY_FILTERS['description_keywords'])} keywords",
    })

    run_id = result["id"]
    print(f"\n  Run created: #{run_id}")
    print(f"  Status: {result['status']} / {result['current_phase']}")
    save_state(run_id, "started")
    return run_id


# ══════════════════════════════════════════════════════════════════════════════
# STEPS 2-8: BACKEND PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def get_latest_prompt() -> tuple[int | None, str | None]:
    result = api("get", f"/pipeline/gathering/prompts?project_id={PROJECT_ID}", raise_on_error=False)
    prompts = result if isinstance(result, list) else result.get("items", [])
    active = [p for p in prompts if p.get("is_active", True)]
    if active:
        latest = max(active, key=lambda p: p["id"])
        print(f"  Prompt: #{latest['id']} '{latest.get('name', '?')}' "
              f"(usage={latest.get('usage_count', 0)}, target_rate={latest.get('avg_target_rate', '?')})")
        return latest["id"], latest.get("prompt_text", "")
    return None, None


def approve_pending_gate(run_id: int) -> bool:
    try:
        gates = api("get", f"/pipeline/gathering/approval-gates?project_id={PROJECT_ID}",
                    raise_on_error=False)
        items = gates if isinstance(gates, list) else gates.get("items", [])
        for g in items:
            if g.get("gathering_run_id") == run_id and g.get("status") == "pending":
                api("post", f"/pipeline/gathering/approval-gates/{g['id']}/approve",
                    json={}, raise_on_error=False)
                print(f"  Gate #{g['id']} approved")
                return True
    except Exception:
        pass
    return False


def blacklist_approved_targets(run_id: int):
    sql = (f"SELECT DISTINCT dc.domain FROM discovered_companies dc "
           f"JOIN company_source_links csl ON csl.discovered_company_id = dc.id "
           f"WHERE csl.gathering_run_id = {run_id} AND dc.is_target = true "
           f"AND dc.domain IS NOT NULL AND dc.domain != ''")
    r = subprocess.run(
        ["docker", "exec", "leadgen-postgres", "psql", "-U", "leadgen",
         "-d", "leadgen", "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=15,
    )
    domains = [d.strip() for d in r.stdout.strip().split("\n") if d.strip()]
    if not domains:
        return
    values = ", ".join(
        f"({PROJECT_ID}, '{d}', 'target_approved_run_{run_id}', 'pipeline', now())"
        for d in domains
    )
    insert_sql = (f"INSERT INTO project_blacklist (project_id, domain, reason, source, created_at) "
                  f"VALUES {values} ON CONFLICT DO NOTHING")
    subprocess.run(
        ["docker", "exec", "leadgen-postgres", "psql", "-U", "leadgen",
         "-d", "leadgen", "-c", insert_sql],
        capture_output=True, text=True, timeout=30,
    )
    print(f"  Blacklist: +{len(domains)} target domains (run #{run_id})")


def step4_scrape(run_id: int) -> dict:
    print(f"\n  Step 4: Scrape websites (run #{run_id})")
    result = api_long("post", f"/pipeline/gathering/runs/{run_id}/scrape",
                      expected_phase="scraped", run_id=run_id, timeout=3600)
    if not result.get("_timeout"):
        print(f"  Scraped: {result.get('scraped', '?')}, Skipped: {result.get('skipped', '?')}")
    return result


def step2_blacklist(run_id: int) -> dict:
    """Run blacklist check -> creates CP1 gate. Returns gate info or {}."""
    print(f"\n{'='*60}")
    print(f"STEP 2: Blacklist Check (run #{run_id})")
    print(f"{'='*60}")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/blacklist-check")
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates", raise_on_error=False)
    gate_list = gates if isinstance(gates, list) else gates.get("items", [])
    pending = [g for g in gate_list if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        scope = gate.get("scope", {})
        save_state(run_id, "awaiting_scope_ok", gate_id=gate["id"])
        print(f"\n  * CHECKPOINT 1 - gate #{gate['id']}")
        print(f"  Passed: {scope.get('passed', '?')}, Rejected: {scope.get('rejected', '?')}")
        return {"gate_id": gate["id"], "scope": scope}
    return {}


def approve_gate(gate_id: int, note: str = "Approved") -> dict:
    """Approve a checkpoint gate."""
    result = api("post", f"/pipeline/gathering/approval-gates/{gate_id}/approve",
                 json={"decision_note": note})
    print(f"  Gate #{gate_id} approved")
    return result


def step3_prefilter(run_id: int) -> dict:
    print(f"\n  Step 3: Pre-filter (run #{run_id})")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/pre-filter")
    print(f"  Passed: {result.get('passed', '?')}")
    return result


def step5_analyze(run_id: int, prompt_text: str = None) -> dict:
    """Run GPT classification -> creates CP2 gate."""
    print(f"\n{'='*60}")
    print(f"STEP 5: Analyze (run #{run_id})")
    print(f"{'='*60}")
    text = prompt_text or DEFAULT_ANALYSIS_PROMPT
    result = api_long("post", f"/pipeline/gathering/runs/{run_id}/analyze",
                      expected_phase="analyzed", run_id=run_id, timeout=3600,
                      params={"prompt_text": text, "model": "gpt-4o-mini"})
    targets_found = result.get("targets_found", result.get("targets_count", "?"))
    total = result.get("total_analyzed", "?")
    target_rate = result.get("target_rate", 0)
    print(f"  Analyzed: {total}, Targets: {targets_found} ({target_rate*100:.1f}%)")

    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates", raise_on_error=False)
    gate_list = gates if isinstance(gates, list) else gates.get("items", [])
    pending = [g for g in gate_list if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        save_state(run_id, "awaiting_targets_ok", gate_id=gate["id"])
        print(f"\n  * CHECKPOINT 2 - gate #{gate['id']}")
        print(f"  Target rate: {target_rate*100:.1f}%")
        print(f"  Review targets, then approve or re-analyze.")
        return {"gate_id": gate["id"], "target_rate": target_rate, "targets_found": targets_found}
    return {"target_rate": target_rate, "targets_found": targets_found}


def step6_prepare_verify(run_id: int) -> dict:
    """Prepare FindyMail verification -> creates CP3 with cost estimate."""
    print(f"\n  Step 6: Prepare Verification (run #{run_id})")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/prepare-verification",
                 raise_on_error=False)
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates", raise_on_error=False)
    gate_list = gates if isinstance(gates, list) else gates.get("items", [])
    pending = [g for g in gate_list if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        scope = gate.get("scope", {})
        print(f"\n  * CHECKPOINT 3 - gate #{gate['id']}")
        print(f"  Emails to verify: {scope.get('emails_to_verify', '?')}")
        print(f"  Estimated cost: ${scope.get('estimated_cost_usd', '?')}")
        return {"gate_id": gate["id"], "scope": scope}
    return result if isinstance(result, dict) else {}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: EXPORT TARGETS
# ══════════════════════════════════════════════════════════════════════════════

def step9_export_targets(force: bool = False) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"STEP 9: Export Targets (project_id={PROJECT_ID})")
    print(f"{'='*60}")

    if TARGETS_FILE.exists() and not force:
        targets = load_json(TARGETS_FILE)
        print(f"  Loaded from cache: {len(targets)} targets")
        return targets

    sql = (f"SELECT domain, name, matched_segment, confidence "
           f"FROM discovered_companies WHERE project_id={PROJECT_ID} AND is_target=true")
    r = subprocess.run(
        ["docker", "exec", "leadgen-postgres", "psql", "-U", "leadgen",
         "-d", "leadgen", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=30,
    )

    targets = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            targets.append({
                "domain": parts[0].strip(),
                "company_name": parts[1].strip(),
                "segment": parts[2].strip(),
                "confidence": parts[3].strip() if len(parts) > 3 else "",
            })

    if not targets:
        print("  No targets found. Complete backend pipeline first (Steps 0-8).")
        sys.exit(1)

    save_json(TARGETS_FILE, targets)

    today = tag()
    save_csv(CSV_DIR / f"targets_{SEGMENT_CODE}_{today}.csv", targets,
             sheet_name=f"{PROJECT_CODE} | Targets | {SEGMENT_CODE} v4 Clay - {today}")
    print(f"  Exported: {len(targets)} targets")

    return targets


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: APOLLO PEOPLE SEARCH
# ══════════════════════════════════════════════════════════════════════════════

APOLLO_SCRAPER_SCRIPT = "scripts/apollo_scraper.js"
APOLLO_PEOPLE_BATCH_SIZE = 30
APOLLO_PEOPLE_MAX_PAGES = 5


def _build_apollo_people_url(domains: list[str], titles: list[str], seniorities: list[str]) -> str:
    from urllib.parse import quote
    url = "https://app.apollo.io/#/people?finderViewId=5b8050d050a0710001ca27c1"
    for d in domains:
        url += f"&organizationDomains[]={quote(d)}"
    for t in titles:
        url += f"&personTitles[]={quote(t)}"
    for s in seniorities:
        url += f"&personSeniorities[]={quote(s)}"
    return url


def _run_apollo_scraper(url: str, max_pages: int, output_path: str) -> list[dict]:
    script = REPO_DIR / APOLLO_SCRAPER_SCRIPT
    if not script.exists():
        script = Path(".") / APOLLO_SCRAPER_SCRIPT
    if not script.exists():
        print(f"    ERROR: {APOLLO_SCRAPER_SCRIPT} not found")
        return []
    args = ["node", str(script), "--url", url, "--max-pages", str(max_pages), "--output", output_path]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=300,
                              cwd=str(script.parent.parent),
                              env={**os.environ, "CHROME_PATH": os.environ.get("CHROME_PATH", "/usr/bin/google-chrome")})
        if result.returncode != 0:
            err = result.stderr[-300:] if result.stderr else result.stdout[-300:]
            print(f"    Scraper error (rc={result.returncode}): {err}")
            return []
        if Path(output_path).exists():
            with open(output_path) as f:
                return json.load(f)
    except subprocess.TimeoutExpired:
        print(f"    Scraper timeout (300s)")
    except Exception as e:
        print(f"    Scraper error: {e}")
    return []


def _map_apollo_person(person: dict, targets_by_domain: dict, batch_domain: str = None) -> dict:
    name = person.get("name", "")
    parts = name.split(None, 1) if name else ["", ""]
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    domain = batch_domain or _normalize_domain(person.get("domain", "") or person.get("company_url", ""))
    if not domain:
        company = person.get("company", "")
        for d, t in targets_by_domain.items():
            if t.get("company_name", "").lower() == company.lower():
                domain = d
                break
    target = targets_by_domain.get(domain, {})
    country = person.get("location", "").split(",")[-1].strip() if person.get("location") else ""
    if not country:
        country = target.get("country", "")
    return {
        "first_name": first_name, "last_name": last_name,
        "email": person.get("email", ""), "title": person.get("title", ""),
        "company_name": normalize_company(person.get("company", "") or target.get("company_name", domain)),
        "domain": domain, "segment": SEGMENT_NAME,
        "linkedin_url": person.get("linkedin_url", person.get("linkedin", "")),
        "country": country,
        "employees": person.get("employees", "") or target.get("employees", ""),
        "social_proof": get_social_proof(country),
    }


def step10_apollo_people_search(targets: list[dict], force: bool = False) -> list[dict]:
    """Search Apollo People UI for contacts at target companies."""
    print(f"\n{'='*60}")
    print(f"STEP 10: Apollo People UI Search (automated)")
    print(f"{'='*60}")

    if CONTACTS_FILE.exists() and not force:
        contacts = load_json(CONTACTS_FILE)
        print(f"  Loaded from cache: {len(contacts)} contacts")
        return contacts

    targets_by_domain = {t.get("domain", "").strip().lower(): t for t in targets if t.get("domain")}
    domains = list(targets_by_domain.keys())

    print(f"  Targets: {len(domains)} domains")
    print(f"  Seniorities: {', '.join(PEOPLE_SENIORITIES)}")
    print(f"  Titles: {len(PEOPLE_TITLES)}")

    batches = [domains[i:i + APOLLO_PEOPLE_BATCH_SIZE]
               for i in range(0, len(domains), APOLLO_PEOPLE_BATCH_SIZE)]
    print(f"  Batches: {len(batches)} x {APOLLO_PEOPLE_BATCH_SIZE}")

    all_contacts = []
    for batch_idx, batch_domains in enumerate(batches):
        print(f"    Batch {batch_idx + 1}/{len(batches)}: {len(batch_domains)} domains...", end=" ", flush=True)
        url = _build_apollo_people_url(batch_domains, PEOPLE_TITLES, PEOPLE_SENIORITIES)
        output_path = f"/tmp/apollo_people_clay_imagency_v4_{batch_idx}.json"
        people = _run_apollo_scraper(url, APOLLO_PEOPLE_MAX_PAGES, output_path)
        print(f"{len(people)} people")

        for person in people:
            batch_domain = batch_domains[0] if len(batch_domains) == 1 else None
            contact = _map_apollo_person(person, targets_by_domain, batch_domain)
            if contact["first_name"] and contact["domain"]:
                all_contacts.append(contact)

        try:
            Path(output_path).unlink(missing_ok=True)
        except Exception:
            pass
        time.sleep(3)

    # Post-filter: exclude contacts with excluded titles
    before_filter = len(all_contacts)
    all_contacts = [c for c in all_contacts if not _title_excluded(c.get("title", ""))]
    excluded = before_filter - len(all_contacts)
    if excluded:
        print(f"\n  Post-filter: removed {excluded} contacts (excluded titles)")

    # Dedupe
    seen = set()
    deduped = []
    for c in all_contacts:
        key = c["linkedin_url"] or f"{c['first_name']}|{c['last_name']}|{c['domain']}"
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    all_contacts = deduped

    save_json(CONTACTS_FILE, all_contacts)

    with_email = sum(1 for c in all_contacts if c["email"])
    with_li = sum(1 for c in all_contacts if c["linkedin_url"])
    print(f"\n  Total: {len(all_contacts)} contacts")
    print(f"  With email: {with_email}, with LinkedIn: {with_li}")

    today = tag()
    save_csv(CSV_DIR / f"import_apollo_people_{today}.csv", all_contacts,
             sheet_name=f"{PROJECT_CODE} | Import | {SEGMENT_CODE} Apollo People v4 Clay - {today}")

    return all_contacts


def step10_import_apollo_csv(csv_path: str, targets: list[dict], force: bool = False) -> list[dict]:
    """Import contacts from a manual Apollo People CSV export."""
    print(f"\n{'='*60}")
    print(f"STEP 10: Import Apollo People CSV")
    print(f"{'='*60}")

    if CONTACTS_FILE.exists() and not force:
        contacts = load_json(CONTACTS_FILE)
        print(f"  Loaded from cache: {len(contacts)} contacts")
        return contacts

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"  ERROR: CSV not found: {csv_path}")
        sys.exit(1)

    targets_by_domain = {t.get("domain", "").strip().lower(): t for t in targets if t.get("domain")}

    APOLLO_CSV_COLUMNS = {
        "first_name": ["First Name", "first_name"],
        "last_name": ["Last Name", "last_name"],
        "email": ["Email", "email", "Email Address"],
        "title": ["Title", "title", "Job Title"],
        "company_name": ["Company", "company", "Company Name", "Organization Name"],
        "domain": ["Website", "website", "Company Domain", "domain", "Domain"],
        "linkedin_url": ["Person Linkedin Url", "LinkedIn URL", "linkedin_url", "LinkedIn", "Person LinkedIn URL"],
        "country": ["Country", "country", "Person Country"],
        "employees": ["# Employees", "employees", "Number of Employees", "Company Size"],
    }

    with csv_file.open("r", encoding="utf-8-sig") as f:
        raw_rows = list(csv.DictReader(f))
    print(f"  CSV rows: {len(raw_rows)}")

    all_contacts = []
    for row in raw_rows:
        def _get(field):
            for col in APOLLO_CSV_COLUMNS.get(field, [field]):
                if col in row and row[col]:
                    return row[col].strip()
            return ""

        domain = _normalize_domain(_get("domain") or (_get("email").split("@")[-1] if "@" in _get("email") else ""))
        target = targets_by_domain.get(domain, {})
        country = _get("country") or target.get("country", "")

        contact = {
            "first_name": _get("first_name"),
            "last_name": _get("last_name"),
            "email": _get("email"),
            "title": _get("title"),
            "company_name": normalize_company(_get("company_name") or target.get("company_name", domain)),
            "domain": domain,
            "segment": SEGMENT_NAME,
            "linkedin_url": _get("linkedin_url"),
            "country": country,
            "employees": _get("employees") or target.get("employees", ""),
            "social_proof": get_social_proof(country),
        }
        if contact["first_name"] and contact["domain"]:
            all_contacts.append(contact)

    # Post-filter excluded titles
    before_filter = len(all_contacts)
    all_contacts = [c for c in all_contacts if not _title_excluded(c.get("title", ""))]
    excluded = before_filter - len(all_contacts)
    if excluded:
        print(f"  Post-filter: removed {excluded} contacts (excluded titles)")

    # Dedupe
    seen = set()
    deduped = []
    for c in all_contacts:
        key = c["linkedin_url"] or f"{c['first_name']}|{c['last_name']}|{c['domain']}"
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    all_contacts = deduped

    save_json(CONTACTS_FILE, all_contacts)
    print(f"  Imported: {len(all_contacts)} contacts")

    today = tag()
    save_csv(CSV_DIR / f"import_apollo_people_{today}.csv", all_contacts,
             sheet_name=f"{PROJECT_CODE} | Import | {SEGMENT_CODE} Apollo People v4 Clay - {today}")

    return all_contacts


# ══════════════════════════════════════════════════════════════════════════════
# GETSALES EXPORT
# ══════════════════════════════════════════════════════════════════════════════

GETSALES_HEADERS = [
    "system_uuid", "pipeline_stage", "full_name", "first_name", "last_name",
    "position", "headline", "about", "linkedin_id", "sales_navigator_id",
    "linkedin_nickname", "linkedin_url", "facebook_nickname", "twitter_nickname",
    "work_email", "personal_email", "work_phone", "personal_phone",
    "connections_number", "followers_number", "primary_language",
    "has_open_profile", "has_verified_profile", "has_premium",
    "location_country", "location_state", "location_city",
    "active_flows", "list_name", "tags",
    "company_name", "company_industry", "company_linkedin_id", "company_domain",
    "company_linkedin_url", "company_employees_range", "company_headquarter",
    "cf_location", "cf_competitor_client",
    "cf_message1", "cf_message2", "cf_message3",
    "cf_personalization", "cf_compersonalization", "cf_personalization1",
    "cf_message4", "cf_linkedin_personalization", "cf_subject", "created_at",
]


def _extract_linkedin_nickname(url: str) -> str:
    m = re.search(r"linkedin\.com/in/([^/?]+)", url or "")
    return m.group(1) if m else ""


def export_getsales(without_email: list[dict], today: str) -> Path:
    date_folder = datetime.now().strftime("%d_%m")
    gs_dir = SOFIA_DIR / "get_sales_hub" / date_folder
    gs_dir.mkdir(parents=True, exist_ok=True)
    out_path = gs_dir / f"GetSales - {SEGMENT_NAME}_without_email - {date_folder.replace('_', '.')}.csv"
    gs_rows = []
    for c in without_email:
        li_url = c.get("linkedin_url", "").strip()
        if li_url and not li_url.startswith("http"):
            li_url = f"https://{li_url}"
        gs = {h: "" for h in GETSALES_HEADERS}
        gs["full_name"] = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        gs["first_name"] = c.get("first_name", "")
        gs["last_name"] = c.get("last_name", "")
        gs["position"] = c.get("title", "")
        gs["linkedin_nickname"] = _extract_linkedin_nickname(li_url)
        gs["linkedin_url"] = li_url
        gs["company_name"] = normalize_company(c.get("company_name", ""))
        gs["company_domain"] = c.get("domain", "")
        gs["cf_location"] = c.get("country", "")
        gs["list_name"] = f"{SEGMENT_NAME} Without Email {today}"
        gs["tags"] = SEGMENT_NAME
        gs_rows.append(gs)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GETSALES_HEADERS)
        writer.writeheader()
        writer.writerows(gs_rows)
    print(f"  GetSales-ready: {out_path.name} ({len(gs_rows)} contacts)")
    return out_path


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
    print(f"\n  * CHECKPOINT: ${cost:.2f} for {len(to_enrich)} contacts.")
    if sys.stdin.isatty():
        print("  Enter to continue, Ctrl+C to abort.")
        input()

    done = load_json(FINDYMAIL_PROGRESS) or {}
    found = not_found = 0
    out_of_credits = False
    t0 = time.time()
    sem = asyncio.Semaphore(FINDYMAIL_CONCURRENT)

    async def process_one(row):
        nonlocal found, not_found, out_of_credits
        if out_of_credits:
            return
        li = row.get("linkedin_url", "").strip()
        if not li:
            return
        if li in done:
            row["email"] = done[li].get("email", "")
            if done[li].get("email"): found += 1
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

    today = tag()
    save_csv(CSV_DIR / f"leads_verified_{today}.csv", with_email,
             sheet_name=f"{PROJECT_CODE} | Leads | {SEGMENT_CODE} Verified Emails v4 Clay - {today}")
    save_csv(CSV_DIR / f"leads_no_email_{today}.csv", without_email,
             sheet_name=f"{PROJECT_CODE} | Leads | {SEGMENT_CODE} No Email v4 Clay - {today}")

    if without_email:
        export_getsales(without_email, today)

    cost = len(with_email) * 0.01
    print(f"\n  Done in {time.time()-t0:.0f}s. With email: {len(with_email)}, without: {len(without_email)}")
    print(f"  FindyMail cost: ${cost:.2f}")
    return all_enriched


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12: SMARTLEAD UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

CAMPAIGN_NAME = "c-OnSocial_IM FIRST AGENCIES v4 Clay ALL GEO #C"
TIMING = [0, 4, 4, 6, 7]  # Day offsets between emails


def sl_params():
    return {"api_key": SMARTLEAD_API_KEY}


def create_campaign(name: str) -> int:
    r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/create", params=sl_params(), json={
        "name": name,
    }, timeout=30)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"  Created campaign: {cid} - {name}")
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
        r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/leads", params=sl_params(),
                       json={"lead_list": batch}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            uploaded = data.get("upload_count", len(batch))
            total += uploaded
            blocked = data.get("block_count", 0)
            dupes = data.get("duplicate_count", 0)
            if blocked or dupes:
                print(f"    Batch: +{uploaded}, blocked={blocked}, dupes={dupes}")
        elif r.status_code == 429:
            time.sleep(70)
            r2 = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/leads", params=sl_params(),
                            json={"lead_list": batch}, timeout=60)
            if r2.status_code == 200:
                total += r2.json().get("upload_count", len(batch))
        else:
            print(f"    Upload error: {r.status_code} {r.text[:200]}")
        time.sleep(1)
    print(f"  Uploaded: {total}/{len(leads)}")
    return total


def _load_sequences() -> list[dict] | None:
    """Load v4 sequence from markdown file."""
    seq_file = SCRIPT_DIR.parent / "projects" / "OnSocial" / "sequences" / "v4_im_first_agencies.md"
    if not seq_file.exists():
        # Fallback to influencer platforms sequence
        seq_file = SCRIPT_DIR.parent / "projects" / "OnSocial" / "sequences" / "v4_influencer_platforms.md"
    if not seq_file.exists():
        print(f"  Sequence file not found")
        return None

    text = seq_file.read_text(encoding="utf-8")
    steps = []
    email_pattern = re.compile(
        r'## Email (\d+[AB]?) - .+?\n\n\*\*Subject:\*\* (.+?)\n\n(.*?)(?=\n---|\n## |\Z)',
        re.DOTALL
    )
    for match in email_pattern.finditer(text):
        label, subject, body = match.group(1), match.group(2), match.group(3).strip()
        body = re.sub(r'\n`\d+ words`', '', body).strip()
        body = body.replace("\n\n", "<br><br>").replace("\n", "<br>")
        subject = subject.replace("\u2014", "-")
        body = body.replace("\u2014", "-")
        steps.append({"label": label, "subject": subject, "body": body})

    if steps:
        print(f"  Loaded {len(steps)} email steps from {seq_file.name}")
    return steps if steps else None


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

    print(f"  Leads with email: {len(deduped)}")

    country_counts = Counter(c.get("country", "UNKNOWN") for c in deduped)
    print(f"  Top countries:")
    for co, cnt in country_counts.most_common(10):
        print(f"    {cnt:3d}  {co}")

    # Social proof stats
    sp_counts = Counter(c.get("social_proof", "NO_PROOF") for c in deduped)
    print(f"  Social proof distribution:")
    for sp, cnt in sp_counts.most_common():
        print(f"    {cnt:3d}  {sp}")

    log = load_json(UPLOAD_LOG) or {}
    cid = log.get("campaign_id")

    # Step 12a: Create or reuse campaign
    if cid:
        print(f"\n  Existing campaign: {cid}")
    else:
        if not _checkpoint(f"Create campaign '{CAMPAIGN_NAME}'?"):
            return
        cid = create_campaign(CAMPAIGN_NAME)
        log["campaign_id"] = cid
        log["campaign_name"] = CAMPAIGN_NAME
        log["at"] = ts()
        save_json(UPLOAD_LOG, log)

    # Step 12b: Attach email accounts
    if not _checkpoint(f"Attach {len(SMARTLEAD_EMAIL_ACCOUNTS)} email accounts?"):
        print("  Skipping email accounts.")
    else:
        r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/email-accounts", params=sl_params(),
                       json={"email_account_ids": SMARTLEAD_EMAIL_ACCOUNTS}, timeout=30)
        if r.status_code == 200:
            print(f"  Attached {len(SMARTLEAD_EMAIL_ACCOUNTS)} email accounts")
        else:
            print(f"  Email accounts error: {r.status_code} {r.text[:200]}")

    # Step 12c: Upload leads
    if not _checkpoint(f"Upload {len(deduped)} leads to campaign {cid}?"):
        print("  Skipping leads upload.")
    else:
        uploaded = upload_leads(cid, deduped)
        log["leads"] = uploaded
        log["uploaded_at"] = ts()
        save_json(UPLOAD_LOG, log)

    # Step 12d: Load and upload sequences
    sequences = _load_sequences()
    if sequences:
        if not _checkpoint(f"Upload {len(sequences)} email steps?"):
            print("  Skipping sequences.")
        else:
            step_groups = {}
            for s in sequences:
                step_num = re.match(r'(\d+)', s["label"]).group(1)
                step_groups.setdefault(step_num, []).append(s)

            for i, (step_num, variants) in enumerate(sorted(step_groups.items())):
                wait_days = TIMING[i] if i < len(TIMING) else 7
                seq_payload = {
                    "seq_number": i + 1,
                    "seq_delay_details": {"delay_in_days": wait_days},
                    "variant_distribution_type": "EQUAL" if len(variants) > 1 else None,
                }
                variant_payloads = []
                for vi, v in enumerate(variants):
                    variant_payloads.append({
                        "subject": v["subject"],
                        "email_body": v["body"],
                        "variant_label": chr(65 + vi) if len(variants) > 1 else None,
                    })
                seq_payload["variants"] = variant_payloads

                r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/sequences",
                               params=sl_params(), json=seq_payload, timeout=30)
                if r.status_code == 200:
                    ab = f" (A/B)" if len(variants) > 1 else ""
                    print(f"    Step {step_num}{ab}: {variants[0]['subject'][:40]}...")
                else:
                    print(f"    Step {step_num} error: {r.status_code} {r.text[:200]}")

            log["sequences_uploaded"] = True
            save_json(UPLOAD_LOG, log)
    else:
        print("  No sequences loaded - add manually in SmartLead UI.")

    # Step 12e: Set schedule
    if not _checkpoint(f"Set schedule Mon-Fri 8am-6pm EST?"):
        print("  Skipping schedule.")
    else:
        r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/schedule", params=sl_params(), json={
            "timezone": "America/New_York", "days_of_the_week": [1, 2, 3, 4, 5],
            "start_hour": "08:00", "end_hour": "18:00",
            "min_time_btw_emails": 5, "max_new_leads_per_day": 500,
        }, timeout=30)
        if r.status_code == 200:
            print(f"  Schedule set: Mon-Fri 8am-6pm EST")
        else:
            print(f"  Schedule error: {r.status_code} {r.text[:200]}")

    # Step 12f: NEVER auto-activate
    print(f"\n  Campaign '{CAMPAIGN_NAME}' is in DRAFTED status.")
    print(f"  Activate manually in SmartLead UI.")

    print(f"\n  Done. Campaign {cid}: {log.get('leads', 0)} leads, "
          f"sequences={'yes' if log.get('sequences_uploaded') else 'no'}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

STEPS = ["start", "blacklist", "prefilter", "scrape", "analyze", "verify",
         "export", "people", "findymail", "upload"]


def main():
    p = argparse.ArgumentParser(description="OnSocial Clay IM_FIRST_AGENCIES v4 ALL GEO Pipeline")
    p.add_argument("--from-step", choices=STEPS, default="start",
                   help="Start from this step")
    p.add_argument("--run-id", type=int, help="Resume existing run")
    p.add_argument("--apollo-csv", help="Apollo People CSV (skip auto scrape)")
    p.add_argument("--max-findymail", type=int, default=1500)
    p.add_argument("--force", action="store_true", help="Force re-run (ignore cache)")
    p.add_argument("--prompt-file", help="Custom analysis prompt file")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print(f"\n{'='*60}")
    print(f"  OnSocial Clay Pipeline - {SEGMENT_NAME} v4 ALL GEO")
    print(f"  {ts()}")
    print(f"{'='*60}")
    print(f"  Project: OnSocial (ID {PROJECT_ID})")
    print(f"  Segment: {SEGMENT_NAME} ({SEGMENT_CODE})")
    print(f"  Company source: Clay (description_keywords, direct, FREE)")
    print(f"  People source: Apollo People UI (Puppeteer, FREE)")
    print(f"  description_keywords: {len(CLAY_FILTERS['description_keywords'])}")
    print(f"  description_keywords_exclude: {len(CLAY_FILTERS['description_keywords_exclude'])}")
    print(f"  Industries: {len(CLAY_FILTERS['industries'])}")
    print(f"  Employees: {CLAY_FILTERS['minimum_member_count']}-{CLAY_FILTERS['maximum_member_count']}")
    print(f"  Geo: ALL (no country_names)")
    print(f"  People seniorities: {', '.join(PEOPLE_SENIORITIES)}")
    print(f"  People titles: {len(PEOPLE_TITLES)}")
    print(f"  Excluded title patterns: {len(EXCLUDED_TITLES_PATTERNS)}")
    print(f"  From step: {args.from_step}")

    if args.dry_run:
        print(f"\n  DRY RUN - no actions taken")
        print(f"\n  description_keywords ({len(CLAY_FILTERS['description_keywords'])}):")
        for kw in CLAY_FILTERS["description_keywords"]:
            print(f"    - {kw}")
        print(f"\n  description_keywords_exclude ({len(CLAY_FILTERS['description_keywords_exclude'])}):")
        for kw in CLAY_FILTERS["description_keywords_exclude"]:
            print(f"    - {kw}")
        print(f"\n  Industries: {CLAY_FILTERS['industries']}")
        print(f"\n  People titles ({len(PEOPLE_TITLES)}):")
        for t in PEOPLE_TITLES:
            print(f"    - {t}")
        print(f"\n  Excluded title patterns ({len(EXCLUDED_TITLES_PATTERNS)}):")
        for t in EXCLUDED_TITLES_PATTERNS:
            print(f"    - {t}")
        print(f"\n  Clay filters JSON:")
        print(json.dumps(CLAY_FILTERS, indent=2))
        return

    steps = STEPS[STEPS.index(args.from_step):]

    prompt_text = None
    if args.prompt_file:
        prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")

    run_id = args.run_id or load_state().get("run_id")

    # -- Step 0: Start Clay gathering --
    if "start" in steps:
        run_id = step0_start()
        # Wait for gathering to complete
        print("\n  Waiting for Clay gathering to complete...")
        conn_errors = 0
        while True:
            time.sleep(15)
            try:
                r = httpx.get(f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
                              headers=BACKEND_HEADERS, timeout=30)
                phase = r.json().get("current_phase", "")
                if phase != "gather":
                    print(f"  Phase: {phase}")
                    break
                print("  ..gathering")
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException):
                conn_errors += 1
                if conn_errors >= 10:
                    print(f"  Too many errors. Resume: --from-step blacklist --run-id {run_id}")
                    sys.exit(1)
                time.sleep(15)

    # -- Step 2: Blacklist -> CP1 --
    if "blacklist" in steps and run_id:
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        phase = run_info.get("current_phase", "")
        if phase == "awaiting_scope_ok":
            gates = api("get", f"/pipeline/gathering/approval-gates?project_id={PROJECT_ID}",
                        raise_on_error=False)
            gate_list = gates if isinstance(gates, list) else gates.get("items", [])
            pending = [g for g in gate_list if g.get("gathering_run_id") == run_id and g.get("status") == "pending"]
            if pending:
                gate = pending[0]
                print(f"\n  * CP1 - gate #{gate['id']}, passed={gate.get('scope',{}).get('passed','?')}")
                print(f"  PAUSING. Approve gate, then resume:")
                print(f"    --from-step prefilter --run-id {run_id}")
                return
        elif phase in ("gathered", "gather"):
            cp1 = step2_blacklist(run_id)
            if cp1.get("gate_id"):
                print(f"\n  PAUSING at CP1. Approve gate #{cp1['gate_id']}, then resume:")
                print(f"    --from-step prefilter --run-id {run_id}")
                return

    # -- Step 3: Pre-filter --
    if "prefilter" in steps and run_id:
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        phase = run_info.get("current_phase", "")
        if phase == "awaiting_scope_ok":
            approve_pending_gate(run_id)
            phase = "scope_approved"
        if phase == "scope_approved":
            step3_prefilter(run_id)

    # -- Step 4: Scrape --
    if "scrape" in steps and run_id:
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        phase = run_info.get("current_phase", "")
        if phase == "filtered":
            step4_scrape(run_id)

    # -- Step 5: Analyze -> CP2 --
    if "analyze" in steps and run_id:
        _, prompt = get_latest_prompt()
        text = prompt_text or prompt or DEFAULT_ANALYSIS_PROMPT
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        phase = run_info.get("current_phase", "")
        if phase == "scraped":
            cp2 = step5_analyze(run_id, text)
            if cp2.get("gate_id"):
                print(f"\n  PAUSING at CP2. Approve gate #{cp2['gate_id']}, then resume:")
                print(f"    --from-step verify --run-id {run_id}")
                return

    # -- Step 6: Verify -> CP3 --
    if "verify" in steps and run_id:
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        phase = run_info.get("current_phase", "")
        if phase == "awaiting_targets_ok":
            approve_pending_gate(run_id)
        blacklist_approved_targets(run_id)
        cp3 = step6_prepare_verify(run_id)
        if cp3.get("gate_id"):
            print(f"\n  PAUSING at CP3. Approve gate #{cp3['gate_id']}, then resume:")
            print(f"    --from-step export --run-id {run_id}")
            return

    # -- Step 9: Export targets --
    if "export" in steps:
        targets = step9_export_targets(force=args.force)
    else:
        targets = load_json(TARGETS_FILE) or []

    # -- Step 10: Apollo People Search --
    if "people" in steps:
        if args.apollo_csv:
            contacts = step10_import_apollo_csv(args.apollo_csv, targets, force=args.force)
        else:
            contacts = step10_apollo_people_search(targets, force=args.force)
    else:
        contacts = load_json(CONTACTS_FILE) or []

    # -- Step 11: FindyMail --
    if "findymail" in steps:
        contacts = asyncio.run(step11_findymail(contacts, max_contacts=args.max_findymail,
                                                  force=args.force))
    else:
        contacts = load_json(ENRICHED_FILE) or contacts

    # -- Step 12: SmartLead Upload --
    if "upload" in steps:
        step12_upload(contacts)


if __name__ == "__main__":
    main()
