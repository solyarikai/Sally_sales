#!/usr/bin/env python3
"""
Historical Messages Sync Script

Fetches ALL historical LinkedIn messages from GetSales and stores them
in contact_activities for AI reply suggestions.

Smartlead replies are already captured via webhooks in processed_replies table.

Usage:
    python -m app.scripts.sync_historical_messages
"""
import asyncio
import sys
import os
import logging
from datetime import datetime

# Add app to path
sys.path.insert(0, '/app')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def send_telegram_progress(message: str):
    """Send progress update to Telegram."""
    try:
        from app.services.notification_service import send_telegram_notification
        await send_telegram_notification(message)
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


async def sync_getsales_historical_messages():
    """
    Sync ALL GetSales LinkedIn messages (both inbox and outbox).
    
    This fetches the complete message history for AI reply suggestions.
    """
    from app.db import async_session_maker
    from app.services.crm_sync_service import GetSalesClient
    from app.models.contact import Contact, ContactActivity
    from sqlalchemy import select, and_
    
    api_key = os.getenv('GETSALES_API_KEY')
    if not api_key:
        logger.error("GETSALES_API_KEY not set")
        return
    
    client = GetSalesClient(api_key)
    
    stats = {
        "inbox_processed": 0,
        "outbox_processed": 0,
        "new_activities": 0,
        "no_contact": 0,
        "duplicates": 0,
        "errors": 0
    }
    
    # Get totals
    _, _, inbox_total = await client.get_inbox_messages(limit=1)
    _, _, outbox_total = await client.get_outbox_messages(limit=1)
    
    await send_telegram_progress(
        "<b>Starting Historical Messages Sync</b>\n\n"
        "Inbox: " + str(inbox_total) + " messages\n"
        "Outbox: " + str(outbox_total) + " messages\n"
        "Total: " + str(inbox_total + outbox_total) + " messages"
    )
    
    logger.info(f"Starting historical sync: {inbox_total} inbox, {outbox_total} outbox")
    
    async with async_session_maker() as session:
        # Build a cache of lead_uuid -> contact_id for faster lookups
        contact_cache = {}
        contacts_query = await session.execute(
            select(Contact.id, Contact.getsales_id).where(Contact.getsales_id.isnot(None))
        )
        for contact_id, getsales_id in contacts_query.all():
            contact_cache[getsales_id] = contact_id
        
        logger.info(f"Loaded {len(contact_cache)} contacts with getsales_id")
        
        # Process inbox messages (inbound)
        offset = 0
        page_size = 100
        last_progress_report = 0
        
        while True:
            try:
                messages, has_more, _ = await client.get_inbox_messages(limit=page_size, offset=offset)
                
                if not messages:
                    break
                
                for msg in messages:
                    stats["inbox_processed"] += 1
                    
                    lead_uuid = msg.get("lead_uuid")
                    if not lead_uuid or lead_uuid not in contact_cache:
                        stats["no_contact"] += 1
                        continue
                    
                    contact_id = contact_cache[lead_uuid]
                    message_id = msg.get("uuid")
                    
                    # Check for duplicate
                    existing = await session.execute(
                        select(ContactActivity.id).where(
                            and_(
                                ContactActivity.source == "getsales",
                                ContactActivity.source_id == str(message_id)
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        stats["duplicates"] += 1
                        continue
                    
                    # Create activity
                    activity = ContactActivity(
                        contact_id=contact_id,
                        company_id=1,
                        activity_type="linkedin_replied",
                        channel="linkedin",
                        direction="inbound",
                        source="getsales",
                        source_id=str(message_id),
                        body=msg.get("text"),
                        snippet=(msg.get("text") or "")[:200],
                        extra_data={
                            "sender_profile_uuid": msg.get("sender_profile_uuid"),
                            "linkedin_conversation_uuid": msg.get("linkedin_conversation_uuid"),
                            "linkedin_type": msg.get("linkedin_type"),
                            "automation": msg.get("automation")
                        },
                        activity_at=datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00")).replace(tzinfo=None) if msg.get("created_at") else datetime.utcnow()
                    )
                    session.add(activity)
                    stats["new_activities"] += 1
                
                # Commit batch
                await session.commit()
                
                # Progress report every 1000 messages
                if stats["inbox_processed"] - last_progress_report >= 1000:
                    last_progress_report = stats["inbox_processed"]
                    logger.info(f"Inbox progress: {stats['inbox_processed']}/{inbox_total} ({stats['new_activities']} new)")
                    await send_telegram_progress(
                        "Inbox: " + str(stats['inbox_processed']) + "/" + str(inbox_total) + "\n"
                        "New: " + str(stats['new_activities'])
                    )
                
                if not has_more:
                    break
                    
                offset += page_size
                await asyncio.sleep(0.05)  # Rate limiting
                
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error processing inbox page at offset {offset}: {e}")
                await asyncio.sleep(1)
                offset += page_size
        
        # Process outbox messages (outbound)
        offset = 0
        last_progress_report = 0
        
        while True:
            try:
                messages, has_more, _ = await client.get_outbox_messages(limit=page_size, offset=offset)
                
                if not messages:
                    break
                
                for msg in messages:
                    stats["outbox_processed"] += 1
                    
                    lead_uuid = msg.get("lead_uuid")
                    if not lead_uuid or lead_uuid not in contact_cache:
                        stats["no_contact"] += 1
                        continue
                    
                    contact_id = contact_cache[lead_uuid]
                    message_id = msg.get("uuid")
                    
                    # Check for duplicate
                    existing = await session.execute(
                        select(ContactActivity.id).where(
                            and_(
                                ContactActivity.source == "getsales",
                                ContactActivity.source_id == str(message_id)
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        stats["duplicates"] += 1
                        continue
                    
                    # Create activity
                    activity = ContactActivity(
                        contact_id=contact_id,
                        company_id=1,
                        activity_type="linkedin_sent",
                        channel="linkedin",
                        direction="outbound",
                        source="getsales",
                        source_id=str(message_id),
                        body=msg.get("text"),
                        snippet=(msg.get("text") or "")[:200],
                        extra_data={
                            "sender_profile_uuid": msg.get("sender_profile_uuid"),
                            "linkedin_conversation_uuid": msg.get("linkedin_conversation_uuid"),
                            "linkedin_type": msg.get("linkedin_type"),
                            "automation": msg.get("automation"),
                            "template_uuid": msg.get("template_uuid")
                        },
                        activity_at=datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00")).replace(tzinfo=None) if msg.get("created_at") else datetime.utcnow()
                    )
                    session.add(activity)
                    stats["new_activities"] += 1
                
                # Commit batch
                await session.commit()
                
                # Progress report every 5000 messages (outbox is larger)
                if stats["outbox_processed"] - last_progress_report >= 5000:
                    last_progress_report = stats["outbox_processed"]
                    logger.info(f"Outbox progress: {stats['outbox_processed']}/{outbox_total} ({stats['new_activities']} new)")
                    await send_telegram_progress(
                        "Outbox: " + str(stats['outbox_processed']) + "/" + str(outbox_total) + "\n"
                        "New: " + str(stats['new_activities'])
                    )
                
                if not has_more:
                    break
                    
                offset += page_size
                await asyncio.sleep(0.05)  # Rate limiting
                
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error processing outbox page at offset {offset}: {e}")
                await asyncio.sleep(1)
                offset += page_size
    
    # Final report
    await send_telegram_progress(
        "<b>Historical Sync Complete</b>\n\n"
        "Inbox: " + str(stats['inbox_processed']) + "\n"
        "Outbox: " + str(stats['outbox_processed']) + "\n"
        "New activities: " + str(stats['new_activities']) + "\n"
        "Duplicates: " + str(stats['duplicates']) + "\n"
        "No contact: " + str(stats['no_contact']) + "\n"
        "Errors: " + str(stats['errors'])
    )
    
    logger.info(f"Historical sync complete: {stats}")
    return stats


async def main():
    """Main entry point."""
    logger.info("Starting historical messages sync...")
    
    stats = await sync_getsales_historical_messages()
    
    logger.info(f"Done! Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
