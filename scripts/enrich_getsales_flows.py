#!/usr/bin/env python3
"""
GetSales Flow Enrichment Script with Telegram notifications
"""
import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/enrich_getsales_flows.log")
    ]
)
logger = logging.getLogger(__name__)

# Configuration
GETSALES_API_KEY = os.environ.get("GETSALES_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8543996153:AAHnqBM52tK2zUUMUEM4fLUA4tozufXoOss")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "57344339")
BATCH_SIZE = 1000
MAX_PAGES = 600
PROGRESS_INTERVAL = 10


async def send_telegram(message: str):
    """Send message to Telegram using httpx."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            })
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)


async def fetch_flows_map(api_key: str) -> Dict[str, str]:
    flows_map = {}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            "https://amazing.getsales.io/flows/api/flows",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"per_page": 200}
        )
        if response.status_code == 200:
            data = response.json()
            for flow in data.get("data", []):
                flows_map[flow["uuid"]] = flow["name"]
            logger.info(f"Loaded {len(flows_map)} flows")
    return flows_map


async def fetch_flows_leads_batch(api_key: str, offset: int, limit: int):
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            "https://amazing.getsales.io/flows/api/flows-leads",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"per_page": limit, "offset": offset}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", []), data.get("total", 0), data.get("has_more", False)
        return [], 0, False


async def get_getsales_contacts(conn) -> Dict[str, int]:
    rows = await conn.fetch(
        "SELECT id, getsales_id FROM contacts WHERE getsales_id IS NOT NULL AND getsales_id != ''"
    )
    return {row["getsales_id"]: row["id"] for row in rows}


async def update_contact_campaigns(conn, contact_id: int, flow_name: str, flow_uuid: str, status: str):
    campaign_entry = {
        "name": flow_name,
        "id": flow_uuid,
        "source": "getsales",
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
    
    existing_ids = {c.get("id") for c in current if isinstance(c, dict)}
    if flow_uuid in existing_ids:
        return False
    
    new_campaigns = current + [campaign_entry]
    await conn.execute(
        "UPDATE contacts SET campaigns = $1::jsonb, updated_at = NOW() WHERE id = $2",
        json.dumps(new_campaigns), contact_id
    )
    return True


async def main():
    global GETSALES_API_KEY
    start_time = datetime.utcnow()
    
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
        await send_telegram("❌ <b>GetSales Enrichment Failed</b>\nGETSALES_API_KEY not found")
        sys.exit(1)
    
    await send_telegram("🚀 <b>GetSales Flow Enrichment Started</b>\nFetching flows and contacts...")
    logger.info("Starting GetSales flow enrichment...")
    
    flows_map = await fetch_flows_map(GETSALES_API_KEY)
    if not flows_map:
        await send_telegram("❌ <b>GetSales Enrichment Failed</b>\nNo flows found")
        sys.exit(1)
    
    conn = await get_db_connection()
    
    try:
        getsales_contacts = await get_getsales_contacts(conn)
        total_contacts = len(getsales_contacts)
        logger.info(f"Found {total_contacts} GetSales contacts")
        
        if not getsales_contacts:
            await send_telegram("⚠️ No GetSales contacts to enrich")
            return
        
        await send_telegram(f"📊 Found <b>{total_contacts}</b> contacts, <b>{len(flows_map)}</b> flows\nProcessing ~510K records...")
        
        offset = 0
        total_processed = 0
        total_matched = 0
        actually_updated = 0
        last_progress_pct = 0
        total_api_records = 510697
        
        for page in range(MAX_PAGES):
            records, total, has_more = await fetch_flows_leads_batch(GETSALES_API_KEY, offset, BATCH_SIZE)
            
            if not records:
                break
            
            for record in records:
                lead_uuid = record.get("lead_uuid")
                if lead_uuid and lead_uuid in getsales_contacts:
                    contact_id = getsales_contacts[lead_uuid]
                    flow_uuid = record.get("flow_uuid")
                    flow_name = flows_map.get(flow_uuid, f"Unknown ({flow_uuid[:8]}...)")
                    status = record.get("status", "unknown")
                    
                    updated = await update_contact_campaigns(conn, contact_id, flow_name, flow_uuid, status)
                    total_matched += 1
                    if updated:
                        actually_updated += 1
            
            total_processed += len(records)
            offset += BATCH_SIZE
            
            current_pct = int((total_processed / total_api_records) * 100)
            
            if current_pct >= last_progress_pct + PROGRESS_INTERVAL:
                last_progress_pct = (current_pct // PROGRESS_INTERVAL) * PROGRESS_INTERVAL
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                eta_seconds = (elapsed / total_processed) * (total_api_records - total_processed) if total_processed > 0 else 0
                eta_minutes = int(eta_seconds / 60)
                
                await send_telegram(
                    f"📈 <b>Progress: {last_progress_pct}%</b>\n"
                    f"Processed: {total_processed:,}/{total_api_records:,}\n"
                    f"Matches: {total_matched} | Updated: {actually_updated}\n"
                    f"ETA: ~{eta_minutes} min"
                )
            
            if page % 50 == 0:
                logger.info(f"Progress: {total_processed:,}/{total_api_records:,} ({current_pct}%), {total_matched} matches")
            
            if not has_more:
                break
            
            await asyncio.sleep(0.05)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        elapsed_min = int(elapsed / 60)
        
        await send_telegram(
            f"✅ <b>GetSales Enrichment Complete!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Processed: <b>{total_processed:,}</b>\n"
            f"🔗 Matches: <b>{total_matched}</b>\n"
            f"✏️ Updated: <b>{actually_updated}</b>\n"
            f"⏱ Duration: <b>{elapsed_min} min</b>"
        )
        
        logger.info(f"Done: {total_processed:,} processed, {total_matched} matches, {actually_updated} updated")
        
    except Exception as e:
        await send_telegram(f"❌ <b>GetSales Enrichment Error</b>\n{str(e)[:200]}")
        logger.error(f"Error: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
