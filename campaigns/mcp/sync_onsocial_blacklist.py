#!/usr/bin/env python3
"""Sync OnSocial manual blacklist from main leadgen DB → mcp_leadgen DB.

Covers 305 domains not captured by MCP's `import_smartlead_campaigns`:
- 83 OnSocial paid clients (never contact — active customers)
- 189 known competitors (Modash, HypeAuditor, Captiv8, Lefty, etc.)
- 33 GPT-rejected domains (wrong industry, not IM-related)

Run ON HETZNER before any MCP-based OnSocial campaign launch.

Usage:
    ssh hetzner "python3 ~/magnum-opus-project/repo/campaigns/mcp/sync_onsocial_blacklist.py <mcp_project_id>"
"""

import subprocess
import sys


def run_psql(container: str, user: str, db: str, sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            user,
            "-d",
            db,
            "-t",
            "-A",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr[:200]}")
    return result.stdout


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <mcp_project_id>", file=sys.stderr)
        sys.exit(1)

    mcp_project_id = int(sys.argv[1])

    # Pull manual blacklist from leadgen (exclude mass imports + campaign-backed)
    pull_sql = """
        SELECT DISTINCT LOWER(domain), reason
        FROM project_blacklist
        WHERE project_id = 42
          AND reason NOT IN (
            'onsocial_20k_exclusion',
            'target_approved_backfill',
            'Failed to scrape website',
            'Failed to parse AI response'
          )
          AND reason NOT LIKE 'SOCCOM campaign%'
          AND reason NOT LIKE 'target_approved_run%'
    """
    raw = run_psql("leadgen-postgres", "leadgen", "leadgen", pull_sql)
    rows = [ln.split("|", 1) for ln in raw.strip().splitlines() if "|" in ln]
    print(f"Pulled {len(rows)} manual-blacklist domains from leadgen")

    if not rows:
        print("Nothing to sync — exiting")
        return

    # Upsert into mcp_leadgen.discovered_companies as blacklisted
    # Schema: id, company_id, project_id, domain, name, status, is_blacklisted, blacklist_reason
    inserted = 0
    for domain, reason in rows:
        domain = domain.strip().replace("'", "''")
        reason = reason.strip().replace("'", "''")[:200]  # truncate long GPT reasons
        upsert_sql = f"""
            INSERT INTO discovered_companies
                (project_id, domain, name, status, is_blacklisted, blacklist_reason, created_at, updated_at)
            VALUES
                ({mcp_project_id}, '{domain}', '{domain}', 'REJECTED', true,
                 'onsocial_crm_sync: {reason}', NOW(), NOW())
            ON CONFLICT (project_id, domain) DO UPDATE
            SET is_blacklisted = true,
                blacklist_reason = EXCLUDED.blacklist_reason,
                updated_at = NOW();
        """
        try:
            run_psql("mcp-postgres", "mcp", "mcp_leadgen", upsert_sql)
            inserted += 1
        except Exception as e:
            print(f"  FAIL {domain}: {str(e)[:100]}")

    print(
        f"Synced {inserted}/{len(rows)} domains → mcp_leadgen project {mcp_project_id}"
    )


if __name__ == "__main__":
    main()
