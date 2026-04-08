#!/usr/bin/env python3
"""
Emergency pause of dangerous leads in SmartLead.

Reads the pause action list from OS_Emergency_Pause_2026-04-08.json,
pauses each lead in its campaign, and writes a rollback log.

Usage:
  python3 sofia/scripts/emergency_pause_leads.py --dry-run   # preview
  python3 sofia/scripts/emergency_pause_leads.py              # execute
  python3 sofia/scripts/emergency_pause_leads.py --rollback   # resume all paused leads
"""

import argparse
import json
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
SSL_CTX = ssl._create_unverified_context()

INPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "output"
    / "OnSocial"
    / "OS_Emergency_Pause_2026-04-08.json"
)
LOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "output"
    / "OnSocial"
    / "OS_Emergency_Pause_Log_2026-04-08.json"
)


def api_post(endpoint, body=None):
    params = f"api_key={API_KEY}"
    url = f"{BASE_URL}{endpoint}?{params}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 SmartLead-CLI/1.0")
    for attempt in range(3):
        try:
            with urlopen(req, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
                time.sleep(0.4)
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5)
                continue
            body_text = e.read().decode() if e.fp else str(e)
            return {"error": f"HTTP {e.code}: {body_text}"}


def main():
    parser = argparse.ArgumentParser(
        description="Emergency pause/resume dangerous leads"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without pausing"
    )
    parser.add_argument(
        "--rollback", action="store_true", help="Resume all previously paused leads"
    )
    args = parser.parse_args()

    if args.rollback:
        if not LOG_PATH.exists():
            print(f"No rollback log found: {LOG_PATH}")
            sys.exit(1)
        log = json.loads(LOG_PATH.read_text())
        paused = [a for a in log if a.get("result") == "paused"]
        print(f"Rolling back {len(paused)} paused leads...")
        for a in paused:
            if args.dry_run:
                print(
                    f"  [DRY] Would resume lead {a['lead_id']} in campaign {a['campaign_id']}"
                )
                continue
            result = api_post(
                f"/campaigns/{a['campaign_id']}/leads/{a['lead_id']}/resume"
            )
            status = (
                "resumed" if not result.get("error") else f"error: {result['error']}"
            )
            print(f"  {a['email']:45s} → {status}")
        return

    if not INPUT_PATH.exists():
        print(f"Input not found: {INPUT_PATH}")
        sys.exit(1)

    actions = json.loads(INPUT_PATH.read_text())
    print(f"Emergency Pause — {len(actions)} actions")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    results = []
    for i, a in enumerate(actions):
        entry = {**a, "timestamp": datetime.now().isoformat()}

        if args.dry_run:
            print(
                f"  [{i + 1}/{len(actions)}] [DRY] {a['email']:45s} camp={a['campaign_id']} reason={a['trigger_reason']}"
            )
            entry["result"] = "dry_run"
        else:
            result = api_post(
                f"/campaigns/{a['campaign_id']}/leads/{a['lead_id']}/pause"
            )
            if result.get("error"):
                entry["result"] = f"error: {result['error']}"
                print(
                    f"  [{i + 1}/{len(actions)}] ERROR {a['email']:45s} → {result['error'][:60]}"
                )
            else:
                entry["result"] = "paused"
                print(
                    f"  [{i + 1}/{len(actions)}] PAUSED {a['email']:45s} in {a['campaign_name'][:40]}"
                )

        results.append(entry)

    # Save log
    LOG_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nLog saved: {LOG_PATH}")
    print(f"To rollback: python3 {__file__} --rollback")


if __name__ == "__main__":
    main()
