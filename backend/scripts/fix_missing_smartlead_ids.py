#!/usr/bin/env python3
"""
Fix contacts that have Smartlead campaign data but missing smartlead_id.
Query Smartlead API by email and update the contact.
"""
import os
import sys
import json
import asyncio
import logging

import httpx
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
BASE_URL = "https://server.smartlead.ai/api/v1"


async def get_smartlead_id_by_email(client: httpx.AsyncClient, email: str) -> str | None:
    """Query Smartlead API to get lead ID by email."""
    try:
        response = await client.get(
            f"{BASE_URL}/leads",
            params={"api_key": SMARTLEAD_API_KEY, "email": email}
        )
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, dict) and data.get("id"):
                return str(data["id"])
    except Exception as e:
        logger.warning(f"Error fetching Smartlead ID for {email}: {e}")
    return None


async def main():
    if not SMARTLEAD_API_KEY:
        logger.error("SMARTLEAD_API_KEY not set")
        return
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Find contacts with Smartlead campaign data but no smartlead_id
    # Use position() instead of LIKE with %
    rows = await conn.fetch("""
        SELECT id, email 
        FROM contacts 
        WHERE smartlead_id IS NULL 
          AND campaigns IS NOT NULL
          AND position('"source": "smartlead"' in campaigns::text) > 0
          AND email IS NOT NULL
          AND email != ''
        LIMIT 2000
    """)
    
    logger.info(f"Found {len(rows)} contacts to fix")
    
    fixed = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, row in enumerate(rows):
            email = row["email"]
            contact_id = row["id"]
            
            smartlead_id = await get_smartlead_id_by_email(client, email)
            
            if smartlead_id:
                await conn.execute(
                    "UPDATE contacts SET smartlead_id = $1, updated_at = NOW() WHERE id = $2",
                    smartlead_id, contact_id
                )
                fixed += 1
                if fixed % 50 == 0:
                    logger.info(f"Fixed {fixed}/{len(rows)} contacts")
            
            # Rate limiting
            if (i + 1) % 10 == 0:
                await asyncio.sleep(0.5)
    
    await conn.close()
    logger.info(f"Done! Fixed {fixed} contacts with smartlead_id")


if __name__ == "__main__":
    asyncio.run(main())
