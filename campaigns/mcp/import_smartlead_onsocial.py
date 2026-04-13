#!/usr/bin/env python3
"""Import all SmartLead campaigns with prefix c-OnSocial_ as blacklist into mcp_leadgen.

Mirrors MCP's `import_smartlead_campaigns` tool but as standalone script.

Usage:
    python3 import_smartlead_onsocial.py <mcp_project_id>

Run ON HETZNER (needs docker exec mcp-postgres + network to SmartLead).
Idempotent — ON CONFLICT DO UPDATE. Safe to re-run.
"""

import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SMARTLEAD_KEY = os.environ.get("SMARTLEAD_API_KEY") or ""
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"
PREFIX = "c-OnSocial_"
REQUEST_DELAY = 1.5  # seconds between SmartLead API calls to avoid 429
MAX_RETRIES = 5
SQL_BATCH = 300  # smaller to avoid ARG_MAX


def http_get(url: str):
    """GET with retry on 429."""
    for attempt in range(MAX_RETRIES):
        req = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; SallyScript/1.0)",
            },
        )
        try:
            with urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = 10 * (attempt + 1)
                print(f"    429, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise


def run_psql_stdin(sql: str) -> str:
    """Stream SQL via stdin — avoids ARG_MAX limit for big batch inserts."""
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "mcp-postgres",
            "psql",
            "-U",
            "mcp",
            "-d",
            "mcp_leadgen",
            "-t",
            "-A",
        ],
        input=sql,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql: {result.stderr[:300]}")
    return result.stdout


def extract_domain(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[1].strip().lower()


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def main():
    if len(sys.argv) != 2 or not SMARTLEAD_KEY:
        print(
            "Usage: python3 import_smartlead_onsocial.py <mcp_project_id>",
            file=sys.stderr,
        )
        print("Needs SMARTLEAD_API_KEY env var", file=sys.stderr)
        sys.exit(1)

    mcp_project_id = int(sys.argv[1])

    # 1. Fetch all campaigns, filter by prefix
    all_campaigns = http_get(f"{SMARTLEAD_BASE}/campaigns?api_key={SMARTLEAD_KEY}")
    onsocial = [c for c in all_campaigns if (c.get("name") or "").startswith(PREFIX)]
    print(f"Found {len(onsocial)} campaigns with prefix '{PREFIX}'")

    # 2. Pull leads per campaign, collect unique domains
    all_domains: dict[str, str] = {}
    for i, c in enumerate(onsocial, 1):
        cid = c["id"]
        cname = c["name"]
        print(f"[{i}/{len(onsocial)}] #{cid} {cname[:60]} ... ", end="", flush=True)
        try:
            offset = 0
            limit = 100
            campaign_domains = 0
            while True:
                time.sleep(REQUEST_DELAY)
                url = f"{SMARTLEAD_BASE}/campaigns/{cid}/leads?api_key={SMARTLEAD_KEY}&offset={offset}&limit={limit}"
                data = http_get(url)
                leads = data if isinstance(data, list) else data.get("data", [])
                if not leads:
                    break
                for lead in leads:
                    email = (
                        (lead.get("lead", {}) or {}).get("email")
                        or lead.get("email")
                        or ""
                    )
                    d = extract_domain(email)
                    if d and d not in all_domains:
                        all_domains[d] = cname
                        campaign_domains += 1
                if len(leads) < limit:
                    break
                offset += limit
            print(f"{campaign_domains} new domains", flush=True)
        except Exception as e:
            print(f"FAIL: {str(e)[:100]}", flush=True)

    print(f"\nTotal unique domains: {len(all_domains)}")
    if not all_domains:
        return

    # 3. Upsert into discovered_companies
    company_id_result = run_psql_stdin(
        f"SELECT company_id FROM projects WHERE id = {mcp_project_id};"
    ).strip()
    if not company_id_result:
        print(f"ERROR: project {mcp_project_id} not found", file=sys.stderr)
        sys.exit(1)
    company_id = int(company_id_result)
    print(f"Writing to project {mcp_project_id} (company_id={company_id})...")

    items = list(all_domains.items())
    inserted = 0
    for i in range(0, len(items), SQL_BATCH):
        batch = items[i : i + SQL_BATCH]
        values = ",".join(
            "({pid}, {cid}, '{d}', '{d}', 'REJECTED', true, 'smartlead_import: {r}', NOW(), NOW())".format(
                pid=mcp_project_id,
                cid=company_id,
                d=sql_escape(d),
                r=sql_escape(c)[:180],
            )
            for d, c in batch
        )
        sql = (
            "INSERT INTO discovered_companies "
            "(project_id, company_id, domain, name, status, is_blacklisted, blacklist_reason, created_at, updated_at) "
            f"VALUES {values} "
            "ON CONFLICT (project_id, domain) DO UPDATE "
            "SET is_blacklisted = true, updated_at = NOW();"
        )
        try:
            run_psql_stdin(sql)
            inserted += len(batch)
            print(f"  batch {i // SQL_BATCH + 1}: +{len(batch)}", flush=True)
        except Exception as e:
            print(f"  batch {i // SQL_BATCH + 1} FAIL: {str(e)[:200]}", flush=True)

    print(
        f"\nInserted/updated {inserted}/{len(items)} domains → mcp_leadgen project {mcp_project_id}"
    )


if __name__ == "__main__":
    main()
