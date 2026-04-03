#!/usr/bin/env python3
"""
FAST GetSales Flow Enrichment - queries by lead_uuid directly!
Uses connection pool for concurrent DB operations.
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
        logging.FileHandler("/tmp/enrich_getsales_flows.log")
    ]
)
logger = logging.getLogger(__name__)

GETSALES_API_KEY = os.environ.get("GETSALES_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8543996153:AAHnqBM52tK2zUUMUEM4fLUA4tozufXoOss")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "57344339")
CONCURRENT_REQUESTS = 5
PROGRESS_INTERVAL = 10


async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            )
    except Exception as e:
        logger.warning(f"Telegram failed: {e}")


async def fetch_flows_map(client: httpx.AsyncClient, api_key: str) -> Dict[str, str]:
    flows_map = {}
    response = await client.get(
        "https://amazing.getsales.io/flows/api/flows",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"per_page": 200}
    )
    if response.status_code == 200:
        for flow in response.json().get("data", []):
            flows_map[flow["uuid"]] = flow["name"]
        logger.info(f"Loaded {len(flows_map)} flows")
    return flows_map


async def fetch_lead_flows(client: httpx.AsyncClient, api_key: str, lead_uuid: str) -> List[dict]:
    try:
        response = await client.get(
            "https://amazing.getsales.io/flows/api/flows-leads",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"filter[lead_uuid]": lead_uuid, "per_page": 100}
        )
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        logger.warning(f"Error fetching flows for {lead_uuid}: {e}")
    return []


async def process_contact(
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    api_key: str,
    contact_id: int,
    lead_uuid: str,
    flows_map: Dict[str, str]
) -> tuple:
    flow_records = await fetch_lead_flows(client, api_key, lead_uuid)
    
    if not flow_records:
        return (0, 0)
    
    campaigns_data = []
    for record in flow_records:
        flow_uuid = record.get("flow_uuid")
        flow_name = flows_map.get(flow_uuid, f"Unknown ({flow_uuid[:8]}...)" if flow_uuid else "Unknown")
        campaigns_data.append({
            "name": flow_name,
            "id": flow_uuid,
            "source": "getsales",
            "status": record.get("status", "unknown"),
            "enriched_at": datetime.utcnow().isoformat()
        })
    
    # Use pool connection for each update
    async with pool.acquire() as conn:
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
        new_entries = [c for c in campaigns_data if c.get("id") not in existing_ids]
        
        if not new_entries:
            return (len(flow_records), 0)
        
        updated_campaigns = current + new_entries
        await conn.execute(
            "UPDATE contacts SET campaigns = $1::jsonb, updated_at = NOW() WHERE id = $2",
            json.dumps(updated_campaigns), contact_id
        )
        return (len(flow_records), len(new_entries))


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
        await send_telegram("❌ <b>GetSales Enrichment Failed</b>\nAPI key not found")
        sys.exit(1)
    
    await send_telegram("🚀 <b>FAST GetSales Enrichment</b>\nUsing filter[lead_uuid] - much faster!")
    logger.info("Starting FAST enrichment...")
    
    # Create connection pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        flows_map = await fetch_flows_map(client, GETSALES_API_KEY)
        
        if not flows_map:
            await send_telegram("❌ No flows found")
            await pool.close()
            sys.exit(1)
        
        # Get contacts
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, getsales_id FROM contacts WHERE getsales_id IS NOT NULL AND getsales_id != ''"
            )
            contacts = [(row["id"], row["getsales_id"]) for row in rows]
        
        total_contacts = len(contacts)
        logger.info(f"Found {total_contacts} contacts")
        
        if not contacts:
            await send_telegram("⚠️ No contacts to enrich")
            await pool.close()
            return
        
        eta_min = total_contacts // CONCURRENT_REQUESTS // 60 + 1
        await send_telegram(
            f"📊 <b>Processing {total_contacts} contacts</b>\n"
            f"Flows: {len(flows_map)}\n"
            f"Parallel: {CONCURRENT_REQUESTS}\n"
            f"ETA: ~{eta_min} min"
        )
        
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        processed = 0
        total_flows = 0
        total_updated = 0
        last_pct = 0
        
        async def process_with_sem(cid, lid):
            async with semaphore:
                return await process_contact(client, pool, GETSALES_API_KEY, cid, lid, flows_map)
        
        # Process in batches
        batch_size = max(total_contacts // 20, 100)
        
        for i in range(0, total_contacts, batch_size):
            batch = contacts[i:i + batch_size]
            tasks = [process_with_sem(cid, lid) for cid, lid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, tuple):
                    total_flows += r[0]
                    total_updated += r[1]
            
            processed += len(batch)
            pct = int((processed / total_contacts) * 100)
            
            if pct >= last_pct + PROGRESS_INTERVAL:
                last_pct = (pct // PROGRESS_INTERVAL) * PROGRESS_INTERVAL
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                eta = int((elapsed / processed) * (total_contacts - processed)) if processed else 0
                
                await send_telegram(
                    f"📈 <b>{last_pct}% complete</b>\n"
                    f"Contacts: {processed}/{total_contacts}\n"
                    f"Flows: {total_flows} | Updated: {total_updated}\n"
                    f"ETA: ~{eta // 60} min"
                )
            
            logger.info(f"{pct}%: {processed}/{total_contacts}, flows={total_flows}, updated={total_updated}")
        
        elapsed = int((datetime.utcnow() - start_time).total_seconds())
        
        await send_telegram(
            f"✅ <b>FAST Enrichment Complete!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Contacts: <b>{total_contacts}</b>\n"
            f"🔗 Flows found: <b>{total_flows}</b>\n"
            f"✏️ New entries: <b>{total_updated}</b>\n"
            f"⏱ Time: <b>{elapsed} sec</b>"
        )
        
        logger.info(f"Done: {total_contacts} contacts, {total_flows} flows, {total_updated} updated in {elapsed}s")
    
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
