#!/usr/bin/env python3
"""
Full SmartLead Contact Import — Synchronous ETL
Phase 1: Download CSVs → TSV on disk (~12 min for 795 campaigns)
Phase 2: COPY into staging → SQL merge into contacts (~2 min)

Usage:
  python3 full_smartlead_import.py              # full run
  python3 full_smartlead_import.py --phase2     # skip download, reuse existing TSV
"""

import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
import requests

SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY", "")
_raw_db = os.getenv("DATABASE_URL", "postgresql://leadgen:leadgen@localhost:5432/leadgen")
DATABASE_URL = _raw_db.replace("postgresql+asyncpg://", "postgresql://", 1)
BASE_URL = "https://server.smartlead.ai/api/v1"
MIN_INTERVAL = 0.4
TSV_PATH = "/tmp/sl_contacts.tsv"
csv.field_size_limit(10 * 1024 * 1024)


def _c(v):
    """Clean value for TSV (strip tabs/newlines)."""
    return str(v or "").replace("\t", " ").replace("\n", " ").replace("\r", "")


def phase1_download():
    """Download all SmartLead campaign CSVs → single TSV file."""
    print("\n=== PHASE 1: Download CSVs ===")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT external_id, name, COALESCE(leads_count, 0), project_id
        FROM campaigns WHERE platform = 'smartlead' AND external_id IS NOT NULL
          AND COALESCE(leads_count, 0) > 0
        ORDER BY leads_count DESC
    """)
    campaigns = cur.fetchall()
    cur.close()
    conn.close()

    total_expected = sum(r[2] for r in campaigns)
    print(f"Campaigns: {len(campaigns)}, expected: {total_expected:,}")

    total_rows = 0
    ok = 0
    failed = []
    started = time.time()
    sess = requests.Session()

    with open(TSV_PATH, "w") as f:
        for idx, (eid, name, cnt, pid) in enumerate(campaigns):
            t0 = time.time()
            try:
                resp = sess.get(f"{BASE_URL}/campaigns/{eid}/leads-export",
                                params={"api_key": SMARTLEAD_API_KEY}, timeout=(10, 120))
            except requests.exceptions.Timeout:
                failed.append((eid, name, cnt, pid)); time.sleep(2); continue
            except Exception as e:
                print(f"  ERR: {name[:40]}: {e}"); failed.append((eid, name, cnt, pid)); continue

            if resp.status_code == 429:
                failed.append((eid, name, cnt, pid)); time.sleep(5); continue
            if resp.status_code != 200:
                continue

            try:
                rows = list(csv.DictReader(io.StringIO(resp.text)))
            except Exception as e:
                print(f"  CSV err: {name[:40]}: {e}"); continue

            for row in rows:
                email = (row.get("email") or "").strip().lower()
                if not email or "@" not in email:
                    continue
                rc = int(row.get("reply_count", 0) or 0)
                ce = {"campaign_name": name, "campaign_id": eid,
                      "lead_status": row.get("status", "ACTIVE"),
                      "added_at": row.get("created_at", "")}
                if rc > 0:
                    ce["reply_time"] = True
                try:
                    cf = json.loads(row.get("custom_fields", "{}") or "{}")
                except Exception:
                    cf = {}
                jt = cf.get("Title", "") or cf.get("Job Title", "")
                # Write TSV manually — no csv.writer quoting issues with JSON
                fields = [
                    email, _c(row.get("id", "")),
                    _c(row.get("first_name", "")), _c(row.get("last_name", "")),
                    _c(row.get("company_name", "")), _c(row.get("phone_number", "")),
                    _c(row.get("linkedin_profile", "")), _c(row.get("location", "")),
                    _c(jt), f"smartlead:{eid}",
                    str(pid) if pid else "", json.dumps(ce),
                ]
                f.write("\t".join(fields) + "\n")
                total_rows += 1
            ok += 1
            if (idx + 1) % 25 == 0 or idx < 3 or len(rows) > 5000:
                el = time.time() - started
                rate = (idx + 1) / el * 60
                eta = (len(campaigns) - idx - 1) / rate if rate > 0 else 0
                print(f"  [{idx+1}/{len(campaigns)}] {total_rows:,} | {rate:.0f}/min | ETA {eta:.1f}m | "
                      f"{len(rows)} in {time.time()-t0:.1f}s | {name[:30]}")
            wait = MIN_INTERVAL - (time.time() - t0)
            if wait > 0:
                time.sleep(wait)

    # Retry
    if failed:
        print(f"\nRetrying {len(failed)} failed campaigns...")
        with open(TSV_PATH, "a") as f:
            for rnd in range(3):
                if not failed:
                    break
                still = []
                time.sleep(10)
                print(f"  Round {rnd+1}: {len(failed)}")
                for eid, name, cnt, pid in failed:
                    try:
                        resp = sess.get(f"{BASE_URL}/campaigns/{eid}/leads-export",
                                        params={"api_key": SMARTLEAD_API_KEY}, timeout=(10, 120))
                    except Exception:
                        still.append((eid, name, cnt, pid)); time.sleep(2); continue
                    if resp.status_code == 429:
                        still.append((eid, name, cnt, pid)); time.sleep(5); continue
                    if resp.status_code != 200:
                        continue
                    try:
                        rows = list(csv.DictReader(io.StringIO(resp.text)))
                    except Exception:
                        continue
                    for row in rows:
                        email = (row.get("email") or "").strip().lower()
                        if not email or "@" not in email:
                            continue
                        rc = int(row.get("reply_count", 0) or 0)
                        ce = {"campaign_name": name, "campaign_id": eid,
                              "lead_status": row.get("status", "ACTIVE"),
                              "added_at": row.get("created_at", "")}
                        if rc > 0:
                            ce["reply_time"] = True
                        try:
                            cf = json.loads(row.get("custom_fields", "{}") or "{}")
                        except Exception:
                            cf = {}
                        jt = cf.get("Title", "") or cf.get("Job Title", "")
                        fields = [
                            email, _c(row.get("id", "")),
                            _c(row.get("first_name", "")), _c(row.get("last_name", "")),
                            _c(row.get("company_name", "")), _c(row.get("phone_number", "")),
                            _c(row.get("linkedin_profile", "")), _c(row.get("location", "")),
                            _c(jt), f"smartlead:{eid}",
                            str(pid) if pid else "", json.dumps(ce),
                        ]
                        f.write("\t".join(fields) + "\n")
                        total_rows += 1
                    ok += 1
                    time.sleep(MIN_INTERVAL)
                failed = still
                print(f"  {len(still)} still failed")

    mb = os.path.getsize(TSV_PATH) / (1024 * 1024)
    print(f"\nPhase 1 done: {ok} campaigns, {total_rows:,} rows, {mb:.1f}MB in {time.time()-started:.0f}s")
    return total_rows


def phase2_merge():
    """Load TSV into staging table, SQL merge into contacts."""
    print("\n=== PHASE 2: SQL merge ===")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    t0 = time.time()

    # Staging table
    cur.execute("DROP TABLE IF EXISTS _staging_sl")
    cur.execute("""
        CREATE UNLOGGED TABLE _staging_sl (
            email TEXT, slid TEXT, first_name TEXT, last_name TEXT,
            company_name TEXT, phone TEXT, linkedin_url TEXT, location TEXT,
            job_title TEXT, source TEXT, project_id TEXT, camp_json TEXT
        )
    """)
    conn.commit()

    # COPY
    print("COPY into staging...")
    with open(TSV_PATH, "r") as f:
        cur.copy_from(f, "_staging_sl", sep="\t", null="")
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM _staging_sl")
    staged = cur.fetchone()[0]
    print(f"  Staged: {staged:,} in {time.time()-t0:.1f}s")

    cur.execute("CREATE INDEX idx_stg_email ON _staging_sl (email)")
    conn.commit()

    # INSERT new contacts
    print("INSERT new contacts...")
    t1 = time.time()
    cur.execute("""
        INSERT INTO contacts (company_id, project_id, email, first_name, last_name,
            company_name, phone, linkedin_url, location, job_title,
            source, smartlead_id, platform_state, status, is_active, created_at, updated_at)
        SELECT DISTINCT ON (s.email)
            1, NULLIF(s.project_id, '')::int,
            LEFT(s.email, 255), LEFT(s.first_name, 255), LEFT(s.last_name, 255),
            LEFT(s.company_name, 500), LEFT(s.phone, 100), LEFT(s.linkedin_url, 500),
            LEFT(s.location, 500), LEFT(s.job_title, 500),
            LEFT(s.source, 50), LEFT(s.slid, 100),
            jsonb_build_object('smartlead', jsonb_build_object('campaigns', jsonb_build_array(s.camp_json::jsonb)))::json,
            'lead', true,
            NOW(), NOW()
        FROM _staging_sl s
        WHERE NOT EXISTS (
            SELECT 1 FROM contacts c WHERE lower(c.email) = s.email AND c.deleted_at IS NULL
        )
        ORDER BY s.email, s.slid
        ON CONFLICT (lower(email)) WHERE deleted_at IS NULL AND email IS NOT NULL AND email != ''
        DO NOTHING
    """)
    inserted = cur.rowcount
    conn.commit()
    print(f"  Inserted: {inserted:,} in {time.time()-t1:.1f}s")

    # Set smartlead_id
    print("Set smartlead_id...")
    t1 = time.time()
    cur.execute("""
        UPDATE contacts c SET smartlead_id = s.slid, updated_at = NOW()
        FROM (SELECT DISTINCT ON (email) email, slid FROM _staging_sl WHERE slid != '' ORDER BY email, slid) s
        WHERE lower(c.email) = s.email AND c.deleted_at IS NULL
          AND (c.smartlead_id IS NULL OR c.smartlead_id = '')
    """)
    print(f"  Set: {cur.rowcount:,} in {time.time()-t1:.1f}s")
    conn.commit()

    # Build aggregated campaigns per email
    print("Aggregate campaigns...")
    t1 = time.time()
    cur.execute("DROP TABLE IF EXISTS _camp_agg")
    cur.execute("""
        CREATE TEMP TABLE _camp_agg AS
        SELECT email,
            jsonb_agg(DISTINCT camp_json::jsonb) as new_camps,
            MAX(NULLIF(project_id, ''))::int as pid,
            MAX(NULLIF(first_name, '')) as fn, MAX(NULLIF(last_name, '')) as ln,
            MAX(NULLIF(company_name, '')) as cn, MAX(NULLIF(linkedin_url, '')) as li,
            MAX(NULLIF(job_title, '')) as jt
        FROM _staging_sl GROUP BY email
    """)
    conn.commit()
    cur.execute("CREATE INDEX idx_ca_em ON _camp_agg (email)")
    conn.commit()
    print(f"  Aggregated in {time.time()-t1:.1f}s")

    # Merge platform_state
    print("Merge platform_state...")
    t1 = time.time()
    cur.execute("""
        UPDATE contacts c SET
            platform_state = jsonb_set(
                COALESCE(c.platform_state::jsonb, '{}'::jsonb),
                '{smartlead,campaigns}',
                COALESCE(
                    (SELECT jsonb_agg(elem) FROM (
                        SELECT elem FROM jsonb_array_elements(
                            COALESCE(c.platform_state::jsonb->'smartlead'->'campaigns', '[]'::jsonb)
                        ) elem
                        WHERE NOT EXISTS (
                            SELECT 1 FROM jsonb_array_elements(a.new_camps) nc
                            WHERE nc->>'campaign_id' = elem->>'campaign_id'
                        )
                        UNION ALL
                        SELECT nc FROM jsonb_array_elements(a.new_camps) nc
                    ) combined),
                    a.new_camps
                )
            )::json,
            project_id = COALESCE(c.project_id, a.pid),
            first_name = COALESCE(NULLIF(c.first_name, ''), LEFT(a.fn, 255)),
            last_name = COALESCE(NULLIF(c.last_name, ''), LEFT(a.ln, 255)),
            company_name = COALESCE(NULLIF(c.company_name, ''), LEFT(a.cn, 500)),
            linkedin_url = COALESCE(NULLIF(c.linkedin_url, ''), LEFT(a.li, 500)),
            job_title = COALESCE(NULLIF(c.job_title, ''), LEFT(a.jt, 500)),
            updated_at = NOW()
        FROM _camp_agg a
        WHERE lower(c.email) = a.email AND c.deleted_at IS NULL
    """)
    merged = cur.rowcount
    conn.commit()
    print(f"  Merged: {merged:,} in {time.time()-t1:.1f}s")

    # Update leads_count
    cur.execute("""
        WITH counts AS (
            SELECT source, COUNT(*) as cnt FROM _staging_sl WHERE source LIKE 'smartlead:%%' GROUP BY source
        )
        UPDATE campaigns c SET leads_count = counts.cnt
        FROM counts WHERE c.external_id = REPLACE(counts.source, 'smartlead:', '') AND c.platform = 'smartlead'
    """)
    conn.commit()

    # Cleanup
    cur.execute("DROP TABLE IF EXISTS _staging_sl")
    cur.execute("DROP TABLE IF EXISTS _camp_agg")
    conn.commit()

    # Final stats
    cur.execute("SELECT COUNT(*) FROM contacts WHERE company_id = 1 AND deleted_at IS NULL")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM contacts WHERE company_id = 1 AND deleted_at IS NULL AND smartlead_id IS NOT NULL")
    sl = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\nPhase 2 done in {time.time()-t0:.0f}s")
    print(f"  Inserted: {inserted:,}, Merged: {merged:,}")
    print(f"  CRM: {total:,} total ({sl:,} SmartLead)")
    return inserted, merged


def main():
    if not SMARTLEAD_API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set"); sys.exit(1)

    lock = "/tmp/sl_import.lock"
    if os.path.exists(lock) and (time.time() - os.path.getmtime(lock)) < 7200:
        print(f"ERROR: Lock exists. rm {lock}"); sys.exit(1)
    with open(lock, "w") as f:
        f.write(str(os.getpid()))

    phase2_only = "--phase2" in sys.argv
    print(f"Start: {datetime.now(timezone.utc).isoformat()}")
    t0 = time.time()

    if phase2_only:
        if not os.path.exists(TSV_PATH):
            print(f"ERROR: {TSV_PATH} not found"); sys.exit(1)
        rows = sum(1 for _ in open(TSV_PATH))
        print(f"Using existing TSV: {rows:,} rows")
    else:
        rows = phase1_download()

    if rows > 0:
        phase2_merge()

    print(f"\nTotal time: {time.time()-t0:.0f}s ({(time.time()-t0)/60:.1f}m)")

    for f in [lock]:
        try:
            os.remove(f)
        except Exception:
            pass


if __name__ == "__main__":
    main()
