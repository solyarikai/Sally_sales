"""
Backfill CRM contacts for Deliryo project (project_id=18).

This one-time script:
1. For extracted_contacts from target companies: update existing CRM contacts
   with project_id, segment, company_name, job_title (fill NULLs).
2. Insert new CRM contacts for extracted emails not yet in the contacts table.
3. For contacts linked to Deliryo SmartLead campaigns: set project_id=18.
4. Clean up junk emails from contacts table.

Usage: docker exec leadgen-backend python scripts/backfill_crm_contacts.py
"""
import asyncio
import json
import logging
import os
import re
import sys
import time

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
PG_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

PROJECT_ID = 18
COMPANY_ID = 1  # Deliryo company

# Deliryo SmartLead campaign name patterns
DELIRYO_CAMPAIGN_PATTERNS = [
    "Deliryo%Из РФ%",
    "Deliryo%БЕЗ ИМЕНИ%",
    "Deliryo%Англ имена%",
]

# Junk email patterns
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
PLACEHOLDER_LOCALS = {
    "email", "name", "your", "user", "test", "corpora", "secretary",
    "example", "sample", "demo", "mail", "admin", "root", "null",
    "undefined", "nobody", "noreply", "no-reply", "vash", "vashe",
    "pochta", "svyaz", "primer", "kontakt", "zapros",
}


def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    email = email.strip().lower()
    if len(email) < 6 or "@" not in email:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return False
    if _CYRILLIC_RE.search(email):
        return False
    if "%" in email or " " in email:
        return False
    if len(local) < 2:
        return False
    if local in PLACEHOLDER_LOCALS:
        return False
    return True


async def main():
    t0 = time.time()
    pool = await asyncpg.create_pool(PG_DSN, min_size=2, max_size=5)

    stats = {
        "updated_from_extracted": 0,
        "inserted_from_extracted": 0,
        "skipped_invalid": 0,
        "updated_from_campaigns": 0,
        "junk_cleaned": 0,
    }

    # ================================================================
    # Step 1: Get all extracted contacts from Deliryo target companies
    # ================================================================
    logger.info("Step 1: Processing extracted contacts from target companies...")

    rows = await pool.fetch("""
        SELECT ec.id, ec.email, ec.first_name, ec.last_name, ec.job_title,
               dc.domain, dc.name as company_name,
               sr.matched_segment
        FROM extracted_contacts ec
        JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
        LEFT JOIN search_results sr ON dc.search_result_id = sr.id
        WHERE dc.project_id = $1 AND dc.company_id = $2
        AND dc.is_target = true
        AND ec.email IS NOT NULL AND ec.email != ''
        ORDER BY ec.id
    """, PROJECT_ID, COMPANY_ID)

    logger.info(f"  Found {len(rows)} extracted contacts from target companies")

    for row in rows:
        email = row["email"].strip()
        if not is_valid_email(email):
            stats["skipped_invalid"] += 1
            continue

        segment = row["matched_segment"]
        company_name = row["company_name"]
        job_title = row["job_title"]
        first_name = row["first_name"] or ""
        last_name = row["last_name"] or ""
        domain = email.split("@")[-1] if "@" in email else None

        # Check if contact already exists
        existing = await pool.fetchrow("""
            SELECT id, project_id, segment, company_name, job_title
            FROM contacts
            WHERE company_id = $1 AND lower(email) = lower($2)
            AND deleted_at IS NULL
            LIMIT 1
        """, COMPANY_ID, email)

        if existing:
            # Update if any fields are NULL
            needs_update = (
                existing["project_id"] is None
                or existing["segment"] is None
                or existing["company_name"] is None
                or existing["job_title"] is None
            )
            if needs_update:
                await pool.execute("""
                    UPDATE contacts SET
                        project_id = COALESCE(project_id, $1),
                        segment = COALESCE(segment, $2),
                        company_name = COALESCE(company_name, $3),
                        job_title = COALESCE(job_title, $4),
                        updated_at = NOW()
                    WHERE id = $5
                """, PROJECT_ID, segment, company_name, job_title, existing["id"])
                stats["updated_from_extracted"] += 1
        else:
            # Insert new contact
            await pool.execute("""
                INSERT INTO contacts (company_id, email, first_name, last_name, domain,
                                      company_name, job_title, project_id, segment,
                                      source, status, is_active,
                                      created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                        'pipeline', 'lead', true, NOW(), NOW())
            """, COMPANY_ID, email, first_name, last_name, domain,
                company_name or "", job_title or "", PROJECT_ID, segment)
            stats["inserted_from_extracted"] += 1

    logger.info(f"  Updated: {stats['updated_from_extracted']}, Inserted: {stats['inserted_from_extracted']}, "
                f"Skipped invalid: {stats['skipped_invalid']}")

    # ================================================================
    # Step 2: Link contacts in Deliryo SmartLead campaigns to project
    # ================================================================
    logger.info("Step 2: Linking contacts in Deliryo SmartLead campaigns to project...")

    # Find contacts whose campaigns JSON contains Deliryo campaign names
    campaign_contacts = await pool.fetch("""
        SELECT id, campaigns
        FROM contacts
        WHERE company_id = $1
        AND deleted_at IS NULL
        AND project_id IS NULL
        AND campaigns IS NOT NULL
        AND campaigns::text LIKE '%Deliryo%'
    """, COMPANY_ID)

    logger.info(f"  Found {len(campaign_contacts)} contacts with Deliryo campaign references")

    for row in campaign_contacts:
        campaigns = row["campaigns"]
        if isinstance(campaigns, str):
            try:
                campaigns = json.loads(campaigns)
            except Exception:
                continue

        if not isinstance(campaigns, list):
            continue

        # Check if any campaign matches Deliryo patterns
        is_deliryo = False
        for camp in campaigns:
            name = camp.get("name", "") if isinstance(camp, dict) else ""
            if "Deliryo" in name or "deliryo" in name.lower():
                is_deliryo = True
                break

        if is_deliryo:
            await pool.execute("""
                UPDATE contacts SET
                    project_id = $1,
                    updated_at = NOW()
                WHERE id = $2
            """, PROJECT_ID, row["id"])
            stats["updated_from_campaigns"] += 1

    logger.info(f"  Linked {stats['updated_from_campaigns']} contacts from Deliryo campaigns to project")

    # ================================================================
    # Step 3: Clean up junk emails from pipeline-pushed contacts
    # ================================================================
    logger.info("Step 3: Cleaning up junk emails...")

    junk_contacts = await pool.fetch("""
        SELECT id, email FROM contacts
        WHERE source IN ('smartlead_pipeline_push', 'pipeline')
        AND deleted_at IS NULL
    """)

    for row in junk_contacts:
        if not is_valid_email(row["email"]):
            await pool.execute("""
                UPDATE contacts SET deleted_at = NOW(), updated_at = NOW()
                WHERE id = $1
            """, row["id"])
            stats["junk_cleaned"] += 1

    logger.info(f"  Soft-deleted {stats['junk_cleaned']} junk email contacts")

    # ================================================================
    # Summary
    # ================================================================
    elapsed = time.time() - t0
    logger.info(f"\n{'='*60}")
    logger.info(f"Backfill completed in {elapsed:.1f}s")
    logger.info(f"  Updated from extracted contacts: {stats['updated_from_extracted']}")
    logger.info(f"  Inserted from extracted contacts: {stats['inserted_from_extracted']}")
    logger.info(f"  Skipped invalid emails:           {stats['skipped_invalid']}")
    logger.info(f"  Linked from Deliryo campaigns:    {stats['updated_from_campaigns']}")
    logger.info(f"  Junk emails cleaned:              {stats['junk_cleaned']}")
    logger.info(f"{'='*60}")

    # Verification
    total_project = await pool.fetchval("""
        SELECT COUNT(*) FROM contacts
        WHERE project_id = $1 AND deleted_at IS NULL
    """, PROJECT_ID)
    total_with_segment = await pool.fetchval("""
        SELECT COUNT(*) FROM contacts
        WHERE project_id = $1 AND segment IS NOT NULL AND deleted_at IS NULL
    """, PROJECT_ID)
    logger.info(f"Verification: Deliryo project contacts = {total_project}, with segment = {total_with_segment}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
