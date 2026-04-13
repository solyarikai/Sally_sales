#!/usr/bin/env python3
"""
OnSocial Lead Pipeline
======================

Две команды:

  # 1. Компании → классифицировать таргеты
  python3 pipeline.py companies --csv OS_import_SOCCOM.csv --project-id 42
  python3 pipeline.py companies --run-id 337 --from-step classify  # возобновить

  # 2. Люди → обогатить → SmartLead
  python3 pipeline.py people --csv apollo_export.csv --project-id 42 --segment SOCCOM
  python3 pipeline.py people --csv apollo_export.csv --project-id 42 --segment SOCCOM --from-step upload

Env: FINDYMAIL_API_KEY, SMARTLEAD_API_KEY
Backend: localhost:8000 (Hetzner)
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

# ── Connections ────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
SOFIA_DIR = SCRIPT_DIR.parent

BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://localhost:8000")
BACKEND_HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
FINDYMAIL_BASE = "https://app.findymail.com"
FINDYMAIL_CONCURRENT = 5

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"

BATCH_SIZE = 500

_AUTO_APPROVE = False

# Apollo CSV column name mapping
APOLLO_CSV_COLUMNS = {
    "first_name": ["First Name", "first_name"],
    "last_name": ["Last Name", "last_name"],
    "email": ["Email", "email", "Email Address"],
    "title": ["Title", "title", "Job Title"],
    "company_name": ["Company", "company", "Company Name", "Organization Name"],
    "domain": [
        "Website",
        "website",
        "Company Domain",
        "domain",
        "Domain",
        "Organization Website",
    ],
    "linkedin_url": [
        "Person Linkedin Url",
        "LinkedIn URL",
        "linkedin_url",
        "LinkedIn",
        "Person LinkedIn URL",
    ],
    "country": ["Country", "country", "Person Country"],
    "company_country": ["Company Country", "company_country"],
    "city": ["City", "city", "Person City"],
    "employees": ["# Employees", "employees", "Number of Employees", "Company Size"],
    "industry": ["Industry", "industry"],
    "seniority": ["Seniority", "seniority"],
    "company_linkedin_url": [
        "Company Linkedin Url",
        "Company LinkedIn URL",
        "company_linkedin_url",
    ],
    "phone": ["Mobile Phone", "Phone", "phone", "Phone Number"],
}

GETSALES_HEADERS = [
    "system_uuid",
    "pipeline_stage",
    "full_name",
    "first_name",
    "last_name",
    "position",
    "headline",
    "about",
    "linkedin_id",
    "sales_navigator_id",
    "linkedin_nickname",
    "linkedin_url",
    "facebook_nickname",
    "twitter_nickname",
    "work_email",
    "personal_email",
    "work_phone",
    "personal_phone",
    "connections_number",
    "followers_number",
    "primary_language",
    "has_open_profile",
    "has_verified_profile",
    "has_premium",
    "location_country",
    "location_state",
    "location_city",
    "active_flows",
    "list_name",
    "tags",
    "company_name",
    "company_industry",
    "company_linkedin_id",
    "company_domain",
    "company_linkedin_url",
    "company_employees_range",
    "company_headquarter",
    "cf_location",
    "cf_competitor_client",
    "cf_message1",
    "cf_message2",
    "cf_message3",
    "cf_personalization",
    "cf_compersonalization",
    "cf_personalization1",
    "cf_message4",
    "cf_linkedin_personalization",
    "cf_subject",
    "created_at",
]

# ── Utilities ──────────────────────────────────────────────────────────────────


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def tag() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(path: Path, rows: list[dict], sheet_name: str = None):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → CSV: {path.name} ({len(rows)} rows)")
    if sheet_name:
        _upload_to_sheets(keys, rows, sheet_name)


def normalize_company(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"\s+", " ", name).strip()
    for suffix in [
        ", Inc.",
        " Inc.",
        ", LLC",
        " LLC",
        ", Ltd.",
        " Ltd.",
        ", Corp.",
        " Corp.",
    ]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def _normalize_domain(raw: str) -> str:
    if not raw:
        return ""
    d = raw.lower().strip().rstrip("/")
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0]
    return d


def _extract_linkedin_nickname(url: str) -> str:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url or "")
    return m.group(1) if m else ""


def _checkpoint(message: str) -> bool:
    print(f"\n  ★ {message}")
    if sys.stdin.isatty():
        print("  [Enter] продолжить, [s] пропустить, [Ctrl+C] отмена.")
        resp = input("  > ").strip().lower()
        return resp != "s"
    elif _AUTO_APPROVE:
        print("  Auto-approve — продолжаю.")
        return True
    else:
        print("  ПАУЗА. Проверь результат выше, потом возобнови с --from-step.")
        sys.exit(0)


# ── Google Sheets ──────────────────────────────────────────────────────────────


def _get_gsheets_creds():
    for path in [
        Path.home() / ".claude/google-sheets/token.json",
        SCRIPT_DIR.parent.parent / ".claude/mcp/google-sheets/token.json",
        Path.home() / "magnum-opus-project/repo/sofia/.google-sheets/token.json",
        SOFIA_DIR / ".google-sheets" / "token.json",
    ]:
        if path.exists():
            return path
    return None


_GSHEETS_FOLDER_MAP = {
    "Leads": "1_1ck-0sn1jXm2px4MCz4o_ZST6J6JfOe",
    "Targets": "124SCStl6SHuMPquxyfj0Av5O8U4kNrTj",
    "Import": "1O-rkQK6btZjXzO-p31ZMsrjcLWeacZRV",
    "Ops": "1K7bVbvVU3LIK5V_cGLwhFKINBdURZLD0",
    "Analytics": "1xRAdlbn2BK3QYBuYtUjgVjhsb2wH5MiV",
    "Archive": "1uLKLR6NFzJHb_XraE5sfKrSe-HbNja9t",
}


def _upload_to_sheets(headers: list[str], rows: list[dict], sheet_name: str):
    token_path = _get_gsheets_creds()
    if not token_path:
        print("  ⚠ Sheet upload failed: Google Sheets token.json not found")
        return
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        sheets_svc = build("sheets", "v4", credentials=creds).spreadsheets()
        drive_svc = build("drive", "v3", credentials=creds)

        # rows can be list[dict] or list[list]
        if rows and isinstance(rows[0], dict):
            data = [headers] + [[str(r.get(h, "")) for h in headers] for r in rows]
        else:
            data = [headers] + [list(r) for r in rows]

        ss = sheets_svc.create(body={"properties": {"title": sheet_name}}).execute()
        sid = ss["spreadsheetId"]
        sheets_svc.values().update(
            spreadsheetId=sid,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": data},
        ).execute()

        # Move to correct Drive folder based on sheet name type
        folder_id = None
        for key, fid in _GSHEETS_FOLDER_MAP.items():
            if f"| {key} |" in sheet_name:
                folder_id = fid
                break
        if folder_id:
            meta = drive_svc.files().get(fileId=sid, fields="parents").execute()
            prev = ",".join(meta.get("parents", []))
            drive_svc.files().update(
                fileId=sid, addParents=folder_id, removeParents=prev, fields="id"
            ).execute()

        print(f"  ✓ Sheets: {sheet_name} ({len(data) - 1} rows)")
    except Exception as e:
        print(f"  ⚠ Sheets upload failed: {e}")


# ── Backend API ────────────────────────────────────────────────────────────────


def api(method: str, path: str, raise_on_error: bool = True, **kwargs) -> dict:
    url = f"{BACKEND_BASE}/api{path}"
    r = getattr(httpx, method)(url, headers=BACKEND_HEADERS, timeout=300, **kwargs)
    if r.status_code >= 400:
        if raise_on_error:
            print(f"  API ERROR {r.status_code}: {r.text[:500]}")
            sys.exit(1)
        return {"_error": r.status_code, "_detail": r.text[:500]}
    return r.json()


def api_long(
    method: str,
    path: str,
    expected_phase: str,
    run_id: int,
    timeout: int = 3600,
    poll_interval: int = 30,
    **kwargs,
) -> dict:
    url = f"{BACKEND_BASE}/api{path}"
    try:
        r = getattr(httpx, method)(
            url, headers=BACKEND_HEADERS, timeout=timeout, **kwargs
        )
        if r.status_code >= 400:
            return {"_error": r.status_code, "_detail": r.text[:500]}
        return r.json()
    except (
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ReadError,
    ) as e:
        print(
            f"  Connection lost ({type(e).__name__}). Backend may still be working..."
        )
        print(f"  Polling until phase reaches '{expected_phase}'...")
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll_interval)
            try:
                r2 = httpx.get(
                    f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
                    headers=BACKEND_HEADERS,
                    timeout=30,
                )
                if r2.status_code == 200:
                    phase = r2.json().get("current_phase", "")
                    print(f"  [{int(time.time() - start)}s] Phase: {phase}")
                    if phase == expected_phase or phase.startswith("awaiting_"):
                        return r2.json()
            except Exception:
                pass
        return {"_timeout": True}


# ── Project Config ─────────────────────────────────────────────────────────────


class ProjectConfig:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.project_name = ""
        self.segments = {}
        self.prompt_id = None
        self.prompt_text = ""
        self.email_accounts = []
        self.schedule = {}
        self.state_dir = None
        self.csv_dir = None

    def load(self):
        print(f"\n  Loading config for project {self.project_id}...")
        try:
            project = api(
                "get", f"/contacts/projects/{self.project_id}", raise_on_error=False
            )
            self.project_name = project.get("name", f"Project_{self.project_id}")
        except Exception:
            self.project_name = f"Project_{self.project_id}"
            print(f"  ⚠ Backend unavailable — using project name '{self.project_name}'")
        print(f"  Project: {self.project_name}")

        try:
            segs = api("get", "/knowledge-base/segments", raise_on_error=False)
            seg_list = segs if isinstance(segs, list) else segs.get("items", [])
            for s in seg_list:
                data = s.get("data", {})
                if data.get("project_id") == self.project_id and s.get(
                    "is_active", True
                ):
                    slug = data.get("slug", s["name"].lower())
                    self.segments[slug] = {"id": s["id"], "name": s["name"], **data}
        except Exception:
            pass
        print(f"  Segments: {', '.join(self.segments.keys()) or 'none'}")

        try:
            result = api(
                "get",
                f"/pipeline/gathering/prompts?project_id={self.project_id}",
                raise_on_error=False,
            )
            prompts = result if isinstance(result, list) else result.get("items", [])
            active = [p for p in prompts if p.get("is_active", True)]
            if active:
                latest = max(active, key=lambda p: p["id"])
                self.prompt_id = latest["id"]
                self.prompt_text = latest.get("prompt_text", "")
                print(f"  Prompt: #{latest['id']} '{latest.get('name', '?')}'")
        except Exception:
            pass

        try:
            pk_accounts = api(
                "get",
                f"/projects/{self.project_id}/knowledge/smartlead/email_accounts",
                raise_on_error=False,
            )
            if pk_accounts and not pk_accounts.get("_error"):
                val = pk_accounts.get("value", "{}")
                parsed = json.loads(val) if isinstance(val, str) else val
                self.email_accounts = parsed.get("account_ids", [])
        except Exception:
            pass

        try:
            pk_config = api(
                "get",
                f"/projects/{self.project_id}/knowledge/smartlead/config",
                raise_on_error=False,
            )
            if pk_config and not pk_config.get("_error"):
                val = pk_config.get("value", "{}")
                parsed = json.loads(val) if isinstance(val, str) else val
                self.schedule = parsed.get("schedule", {})
        except Exception:
            pass

        project_slug = self.project_name.replace(" ", "").lower()
        self.state_dir = SOFIA_DIR.parent / "state" / project_slug
        self.csv_dir = SOFIA_DIR / "output" / self.project_name / "pipeline"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        print(f"  State: {self.state_dir}")
        print(f"  Email accounts: {len(self.email_accounts)}")

    def get_social_proof(self, country: str, segment_slug: str) -> str:
        seg = self.segments.get(segment_slug, {})
        sp = seg.get("social_proof", {})
        return sp.get(country, sp.get("_default", ""))

    def get_campaign_name(self, segment_slug: str, contacts: list) -> str:
        seg = self.segments.get(segment_slug, {})
        template = seg.get("campaign_name_template", "c-{project}_{segment} {geo} #C")
        countries = set(c.get("country", "") for c in contacts if c.get("country"))
        geo = "ALL GEO" if len(countries) > 3 else ", ".join(sorted(countries)).upper()
        display_name = seg.get("display_name", seg.get("name", segment_slug))
        return template.format(project=self.project_name, segment=display_name, geo=geo)

    def validate_email_accounts(self) -> list:
        if not self.email_accounts:
            print("  ⚠ No email accounts configured")
            return []
        active = []
        for aid in self.email_accounts:
            try:
                r = httpx.get(
                    f"{SMARTLEAD_BASE}/email-accounts/{aid}",
                    params={"api_key": SMARTLEAD_API_KEY},
                    timeout=10,
                )
                if r.status_code == 200 and r.json().get("is_active", True):
                    active.append(aid)
                elif r.status_code == 200:
                    print(f"  ✗ #{aid} — inactive, skipping")
            except Exception:
                active.append(aid)
        self.email_accounts = active
        return active


# ══════════════════════════════════════════════════════════════════════════════
# CMD: COMPANIES — CSV → classify → targets
# ══════════════════════════════════════════════════════════════════════════════


def _read_domains_from_csv(csv_path: Path) -> list[str]:
    """Extract domains from companies CSV (Website / Domain column)."""
    domains = []
    skipped = 0
    with csv_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = ""
            for col in [
                "Website",
                "website",
                "Domain",
                "domain",
                "Company Domain",
                "URL",
            ]:
                if row.get(col, "").strip():
                    raw = row[col].strip()
                    break
            d = _normalize_domain(raw)
            if d and "." in d:
                domains.append(d)
            else:
                skipped += 1
    domains = list(dict.fromkeys(domains))  # dedup, preserve order
    print(f"  Domains extracted: {len(domains)} (skipped {skipped} empty)")
    return domains


def _create_run(config: ProjectConfig, domains: list[str]) -> int:
    result = api(
        "post",
        "/pipeline/gathering/start",
        json={
            "project_id": config.project_id,
            "source_type": "manual.companies.manual",
            "filters": {"domains": domains},
            "triggered_by": "operator",
            "input_mode": "import",
            "notes": f"pipeline.py import — {len(domains)} domains — {tag()}",
        },
    )
    run_id = result["id"]
    print(f"  Run #{run_id} created ({len(domains)} domains)")
    return run_id


def _wait_for_phase(run_id: int, target_phase: str, timeout_s: int = 120):
    """Poll until run leaves 'gather' phase."""
    for _ in range(timeout_s // 5):
        time.sleep(5)
        r = httpx.get(
            f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
            headers=BACKEND_HEADERS,
            timeout=30,
        )
        if r.status_code == 200:
            phase = r.json().get("current_phase", "")
            if phase != "gather":
                print(f"  Phase: {phase}")
                return phase
    print("  WARNING: timeout waiting for dedup phase")
    return ""


def _approve_pending_gate(config: ProjectConfig, run_id: int) -> bool:
    gates = api(
        "get",
        f"/pipeline/gathering/approval-gates?project_id={config.project_id}",
        raise_on_error=False,
    )
    items = gates if isinstance(gates, list) else gates.get("items", [])
    for g in items:
        if g.get("gathering_run_id") == run_id and g.get("status") == "pending":
            api(
                "post",
                f"/pipeline/gathering/approval-gates/{g['id']}/approve",
                json={},
                raise_on_error=False,
            )
            print(f"  Gate #{g['id']} approved")
            return True
    return False


def _run_companies(config: ProjectConfig, args):
    run_id = args.run_id
    from_step = args.from_step or "blacklist"

    # ── Create run from CSV ──────────────────────────────────────────────────
    if not run_id:
        if not args.csv:
            print("ERROR: --csv required (or --run-id to resume)")
            sys.exit(1)
        csv_path = Path(args.csv)
        print(f"\n  CSV: {csv_path.name}")
        domains = _read_domains_from_csv(csv_path)
        if not domains:
            print("  ERROR: No domains found in CSV")
            sys.exit(1)

        # Split into batches if needed
        if len(domains) > BATCH_SIZE:
            batches = [
                domains[i : i + BATCH_SIZE] for i in range(0, len(domains), BATCH_SIZE)
            ]
            print(f"  Splitting into {len(batches)} batches of {BATCH_SIZE}")
        else:
            batches = [domains]

        run_ids = [_create_run(config, batch) for batch in batches]
        # Process each run through dedup→blacklist→prefilter→scrape→classify
        for rid in run_ids:
            _wait_for_phase(rid, "gathered")
            _run_companies_pipeline(config, rid, args)
        return

    # ── Resume existing run ─────────────────────────────────────────────────
    print(f"\n  Resuming run #{run_id} from step '{from_step}'")
    _run_companies_pipeline(config, run_id, args, from_step=from_step)


def _run_companies_pipeline(
    config: ProjectConfig, run_id: int, args, from_step: str = "blacklist"
):
    STEPS = [
        "blacklist",
        "prefilter",
        "scrape",
        "classify",
        "verify",
        "adjust",
        "export",
    ]
    start_idx = STEPS.index(from_step) if from_step in STEPS else 0

    def should_run(step: str) -> bool:
        return STEPS.index(step) >= start_idx

    # ── Check current phase ──────────────────────────────────────────────────
    run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
    phase = run_info.get("current_phase", "")
    print(f"\n  Run #{run_id} — phase: {phase}")

    # ── STEP 1-2: BLACKLIST ──────────────────────────────────────────────────
    if should_run("blacklist") and phase in ("gathered",):
        print(f"\n{'─' * 50}")
        print("  STEP 2: BLACKLIST")
        result = api("post", f"/pipeline/gathering/runs/{run_id}/blacklist-check")
        gates = api(
            "get", f"/pipeline/gathering/approval-gates?project_id={config.project_id}"
        )
        items = gates if isinstance(gates, list) else gates.get("items", [])
        pending = [
            g
            for g in items
            if g.get("gathering_run_id") == run_id and g.get("status") == "pending"
        ]
        if pending:
            gate = pending[0]
            scope = gate.get("scope", {})
            print(
                f"  Passed: {scope.get('passed', '?')}, Rejected: {scope.get('rejected', '?')}"
            )
            print(f"\n  ★ CP1 — gate #{gate['id']}")
            print("  Проверь scope — правильный проект? правильный сегмент?")
            if _checkpoint("Approve scope?"):
                api(
                    "post",
                    f"/pipeline/gathering/approval-gates/{gate['id']}/approve",
                    json={"decision_note": "Approved"},
                )
        run_info = api(
            "get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False
        )
        phase = run_info.get("current_phase", "")

    # ── STEP 3: PREFILTER ────────────────────────────────────────────────────
    if should_run("prefilter") and phase == "scope_approved":
        print(f"\n{'─' * 50}")
        print("  STEP 3: PREFILTER")
        r = api("post", f"/pipeline/gathering/runs/{run_id}/pre-filter")
        print(f"  Passed: {r.get('passed', '?')}")
        run_info = api(
            "get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False
        )
        phase = run_info.get("current_phase", "")

    # ── STEP 4: SCRAPE ───────────────────────────────────────────────────────
    if should_run("scrape") and phase == "filtered":
        print(f"\n{'─' * 50}")
        print("  STEP 4: SCRAPE (10-60 min...)")
        result = api_long(
            "post",
            f"/pipeline/gathering/runs/{run_id}/scrape",
            expected_phase="scraped",
            run_id=run_id,
            timeout=3600,
        )
        if not result.get("_timeout"):
            print(
                f"  Scraped: {result.get('scraped', '?')}, Skipped: {result.get('skipped', '?')}"
            )
        run_info = api(
            "get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False
        )
        phase = run_info.get("current_phase", "")

    # ── STEP 5: CLASSIFY ─────────────────────────────────────────────────────
    if should_run("classify") and phase == "scraped":
        print(f"\n{'─' * 50}")
        print("  STEP 5: CLASSIFY")
        prompt_text = config.prompt_text
        if not prompt_text:
            print("  ERROR: No classify prompt in DB")
            sys.exit(1)
        result = api_long(
            "post",
            f"/pipeline/gathering/runs/{run_id}/analyze",
            expected_phase="analyzed",
            run_id=run_id,
            timeout=3600,
            params={"model": "gpt-4o-mini", "prompt_text": prompt_text},
        )
        targets = result.get("targets_found", 0)
        total = result.get("total_analyzed", 0)
        print(
            f"  Targets: {targets}/{total} ({targets / total * 100:.0f}%)"
            if total
            else "  No companies analyzed"
        )

        # Show target list
        gates = api(
            "get", f"/pipeline/gathering/approval-gates?project_id={config.project_id}"
        )
        items = gates if isinstance(gates, list) else gates.get("items", [])
        pending = [
            g
            for g in items
            if g.get("gathering_run_id") == run_id and g.get("status") == "pending"
        ]
        if pending:
            gate = pending[0]
            target_list = gate.get("scope", {}).get("targets", [])
            if isinstance(target_list, list):
                for t in target_list[:30]:
                    print(
                        f"    {t.get('domain', '?')} — {t.get('name', '?')} ({t.get('segment', '?')} {t.get('confidence', '?')})"
                    )
                if len(target_list) > 30:
                    print(f"    ... +{len(target_list) - 30} more")

        print("\n  ★ CP2 — проверь таргеты выше.")
        print(
            "  Если accuracy < 90% — используй --from-step adjust --run-id {run_id} --prompt-file new_prompt.txt"
        )
        _checkpoint("Таргеты корректны?")
        if pending:
            api(
                "post",
                f"/pipeline/gathering/approval-gates/{pending[0]['id']}/approve",
                json={"decision_note": "Approved"},
            )
        run_info = api(
            "get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False
        )
        phase = run_info.get("current_phase", "")

    # ── STEP 7: ADJUST (re-classify) ────────────────────────────────────────
    if should_run("adjust") and args.__dict__.get("prompt_file"):
        print(f"\n{'─' * 50}")
        print("  STEP 7: ADJUST — re-classify with new prompt")
        prompt_file = Path(args.prompt_file)
        if not prompt_file.exists():
            print(f"  ERROR: prompt file not found: {prompt_file}")
            sys.exit(1)
        new_prompt = prompt_file.read_text(encoding="utf-8").strip()
        result = api(
            "post",
            f"/pipeline/gathering/runs/{run_id}/re-analyze",
            params={"model": "gpt-4o-mini", "prompt_text": new_prompt},
        )
        print(f"  New target rate: {result.get('target_rate', 0) * 100:.1f}%")
        print(f"  Targets: {result.get('targets_count', '?')}")
        _approve_pending_gate(config, run_id)

    # ── STEP 8: EXPORT ───────────────────────────────────────────────────────
    if should_run("export"):
        print(f"\n{'─' * 50}")
        print(f"  STEP 8: EXPORT (run #{run_id})")
        sql = (
            f"SELECT dc.domain, dc.name, dc.matched_segment, dc.confidence "
            f"FROM discovered_companies dc "
            f"WHERE dc.project_id={config.project_id} "
            f"AND dc.is_target=true "
            f"AND dc.domain = ANY("
            f"SELECT jsonb_array_elements_text(gr.filters->'domains') "
            f"FROM gathering_runs gr WHERE gr.id={run_id})"
        )
        is_hetzner = os.path.exists("/home/leadokol/magnum-opus-project")
        psql_cmd = f"docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -F'|' -c \"{sql}\""
        run_args = (
            ["bash", "-c", psql_cmd] if is_hetzner else ["ssh", "hetzner", psql_cmd]
        )
        r = subprocess.run(run_args, capture_output=True, text=True, timeout=30)
        targets = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                targets.append(
                    {
                        "domain": parts[0].strip(),
                        "company_name": parts[1].strip(),
                        "segment": parts[2].strip(),
                        "confidence": parts[3].strip() if len(parts) > 3 else "",
                    }
                )
        if not targets:
            print("  No targets found for this run")
            return
        today = tag()
        by_seg = {}
        for t in targets:
            by_seg.setdefault(t["segment"], []).append(t)
        print(f"  Targets: {len(targets)}")
        for seg_name, seg_targets in sorted(by_seg.items()):
            print(f"    {seg_name}: {len(seg_targets)}")
            safe = seg_name.replace("/", "-").replace(" ", "_").replace("|", "-")
            save_csv(
                config.csv_dir / f"targets_{safe}_r{run_id}_{today}.csv",
                seg_targets,
                sheet_name=f"OS | Targets | {seg_name} r{run_id} — {today}",
            )
        print("\n  Готово. Идёшь в Apollo, берёшь людей → pipeline.py people --csv ...")


# ══════════════════════════════════════════════════════════════════════════════
# CMD: PEOPLE — Apollo CSV → FindyMail → SmartLead
# ══════════════════════════════════════════════════════════════════════════════


def _map_apollo_row(row: dict, config: ProjectConfig, segment_slug: str) -> dict:
    """Map Apollo CSV row to contact format."""

    def _get(field: str) -> str:
        for col in APOLLO_CSV_COLUMNS.get(field, [field]):
            if row.get(col, "").strip():
                return row[col].strip()
        return ""

    email = _get("email")
    domain = _normalize_domain(
        _get("domain") or (email.split("@")[-1] if "@" in email else "")
    )
    country = _get("country")
    seg = config.segments.get(segment_slug, {})
    segment_name = seg.get("name", segment_slug.upper())
    social_proof = config.get_social_proof(country, segment_slug)

    return {
        "first_name": _get("first_name"),
        "last_name": _get("last_name"),
        "email": email,
        "title": _get("title"),
        "company_name": normalize_company(_get("company_name") or domain),
        "domain": domain,
        "segment": segment_name,
        "linkedin_url": _get("linkedin_url"),
        "company_linkedin_url": _get("company_linkedin_url"),
        "country": country,
        "city": _get("city"),
        "company_country": _get("company_country") or country,
        "employees": _get("employees"),
        "industry": _get("industry"),
        "seniority": _get("seniority"),
        "phone": _get("phone"),
        "social_proof": social_proof,
    }


async def _find_email(client: httpx.AsyncClient, linkedin_url: str) -> dict:
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers={
                "Authorization": f"Bearer {FINDYMAIL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"linkedin_url": url},
            timeout=60.0,
        )
        if r.status_code == 200:
            data = r.json()
            contact = data.get("contact", {})
            return {
                "email": data.get("email") or contact.get("email") or "",
                "verified": data.get("verified", False)
                or contact.get("verified", False),
            }
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return {"email": "", "verified": False}
    except RuntimeError:
        raise
    except Exception:
        return {"email": "", "verified": False}


async def _verify_email(client: httpx.AsyncClient, email: str) -> dict:
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/verify",
            headers={
                "Authorization": f"Bearer {FINDYMAIL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"email": email},
            timeout=30.0,
        )
        if r.status_code == 200:
            data = r.json()
            return {"email": email, "verified": data.get("verified", False)}
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return {"email": email, "verified": False}
    except RuntimeError:
        raise
    except Exception:
        return {"email": email, "verified": False}


async def _run_findymail(config: ProjectConfig, contacts: list[dict]) -> list[dict]:
    enriched_file = config.state_dir / "enriched.json"
    progress_file = config.state_dir / "findymail_progress.json"

    already_have = [c for c in contacts if c.get("email")]
    to_enrich = [c for c in contacts if not c.get("email") and c.get("linkedin_url")]

    print(f"\n{'=' * 60}")
    print("  FINDYMAIL — Email Enrichment")
    print(f"{'=' * 60}")
    print(f"  С email: {len(already_have)} (к верификации)")
    print(f"  К обогащению: {len(to_enrich)} (${len(to_enrich) * 0.01:.2f} макс)")

    if not FINDYMAIL_API_KEY:
        print("  ERROR: FINDYMAIL_API_KEY not set")
        sys.exit(1)

    out_of_credits = False
    sem = asyncio.Semaphore(FINDYMAIL_CONCURRENT)
    t0 = time.time()

    # ── Verify existing emails ────────────────────────────────────────────────
    verified_count = unverified_count = 0
    print(f"\n  Верификация {len(already_have)} существующих email...")
    _checkpoint(
        f"Верифицировать {len(already_have)} email через FindyMail (${len(already_have) * 0.01:.2f})?"
    )

    async def verify_one(row):
        nonlocal verified_count, unverified_count, out_of_credits
        if out_of_credits:
            return
        email = row.get("email", "").strip()
        if not email:
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await _verify_email(client, email)
                except RuntimeError:
                    out_of_credits = True
                    return
        row["email_verified"] = res.get("verified", False)
        if res.get("verified"):
            verified_count += 1
            print(
                f"  ✓ {row.get('first_name', '')} {row.get('last_name', '')} <{email}>"
            )
        else:
            unverified_count += 1
            print(
                f"  ✗ {row.get('first_name', '')} {row.get('last_name', '')} <{email}>"
            )

    for i in range(0, len(already_have), 20):
        if out_of_credits:
            print("\n  OUT OF CREDITS — верификация прервана")
            break
        await asyncio.gather(*[verify_one(r) for r in already_have[i : i + 20]])

    print(
        f"  Верификация: ✓ {verified_count} валидных, ✗ {unverified_count} невалидных"
    )

    # ── Find missing emails ───────────────────────────────────────────────────
    _checkpoint(f"Запустить FindyMail для {len(to_enrich)} контактов?")

    done = load_json(progress_file) or {}
    found = not_found = 0

    async def process_one(row):
        nonlocal found, not_found, out_of_credits
        if out_of_credits:
            return
        li = row.get("linkedin_url", "").strip()
        if not li:
            return
        if li in done:
            row["email"] = done[li].get("email", "")
            row["email_verified"] = done[li].get("verified", False)
            if done[li].get("email"):
                found += 1
            else:
                not_found += 1
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await _find_email(client, li)
                except RuntimeError:
                    out_of_credits = True
                    return
            row["email"] = res.get("email", "")
            row["email_verified"] = res.get("verified", False)
            done[li] = res
            if res.get("email"):
                found += 1
                print(
                    f"  ✓ {row.get('first_name', '')} {row.get('last_name', '')} → {res['email']}"
                )
            else:
                not_found += 1

    for i in range(0, len(to_enrich), 20):
        if out_of_credits:
            print("\n  OUT OF CREDITS")
            break
        await asyncio.gather(*[process_one(r) for r in to_enrich[i : i + 20]])
        save_json(progress_file, done)

    all_enriched = already_have + to_enrich
    save_json(enriched_file, all_enriched)
    print(
        f"\n  Done in {time.time() - t0:.0f}s — найдено: {found}, не найдено: {not_found}"
    )
    total_cost = (verified_count + unverified_count + found) * 0.01
    print(f"  Стоимость: ${total_cost:.2f}")
    return all_enriched


def _export_getsales(
    config: ProjectConfig, without_email: list[dict], today: str
) -> Path:
    """Save without-email contacts to GetSales-ready CSV for LinkedIn outreach."""
    date_folder = datetime.now().strftime("%d_%m")
    gs_dir = SOFIA_DIR / "get_sales_hub" / date_folder
    gs_dir.mkdir(parents=True, exist_ok=True)
    seg = without_email[0].get("segment", "UNKNOWN") if without_email else "UNKNOWN"
    out_path = (
        gs_dir / f"GetSales — {seg}_without_email — {date_folder.replace('_', '.')}.csv"
    )
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
        gs["linkedin_id"] = _extract_linkedin_nickname(li_url)
        gs["linkedin_url"] = li_url
        gs["company_name"] = normalize_company(c.get("company_name", ""))
        gs["company_domain"] = c.get("domain", "")
        gs["cf_location"] = c.get("company_country", "") or c.get("country", "")
        gs["list_name"] = f"{seg} Without Email {today}"
        gs["tags"] = seg
        gs_rows.append(gs)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GETSALES_HEADERS)
        writer.writeheader()
        writer.writerows(gs_rows)
    print(f"  GetSales: {out_path.name} ({len(gs_rows)} contacts)")
    return out_path


def _filter_existing_contacts(emails: list[str], project_id: int) -> dict:
    if not emails:
        return {}
    BLOCK_STATUSES = ("replied", "meeting_booked", "not_qualified", "sent")
    sanitized = [e.replace("'", "''").lower().strip() for e in emails if e and "@" in e]
    if not sanitized:
        return {}
    existing = {}
    for i in range(0, len(sanitized), 500):
        batch = sanitized[i : i + 500]
        email_list = ",".join(f"'{e}'" for e in batch)
        sql = (
            f"SELECT lower(email), status FROM contacts "
            f"WHERE project_id = {project_id} AND lower(email) IN ({email_list})"
        )
        psql_cmd = f"docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -F'|' -c \"{sql}\""
        is_hetzner = os.path.exists("/home/leadokol/magnum-opus-project")
        run_args = (
            ["bash", "-c", psql_cmd] if is_hetzner else ["ssh", "hetzner", psql_cmd]
        )
        try:
            result = subprocess.run(
                run_args, capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|")
                    existing[parts[0].strip()] = parts[1].strip()
        except Exception as e:
            print(f"  WARNING: contact DB check failed: {e}")
    blocked = {e: s for e, s in existing.items() if s in BLOCK_STATUSES}
    if blocked:
        print(f"  DEDUP: {len(blocked)} blocked (already in DB)")
    return blocked


def _upload_to_smartlead(config: ProjectConfig, contacts: list[dict]):
    """Upload contacts grouped by segment. Creates campaign if needed."""
    print(f"\n{'=' * 60}")
    print("  SMARTLEAD — Upload")
    print(f"{'=' * 60}")

    if not SMARTLEAD_API_KEY:
        print("  ERROR: SMARTLEAD_API_KEY not set")
        sys.exit(1)

    # Dedup by email
    seen = set()
    deduped = []
    for c in contacts:
        e = c.get("email", "").strip().lower()
        if e and e not in seen:
            seen.add(e)
            deduped.append(c)

    by_segment = {}
    for c in deduped:
        seg = c.get("segment", "UNKNOWN")
        by_segment.setdefault(seg, []).append(c)

    upload_log = load_json(config.state_dir / "upload_log.json") or {}
    TIMING = [0, 4, 4, 6, 7]

    for seg_name, seg_contacts in sorted(by_segment.items()):
        seg_slug = next(
            (sl for sl, sd in config.segments.items() if sd["name"] == seg_name), ""
        )
        campaign_name = config.get_campaign_name(seg_slug or seg_name, seg_contacts)
        print(f"\n{'─' * 50}")
        print(f"  Segment: {seg_name} — {len(seg_contacts)} contacts")
        print(f"  Campaign: {campaign_name}")

        # Social proof stats
        sp_counts = Counter(c.get("social_proof", "NO_PROOF") for c in seg_contacts)
        for sp, cnt in sp_counts.most_common():
            print(f"    {cnt:3d}  {sp}")

        if not _checkpoint(f"Загрузить '{campaign_name}'?"):
            continue

        # Campaign
        cid = upload_log.get(seg_name, {}).get("campaign_id")
        if cid:
            print(f"  Кампания уже существует: #{cid}")
        else:
            r = httpx.post(
                f"{SMARTLEAD_BASE}/campaigns/create",
                params={"api_key": SMARTLEAD_API_KEY},
                json={"name": campaign_name},
                timeout=30,
            )
            r.raise_for_status()
            cid = r.json()["id"]
            print(f"  Создана кампания #{cid}")
            upload_log[seg_name] = {
                "campaign_id": cid,
                "campaign_name": campaign_name,
                "at": ts(),
            }
            save_json(config.state_dir / "upload_log.json", upload_log)

        # Email accounts
        active_accounts = config.validate_email_accounts()
        if active_accounts:
            r = httpx.post(
                f"{SMARTLEAD_BASE}/campaigns/{cid}/email-accounts",
                params={"api_key": SMARTLEAD_API_KEY},
                json={"email_account_ids": active_accounts},
                timeout=30,
            )
            if r.status_code == 200:
                print(f"  Привязано {len(active_accounts)} email-аккаунтов")

        # Contact dedup against DB
        all_emails = [
            c["email"].strip().lower() for c in seg_contacts if c.get("email")
        ]
        blocked = _filter_existing_contacts(all_emails, config.project_id)
        if blocked:
            seg_contacts = [
                c for c in seg_contacts if c.get("email", "").lower() not in blocked
            ]

        # Upload leads
        leads = []
        for c in seg_contacts:
            leads.append(
                {
                    "email": c["email"].strip(),
                    "first_name": c.get("first_name", ""),
                    "last_name": c.get("last_name", ""),
                    "company_name": normalize_company(c.get("company_name", "")),
                    "website": c.get("domain", ""),
                    "linkedin_profile": c.get("linkedin_url", ""),
                    "location": c.get("city", ""),
                    "custom_fields": {
                        "social_proof": c.get("social_proof", ""),
                        "title": c.get("title", ""),
                        "country": c.get("company_country", "") or c.get("country", ""),
                        "segment": c.get("segment", ""),
                        "city": c.get("city", ""),
                        "industry": c.get("industry", ""),
                        "seniority": c.get("seniority", ""),
                        "employees": c.get("employees", ""),
                        "company_linkedin": c.get("company_linkedin_url", ""),
                        "phone": c.get("phone", ""),
                    },
                }
            )
        total_uploaded = 0
        for i in range(0, len(leads), 100):
            batch = leads[i : i + 100]
            r = httpx.post(
                f"{SMARTLEAD_BASE}/campaigns/{cid}/leads",
                params={"api_key": SMARTLEAD_API_KEY},
                json={"lead_list": batch},
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                total_uploaded += data.get("upload_count", len(batch))
            elif r.status_code == 429:
                time.sleep(70)
                r2 = httpx.post(
                    f"{SMARTLEAD_BASE}/campaigns/{cid}/leads",
                    params={"api_key": SMARTLEAD_API_KEY},
                    json={"lead_list": batch},
                    timeout=60,
                )
                if r2.status_code == 200:
                    total_uploaded += r2.json().get("upload_count", len(batch))
            else:
                print(f"  ⚠ Upload error: {r.status_code} {r.text[:200]}")
            time.sleep(1)
        print(f"  Загружено: {total_uploaded}/{len(leads)}")
        upload_log[seg_name]["leads"] = total_uploaded
        save_json(config.state_dir / "upload_log.json", upload_log)

        # Sync to backend DB
        bulk = [
            {
                "email": c.get("email", ""),
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "company_name": c.get("company_name"),
                "domain": c.get("domain"),
                "job_title": c.get("title"),
                "segment": seg_name,
                "project_id": config.project_id,
                "source": "pipeline_people",
                "linkedin_url": c.get("linkedin_url"),
                "location": c.get("company_country"),
            }
            for c in seg_contacts
            if c.get("email")
        ]
        if bulk:
            api("post", "/contacts/bulk", json=bulk, raise_on_error=False)
            print(f"  Синхронизировано в DB: {len(bulk)}")

        # Sequences
        sequences = _get_sequences(config, seg_slug) if seg_slug else None
        if sequences:
            if _checkpoint(f"Загрузить секвенсы ({len(sequences)} шагов)?"):
                step_groups = {}
                for s in sequences:
                    m = re.match(r"(\d+)", s["label"])
                    num = m.group(1) if m else "1"
                    step_groups.setdefault(num, []).append(s)
                seq_payload = []
                for i, (num, variants) in enumerate(sorted(step_groups.items())):
                    wait_days = TIMING[i] if i < len(TIMING) else 7
                    body = variants[0]["body"]
                    if "\n" in body and "<br>" not in body:
                        body = body.replace("\n\n", "<br><br>").replace("\n", "<br>")
                    subject = (
                        variants[0]["subject"]
                        .replace("\u2014", "-")
                        .replace("\u2013", "-")
                    )
                    body = body.replace("\u2014", "-").replace("\u2013", "-")
                    seq_payload.append(
                        {
                            "seq_number": i + 1,
                            "seq_delay_details": {"delay_in_days": wait_days},
                            "subject": subject,
                            "email_body": body,
                        }
                    )
                r = httpx.post(
                    f"{SMARTLEAD_BASE}/campaigns/{cid}/sequences",
                    params={"api_key": SMARTLEAD_API_KEY},
                    json={"sequences": seq_payload},
                    timeout=30,
                )
                if r.status_code == 200:
                    print(f"  Секвенсы загружены ({len(seq_payload)} шагов)")
                    for num, variants in sorted(step_groups.items()):
                        if len(variants) > 1:
                            print(
                                f"  ⚠ Step {num} B-вариант — добавить вручную в SmartLead UI"
                            )
                else:
                    print(f"  ⚠ Sequences error: {r.status_code}")
                upload_log[seg_name]["sequences_uploaded"] = True
                save_json(config.state_dir / "upload_log.json", upload_log)
        else:
            print("  ⚠ Секвенсы не найдены — добавить вручную в SmartLead UI")

        # Schedule
        if config.schedule:
            r = httpx.post(
                f"{SMARTLEAD_BASE}/campaigns/{cid}/schedule",
                params={"api_key": SMARTLEAD_API_KEY},
                json=config.schedule,
                timeout=30,
            )
            if r.status_code == 200:
                print("  Расписание установлено")

        print(f"\n  ✓ Кампания '{campaign_name}' готова — DRAFTED")
        print("  → Активируй вручную в SmartLead UI")

    # Summary
    print(f"\n{'=' * 60}")
    for seg, info in upload_log.items():
        seqs = "✅" if info.get("sequences_uploaded") else "❌"
        print(
            f"  {info.get('campaign_name', seg)}: {info.get('leads', 0)} leads, sequences={seqs}"
        )


def _get_sequences(config: ProjectConfig, segment_slug: str) -> list:
    seg = config.segments.get(segment_slug, {})
    seq_file_path = seg.get("sequence_file", "")
    if not seq_file_path:
        return None
    for base in [SOFIA_DIR.parent, SOFIA_DIR, Path(".")]:
        full_path = base / seq_file_path
        if full_path.exists():
            text = full_path.read_text(encoding="utf-8")
            steps = []
            pattern = re.compile(
                r"## Email (\d+[AB]?) .+?\n\n\*\*Subject:\*\* (.+?)\n\n(.*?)(?=\n---|\n## |\Z)",
                re.DOTALL,
            )
            for m in pattern.finditer(text):
                label, subject, body = m.group(1), m.group(2), m.group(3).strip()
                body = re.sub(r"\n`\d+ words`", "", body).strip()
                steps.append({"label": label, "subject": subject, "body": body})
            if steps:
                print(f"  Секвенс: {len(steps)} шагов из {full_path.name}")
                return steps
    return None


def _fetch_kb_blocklist() -> tuple[set, set]:
    """Fetch kb_blocklist from DB. Returns (blocked_domains, blocked_emails)."""
    sql = "SELECT domain, email FROM kb_blocklist"
    psql_cmd = f"docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -F'|' -c \"{sql}\""
    is_hetzner = os.path.exists("/home/leadokol/magnum-opus-project")
    run_args = ["bash", "-c", psql_cmd] if is_hetzner else ["ssh", "hetzner", psql_cmd]
    try:
        result = subprocess.run(run_args, capture_output=True, text=True, timeout=30)
        domains: set = set()
        emails: set = set()
        for line in result.stdout.strip().splitlines():
            if "|" in line:
                parts = line.split("|", 1)
                d = parts[0].strip().lower()
                e = parts[1].strip().lower() if len(parts) > 1 else ""
                if d:
                    domains.add(d)
                if e:
                    emails.add(e)
        print(f"  Блэклист: {len(domains)} доменов, {len(emails)} email из БД")
        return domains, emails
    except Exception as ex:
        print(f"  WARNING: kb_blocklist fetch failed: {ex}")
        return set(), set()


def _apply_blacklist(
    contacts: list[dict], blocked_domains: set, blocked_emails: set
) -> list[dict]:
    """Drop contacts matching kb_blocklist by email or domain."""
    kept = []
    dropped = []
    for c in contacts:
        email = c.get("email", "").strip().lower()
        domain = c.get("domain", "").strip().lower()
        email_domain = email.split("@")[-1] if "@" in email else ""

        if email and email in blocked_emails:
            dropped.append((c, f"email:{email}"))
            continue
        if email_domain and email_domain in blocked_domains:
            dropped.append((c, f"domain:{email_domain}"))
            continue
        if domain and domain in blocked_domains:
            dropped.append((c, f"domain:{domain}"))
            continue
        kept.append(c)

    if dropped:
        print(f"  BLACKLIST: убрано {len(dropped)} контактов")
        for c, reason in dropped[:10]:
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            print(f"    ✗ {name} [{reason}]")
        if len(dropped) > 10:
            print(f"    ... и ещё {len(dropped) - 10}")
    return kept


def _dedup_vs_crm(contacts: list[dict], project_id: int = 42) -> list[dict]:
    """Drop contacts whose email already exists in CRM (contacts table) for this project.
    Only blocks contacts with statuses: sent, replied, meeting_booked, not_qualified.
    """
    BLOCK_STATUSES = ("replied", "meeting_booked", "not_qualified", "sent")
    emails = [
        c.get("email", "").replace("'", "''").strip().lower()
        for c in contacts
        if c.get("email") and "@" in c.get("email", "")
    ]
    if not emails:
        return contacts

    found: set = set()
    for i in range(0, len(emails), 500):
        batch = emails[i : i + 500]
        email_list = ",".join(f"'{e}'" for e in batch)
        statuses_sql = "(" + ",".join(f"'{s}'" for s in BLOCK_STATUSES) + ")"
        sql = (
            f"SELECT lower(email) FROM contacts "
            f"WHERE project_id = {project_id} "
            f"AND lower(email) IN ({email_list}) "
            f"AND status IN {statuses_sql}"
        )
        psql_cmd = (
            f'docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -c "{sql}"'
        )
        is_hetzner = os.path.exists("/home/leadokol/magnum-opus-project")
        run_args = (
            ["bash", "-c", psql_cmd] if is_hetzner else ["ssh", "hetzner", psql_cmd]
        )
        try:
            result = subprocess.run(
                run_args, capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.strip().splitlines():
                e = line.strip().lower()
                if e:
                    found.add(e)
        except Exception as ex:
            print(f"  WARNING: CRM dedup check failed: {ex}")

    if found:
        before = len(contacts)
        contacts = [
            c for c in contacts if c.get("email", "").strip().lower() not in found
        ]
        print(
            f"  DEDUP CRM: {before} → {len(contacts)} (убрано {before - len(contacts)})"
        )
    else:
        print("  DEDUP CRM: дублей нет")
    return contacts


def _run_people(config: ProjectConfig, args):
    from_step = args.from_step or "findymail"
    today = tag()
    segment_slug = args.segment.lower() if args.segment else ""

    # ── Load contacts ────────────────────────────────────────────────────────
    if from_step == "findymail":
        if not args.csv:
            print("ERROR: --csv required")
            sys.exit(1)
        csv_path = Path(args.csv)
        contacts = []
        with csv_path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                c = _map_apollo_row(row, config, segment_slug)
                if c["first_name"] or c["email"]:
                    contacts.append(c)
        print(f"\n  Загружено из CSV: {len(contacts)} контактов")
        with_email = sum(1 for c in contacts if c.get("email"))
        without_email = sum(
            1 for c in contacts if not c.get("email") and c.get("linkedin_url")
        )
        print(f"  С email: {with_email}, без email (LinkedIn): {without_email}")

        # ── Blacklist (kb_blocklist) ─────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("  BLACKLIST — kb_blocklist")
        print(f"{'=' * 60}")
        bl_domains, bl_emails = _fetch_kb_blocklist()
        contacts = _apply_blacklist(contacts, bl_domains, bl_emails)

        # FindyMail
        enriched = asyncio.run(_run_findymail(config, contacts))

        # ── Dedup vs OnSocial CRM ────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("  DEDUP — OnSocial CRM (contacts project_id=42)")
        print(f"{'=' * 60}")
        enriched = _dedup_vs_crm(enriched, project_id=config.project_id)
    else:
        # from-step upload: load from enriched.json
        enriched_file = config.state_dir / "enriched.json"
        enriched = load_json(enriched_file)
        if not enriched:
            print(f"  ERROR: enriched.json not found at {enriched_file}")
            sys.exit(1)
        print(f"  Загружено из enriched.json: {len(enriched)} контактов")

    # ── Split & save ────────────────────────────────────────────────────────
    with_email = [c for c in enriched if c.get("email", "").strip()]
    without_email_li = [
        c for c in enriched if not c.get("email") and c.get("linkedin_url")
    ]

    seg_label = segment_slug.upper()
    save_csv(
        config.csv_dir / f"leads_with_email_{seg_label}_{today}.csv",
        with_email,
        sheet_name=f"OS | Leads | {seg_label} — {today}",
    )
    save_csv(
        config.csv_dir / f"leads_linkedin_only_{seg_label}_{today}.csv",
        without_email_li,
        sheet_name=f"OS | Leads | {seg_label} LinkedIn Only — {today}",
    )

    if without_email_li:
        _export_getsales(config, without_email_li, today)

    print(f"\n  С email: {len(with_email)}, только LinkedIn: {len(without_email_li)}")

    # ── SmartLead upload ────────────────────────────────────────────────────
    if getattr(args, "no_upload", False):
        print("  ✓ SmartLead upload пропущен (--no-upload)")
    elif with_email:
        _upload_to_smartlead(config, with_email)
    else:
        print("  ⚠ Нет контактов с email — SmartLead upload пропущен")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def main():
    global _AUTO_APPROVE

    parser = argparse.ArgumentParser(description="OnSocial Lead Pipeline")
    sub = parser.add_subparsers(dest="cmd")

    # companies
    p_comp = sub.add_parser(
        "companies", help="CSV компаний → classify → export targets"
    )
    p_comp.add_argument("--csv", help="CSV с компаниями (Website/Domain колонка)")
    p_comp.add_argument("--project-id", type=int, default=42)
    p_comp.add_argument("--run-id", type=int, help="Возобновить существующий ран")
    p_comp.add_argument(
        "--from-step",
        choices=[
            "blacklist",
            "prefilter",
            "scrape",
            "classify",
            "verify",
            "adjust",
            "export",
        ],
    )
    p_comp.add_argument("--prompt-file", help="Новый промпт для --from-step adjust")
    p_comp.add_argument("--auto-approve", action="store_true")

    # people
    p_ppl = sub.add_parser("people", help="Apollo CSV → FindyMail → SmartLead")
    p_ppl.add_argument("--csv", help="Apollo CSV export с людьми")
    p_ppl.add_argument("--project-id", type=int, default=42)
    p_ppl.add_argument(
        "--segment", required=True, help="Сегмент: soccom / imagency / infplat"
    )
    p_ppl.add_argument("--from-step", choices=["findymail", "upload"])
    p_ppl.add_argument("--auto-approve", action="store_true")
    p_ppl.add_argument(
        "--no-upload",
        action="store_true",
        help="Пропустить SmartLead upload, сохранить только в Sheets",
    )

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    _AUTO_APPROVE = getattr(args, "auto_approve", False)

    print("═" * 60)
    print(f"  OnSocial Pipeline — {ts()}")
    print("═" * 60)

    config = ProjectConfig(args.project_id)
    config.load()

    if args.cmd == "companies":
        _run_companies(config, args)
    elif args.cmd == "people":
        _run_people(config, args)


if __name__ == "__main__":
    main()
