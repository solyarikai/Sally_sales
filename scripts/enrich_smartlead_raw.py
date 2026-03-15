#!/usr/bin/env python3
"""Enrich contacts.smartlead_raw with full SmartLead CSV data for project_id=9 (EasyStaff Global)."""

import csv
import io
import json
import sys
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE_URL = "https://server.smartlead.ai/api/v1"
DB_DSN = "postgresql://leadgen:leadgen_secret@postgres:5432/leadgen"
PROJECT_ID = 9

def get_campaigns(conn):
    """Get all SmartLead campaigns for project."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, external_id, name FROM campaigns WHERE project_id=%s AND platform='smartlead' ORDER BY id",
        (PROJECT_ID,)
    )
    rows = cur.fetchall()
    cur.close()
    return rows

def strip_null_bytes(s):
    """Remove null bytes from string."""
    if isinstance(s, str):
        return s.replace('\x00', '')
    return s

def clean_dict(d):
    """Recursively strip null bytes from all string values in a dict."""
    cleaned = {}
    for k, v in d.items():
        k = strip_null_bytes(k)
        if isinstance(v, str):
            cleaned[k] = strip_null_bytes(v)
        elif isinstance(v, dict):
            cleaned[k] = clean_dict(v)
        else:
            cleaned[k] = v
    return cleaned

def download_csv(external_id, campaign_name):
    """Download CSV export for a campaign. Returns list of dicts."""
    url = f"{BASE_URL}/campaigns/{external_id}/leads-export?api_key={API_KEY}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200:
                text = resp.text.replace('\x00', '')
                reader = csv.DictReader(io.StringIO(text))
                rows = [clean_dict(row) for row in reader]
                return rows
            elif resp.status_code == 429 or "Plan expired" in resp.text:
                print(f"  Rate limited/plan issue, waiting 30s (attempt {attempt+1})")
                time.sleep(30)
            else:
                print(f"  HTTP {resp.status_code} for campaign {external_id}: {resp.text[:200]}")
                return []
        except Exception as e:
            print(f"  Error downloading {external_id}: {e}")
            time.sleep(5)
    return []

def parse_created_at(val):
    """Parse SmartLead created_at to datetime."""
    if not val:
        return None
    try:
        # Format: 2026-03-13T15:56:52.000Z
        return datetime.fromisoformat(val.replace('Z', '+00:00'))
    except:
        return None

def enrich_batch(conn, rows, campaign_name, campaign_db_id):
    """Bulk update contacts with smartlead_raw data."""
    if not rows:
        return 0

    cur = conn.cursor()

    # Create temp table
    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _sl_enrich (
            email TEXT,
            smartlead_id TEXT,
            smartlead_raw JSONB,
            sl_created_at TIMESTAMPTZ,
            campaign_name TEXT
        ) ON COMMIT DROP
    """)
    cur.execute("TRUNCATE _sl_enrich")

    # Prepare data
    values = []
    for row in rows:
        email = (row.get('email') or '').strip().lower()
        if not email:
            continue
        sl_id = row.get('id', '')
        created_at = parse_created_at(row.get('created_at'))
        raw_json = json.dumps(row, ensure_ascii=False)
        values.append((email, sl_id, raw_json, created_at, campaign_name))

    if not values:
        cur.close()
        return 0

    execute_values(
        cur,
        "INSERT INTO _sl_enrich (email, smartlead_id, smartlead_raw, sl_created_at, campaign_name) VALUES %s",
        values,
        page_size=1000
    )

    # Update contacts: set smartlead_raw, optionally update created_at and smartlead_id
    cur.execute("""
        UPDATE contacts c
        SET
            smartlead_raw = e.smartlead_raw,
            smartlead_id = COALESCE(NULLIF(c.smartlead_id, ''), e.smartlead_id),
            created_at = CASE
                WHEN e.sl_created_at IS NOT NULL AND (c.created_at IS NULL OR c.created_at > e.sl_created_at)
                THEN e.sl_created_at
                ELSE c.created_at
            END,
            updated_at = NOW()
        FROM _sl_enrich e
        WHERE LOWER(c.email) = e.email
          AND c.project_id = %s
          AND (c.smartlead_raw = '{}'::jsonb OR c.smartlead_raw IS NULL)
    """, (PROJECT_ID,))

    updated = cur.rowcount
    conn.commit()
    cur.close()
    return updated

def main():
    conn = psycopg2.connect(DB_DSN)
    campaigns = get_campaigns(conn)
    print(f"Found {len(campaigns)} campaigns for project {PROJECT_ID}")

    total_updated = 0
    total_csv_rows = 0

    for i, (db_id, ext_id, name) in enumerate(campaigns):
        print(f"[{i+1}/{len(campaigns)}] {name} (ext={ext_id})...", end=" ", flush=True)
        rows = download_csv(ext_id, name)
        if not rows:
            print("0 rows")
            continue

        total_csv_rows += len(rows)
        updated = enrich_batch(conn, rows, name, db_id)
        total_updated += updated
        print(f"{len(rows)} CSV rows, {updated} enriched")

        # Small delay to avoid rate limits
        if (i + 1) % 10 == 0:
            time.sleep(2)

    # Final stats
    cur = conn.cursor()
    cur.execute("""
        SELECT count(*) as total,
               count(*) FILTER (WHERE smartlead_raw = '{}'::jsonb OR smartlead_raw IS NULL) as empty
        FROM contacts WHERE project_id=%s
    """, (PROJECT_ID,))
    total, empty = cur.fetchone()
    cur.close()
    conn.close()

    print(f"\n=== DONE ===")
    print(f"Total CSV rows processed: {total_csv_rows}")
    print(f"Total contacts enriched: {total_updated}")
    print(f"Contacts remaining empty: {empty}/{total}")

if __name__ == "__main__":
    main()
