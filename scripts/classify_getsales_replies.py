#!/usr/bin/env python3
import asyncio
import asyncpg
import httpx
import os

OPENAI_API_KEY = "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"

CATEGORIES = ["interested", "meeting_request", "not_interested", "out_of_office", "wrong_person", "question", "other"]

SYSTEM_PROMPT = """Classify B2B outreach replies into: interested, meeting_request, not_interested, out_of_office, wrong_person, question, other.
Reply with ONLY the category name."""

async def classify_one(client, body):
    try:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": body[:500]}
                ],
                "max_tokens": 20,
                "temperature": 0
            },
            timeout=30.0
        )
        data = response.json()
        category = data["choices"][0]["message"]["content"].strip().lower()
        return category if category in CATEGORIES else "other"
    except Exception as e:
        print(f"Error: {e}")
        return "other"

async def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
    db_url = db_url.replace("postgresql://", "postgres://").replace("+asyncpg", "")
    
    conn = await asyncpg.connect(db_url)
    
    rows = await conn.fetch(
        "SELECT id, body FROM contact_activities "
        "WHERE source = 'getsales' AND activity_type = 'linkedin_replied' "
        "AND body IS NOT NULL AND body != '' "
        "AND (extra_data->>'category' IS NULL OR extra_data->>'category' = '') "
        "LIMIT 1100"
    )
    
    print(f"Found {len(rows)} unclear replies to classify")
    
    if len(rows) == 0:
        await conn.close()
        return
    
    total = 0
    async with httpx.AsyncClient() as client:
        for row in rows:
            category = await classify_one(client, row["body"])
            # Use raw SQL with explicit cast
            await conn.execute(
                f"UPDATE contact_activities SET extra_data = (COALESCE(extra_data, '{{}}')::jsonb || jsonb_build_object('category', '{category}'))::json WHERE id = {row['id']}"
            )
            total += 1
            if total % 50 == 0:
                print(f"Classified {total}/{len(rows)}...")
            await asyncio.sleep(0.1)
    
    results = await conn.fetch(
        "SELECT extra_data->>'category' as category, COUNT(*) as count "
        "FROM contact_activities "
        "WHERE source = 'getsales' AND activity_type = 'linkedin_replied' "
        "GROUP BY extra_data->>'category' ORDER BY count DESC"
    )
    
    print("\nFinal results:")
    for r in results:
        print(f"  {r['category'] or 'NULL'}: {r['count']}")
    
    await conn.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
