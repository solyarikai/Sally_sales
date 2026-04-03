"""
Seed OnSocial (project 42) push rules pointing to existing SmartLead campaigns.

Campaigns (already in SmartLead):
  1. "c-OnSocial_IM agencies & SaaS_US&EU" (2947684) — named contacts with first_name
  2. "c-OnSocial БЕЗ ИМЕНИ" (2953769) — generic/no-name contacts

Usage (Hetzner):
  docker exec leadgen-backend python3 /scripts/seed_onsocial_push_rules.py

Env vars needed: DATABASE_URL, SMARTLEAD_API_KEY
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app")
os.chdir("/app")


ONSOCIAL_PROJECT_ID = 42
ONSOCIAL_COMPANY_ID = 1

# Campaign IDs (already exist in SmartLead)
CAMPAIGNS = {
    "named": {"id": "2947684", "name": "c-OnSocial_IM agencies & SaaS_US&EU"},
    "noname": {"id": "2953769", "name": "c-OnSocial БЕЗ ИМЕНИ"},
}


async def main():
    from app.db import async_session_maker
    from sqlalchemy import text

    async with async_session_maker() as session:
        # Deactivate existing rules for this project
        await session.execute(text("""
            UPDATE campaign_push_rules SET is_active = false
            WHERE project_id = :pid AND company_id = :cid
        """), {"pid": ONSOCIAL_PROJECT_ID, "cid": ONSOCIAL_COMPANY_ID})

        rules = [
            {
                "key": "noname",
                "name": "OnSocial БЕЗ ИМЕНИ — generic emails",
                "description": "Contacts with no first_name or generic emails. English sequences without {{first_name}}.",
                "language": "any",
                "has_first_name": False,
                "use_first_name_var": False,
                "sequence_language": "en",
                "priority": 10,  # Highest — catch generics first
            },
            {
                "key": "named",
                "name": "OnSocial Named — contacts with name",
                "description": "Contacts with first name. English sequences with {{first_name}}.",
                "language": "any",
                "has_first_name": True,
                "use_first_name_var": True,
                "sequence_language": "en",
                "priority": 1,  # Lower — fallback for all named
            },
        ]

        for rule_def in rules:
            camp = CAMPAIGNS[rule_def["key"]]
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
                "cid": ONSOCIAL_COMPANY_ID,
                "pid": ONSOCIAL_PROJECT_ID,
                "name": rule_def["name"],
                "desc": rule_def["description"],
                "lang": rule_def["language"],
                "has_name": rule_def["has_first_name"],
                "use_fname": rule_def["use_first_name_var"],
                "seq_lang": rule_def["sequence_language"],
                "camp_name": camp["name"],
                "camp_id": camp["id"],
                "priority": rule_def["priority"],
            })
            print(f"  Created rule: '{rule_def['name']}' → campaign {camp['id']}")

        await session.commit()

    # Verify
    async with async_session_maker() as session:
        result = await session.execute(text("""
            SELECT name, language, has_first_name, current_campaign_id, priority, is_active
            FROM campaign_push_rules
            WHERE project_id = :pid AND company_id = :cid AND is_active = true
            ORDER BY priority DESC
        """), {"pid": ONSOCIAL_PROJECT_ID, "cid": ONSOCIAL_COMPANY_ID})
        rows = result.fetchall()
        print(f"\nActive push rules ({len(rows)}):")
        for row in rows:
            print(f"  [{row[4]}] '{row[0]}' lang={row[1]} has_name={row[2]} campaign={row[3]}")

    print("\nDone! Use POST /pipeline/projects/42/push-to-smartlead to trigger push.")


if __name__ == "__main__":
    asyncio.run(main())
