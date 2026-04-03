#!/usr/bin/env python3
"""
CRM Stats - Comprehensive outbound funnel metrics.
Run: docker exec leadgen-backend python3 /app/scripts/check_stats.py
"""
import asyncio
import asyncpg
import os

async def get_stats():
    db_url = os.getenv('DATABASE_URL', 'postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen')
    db_url = db_url.replace('postgresql://', 'postgres://').replace('+asyncpg', '')
    
    conn = await asyncpg.connect(db_url)
    
    # Basic counts
    stats = await conn.fetchrow('''
        SELECT 
            (SELECT COUNT(*) FROM contacts) as total_contacts,
            (SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL) as smartlead_contacts,
            (SELECT COUNT(*) FROM contacts WHERE getsales_id IS NOT NULL) as getsales_contacts,
            (SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL AND getsales_id IS NOT NULL) as merged,
            (SELECT COUNT(*) FROM contacts WHERE has_replied = true) as replied_contacts,
            (SELECT COUNT(*) FROM processed_replies) as smartlead_replies,
            (SELECT COUNT(*) FROM contact_activities WHERE source = 'getsales' AND activity_type = 'linkedin_replied') as getsales_replies
    ''')
    
    # Campaign counts from contacts.campaigns JSON column
    campaign_stats = await conn.fetchrow('''
        WITH campaign_data AS (
            SELECT jsonb_array_elements(campaigns::jsonb) as campaign
            FROM contacts
            WHERE campaigns IS NOT NULL 
              AND campaigns::text != '[]'
              AND campaigns::text LIKE '[%'
        )
        SELECT 
            COUNT(DISTINCT campaign->>'id') as total_campaigns,
            COUNT(DISTINCT campaign->>'id') FILTER (WHERE campaign->>'source' = 'smartlead') as smartlead_campaigns,
            COUNT(DISTINCT campaign->>'id') FILTER (WHERE campaign->>'source' = 'getsales') as getsales_campaigns,
            COUNT(*) as contact_campaign_links
        FROM campaign_data
    ''')
    
    # Campaign status breakdown from contacts.campaigns
    campaign_statuses = await conn.fetch('''
        WITH campaign_data AS (
            SELECT jsonb_array_elements(campaigns::jsonb) as campaign
            FROM contacts
            WHERE campaigns IS NOT NULL 
              AND campaigns::text != '[]'
              AND campaigns::text LIKE '[%'
        )
        SELECT 
            campaign->>'source' as source,
            campaign->>'status' as status,
            COUNT(DISTINCT campaign->>'id') as count
        FROM campaign_data
        GROUP BY campaign->>'source', campaign->>'status'
        ORDER BY campaign->>'source', count DESC
    ''')
    
    # Status breakdown (new funnel)
    statuses = await conn.fetch('''
        SELECT status, COUNT(*) as count FROM contacts 
        GROUP BY status ORDER BY count DESC
    ''')
    
    # Reply sentiment breakdown
    sentiments = await conn.fetch('''
        SELECT reply_sentiment, COUNT(*) as count FROM contacts 
        WHERE reply_sentiment IS NOT NULL
        GROUP BY reply_sentiment ORDER BY count DESC
    ''')
    
    # Reply category breakdown (from activities)
    categories = await conn.fetch('''
        SELECT extra_data->>'category' as category, COUNT(*) as count
        FROM contact_activities 
        WHERE activity_type LIKE '%replied%' AND extra_data->>'category' IS NOT NULL
        GROUP BY extra_data->>'category' ORDER BY count DESC
    ''')
    
    # Touches distribution
    touches = await conn.fetch('''
        SELECT 
            CASE 
                WHEN jsonb_array_length(touches::jsonb) = 0 THEN '0'
                WHEN jsonb_array_length(touches::jsonb) = 1 THEN '1'
                WHEN jsonb_array_length(touches::jsonb) BETWEEN 2 AND 5 THEN '2-5'
                WHEN jsonb_array_length(touches::jsonb) BETWEEN 6 AND 10 THEN '6-10'
                ELSE '10+'
            END as touch_range,
            COUNT(*) as count
        FROM contacts
        WHERE touches IS NOT NULL AND touches::text != '[]'
        GROUP BY 1
        ORDER BY MIN(jsonb_array_length(touches::jsonb))
    ''')
    
    # Raw data enrichment progress
    raw_stats = await conn.fetchrow('''
        SELECT 
            COUNT(*) FILTER (WHERE smartlead_id IS NOT NULL) as sl_total,
            COUNT(*) FILTER (WHERE smartlead_id IS NOT NULL AND smartlead_raw::text != '{}') as sl_enriched,
            COUNT(*) FILTER (WHERE getsales_id IS NOT NULL) as gs_total,
            COUNT(*) FILTER (WHERE getsales_id IS NOT NULL AND getsales_raw::text != '{}') as gs_enriched
        FROM contacts
    ''')
    
    await conn.close()
    
    # Print report
    print()
    print('=' * 60)
    print('              OUTBOUND FUNNEL REPORT')
    print('=' * 60)
    print()
    
    print('CONTACTS')
    print('-' * 45)
    print(f'  Total Contacts:       {stats["total_contacts"]:>12,}')
    print(f'  Smartlead:            {stats["smartlead_contacts"]:>12,}')
    print(f'  GetSales:             {stats["getsales_contacts"]:>12,}')
    print(f'  Merged (both IDs):    {stats["merged"]:>12,}')
    print()
    
    print('CAMPAIGNS')
    print('-' * 45)
    print(f'  Total Campaigns:      {campaign_stats["total_campaigns"]:>12,}')
    print(f'  Smartlead:            {campaign_stats["smartlead_campaigns"]:>12,}')
    print(f'  GetSales:             {campaign_stats["getsales_campaigns"]:>12,}')
    print(f'  Contact-Campaign Links:{campaign_stats["contact_campaign_links"]:>11,}')
    print()
    
    if campaign_statuses:
        print('CAMPAIGN STATUS')
        print('-' * 45)
        current_source = None
        for row in campaign_statuses:
            source = row['source'] or 'unknown'
            if source != current_source:
                current_source = source
                print(f'  {source.upper()}:')
            status = row['status'] or 'unknown'
            print(f'    {status:20} {row["count"]:>10,}')
        print()
    
    print('STATUS (Funnel Stage)')
    print('-' * 45)
    for row in statuses:
        status = row['status'] or 'unknown'
        emoji = {
            'touched': '📤', 'warm': '🟢', 'not_interested': '🔴',
            'out_of_office': '🏖️', 'wrong_person': '❌', 
            'scheduled': '📅', 'qualified': '✅', 'not_qualified': '❎',
            'replied': '💬', 'lead': '👤'
        }.get(status, '⚪')
        print(f'  {emoji} {status:20} {row["count"]:>12,}')
    print()
    
    print('REPLY SENTIMENT')
    print('-' * 45)
    for row in sentiments:
        sentiment = row['reply_sentiment'] or 'unknown'
        emoji = {'warm': '🟢', 'neutral': '🟡', 'cold': '🔴'}.get(sentiment, '⚪')
        print(f'  {emoji} {sentiment:20} {row["count"]:>12,}')
    print()
    
    print('REPLY CATEGORIES (All Sources)')
    print('-' * 45)
    for row in categories:
        cat = row['category'] or 'unknown'
        print(f'  {cat:25} {row["count"]:>12,}')
    print()
    
    print('TOUCHES (Activities per Contact)')
    print('-' * 45)
    for row in touches:
        print(f'  {row["touch_range"]:20} {row["count"]:>12,}')
    print()
    
    print('REPLIES (from webhooks/API)')
    print('-' * 45)
    print(f'  Smartlead Replies:    {stats["smartlead_replies"]:>12,}')
    print(f'  GetSales Replies:     {stats["getsales_replies"]:>12,}')
    print()
    
    # Raw data enrichment
    sl_pct = (raw_stats['sl_enriched'] / raw_stats['sl_total'] * 100) if raw_stats['sl_total'] > 0 else 0
    gs_pct = (raw_stats['gs_enriched'] / raw_stats['gs_total'] * 100) if raw_stats['gs_total'] > 0 else 0
    print('RAW DATA ENRICHMENT')
    print('-' * 45)
    print(f'  Smartlead:  {raw_stats["sl_enriched"]:>6,} / {raw_stats["sl_total"]:>6,} ({sl_pct:>5.1f}%)')
    print(f'  GetSales:   {raw_stats["gs_enriched"]:>6,} / {raw_stats["gs_total"]:>6,} ({gs_pct:>5.1f}%)')
    print()
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(get_stats())
