#!/usr/bin/env python3
"""
CRM Stats Script - Quick overview of all key metrics.
Run: docker exec leadgen-backend python3 /app/scripts/check_stats.py
"""
import asyncio
import asyncpg
import os

async def get_stats():
    # Connect to database
    db_url = os.getenv('DATABASE_URL', 'postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen')
    # Convert to asyncpg format
    db_url = db_url.replace('postgresql://', 'postgres://').replace('+asyncpg', '')
    
    conn = await asyncpg.connect(db_url)
    
    # Get all stats in one query
    stats = await conn.fetchrow('''
        SELECT 
            (SELECT COUNT(*) FROM contacts) as total_contacts,
            (SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL) as smartlead_contacts,
            (SELECT COUNT(*) FROM contacts WHERE getsales_id IS NOT NULL) as getsales_contacts,
            (SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL AND getsales_id IS NOT NULL) as merged,
            (SELECT COUNT(*) FROM contacts WHERE has_replied = true) as replied_contacts,
            (SELECT COUNT(*) FROM processed_replies) as smartlead_replies,
            (SELECT COUNT(*) FROM contact_activities WHERE source = 'getsales' AND activity_type LIKE '%replied%') as getsales_replies,
            (SELECT COUNT(*) FROM contact_activities) as total_activities,
            (SELECT COUNT(*) FROM contact_activities WHERE source = 'smartlead') as smartlead_activities,
            (SELECT COUNT(*) FROM contact_activities WHERE source = 'getsales') as getsales_activities
    ''')
    
    await conn.close()
    
    # Print formatted report
    print()
    print('=' * 50)
    print('           CRM STATS REPORT')
    print('=' * 50)
    print()
    print('CONTACTS')
    print('-' * 30)
    print(f'  Total Contacts:      {stats["total_contacts"]:,}')
    print(f'  Smartlead Contacts:  {stats["smartlead_contacts"]:,}')
    print(f'  GetSales Contacts:   {stats["getsales_contacts"]:,}')
    print(f'  Merged (both IDs):   {stats["merged"]:,}')
    print()
    print('REPLIES')
    print('-' * 30)
    print(f'  Replied Contacts:    {stats["replied_contacts"]:,}')
    print(f'  Smartlead Replies:   {stats["smartlead_replies"]:,}')
    print(f'  GetSales Replies:    {stats["getsales_replies"]:,}')
    print()
    print('ACTIVITIES')
    print('-' * 30)
    print(f'  Total Activities:    {stats["total_activities"]:,}')
    print(f'  Smartlead:           {stats["smartlead_activities"]:,}')
    print(f'  GetSales:            {stats["getsales_activities"]:,}')
    print()
    print('=' * 50)
    print()

if __name__ == '__main__':
    asyncio.run(get_stats())
