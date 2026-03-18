"""Backfill ProcessedReply records for LinkedIn replies dropped by the email death gate.

Usage: docker exec leadgen-backend python -m app.scripts.backfill_dropped_replies [--all] [--dry-run]

By default: only Rizzult week 17 (Mar 17-23).
With --all: all 149 dropped replies across all projects.
With --dry-run: print what would be done without creating records.
"""
import asyncio
import json
import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def backfill(all_projects: bool = False, dry_run: bool = False):
    from app.db import async_session_maker
    from app.models.contact import Contact
    from app.services.reply_processor import process_getsales_reply
    from sqlalchemy import select, text

    date_filter = ""
    if not all_projects:
        date_filter = """
              AND c2.name ILIKE '%rizzult%'
              AND we.created_at >= '2026-03-17'
              AND we.created_at < '2026-03-24'
        """

    query = f"""
        SELECT we.id, we.payload, we.campaign_id, c2.name as campaign_name, we.created_at
        FROM webhook_events we
        LEFT JOIN campaigns c2 ON c2.external_id = we.campaign_id
        WHERE we.event_type = 'linkedin_inbox'
          AND we.processed = true
          AND we.lead_email NOT LIKE '%@%'
          AND we.created_at > '2026-03-01'
          {date_filter}
        ORDER BY we.created_at
    """

    async with async_session_maker() as session:
        result = await session.execute(text(query))
        events = result.fetchall()
        logger.info(f"Found {len(events)} dropped events to backfill")

        created = 0
        skipped = 0
        errors = 0

        for ev in events:
            ev_id, payload_str, campaign_id, campaign_name, created_at = ev
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            body = payload.get("body", payload)
            contact_data = body.get("contact", {})
            lead_uuid = contact_data.get("uuid")
            automation_data = body.get("automation", {})
            linkedin_message = body.get("linkedin_message", {})
            message_text = linkedin_message.get("text", "")

            first_name = contact_data.get("first_name", "")
            last_name = contact_data.get("last_name", "")

            if not lead_uuid:
                logger.info(f"  Event {ev_id}: no lead_uuid, skipping")
                skipped += 1
                continue

            # Find contact
            contact = (await session.execute(
                select(Contact).where(Contact.getsales_id == lead_uuid, Contact.deleted_at.is_(None))
            )).scalar_one_or_none()

            if not contact:
                logger.info(f"  Event {ev_id}: no contact for UUID {lead_uuid} ({first_name} {last_name}), skipping")
                skipped += 1
                continue

            # Parse timestamp
            sent_at_str = linkedin_message.get("sent_at")
            if sent_at_str:
                try:
                    activity_at = datetime.fromisoformat(
                        sent_at_str.replace(" ", "T").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except (ValueError, TypeError):
                    activity_at = datetime.utcnow()
            else:
                activity_at = datetime.utcnow()

            flow_name = automation_data.get("name", "") if isinstance(automation_data, dict) else (campaign_name or "")
            flow_uuid = automation_data.get("uuid", "") if isinstance(automation_data, dict) else (campaign_id or "")

            logger.info(f"  Event {ev_id}: {first_name} {last_name} -> {flow_name or campaign_name}")

            if dry_run:
                created += 1
                continue

            try:
                async with session.begin_nested():
                    pr = await process_getsales_reply(
                        message_text=message_text,
                        contact=contact,
                        flow_name=flow_name,
                        flow_uuid=flow_uuid,
                        message_id=linkedin_message.get("uuid", ""),
                        activity_at=activity_at,
                        raw_data=body,
                        session=session,
                    )
                if pr:
                    # Prevent notification spam
                    pr.telegram_sent_at = datetime.utcnow()

                    # Sheet sync: allow for Rizzult week 17, block for everything else
                    is_rizzult_wk17 = (
                        campaign_name
                        and "rizzult" in campaign_name.lower()
                        and activity_at >= datetime(2026, 3, 17)
                        and activity_at < datetime(2026, 3, 24)
                    )
                    if not is_rizzult_wk17:
                        pr.sheet_synced_at = datetime.utcnow()

                    await session.commit()
                    sheet_status = "sheet sync ENABLED" if not pr.sheet_synced_at else "sheet sync blocked"
                    logger.info(f"    -> Created ProcessedReply {pr.id} ({sheet_status})")
                    created += 1
                else:
                    logger.info(f"    -> process_getsales_reply returned None")
                    skipped += 1
            except Exception as e:
                logger.error(f"    -> ERROR: {e}")
                await session.rollback()
                errors += 1

        logger.info(f"\nDone: {created} created, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    all_projects = "--all" in sys.argv
    dry_run = "--dry-run" in sys.argv
    asyncio.run(backfill(all_projects=all_projects, dry_run=dry_run))
