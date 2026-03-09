"""
Backfill SmartLead source created_at into CRM contacts' platform_state.

Uses SmartLead's /campaigns/{id}/leads-export endpoint (returns full CSV in one call).
Stores `added_at` per campaign entry in platform_state for accurate time-filtered analytics.

Usage:
    # Run on server:
    docker exec leadgen-backend python3 -m scripts.backfill_smartlead_dates

    # Or locally:
    python scripts/backfill_smartlead_dates.py
"""
import asyncio
import csv
import io
import logging
import os
import sys
import time

import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        logger.warning(f"  Export failed for campaign {campaign_id}: {resp.status_code}")
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
    """Main backfill: export CSVs for top campaigns, update platform_state.added_at."""
    from sqlalchemy import select, and_, text
    from sqlalchemy.orm.attributes import flag_modified
    from app.db import async_session_maker
    from app.models.campaign import Campaign
    from app.models.contact import Contact

    async with async_session_maker() as session:
        # Get top campaigns by leads_count (most impactful first)
        result = await session.execute(
            select(Campaign).where(
                and_(
                    Campaign.platform == "smartlead",
                    Campaign.external_id.isnot(None),
                    Campaign.leads_count > 0,
                )
            ).order_by(Campaign.leads_count.desc())
        )
        campaigns = result.scalars().all()
        logger.info(f"Found {len(campaigns)} SmartLead campaigns with leads")

    client = httpx.AsyncClient(timeout=120)
    total_updated = 0
    total_campaigns = 0

    for idx, camp in enumerate(campaigns):
        t0 = time.time()
        try:
            leads = await export_campaign_leads(client, camp.external_id)
        except Exception as e:
            logger.warning(f"  [{idx+1}/{len(campaigns)}] {camp.name[:40]}: export error: {e}")
            await asyncio.sleep(2)
            continue
        t1 = time.time()

        if not leads:
            if idx % 50 == 0:
                logger.info(f"  [{idx+1}/{len(campaigns)}] {camp.name[:60]}: 0 leads exported, skipping")
            await asyncio.sleep(0.5)
            continue

        total_campaigns += 1
        # Build email -> created_at lookup
        date_by_email = {lead["email"]: lead["created_at"] for lead in leads}

        # Update contacts in DB
        async with async_session_maker() as session:
            # Find CRM contacts that have this campaign in platform_state
            emails = list(date_by_email.keys())
            # Process in batches of 500 emails
            batch_updated = 0
            for i in range(0, len(emails), 500):
                batch = emails[i:i + 500]
                contact_result = await session.execute(
                    select(Contact).where(
                        and_(
                            Contact.email.in_(batch),
                            Contact.deleted_at.is_(None),
                        )
                    )
                )
                contacts = contact_result.scalars().all()

                for contact in contacts:
                    ps = contact.platform_state
                    if not ps or not isinstance(ps, dict):
                        continue
                    sl_data = ps.get("smartlead", {})
                    sl_campaigns = sl_data.get("campaigns", [])
                    if not sl_campaigns:
                        continue

                    email_lower = (contact.email or "").lower()
                    source_date = date_by_email.get(email_lower)
                    if not source_date:
                        continue

                    changed = False
                    for c_entry in sl_campaigns:
                        if not isinstance(c_entry, dict):
                            continue
                        c_name = (c_entry.get("name") or "").lower()
                        camp_name_lower = camp.name.lower()
                        # Match by campaign name or ID
                        if c_name == camp_name_lower or str(c_entry.get("id")) == camp.external_id:
                            if not c_entry.get("added_at"):
                                c_entry["added_at"] = source_date
                                changed = True

                    if changed:
                        contact.platform_state = ps
                        flag_modified(contact, "platform_state")
                        batch_updated += 1

                await session.commit()

            total_updated += batch_updated
            elapsed = t1 - t0
            if batch_updated > 0 or idx % 50 == 0:
                logger.info(
                    f"  [{idx+1}/{len(campaigns)}] {camp.name[:50]:50s} {len(leads):>6,} exported  {batch_updated:>5} updated  {elapsed:.1f}s"
                )

        # Rate limit: ~1s between campaigns
        await asyncio.sleep(1)

    await client.aclose()
    logger.info(f"\nDone: {total_campaigns} campaigns processed, {total_updated} contacts updated with added_at")


if __name__ == "__main__":
    asyncio.run(backfill())
