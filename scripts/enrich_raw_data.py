#!/usr/bin/env python3
"""
Raw Data Enrichment Script
Fetches complete data from Smartlead/GetSales APIs and stores in raw columns.
Run: docker exec -d leadgen-backend python3 /app/scripts/enrich_raw_data.py
"""
import asyncio
import asyncpg
import httpx
import os
import json
from datetime import datetime

SMARTLEAD_API_KEY = os.getenv('SMARTLEAD_API_KEY', 'eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5')
GETSALES_API_KEY = os.getenv('GETSALES_API_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZWFtX2lkIjo4MjgsInVzZXJfaWQiOjEwNTgsInNjb3BlcyI6WyJhZG1pbiJdLCJpYXQiOjE3MzY1MDExNzR9.R_skxWr52Bl8tcNR5hSLey84_BMntjiLLjoH31FxV-M')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7819187032:AAEgLFfbKblxXpNq7CZwAQK-SG67cEF9Q8E')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '312546298')

async def send_telegram(message):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                json={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
            )
    except:
        pass

async def fetch_smartlead_data(client, lead_id):
    """Fetch complete Smartlead data for a lead."""
    try:
        # Step 1: Get campaigns for this lead
        campaigns_resp = await client.get(
            f'https://server.smartlead.ai/api/v1/leads/{lead_id}/campaigns?api_key={SMARTLEAD_API_KEY}',
            timeout=30
        )
        campaigns = campaigns_resp.json() if campaigns_resp.status_code == 200 else []
        
        # Step 2: Get message history for each campaign (limit to first 3)
        conversations = {}
        for campaign in campaigns[:3]:
            cid = campaign.get('id') or campaign.get('campaign_id')
            if cid:
                try:
                    history_resp = await client.get(
                        f'https://server.smartlead.ai/api/v1/campaigns/{cid}/leads/{lead_id}/message-history?api_key={SMARTLEAD_API_KEY}',
                        timeout=30
                    )
                    if history_resp.status_code == 200:
                        conversations[str(cid)] = history_resp.json()
                except:
                    pass
                await asyncio.sleep(0.2)  # Rate limit
        
        return {
            'fetched_at': datetime.utcnow().isoformat(),
            'campaigns': campaigns,
            'conversations': conversations
        }
    except Exception as e:
        return {'error': str(e), 'fetched_at': datetime.utcnow().isoformat()}

async def fetch_getsales_data(client, lead_uuid):
    """Fetch complete GetSales data for a contact."""
    headers = {'Authorization': f'Bearer {GETSALES_API_KEY}'}
    try:
        # Step 1: Get full profile
        profile_resp = await client.get(
            f'https://amazing.getsales.io/leads/api/leads/{lead_uuid}',
            headers=headers, timeout=30
        )
        profile = profile_resp.json() if profile_resp.status_code == 200 else {}
        
        # Step 2: Get LinkedIn messages for this contact
        messages = []
        try:
            msgs_resp = await client.get(
                f'https://amazing.getsales.io/flows/api/linkedin-messages?filter[lead_uuid]={lead_uuid}&sort[created_at]=desc&limit=50',
                headers=headers, timeout=30
            )
            if msgs_resp.status_code == 200:
                messages = msgs_resp.json().get('data', [])
        except:
            pass
        
        return {
            'fetched_at': datetime.utcnow().isoformat(),
            'profile': profile,
            'messages': messages[:20]  # Keep last 20 messages
        }
    except Exception as e:
        return {'error': str(e), 'fetched_at': datetime.utcnow().isoformat()}

async def main():
    db_url = os.getenv('DATABASE_URL', 'postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen')
    db_url = db_url.replace('postgresql://', 'postgres://').replace('+asyncpg', '')
    
    conn = await asyncpg.connect(db_url)
    
    # Get counts
    counts = await conn.fetchrow('''
        SELECT 
            COUNT(*) FILTER (WHERE smartlead_id IS NOT NULL AND smartlead_raw::text = '{}') as sl_pending,
            COUNT(*) FILTER (WHERE getsales_id IS NOT NULL AND getsales_raw::text = '{}') as gs_pending
        FROM contacts
    ''')
    
    sl_total = counts['sl_pending']
    gs_total = counts['gs_pending']
    
    await send_telegram(f'Starting raw data enrichment:\n- Smartlead: {sl_total:,} contacts\n- GetSales: {gs_total:,} contacts')
    
    async with httpx.AsyncClient() as client:
        # Process Smartlead contacts
        sl_done = 0
        while True:
            rows = await conn.fetch('''
                SELECT id, smartlead_id FROM contacts
                WHERE smartlead_id IS NOT NULL AND smartlead_raw::text = '{}'
                LIMIT 50
            ''')
            if not rows:
                break
            
            for row in rows:
                data = await fetch_smartlead_data(client, row['smartlead_id'])
                await conn.execute(
                    'UPDATE contacts SET smartlead_raw = $1 WHERE id = $2',
                    json.dumps(data), row['id']
                )
                sl_done += 1
                await asyncio.sleep(0.3)  # Rate limit: ~3 req/sec
            
            if sl_done % 500 == 0:
                await send_telegram(f'Smartlead progress: {sl_done:,} / {sl_total:,} ({sl_done*100//sl_total}%)')
        
        # Process GetSales contacts
        gs_done = 0
        while True:
            rows = await conn.fetch('''
                SELECT id, getsales_id FROM contacts
                WHERE getsales_id IS NOT NULL AND getsales_raw::text = '{}'
                LIMIT 50
            ''')
            if not rows:
                break
            
            for row in rows:
                data = await fetch_getsales_data(client, row['getsales_id'])
                await conn.execute(
                    'UPDATE contacts SET getsales_raw = $1 WHERE id = $2',
                    json.dumps(data), row['id']
                )
                gs_done += 1
                await asyncio.sleep(0.2)
            
            if gs_done % 500 == 0:
                await send_telegram(f'GetSales progress: {gs_done:,} / {gs_total:,} ({gs_done*100//gs_total}%)')
    
    await conn.close()
    await send_telegram(f'Raw data enrichment complete!\n- Smartlead: {sl_done:,}\n- GetSales: {gs_done:,}')

if __name__ == '__main__':
    asyncio.run(main())
