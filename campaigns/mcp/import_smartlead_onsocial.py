#!/usr/bin/env python3
"""Import all SmartLead campaigns with prefix c-OnSocial_ as blacklist into mcp_leadgen.

Mirrors MCP's `import_smartlead_campaigns` tool but as standalone script.

Usage:
    python3 import_smartlead_onsocial.py <mcp_project_id>

Run ON HETZNER (needs docker exec mcp-postgres + network to SmartLead).
"""

import os
import subprocess
import sys
from urllib.request import Request, urlopen
import json


SMARTLEAD_KEY = os.environ.get("SMARTLEAD_API_KEY") or ""
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"
PREFIX = "c-OnSocial_"


def http_get(url: str) -> dict | list:
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; SallyScript/1.0)",
        },
    )
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def run_psql(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "mcp-postgres",
            "psql",
            "-U",
            "mcp",
            "-d",
            "mcp_leadgen",
            "-t",
            "-A",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql: {result.stderr[:300]}")
    return result.stdout


def extract_domain(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[1].strip().lower()


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
    all_domains: dict[str, str] = {}  # domain -> campaign_name
    for i, c in enumerate(onsocial, 1):
        cid = c["id"]
        cname = c["name"]
        print(f"[{i}/{len(onsocial)}] #{cid} {cname[:60]} ... ", end="", flush=True)
        try:
            # smartlead lists leads with pagination
            offset = 0
            limit = 100
            campaign_domains = 0
            while True:
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
            print(f"{campaign_domains} new domains")
        except Exception as e:
            print(f"FAIL: {str(e)[:100]}")

    print(f"\nTotal unique domains: {len(all_domains)}")
    if not all_domains:
        return

    # 3. Upsert into discovered_companies
    company_id_result = run_psql(
        f"SELECT company_id FROM projects WHERE id = {mcp_project_id};"
    ).strip()
    if not company_id_result:
        print(f"ERROR: project {mcp_project_id} not found", file=sys.stderr)
        sys.exit(1)
    company_id = int(company_id_result)
    print(f"Writing to project {mcp_project_id} (company_id={company_id})...")

    # Batch insert (1000 at a time)
    items = list(all_domains.items())
    inserted = 0
    BATCH = 1000
    for i in range(0, len(items), BATCH):
        batch = items[i : i + BATCH]
        values = ",".join(
            f"({mcp_project_id}, {company_id}, '{d.replace(chr(39), chr(39) + chr(39))}', "
            f"'{d.replace(chr(39), chr(39) + chr(39))}', 'REJECTED', true, "
            f"'smartlead_import: {c.replace(chr(39), chr(39) + chr(39))[:180]}', NOW(), NOW())"
            for d, c in batch
        )
        sql = f"""
            INSERT INTO discovered_companies
                (project_id, company_id, domain, name, status, is_blacklisted, blacklist_reason, created_at, updated_at)
            VALUES {values}
            ON CONFLICT (project_id, domain) DO UPDATE
            SET is_blacklisted = true, updated_at = NOW();
        """
        try:
            run_psql(sql)
            inserted += len(batch)
            print(f"  batch {i // BATCH + 1}: +{len(batch)}")
        except Exception as e:
            print(f"  batch {i // BATCH + 1} FAIL: {str(e)[:200]}")

    print(
        f"\nInserted/updated {inserted}/{len(items)} domains → mcp_leadgen project {mcp_project_id}"
    )


if __name__ == "__main__":
    main()
