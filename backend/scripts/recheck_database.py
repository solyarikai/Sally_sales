#!/usr/bin/env python3
"""
Database Recheck — Verify CRM sync integrity.

Saves results to: checks/<timestamp>/
  - 01_contacts_by_source.txt
  - 02_campaigns.txt
  - 03_api_crossref.txt
  - 04_activities.txt
  - 05_data_quality.txt
  - 06_sample_replied.txt
  - 07_summary.txt
  - full_report.txt (combined)

What it checks:
  - DB (PostgreSQL at 46.62.210.24) — contacts, campaigns JSON, activities
  - SmartLead API — live campaign list, compared with DB campaign names
  - GetSales API — live automation/flow list, compared with DB campaign names
  - Data quality — missing campaigns, orphan activities, placeholder emails, dupes

Run: cd backend && venv/bin/python scripts/recheck_database.py
"""
import asyncio
import asyncpg
import httpx
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # magnum-opus/
CHECKS_DIR = PROJECT_ROOT / "checks"


def make_output_dir():
    """Create checks/<timestamp>/ directory and return path."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = CHECKS_DIR / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


class ReportWriter:
    """Write to both console and file simultaneously."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self._current_file = None
        self._full_lines = []

    def start_section(self, filename: str):
        self._current_file = self.out_dir / filename
        self._current_lines = []

    def write(self, line: str = ""):
        print(line)
        self._current_lines.append(line)
        self._full_lines.append(line)

    def end_section(self):
        if self._current_file:
            self._current_file.write_text("\n".join(self._current_lines) + "\n")
        self._current_file = None

    def save_full_report(self):
        (self.out_dir / "full_report.txt").write_text("\n".join(self._full_lines) + "\n")


async def main():
    # Load .env from backend dir
    env_file = SCRIPT_DIR.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://leadgen:leadgen_secret@46.62.210.24:5432/leadgen")
    # asyncpg needs plain postgres:// URL
    db_url = db_url.replace("postgresql+asyncpg://", "postgres://").replace("postgresql://", "postgres://")

    conn = await asyncpg.connect(db_url)

    out_dir = make_output_dir()
    r = ReportWriter(out_dir)

    r.start_section("00_header.txt")
    r.write("=" * 70)
    r.write("  DATABASE RECHECK REPORT")
    r.write(f"  Generated: {datetime.utcnow().isoformat()}Z")
    r.write(f"  Output: {out_dir}")
    r.write("=" * 70)
    r.end_section()

    # ── 1. Contacts by source ──
    r.start_section("01_contacts_by_source.txt")
    r.write("\n── 1. CONTACTS BY SOURCE ──")
    r.write("  (What: counts of contacts grouped by source system, with reply breakdown)")
    r.write("  (Where: DB contacts table)")
    r.write()
    rows = await conn.fetch('''
        SELECT
            source,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE has_replied = true) as replied,
            COUNT(*) FILTER (WHERE has_replied = false OR has_replied IS NULL) as not_replied
        FROM contacts
        WHERE deleted_at IS NULL
        GROUP BY source
        ORDER BY total DESC
    ''')
    total_all = 0
    for row in rows:
        total_all += row["total"]
        r.write(f"  {row['source']:30s}  total={row['total']:>5}  replied={row['replied']:>4}  not_replied={row['not_replied']:>5}")
    r.write(f"  {'TOTAL':30s}  total={total_all:>5}")
    r.end_section()

    # ── 2. Unique campaigns by source ──
    r.start_section("02_campaigns.txt")
    r.write("\n── 2. UNIQUE CAMPAIGNS (from contacts.campaigns JSON) ──")
    r.write("  (What: campaign names extracted from contacts.campaigns JSON field)")
    r.write("  (Where: DB contacts.campaigns column)")
    r.write()
    campaign_rows = await conn.fetch('''
        WITH campaign_data AS (
            SELECT jsonb_array_elements(campaigns::jsonb) as campaign
            FROM contacts
            WHERE campaigns IS NOT NULL
              AND campaigns::text != '[]'
              AND campaigns::text LIKE '[%'
              AND deleted_at IS NULL
        )
        SELECT
            campaign->>'source' as source,
            campaign->>'name' as name,
            COUNT(*) as contact_count
        FROM campaign_data
        WHERE campaign->>'name' IS NOT NULL
        GROUP BY campaign->>'source', campaign->>'name'
        ORDER BY campaign->>'source', contact_count DESC
    ''')

    by_source = {}
    for row in campaign_rows:
        src = row["source"] or "unknown"
        by_source.setdefault(src, []).append((row["name"], row["contact_count"]))

    for src, campaigns in sorted(by_source.items()):
        r.write(f"  Source: {src} ({len(campaigns)} campaigns)")
        for name, cnt in campaigns:
            r.write(f"    {name[:55]:55s}  contacts={cnt}")
        r.write()
    r.end_section()

    # ── 3. Cross-reference with live APIs ──
    r.start_section("03_api_crossref.txt")
    r.write("\n── 3. LIVE API CROSS-REFERENCE ──")
    r.write("  (What: compare DB campaign counts with live SmartLead + GetSales APIs)")
    r.write("  (Where: SmartLead API /campaigns, GetSales API /automations)")
    r.write()

    smartlead_key = os.getenv("SMARTLEAD_API_KEY")
    getsales_key = os.getenv("GETSALES_API_KEY")
    sl_api_campaigns = []
    gs_api_flows = []

    if smartlead_key:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://server.smartlead.ai/api/v1/campaigns",
                    params={"api_key": smartlead_key},
                )
                if resp.status_code == 200:
                    sl_api_campaigns = resp.json()
                    active = [c for c in sl_api_campaigns if c.get("status") == "ACTIVE"]
                    r.write(f"  SmartLead API: {len(sl_api_campaigns)} total campaigns, {len(active)} active")
                    db_sl_count = len(by_source.get("smartlead", []))
                    r.write(f"  SmartLead DB:  {db_sl_count} unique campaign names in contacts")
                    if db_sl_count < len(active):
                        r.write(f"  ⚠ {len(active) - db_sl_count} API campaigns may not have contacts synced yet")

                    # Show which API campaigns are NOT in DB
                    db_campaign_names = {name.lower() for name, _ in by_source.get("smartlead", [])}
                    api_names = [(c.get("name", ""), c.get("status", ""), c.get("id")) for c in sl_api_campaigns]
                    missing_in_db = [(n, s, cid) for n, s, cid in api_names if n.lower() not in db_campaign_names and s == "ACTIVE"]
                    if missing_in_db:
                        r.write(f"\n  SmartLead campaigns NOT in DB ({len(missing_in_db)}):")
                        for n, s, cid in missing_in_db[:15]:
                            r.write(f"    [{cid}] {n} ({s})")
                else:
                    r.write(f"  SmartLead API error: {resp.status_code}")
        except Exception as e:
            r.write(f"  SmartLead API error: {e}")
    else:
        r.write("  SmartLead: API key not set, skipping")

    r.write()

    if getsales_key:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://amazing.getsales.io/flows/api/flows",
                    headers={"Authorization": f"Bearer {getsales_key}"},
                    params={"per_page": 200},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    gs_api_flows = data.get("data", []) if isinstance(data, dict) else data
                    r.write(f"  GetSales API:  {len(gs_api_flows)} automations/flows")
                    db_gs_count = len(by_source.get("getsales", []))
                    r.write(f"  GetSales DB:   {db_gs_count} unique campaign names in contacts")
                else:
                    r.write(f"  GetSales API error: {resp.status_code}")
        except Exception as e:
            r.write(f"  GetSales API error: {e}")
    else:
        r.write("  GetSales: API key not set, skipping")

    r.end_section()

    # ── 4. Activities by type + direction ──
    r.start_section("04_activities.txt")
    r.write("\n── 4. ACTIVITIES BY TYPE + DIRECTION ──")
    r.write("  (What: contact_activities breakdown — verifies both inbound AND outbound exist)")
    r.write("  (Where: DB contact_activities table)")
    r.write()
    activity_rows = await conn.fetch('''
        SELECT activity_type, channel, direction, source, COUNT(*) as cnt
        FROM contact_activities
        GROUP BY activity_type, channel, direction, source
        ORDER BY source, channel, activity_type
    ''')
    for row in activity_rows:
        r.write(f"  {row['source']:12s} {row['channel']:10s} {row['activity_type']:25s} {row['direction'] or 'n/a':10s} count={row['cnt']}")

    has_inbound = any(row["direction"] == "inbound" for row in activity_rows)
    has_outbound = any(row["direction"] == "outbound" for row in activity_rows)
    r.write()
    r.write(f"  Has inbound activities:  {'YES' if has_inbound else 'NO ⚠'}")
    r.write(f"  Has outbound activities: {'YES' if has_outbound else 'NO ⚠'}")
    r.end_section()

    # ── 5. Data quality ──
    r.start_section("05_data_quality.txt")
    r.write("\n── 5. DATA QUALITY ──")
    r.write("  (What: contacts missing campaigns, orphan activities, placeholder emails, dupes)")
    r.write("  (Where: DB contacts + contact_activities)")
    r.write()

    missing_campaigns = await conn.fetchval('''
        SELECT COUNT(*) FROM contacts
        WHERE deleted_at IS NULL
          AND (campaigns IS NULL OR campaigns::text = '[]' OR campaigns::text = 'null')
    ''')
    r.write(f"  Contacts missing campaigns JSON:  {missing_campaigns}")

    placeholder = await conn.fetchval('''
        SELECT COUNT(*) FROM contacts
        WHERE deleted_at IS NULL
          AND (email LIKE '%@placeholder.local' OR email LIKE '%@getsales.local')
    ''')
    r.write(f"  Contacts with placeholder emails:  {placeholder}")

    orphans = await conn.fetchval('''
        SELECT COUNT(*) FROM contact_activities ca
        LEFT JOIN contacts c ON ca.contact_id = c.id
        WHERE c.id IS NULL
    ''')
    r.write(f"  Orphan activities (no contact):    {orphans}")

    replied_no_activity = await conn.fetchval('''
        SELECT COUNT(*) FROM contacts c
        WHERE c.deleted_at IS NULL
          AND c.has_replied = true
          AND NOT EXISTS (
            SELECT 1 FROM contact_activities ca
            WHERE ca.contact_id = c.id AND ca.direction = 'inbound'
          )
    ''')
    r.write(f"  Replied but no inbound activity:   {replied_no_activity}")

    dupes = await conn.fetchval('''
        SELECT COUNT(*) FROM (
            SELECT email, COUNT(*) FROM contacts
            WHERE deleted_at IS NULL
            GROUP BY email HAVING COUNT(*) > 1
        ) sub
    ''')
    r.write(f"  Duplicate email groups:            {dupes}")
    r.end_section()

    # ── 6. Sample replied contacts ──
    r.start_section("06_sample_replied.txt")
    r.write("\n── 6. SAMPLE REPLIED CONTACTS (local activity count) ──")
    r.write("  (What: 10 most recent replied contacts with their activity breakdown)")
    r.write("  (Where: DB contacts + contact_activities)")
    r.write()
    sample = await conn.fetch('''
        SELECT c.id, c.email, c.source, c.reply_channel,
               (SELECT COUNT(*) FROM contact_activities ca WHERE ca.contact_id = c.id) as activity_count,
               (SELECT COUNT(*) FROM contact_activities ca WHERE ca.contact_id = c.id AND ca.direction = 'inbound') as inbound_count,
               (SELECT COUNT(*) FROM contact_activities ca WHERE ca.contact_id = c.id AND ca.direction = 'outbound') as outbound_count
        FROM contacts c
        WHERE c.has_replied = true AND c.deleted_at IS NULL
        ORDER BY c.last_reply_at DESC NULLS LAST
        LIMIT 10
    ''')
    for row in sample:
        r.write(
            f"  [{row['id']:>5}] {row['email'][:40]:40s} src={row['source']:15s} ch={row['reply_channel'] or 'n/a':8s} "
            f"activities={row['activity_count']} (in={row['inbound_count']}, out={row['outbound_count']})"
        )
    r.end_section()

    # ── 7. Summary ──
    r.start_section("07_summary.txt")
    r.write("\n── 7. SUMMARY ──")
    total_activities = await conn.fetchval("SELECT COUNT(*) FROM contact_activities")
    total_processed = await conn.fetchval("SELECT COUNT(*) FROM processed_replies")
    total_projects = await conn.fetchval("SELECT COUNT(*) FROM projects WHERE deleted_at IS NULL")
    r.write(f"  Total contacts:          {total_all}")
    r.write(f"  Total activities:        {total_activities}")
    r.write(f"  Total processed replies: {total_processed}")
    r.write(f"  Total projects:          {total_projects}")
    r.write(f"  Campaigns in DB:         {sum(len(v) for v in by_source.values())}")
    r.write()
    r.write("=" * 70)
    r.write("  RECHECK COMPLETE")
    r.write("=" * 70)
    r.end_section()

    r.save_full_report()
    print(f"\n📁 Results saved to: {out_dir}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
