"""
Backfill SmartLead source created_at into CRM contacts' platform_state.

Uses SmartLead's /campaigns/{id}/leads-export endpoint (returns full CSV in one call).
Stores `added_at` per campaign entry in platform_state for accurate time-filtered analytics.

Two-phase approach to avoid deadlocks with CRM sync:
  Phase 1: Download all CSVs from SmartLead (fast, API only)
  Phase 2: Batch UPDATE using raw SQL with short lock timeout

Usage:
    docker cp scripts/backfill_smartlead_dates.py leadgen-backend:/app/
    docker exec -d leadgen-backend bash -c 'python3 backfill_smartlead_dates.py > /tmp/backfill.log 2>&1'
    docker exec leadgen-backend tail -f /tmp/backfill.log
"""
import asyncio
import csv
import io
import json
import logging
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Suppress SQLAlchemy echo
for name in ["sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects"]:
    logging.getLogger(name).setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY", "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5")
BASE_URL = "https://server.smartlead.ai/api/v1"


async def export_campaign_leads(client: httpx.AsyncClient, campaign_id: str) -> list[dict]:
    """Download all leads for a campaign via CSV export (single API call)."""
    resp = await client.get(
        f"{BASE_URL}/campaigns/{campaign_id}/leads-export",
        params={"api_key": SMARTLEAD_API_KEY},
        timeout=120,
    )
    if resp.status_code != 200:
        return []

    reader = csv.DictReader(io.StringIO(resp.text))
    leads = []
    for row in reader:
        email = (row.get("email") or "").strip().lower()
        created_at = row.get("created_at", "")
        if email and created_at:
            leads.append({"email": email, "created_at": created_at})
    return leads


async def backfill():
    """Two-phase backfill: download CSVs, then batch update DB."""
    from sqlalchemy import text
    from app.db import async_session_maker

    # Suppress echo on the engine itself
    async with async_session_maker() as session:
        bind = session.get_bind()
        bind.echo = False

    # Phase 1: Get campaign list
    async with async_session_maker() as session:
        result = await session.execute(text("""
            SELECT id, name, external_id, leads_count
            FROM campaigns
            WHERE platform = 'smartlead' AND external_id IS NOT NULL AND COALESCE(leads_count, 0) > 0
            ORDER BY leads_count DESC
        """))
        campaigns = result.all()
        logger.info(f"Phase 1: Found {len(campaigns)} SmartLead campaigns with leads")

    # Phase 1: Download all CSVs
    client = httpx.AsyncClient(timeout=120)
    campaign_dates = {}  # {(camp_name, camp_ext_id): {email: created_at}}

    for idx, (camp_id, camp_name, camp_ext_id, camp_leads) in enumerate(campaigns):
        try:
            leads = await export_campaign_leads(client, camp_ext_id)
        except Exception as e:
            logger.warning(f"  [{idx+1}/{len(campaigns)}] Export error: {e}")
            await asyncio.sleep(2)
            continue

        if leads:
            date_by_email = {lead["email"]: lead["created_at"] for lead in leads}
            campaign_dates[(camp_name, camp_ext_id)] = date_by_email
            if (idx + 1) % 50 == 0 or idx < 5:
                logger.info(f"  [{idx+1}/{len(campaigns)}] Downloaded {camp_name[:40]} ({len(leads)} leads)")

        await asyncio.sleep(0.3)

    await client.aclose()
    logger.info(f"Phase 1 complete: {len(campaign_dates)} campaigns with data, downloading done")

    # Phase 2: Update contacts using raw SQL with short lock timeout
    # Process one contact at a time using raw SQL jsonb manipulation
    total_updated = 0
    total_skipped = 0
    total_already = 0

    for camp_idx, ((camp_name, camp_ext_id), date_by_email) in enumerate(campaign_dates.items()):
        camp_name_lower = camp_name.lower()
        emails = list(date_by_email.keys())
        batch_updated = 0
        batch_skipped = 0

        # Process in batches of 200 emails
        for i in range(0, len(emails), 200):
            batch = emails[i:i + 200]

            try:
                async with async_session_maker() as session:
                    # Set short lock timeout to avoid deadlocks
                    await session.execute(text("SET LOCAL lock_timeout = '200ms'"))

                    # Get contacts with their platform_state
                    placeholders = ", ".join(f":e{j}" for j in range(len(batch)))
                    params = {f"e{j}": email for j, email in enumerate(batch)}

                    result = await session.execute(
                        text(f"""
                            SELECT id, email, platform_state
                            FROM contacts
                            WHERE email IN ({placeholders})
                            AND deleted_at IS NULL
                        """),
                        params
                    )
                    contacts = result.all()

                    for contact_id, email, ps in contacts:
                        if not ps or not isinstance(ps, dict):
                            continue
                        sl_campaigns = ps.get("smartlead", {}).get("campaigns", [])
                        if not sl_campaigns:
                            continue

                        email_lower = (email or "").lower()
                        source_date = date_by_email.get(email_lower)
                        if not source_date:
                            continue

                        changed = False
                        for c_entry in sl_campaigns:
                            if not isinstance(c_entry, dict):
                                continue
                            c_name = (c_entry.get("name") or "").lower()
                            if (c_name == camp_name_lower or str(c_entry.get("id")) == camp_ext_id) and not c_entry.get("added_at"):
                                c_entry["added_at"] = source_date
                                changed = True

                        if changed:
                            try:
                                await session.execute(
                                    text("UPDATE contacts SET platform_state = :ps WHERE id = :id"),
                                    {"ps": json.dumps(ps), "id": contact_id}
                                )
                                batch_updated += 1
                            except Exception:
                                batch_skipped += 1

                    await session.commit()
            except Exception as e:
                err_str = str(e)
                if "lock" in err_str.lower() or "timeout" in err_str.lower():
                    batch_skipped += len(batch)
                else:
                    logger.warning(f"  DB error on campaign {camp_name[:30]} batch {i}: {err_str[:80]}")
                await asyncio.sleep(0.5)

        total_updated += batch_updated
        total_skipped += batch_skipped

        if batch_updated > 0 or (camp_idx + 1) % 50 == 0:
            logger.info(
                f"  [{camp_idx+1}/{len(campaign_dates)}] {camp_name[:45]:45s} {len(emails):>6,} leads  {batch_updated:>5} updated  {batch_skipped:>3} skipped"
            )

    logger.info(f"\nDone: {len(campaign_dates)} campaigns, {total_updated} contacts updated, {total_skipped} skipped (locked)")


if __name__ == "__main__":
    asyncio.run(backfill())
