#!/usr/bin/env python3
"""
TFP Fashion Pipeline Monitor & Google Sheet Writer

- Monitors all 9 gathering runs for TFP project
- When Italy/France/Germany finish scraping → auto-triggers analyze
- Writes ICP targets to Google Sheet every 100 new results
- Saves progress so it can be resumed if interrupted
"""

import time
import os
import sys
import json
import requests
import importlib.util
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID = 13
BASE_URL = "http://localhost:8000"
API_HEADERS = {"X-Company-ID": "1"}
BATCH_SIZE = 100
POLL_INTERVAL = 60  # seconds between DB polls
PROGRESS_FILE = "/tmp/tfp_monitor_progress.json"

# All 9 TFP Clay gathering runs
RUNS = {
    21: "Italy",
    24: "France",
    27: "Germany",
    42: "UK",
    44: "Belgium",
    46: "DACH",
    47: "CEE",
    # 43 (Spain) and 45 (Nordics) have 0 companies — skip
}

ICP_PROMPT = (
    "TFP targets European D2C fashion brands with own collections. "
    "Target: fashion/apparel/footwear/accessories brand, own products, D2C or hybrid, "
    "5-500 employees, European. "
    "Not target: pure retailer, marketplace, no own brand, non-fashion, "
    "Polish brand, Netherlands/Dutch brand."
)

SHEET_HEADERS = [
    "Domain", "Company Name", "Country", "Confidence", "Is Target",
    "Segment", "Reasoning", "Run ID", "Country Split", "Analyzed At"
]

# ── Load Google Sheets service ─────────────────────────────────────────────────
_gss_path = ROOT / "backend" / "app" / "services" / "google_sheets_service.py"
_spec = importlib.util.spec_from_file_location("gss", str(_gss_path))
_gss_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gss_mod)
gss = _gss_mod.google_sheets_service
gss._initialize()

# ── DB connection ──────────────────────────────────────────────────────────────
DB_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen@localhost:5432/leadgen")


def get_db():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


# ── Progress state ─────────────────────────────────────────────────────────────
def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {
        "sheet_id": None,
        "sheet_url": None,
        "written_company_ids": [],
        "analyze_triggered": [],  # run IDs where analyze was triggered
        "last_written_count": 0,
        "started_at": datetime.utcnow().isoformat(),
    }


def save_progress(state):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── Google Sheet helpers ───────────────────────────────────────────────────────
def create_sheet(state):
    """Create a new sheet on the shared Drive."""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    result = gss.create_reply_sheet_via_drive(f"TFP Fashion ICP Targets — {date_str}")
    if not result:
        print("ERROR: Could not create Google Sheet")
        sys.exit(1)

    sheet_id = result["id"] if isinstance(result, dict) else result
    # Try getting URL
    try:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    except Exception:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    # Rename Sheet1 to "Targets" and write headers
    try:
        gss.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"updateSheetProperties": {
                "properties": {"sheetId": 0, "title": "Targets"},
                "fields": "title"
            }}]}
        ).execute()
    except Exception as e:
        print(f"  Warning: could not rename sheet tab: {e}")

    # Write headers
    gss.sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Targets!A1",
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]}
    ).execute()

    # Add progress tab
    try:
        gss.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Progress"}}}]}
        ).execute()
        gss.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Progress!A1",
            valueInputOption="RAW",
            body={"values": [["Run ID", "Country", "Phase", "Scraped", "Total", "Analyzed", "Targets", "Updated At"]]}
        ).execute()
    except Exception as e:
        print(f"  Warning: could not add Progress tab: {e}")

    state["sheet_id"] = sheet_id
    state["sheet_url"] = sheet_url
    save_progress(state)
    print(f"  Sheet created: {sheet_url}")
    return sheet_id


def append_targets_to_sheet(sheet_id, rows):
    """Append a list of rows to the Targets tab."""
    if not rows:
        return
    gss.sheets_service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Targets!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}
    ).execute()


def update_progress_tab(sheet_id, run_stats):
    """Overwrite the Progress tab with current run stats."""
    rows = [["Run ID", "Country", "Phase", "Scraped", "Total", "Analyzed", "Targets", "Updated At"]]
    for stat in run_stats:
        rows.append([
            stat["run_id"], stat["country"], stat["phase"],
            stat["scraped"], stat["total"],
            stat["analyzed"], stat["targets"],
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        ])
    try:
        gss.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Progress!A1",
            valueInputOption="RAW",
            body={"values": rows}
        ).execute()
    except Exception as e:
        print(f"  Warning: could not update Progress tab: {e}")


# ── Pipeline helpers ───────────────────────────────────────────────────────────
def get_run_phases(conn):
    with conn.cursor() as cur:
        run_ids = list(RUNS.keys())
        cur.execute("""
            SELECT gr.id, gr.current_phase,
                   COUNT(DISTINCT cs.id) as scraped,
                   COUNT(DISTINCT dc.id) as total,
                   COUNT(DISTINCT CASE WHEN dc.is_target IS NOT NULL THEN dc.id END) as analyzed,
                   COUNT(DISTINCT CASE WHEN dc.is_target = true THEN dc.id END) as targets
            FROM gathering_runs gr
            LEFT JOIN discovered_companies dc ON dc.first_found_by = gr.id
            LEFT JOIN company_scrapes cs ON cs.discovered_company_id = dc.id
            WHERE gr.id = ANY(%s)
            GROUP BY gr.id
        """, (run_ids,))
        return {r["id"]: r for r in cur.fetchall()}


def get_new_targets(conn, already_written_ids):
    """Fetch all is_target=true companies not yet written."""
    run_ids = list(RUNS.keys())
    with conn.cursor() as cur:
        cur.execute("""
            SELECT dc.id, dc.domain, dc.name, dc.confidence, dc.reasoning,
                   dc.first_found_by as run_id,
                   dc.company_info->>'country' as country,
                   dc.company_info->>'segment' as segment,
                   dc.updated_at
            FROM discovered_companies dc
            WHERE dc.project_id = %s
              AND dc.is_target = true
              AND dc.first_found_by = ANY(%s)
              AND dc.id != ALL(%s)
            ORDER BY dc.confidence DESC
        """, (PROJECT_ID, run_ids, already_written_ids or [0]))
        return cur.fetchall()


def trigger_analyze(run_id, state):
    """Call the analyze API for a run that just finished scraping."""
    if run_id in state["analyze_triggered"]:
        return False
    print(f"  Triggering analyze for run {run_id} ({RUNS[run_id]})...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/pipeline/gathering/runs/{run_id}/analyze",
            params={"prompt_text": ICP_PROMPT, "model": "gpt-4o-mini"},
            headers=API_HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            state["analyze_triggered"].append(run_id)
            save_progress(state)
            print(f"  ✓ Analyze started for run {run_id} ({RUNS[run_id]})")
            return True
        else:
            print(f"  ✗ Analyze failed for run {run_id}: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"  ✗ Analyze trigger error for run {run_id}: {e}")
    return False


# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    state = load_progress()
    conn = get_db()
    print(f"\n=== TFP Fashion Monitor started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    # Create sheet if not exists
    if not state["sheet_id"]:
        print("Creating Google Sheet...")
        create_sheet(state)
    else:
        print(f"Resuming — sheet: {state['sheet_url']}")

    sheet_id = state["sheet_id"]
    pending_rows = []  # accumulate before writing
    written_ids = set(state["written_company_ids"])

    while True:
        try:
            conn.close()
            conn = get_db()
        except Exception:
            pass

        # ── 1. Check run phases ──────────────────────────────────────────────
        phases = get_run_phases(conn)
        run_stats = []

        for run_id, country in RUNS.items():
            info = phases.get(run_id, {})
            phase = info.get("current_phase", "unknown")
            scraped = info.get("scraped", 0)
            total = info.get("total", 0)
            analyzed = info.get("analyzed", 0)
            targets = info.get("targets", 0)

            run_stats.append({
                "run_id": run_id, "country": country, "phase": phase,
                "scraped": scraped, "total": total,
                "analyzed": analyzed, "targets": targets
            })

            # If scraping just finished and analyze not yet triggered
            if phase == "scraped" and run_id not in state["analyze_triggered"]:
                trigger_analyze(run_id, state)

        # ── 2. Collect new targets ───────────────────────────────────────────
        new_targets = get_new_targets(conn, list(written_ids))
        for row in new_targets:
            country_split = RUNS.get(row["run_id"], "Unknown")
            pending_rows.append([
                row["domain"] or "",
                row["name"] or "",
                row["country"] or "",
                round(row["confidence"] or 0, 3),
                "YES",
                row["segment"] or "",
                (row["reasoning"] or "")[:500],
                row["run_id"],
                country_split,
                str(row["updated_at"])[:19] if row["updated_at"] else "",
            ])
            written_ids.add(row["id"])

        # ── 3. Write to sheet every BATCH_SIZE results ───────────────────────
        if len(pending_rows) >= BATCH_SIZE:
            batch = pending_rows[:BATCH_SIZE]
            pending_rows = pending_rows[BATCH_SIZE:]
            print(f"  Writing {len(batch)} targets to sheet (total written: {len(written_ids)})...")
            append_targets_to_sheet(sheet_id, batch)
            state["written_company_ids"] = list(written_ids)
            state["last_written_count"] = len(written_ids)
            save_progress(state)

        # ── 4. Update progress tab ───────────────────────────────────────────
        update_progress_tab(sheet_id, run_stats)

        # ── 5. Print status ──────────────────────────────────────────────────
        total_targets = sum(s["targets"] for s in run_stats)
        total_analyzed = sum(s["analyzed"] for s in run_stats)
        total_companies = sum(s["total"] for s in run_stats)
        print(f"[{datetime.utcnow().strftime('%H:%M')}] "
              f"Analyzed: {total_analyzed}/{total_companies} | "
              f"Targets: {total_targets} | "
              f"Written to sheet: {len(written_ids)} | "
              f"Pending: {len(pending_rows)}")

        for s in run_stats:
            status_emoji = {
                "filtered": "⏳",
                "scraped": "🔄",
                "awaiting_targets_ok": "✅",
                "completed": "✅",
            }.get(s["phase"], "❓")
            print(f"  {status_emoji} Run {s['run_id']} ({s['country']}): "
                  f"phase={s['phase']}, scraped={s['scraped']}/{s['total']}, "
                  f"analyzed={s['analyzed']}, targets={s['targets']}")

        # ── 6. Check if all done ─────────────────────────────────────────────
        done_phases = {"awaiting_targets_ok", "completed", "pushed"}
        all_done = all(
            phases.get(rid, {}).get("current_phase") in done_phases
            for rid in RUNS
        )
        if all_done:
            # Write remaining pending rows
            if pending_rows:
                print(f"  Final write: {len(pending_rows)} remaining targets...")
                append_targets_to_sheet(sheet_id, pending_rows)
                state["written_company_ids"] = list(written_ids)
                save_progress(state)
            print(f"\n=== ALL RUNS COMPLETE ===")
            print(f"Sheet: {state['sheet_url']}")
            print(f"Total targets written: {len(written_ids)}")
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
