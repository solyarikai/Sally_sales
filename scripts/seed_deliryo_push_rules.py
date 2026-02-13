"""
Seed the 3 Deliryo push rules pointing to existing SmartLead campaigns.

Campaigns (already created in SmartLead):
  1. "Deliryo 11.02 Из РФ БЕЗ ИМЕНИ" — generic/no-name, Russian sequences, no {{first_name}}
  2. "Deliryo 11.02 Из РФ Англ имена" — English names, English sequences, with {{first_name}}
  3. "Deliryo 11.02 Из РФ" — Russian names, Russian sequences, with {{first_name}}

Usage:
  python scripts/seed_deliryo_push_rules.py

Env vars needed: DATABASE_URL, SMARTLEAD_API_KEY
"""
import asyncio
import os
import sys
import httpx

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text


# --- Config ---
# Set these to your actual values, or pull from env/DB
DELIRYO_PROJECT_ID = int(os.environ.get("DELIRYO_PROJECT_ID", "1"))
DELIRYO_COMPANY_ID = int(os.environ.get("DELIRYO_COMPANY_ID", "1"))

# Campaign name → SmartLead campaign ID mapping
# These will be auto-discovered from SmartLead API
CAMPAIGN_NAMES = {
    "noname": "Deliryo 11.02 Из РФ БЕЗ ИМЕНИ",
    "en_name": "Deliryo 11.02 Из РФ Англ имена",
    "ru_name": "Deliryo 11.02 Из РФ",
}


async def find_campaigns_by_name(api_key: str) -> dict[str, str]:
    """Find SmartLead campaign IDs by name."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://server.smartlead.ai/api/v1/campaigns",
            params={"api_key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        # Handle different response formats
        if isinstance(data, list):
            campaigns = data
        elif isinstance(data, dict):
            campaigns = data.get("campaigns", data.get("data", []))
        else:
            campaigns = []

    found = {}
    for camp in campaigns:
        name = camp.get("name", "")
        camp_id = str(camp.get("id", ""))
        for key, target_name in CAMPAIGN_NAMES.items():
            if target_name in name:
                found[key] = camp_id
                print(f"  Found: '{name}' → ID {camp_id} (rule: {key})")

    return found


async def main():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        from app.core.config import settings
        database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    api_key = os.environ.get("SMARTLEAD_API_KEY", "")
    if not api_key:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("Looking up campaigns in SmartLead...")
    campaign_ids = await find_campaigns_by_name(api_key)

    if len(campaign_ids) < 3:
        print(f"\nWARNING: Only found {len(campaign_ids)}/3 campaigns:")
        for key, name in CAMPAIGN_NAMES.items():
            status = f"ID={campaign_ids[key]}" if key in campaign_ids else "NOT FOUND"
            print(f"  {key}: '{name}' → {status}")
        print("\nProceeding with what we have...")

    # Define the 3 rules
    rules = [
        {
            "key": "noname",
            "name": "Deliryo БЕЗ ИМЕНИ — generic emails",
            "description": "Contacts with generic emails (info@, contact@) or no first name. Russian sequences without {{first_name}}.",
            "language": "any",
            "has_first_name": False,
            "use_first_name_var": False,
            "sequence_language": "ru",
            "priority": 10,  # Highest — catch generics first
        },
        {
            "key": "en_name",
            "name": "Deliryo Англ имена — English names",
            "description": "Contacts with English/Latin first names. English sequences with {{first_name}}.",
            "language": "en",
            "has_first_name": True,
            "use_first_name_var": True,
            "sequence_language": "en",
            "priority": 5,
        },
        {
            "key": "ru_name",
            "name": "Deliryo Из РФ — Russian names",
            "description": "Contacts with Russian/Cyrillic first names. Russian sequences with {{first_name}}.",
            "language": "ru",
            "has_first_name": True,
            "use_first_name_var": True,
            "sequence_language": "ru",
            "priority": 1,  # Lowest — fallback for Russian names
        },
    ]

    async with async_session() as session:
        # Deactivate any existing rules for this project
        await session.execute(text("""
            UPDATE campaign_push_rules SET is_active = false
            WHERE project_id = :pid AND company_id = :cid
        """), {"pid": DELIRYO_PROJECT_ID, "cid": DELIRYO_COMPANY_ID})

        for rule_def in rules:
            campaign_id = campaign_ids.get(rule_def["key"])
            if not campaign_id:
                print(f"  SKIP rule '{rule_def['name']}' — no campaign found")
                continue

            # Insert or update
            await session.execute(text("""
                INSERT INTO campaign_push_rules (
                    company_id, project_id, name, description,
                    language, has_first_name, use_first_name_var,
                    sequence_language, campaign_name_template,
                    current_campaign_id, current_campaign_lead_count,
                    max_leads_per_campaign, priority, is_active,
                    created_at, updated_at
                ) VALUES (
                    :cid, :pid, :name, :desc,
                    :lang, :has_name, :use_fname,
                    :seq_lang, :camp_name,
                    :camp_id, 0,
                    5000, :priority, true,
                    NOW(), NOW()
                )
                ON CONFLICT DO NOTHING
            """), {
                "cid": DELIRYO_COMPANY_ID,
                "pid": DELIRYO_PROJECT_ID,
                "name": rule_def["name"],
                "desc": rule_def["description"],
                "lang": rule_def["language"],
                "has_name": rule_def["has_first_name"],
                "use_fname": rule_def["use_first_name_var"],
                "seq_lang": rule_def["sequence_language"],
                "camp_name": CAMPAIGN_NAMES[rule_def["key"]],
                "camp_id": campaign_id,
                "priority": rule_def["priority"],
            })
            print(f"  Created rule: '{rule_def['name']}' → campaign {campaign_id}")

        await session.commit()

    # Verify
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT name, language, has_first_name, current_campaign_id, priority, is_active
            FROM campaign_push_rules
            WHERE project_id = :pid AND company_id = :cid AND is_active = true
            ORDER BY priority DESC
        """), {"pid": DELIRYO_PROJECT_ID, "cid": DELIRYO_COMPANY_ID})
        rows = result.fetchall()
        print(f"\nActive push rules ({len(rows)}):")
        for row in rows:
            print(f"  [{row[4]}] '{row[0]}' lang={row[1]} has_name={row[2]} campaign={row[3]}")

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
