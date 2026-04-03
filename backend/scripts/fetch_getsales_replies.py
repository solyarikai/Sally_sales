#!/usr/bin/env python3
"""
GetSales LinkedIn Reply Fetcher

Fetches inbox messages from GetSales API and marks contacts as replied.
Run in background: nohup python3 fetch_getsales_replies.py > /tmp/fetch_getsales_replies.log 2>&1 &

API: GET https://amazing.getsales.io/flows/api/linkedin-messages?filter[type]=inbox
"""
import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List

import httpx
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/fetch_getsales_replies.log")
    ]
)
logger = logging.getLogger(__name__)

GETSALES_API_KEY = os.environ.get("GETSALES_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
BATCH_SIZE = 100
MAX_PAGES = 300  # 19,527 / 100 = ~196 pages


async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)


async def fetch_inbox_messages(api_key: str, offset: int, limit: int):
    """Fetch inbox messages from GetSales."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            "https://amazing.getsales.io/flows/api/linkedin-messages",
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "limit": limit,
                "offset": offset,
                "filter[type]": "inbox",
                "order_field": "sent_at",
                "order_type": "desc"
            }
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", []), data.get("total", 0), data.get("has_more", False)
        else:
            logger.error(f"Failed at offset {offset}: {response.status_code}")
            return [], 0, False


async def get_getsales_contacts(conn) -> Dict[str, int]:
    """Get mapping of getsales_id (UUID) -> contact.id"""
    rows = await conn.fetch(
        "SELECT id, getsales_id FROM contacts WHERE getsales_id IS NOT NULL AND getsales_id != ''"
    )
    return {row["getsales_id"]: row["id"] for row in rows}


async def update_contact_replied(conn, contact_id: int, reply_at: datetime, message_text: str):
    """Mark contact as replied."""
    # Check if already marked
    row = await conn.fetchrow(
        "SELECT has_replied, last_reply_at FROM contacts WHERE id = $1",
        contact_id
    )
    
    if row and row["has_replied"]:
        # Already marked, check if this reply is newer
        if row["last_reply_at"] and reply_at <= row["last_reply_at"]:
            return False
    
    await conn.execute("""
        UPDATE contacts 
        SET has_replied = true,
            reply_channel = 'linkedin',
            last_reply_at = $1,
            status = 'replied',
            updated_at = NOW()
        WHERE id = $2
    """, reply_at, contact_id)
    return True


async def create_activity(conn, contact_id: int, company_id: int, message: dict, reply_at: datetime):
    """Create contact activity record for the reply."""
    # Check if activity already exists (by message UUID)
    message_uuid = message.get("uuid")
    existing = await conn.fetchrow(
        "SELECT id FROM contact_activities WHERE source_id = $1 AND source = 'getsales'",
        message_uuid
    )
    if existing:
        return False
    
    await conn.execute("""
        INSERT INTO contact_activities 
        (contact_id, company_id, activity_type, channel, direction, source, source_id, 
         body, snippet, activity_at, extra_data, created_at, updated_at)
        VALUES ($1, $2, 'linkedin_replied', 'linkedin', 'inbound', 'getsales', $3,
                $4, $5, $6, $7, NOW(), NOW())
    """,
        contact_id,
        company_id,
        message_uuid,
        message.get("text"),
        (message.get("text") or "")[:200],
        reply_at,
        json.dumps({
            "sender_profile_uuid": message.get("sender_profile_uuid"),
            "linkedin_conversation_uuid": message.get("linkedin_conversation_uuid"),
            "linkedin_type": message.get("linkedin_type"),
            "automation": message.get("automation"),
        })
    )
    return True


async def main():
    global GETSALES_API_KEY
    if not GETSALES_API_KEY:
        for env_file in ["/app/.env", os.path.expanduser("~/magnum-opus-project/repo/.env")]:
            if os.path.exists(env_file):
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("GETSALES_API_KEY="):
                            GETSALES_API_KEY = line.strip().split("=", 1)[1]
                            break
                if GETSALES_API_KEY:
                    break
    
    if not GETSALES_API_KEY:
        logger.error("GETSALES_API_KEY not found")
        sys.exit(1)
    
    logger.info("Starting GetSales reply fetch...")
    
    conn = await get_db_connection()
    
    try:
        # Get contacts mapping
        getsales_contacts = await get_getsales_contacts(conn)
        logger.info(f"Found {len(getsales_contacts)} GetSales contacts")
        
        if not getsales_contacts:
            logger.warning("No contacts to check for replies")
            return
        
        offset = 0
        total_processed = 0
        total_matched = 0
        contacts_updated = 0
        activities_created = 0
        
        for page in range(MAX_PAGES):
            messages, total, has_more = await fetch_inbox_messages(GETSALES_API_KEY, offset, BATCH_SIZE)
            
            if not messages:
                break
            
            for msg in messages:
                lead_uuid = msg.get("lead_uuid")
                if lead_uuid and lead_uuid in getsales_contacts:
                    contact_id = getsales_contacts[lead_uuid]
                    total_matched += 1
                    
                    # Parse sent_at
                    sent_at_str = msg.get("sent_at")
                    if sent_at_str:
                        try:
                            reply_at = datetime.fromisoformat(sent_at_str.replace("Z", ""))
                        except:
                            reply_at = datetime.utcnow()
                    else:
                        reply_at = datetime.utcnow()
                    
                    # Update contact
                    updated = await update_contact_replied(conn, contact_id, reply_at, msg.get("text"))
                    if updated:
                        contacts_updated += 1
                    
                    # Get company_id
                    row = await conn.fetchrow("SELECT company_id FROM contacts WHERE id = $1", contact_id)
                    company_id = row["company_id"] if row else 1
                    
                    # Create activity
                    created = await create_activity(conn, contact_id, company_id, msg, reply_at)
                    if created:
                        activities_created += 1
            
            total_processed += len(messages)
            offset += BATCH_SIZE
            
            if page % 20 == 0:
                logger.info(f"Progress: {total_processed:,}/{total:,}, {total_matched} matches, {contacts_updated} updated, {activities_created} activities")
            
            if not has_more:
                break
            
            await asyncio.sleep(0.1)
        
        await conn.close()
        logger.info(f"Done: {total_processed:,} messages, {total_matched} matches, {contacts_updated} contacts updated, {activities_created} activities created")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await conn.close()
        raise


if __name__ == "__main__":
    asyncio.run(main())
