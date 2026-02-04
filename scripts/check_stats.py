#!/usr/bin/env python3
"""
CRM Stats Script - Comprehensive overview of all key metrics and funnel stages.
Run: docker exec leadgen-backend python3 /app/scripts/check_stats.py
"""
import asyncio
import asyncpg
import os

async def get_stats():
    # Connect to database
    db_url = os.getenv('DATABASE_URL', 'postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen')
    db_url = db_url.replace('postgresql://', 'postgres://').replace('+asyncpg', '')
    
    conn = await asyncpg.connect(db_url)
    
    # Get all stats
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
    
    # Get funnel stages
    funnel = await conn.fetch('''
        SELECT funnel_stage, COUNT(*) as count 
        FROM contacts 
        GROUP BY funnel_stage 
        ORDER BY CASE funnel_stage
            WHEN 'new' THEN 1
            WHEN 'contacted' THEN 2
            WHEN 'engaged' THEN 3
            WHEN 'replied' THEN 4
            WHEN 'scheduled' THEN 5
            WHEN 'qualified' THEN 6
            WHEN 'disqualified' THEN 7
            ELSE 8
        END
    ''')
    
    # Get reply sentiments
    sentiments = await conn.fetch('''
        SELECT reply_sentiment, COUNT(*) as count
        FROM contacts 
        WHERE reply_sentiment IS NOT NULL
        GROUP BY reply_sentiment
        ORDER BY CASE reply_sentiment
            WHEN 'warm' THEN 1
            WHEN 'neutral' THEN 2
            WHEN 'cold' THEN 3
        END
    ''')
    
    # Get reply categories
    categories = await conn.fetch('''
        SELECT reply_category, COUNT(*) as count
        FROM contacts 
        WHERE reply_category IS NOT NULL
        GROUP BY reply_category
        ORDER BY count DESC
        LIMIT 10
    ''')
    
    # Get campaign count distribution
    campaign_dist = await conn.fetch('''
        SELECT 
            CASE 
                WHEN campaign_count = 0 THEN '0'
                WHEN campaign_count = 1 THEN '1'
                WHEN campaign_count BETWEEN 2 AND 3 THEN '2-3'
                WHEN campaign_count BETWEEN 4 AND 6 THEN '4-6'
                WHEN campaign_count BETWEEN 7 AND 10 THEN '7-10'
                ELSE '10+'
            END as campaigns,
            COUNT(*) as count
        FROM contacts
        GROUP BY 1
        ORDER BY MIN(campaign_count)
    ''')
    
    await conn.close()
    
    # Print formatted report
    print()
    print('=' * 60)
    print('              CRM STATS REPORT')
    print('=' * 60)
    print()
    
    print('CONTACTS')
    print('-' * 40)
    print(f'  Total Contacts:      {stats["total_contacts"]:>10,}')
    print(f'  Smartlead Contacts:  {stats["smartlead_contacts"]:>10,}')
    print(f'  GetSales Contacts:   {stats["getsales_contacts"]:>10,}')
    print(f'  Merged (both IDs):   {stats["merged"]:>10,}')
    print()
    
    print('FUNNEL STAGES')
    print('-' * 40)
    for row in funnel:
        stage = row['funnel_stage'] or 'unknown'
        print(f'  {stage.capitalize():20} {row["count"]:>10,}')
    print()
    
    print('REPLY SENTIMENTS')
    print('-' * 40)
    for row in sentiments:
        sentiment = row['reply_sentiment'] or 'unknown'
        emoji = {'warm': '🟢', 'neutral': '🟡', 'cold': '🔴'}.get(sentiment, '⚪')
        print(f'  {emoji} {sentiment.capitalize():17} {row["count"]:>10,}')
    print()
    
    print('REPLY CATEGORIES (Top 10)')
    print('-' * 40)
    for row in categories:
        cat = row['reply_category'] or 'unknown'
        print(f'  {cat:25} {row["count"]:>10,}')
    print()
    
    print('CAMPAIGN ENROLLMENT')
    print('-' * 40)
    for row in campaign_dist:
        print(f'  {row["campaigns"]:20} {row["count"]:>10,}')
    print()
    
    print('ACTIVITIES')
    print('-' * 40)
    print(f'  Total Activities:    {stats["total_activities"]:>10,}')
    print(f'  Smartlead:           {stats["smartlead_activities"]:>10,}')
    print(f'  GetSales:            {stats["getsales_activities"]:>10,}')
    print()
    
    print('REPLIES (from webhooks)')
    print('-' * 40)
    print(f'  Smartlead Replies:   {stats["smartlead_replies"]:>10,}')
    print(f'  GetSales Replies:    {stats["getsales_replies"]:>10,}')
    print()
    print('=' * 60)
    print()

if __name__ == '__main__':
    asyncio.run(get_stats())
