#!/usr/bin/env python3
"""
Smartlead Campaign Enrichment Script
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
        logging.FileHandler("/tmp/enrich_smartlead_campaigns.log")
    ]
)
logger = logging.getLogger(__name__)

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
BASE_URL = "https://server.smartlead.ai/api/v1"


async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)


async def fetch_campaigns(api_key: str) -> List[Dict]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{BASE_URL}/campaigns",
            params={"api_key": api_key}
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            return data.get("campaigns", data.get("data", []))
        return []


async def fetch_campaign_leads(api_key: str, campaign_id: int, limit: int = 500, offset: int = 0) -> List[Dict]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{BASE_URL}/campaigns/{campaign_id}/statistics",
            params={"api_key": api_key, "limit": limit, "offset": offset}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        return []


async def get_contacts_by_email(conn) -> Dict[str, int]:
    rows = await conn.fetch("SELECT id, email FROM contacts WHERE email IS NOT NULL AND email != ''")
    return {row["email"].lower().strip(): row["id"] for row in rows}


async def update_contact_campaign(conn, contact_id: int, campaign_name: str, campaign_id: int, status: str):
    campaign_entry = {
        "name": campaign_name,
        "id": str(campaign_id),
        "source": "smartlead",
        "status": status,
        "enriched_at": datetime.utcnow().isoformat()
    }
    
    row = await conn.fetchrow("SELECT campaigns FROM contacts WHERE id = $1", contact_id)
    current_raw = row["campaigns"] if row else None
    
    if current_raw is None:
        current = []
    elif isinstance(current_raw, str):
        try:
            current = json.loads(current_raw)
        except:
            current = []
    elif isinstance(current_raw, list):
        current = current_raw
    else:
        current = []
    
    # Check if already has this campaign (by id)
    existing_ids = {c.get("id") for c in current if isinstance(c, dict)}
    if str(campaign_id) in existing_ids:
        return False
    
    new_campaigns = current + [campaign_entry]
    await conn.execute(
        "UPDATE contacts SET campaigns = $1::jsonb, updated_at = NOW() WHERE id = $2",
        json.dumps(new_campaigns), contact_id
    )
    return True


async def main():
    global SMARTLEAD_API_KEY
    if not SMARTLEAD_API_KEY:
        for env_file in ["/app/.env", os.path.expanduser("~/magnum-opus-project/repo/.env")]:
            if os.path.exists(env_file):
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("SMARTLEAD_API_KEY="):
                            SMARTLEAD_API_KEY = line.strip().split("=", 1)[1]
                            break
                if SMARTLEAD_API_KEY:
                    break
    
    if not SMARTLEAD_API_KEY:
        logger.error("SMARTLEAD_API_KEY not found")
        sys.exit(1)
    
    logger.info("Starting Smartlead campaign enrichment...")
    
    campaigns = await fetch_campaigns(SMARTLEAD_API_KEY)
    logger.info(f"Found {len(campaigns)} campaigns")
    
    if not campaigns:
        return
    
    conn = await get_db_connection()
    
    try:
        contacts_by_email = await get_contacts_by_email(conn)
        logger.info(f"Found {len(contacts_by_email)} contacts with email")
        
        total_matched = 0
        total_updated = 0
        
        for i, campaign in enumerate(campaigns):
            campaign_id = campaign.get("id")
            campaign_name = campaign.get("name", f"Campaign {campaign_id}")
            campaign_status = campaign.get("status", "unknown")
            
            # Fetch leads (paginate)
            offset = 0
            campaign_matches = 0
            while True:
                leads = await fetch_campaign_leads(SMARTLEAD_API_KEY, campaign_id, limit=500, offset=offset)
                if not leads:
                    break
                
                for lead in leads:
                    email = (lead.get("lead_email") or "").lower().strip()
                    if email and email in contacts_by_email:
                        contact_id = contacts_by_email[email]
                        lead_status = lead.get("lead_status", campaign_status)
                        updated = await update_contact_campaign(conn, contact_id, campaign_name, campaign_id, lead_status)
                        total_matched += 1
                        campaign_matches += 1
                        if updated:
                            total_updated += 1
                
                if len(leads) < 500:
                    break
                offset += 500
                await asyncio.sleep(0.05)
            
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i+1}/{len(campaigns)} campaigns, {total_matched} matches, {total_updated} updated")
            
            await asyncio.sleep(0.02)
        
        logger.info(f"Done: {len(campaigns)} campaigns, {total_matched} matches, {total_updated} updated")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
