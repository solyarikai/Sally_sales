#!/usr/bin/env python3
"""Import individual contacts (people) from all c-OnSocial_* SmartLead campaigns
into mcp_leadgen.extracted_contacts.

This is contact-level blacklist — MCP uses extracted_contacts to skip
already-contacted people when enriching via Apollo.

Usage:
    python3 import_smartlead_contacts.py <mcp_project_id>

Run ON HETZNER. Needs SMARTLEAD_API_KEY. Idempotent (ON CONFLICT updates).
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
REQUEST_DELAY = 1.5
MAX_RETRIES = 5
SQL_BATCH = 200


def http_get(url: str):
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


def run_psql(sql: str) -> str:
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


def sql_escape(s: str) -> str:
    return (s or "").replace("'", "''")


def extract_domain(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[1].strip().lower()


def main():
    if len(sys.argv) != 2 or not SMARTLEAD_KEY:
        print(
            "Usage: python3 import_smartlead_contacts.py <mcp_project_id>",
            file=sys.stderr,
        )
        print("Needs SMARTLEAD_API_KEY env var", file=sys.stderr)
        sys.exit(1)

    mcp_project_id = int(sys.argv[1])

    # 1. Fetch campaigns with c-OnSocial_ prefix
    all_campaigns = http_get(f"{SMARTLEAD_BASE}/campaigns?api_key={SMARTLEAD_KEY}")
    onsocial = [c for c in all_campaigns if (c.get("name") or "").startswith(PREFIX)]
    print(f"Found {len(onsocial)} campaigns with prefix '{PREFIX}'")

    # 2. Pull every lead, collect unique by email
    contacts: dict[str, dict] = {}  # email -> contact dict
    for i, c in enumerate(onsocial, 1):
        cid = c["id"]
        cname = c["name"]
        print(f"[{i}/{len(onsocial)}] #{cid} {cname[:60]} ... ", end="", flush=True)
        try:
            offset = 0
            limit = 100
            new_contacts = 0
            while True:
                time.sleep(REQUEST_DELAY)
                url = f"{SMARTLEAD_BASE}/campaigns/{cid}/leads?api_key={SMARTLEAD_KEY}&offset={offset}&limit={limit}"
                data = http_get(url)
                leads = data if isinstance(data, list) else data.get("data", [])
                if not leads:
                    break
                for lead_wrapper in leads:
                    ld = (
                        lead_wrapper.get("lead", {})
                        if isinstance(lead_wrapper, dict)
                        else {}
                    )
                    # SmartLead response: {lead: {email, first_name, ...}, ...}
                    if not ld:
                        ld = lead_wrapper
                    email = (ld.get("email") or "").strip().lower()
                    if not email or "@" not in email:
                        continue
                    if email in contacts:
                        continue
                    contacts[email] = {
                        "email": email,
                        "first_name": ld.get("first_name") or "",
                        "last_name": ld.get("last_name") or "",
                        "job_title": ld.get("job_title") or "",
                        "linkedin_url": ld.get("linkedin_url") or "",
                        "phone": ld.get("phone_number") or "",
                        "domain": extract_domain(email),
                        "source_campaign": cname,
                    }
                    new_contacts += 1
                if len(leads) < limit:
                    break
                offset += limit
            print(f"+{new_contacts} new contacts", flush=True)
        except Exception as e:
            print(f"FAIL: {str(e)[:100]}", flush=True)

    print(f"\nTotal unique contacts: {len(contacts)}")
    if not contacts:
        return

    # 3. Create unique constraint if missing (for ON CONFLICT)
    run_psql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_extracted_contacts_proj_email "
        "ON extracted_contacts (project_id, lower(email));"
    )

    # 4. Upsert into extracted_contacts
    items = list(contacts.values())
    inserted = 0
    for i in range(0, len(items), SQL_BATCH):
        batch = items[i : i + SQL_BATCH]
        values = ",".join(
            "({pid}, '{email}', '{fn}', '{ln}', '{title}', '{li}', '{phone}', "
            "'smartlead_import', false, '{{\"source_campaign\": \"{src}\"}}'::jsonb, NOW())".format(
                pid=mcp_project_id,
                email=sql_escape(c["email"]),
                fn=sql_escape(c["first_name"])[:200],
                ln=sql_escape(c["last_name"])[:200],
                title=sql_escape(c["job_title"])[:200],
                li=sql_escape(c["linkedin_url"])[:490],
                phone=sql_escape(c["phone"])[:40],
                src=sql_escape(c["source_campaign"])[:180],
            )
            for c in batch
        )
        sql = (
            "INSERT INTO extracted_contacts "
            "(project_id, email, first_name, last_name, job_title, linkedin_url, phone, "
            "email_source, email_verified, source_data, created_at) "
            f"VALUES {values} "
            "ON CONFLICT (project_id, lower(email)) DO UPDATE "
            "SET email_source = EXCLUDED.email_source, source_data = EXCLUDED.source_data;"
        )
        try:
            run_psql(sql)
            inserted += len(batch)
            print(f"  batch {i // SQL_BATCH + 1}: +{len(batch)}", flush=True)
        except Exception as e:
            print(f"  batch {i // SQL_BATCH + 1} FAIL: {str(e)[:200]}", flush=True)

    print(
        f"\nInserted/updated {inserted}/{len(items)} contacts → mcp_leadgen project {mcp_project_id}"
    )


if __name__ == "__main__":
    main()
