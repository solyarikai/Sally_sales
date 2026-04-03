#!/usr/bin/env python3
"""
Raw Data Gathering Progress Tracker
Run: docker exec leadgen-backend python3 /app/scripts/check_raw_data_progress.py
"""
import asyncio
import asyncpg
import os
from datetime import datetime

async def check_progress():
    db_url = os.getenv('DATABASE_URL', 'postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen')
    db_url = db_url.replace('postgresql://', 'postgres://').replace('+asyncpg', '')
    
    conn = await asyncpg.connect(db_url)
    
    stats = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE smartlead_id IS NOT NULL) as has_smartlead,
            COUNT(*) FILTER (WHERE getsales_id IS NOT NULL) as has_getsales,
            COUNT(*) FILTER (WHERE smartlead_raw::text != '{}') as smartlead_raw_filled,
            COUNT(*) FILTER (WHERE getsales_raw::text != '{}') as getsales_raw_filled,
            COUNT(*) FILTER (WHERE touches::text != '[]' AND touches IS NOT NULL) as has_touches
        FROM contacts
    ''')
    
    activities = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total_activities,
            COUNT(*) FILTER (WHERE source = 'smartlead') as smartlead_activities,
            COUNT(*) FILTER (WHERE source = 'getsales') as getsales_activities
        FROM contact_activities
    ''')
    
    replies = await conn.fetchrow('''
        SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE raw_webhook_data IS NOT NULL) as with_raw
        FROM processed_replies
    ''')
    
    await conn.close()
    
    print()
    print('=' * 60)
    print('        RAW DATA GATHERING PROGRESS')
    print('=' * 60)
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()
    
    sl_pct = (stats['smartlead_raw_filled'] / stats['has_smartlead'] * 100) if stats['has_smartlead'] > 0 else 0
    gs_pct = (stats['getsales_raw_filled'] / stats['has_getsales'] * 100) if stats['has_getsales'] > 0 else 0
    
    print(f'  Smartlead: {stats["smartlead_raw_filled"]:>6,} / {stats["has_smartlead"]:>6,} ({sl_pct:>5.1f}%)')
    print(f'  GetSales:  {stats["getsales_raw_filled"]:>6,} / {stats["has_getsales"]:>6,} ({gs_pct:>5.1f}%)')
    print(f'  Touches:   {stats["has_touches"]:>6,} contacts')
    print()
    print(f'  Activities: {activities["total_activities"]:>6,} (SL: {activities["smartlead_activities"]}, GS: {activities["getsales_activities"]})')
    print(f'  Replies:    {replies["total"]:>6,} ({replies["with_raw"]} with raw data)')
    print()
    
    sl_bar = int(sl_pct / 5)
    gs_bar = int(gs_pct / 5)
    print(f'  SL [{"#" * sl_bar}{"_" * (20-sl_bar)}] {sl_pct:.1f}%')
    print(f'  GS [{"#" * gs_bar}{"_" * (20-gs_bar)}] {gs_pct:.1f}%')
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(check_progress())
