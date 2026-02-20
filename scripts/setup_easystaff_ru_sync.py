"""
EasyStaff RU (Project 40) — Full data setup for sheet sync.

Steps:
1. Assign SmartLead contacts to project 40 (by campaign_filters match)
2. Assign GetSales contacts to project 40 (by sender profile UUIDs)
3. Import missing contacts from Google Sheet Leads tab
4. Run initial qualification poll from sheet
5. Enable sheet sync
"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ID = 40
SHEET_ID = "1gsHVo3bv9WGKgipQ5RTK71tya8xHPdk9r78S_EwAroM"

# EasyStaff RU GetSales sender profile UUIDs
EASYSTAFF_SENDER_PROFILES = [
    "b10a34f2-e7d0-490e-bc67-012b7ccd35b8",  # Алекс
    "4d1effeb-34fc-4999-bada-4a3651021adb",  # Катя
    "7f829fca-20b8-4f0d-a19e-ec1b3f76704e",  # Элеонора
    "07d392a8-13bb-4a30-a86f-9fe692b7055a",  # Андрей
    "5ecc3a67-75f4-413d-96e7-ca256e3113e0",  # Александр
    "774af09b-8158-4150-835d-6cf1ee00819a",  # Сергей
    "d67e1028-cf06-4ae8-bcc3-16e41710f19c",  # Александра
    "b3b69a39-6b46-4043-85b1-ef4ce22239d5",  # Александра (2)
    "cf73001d-f893-4396-b301-0691ffdccd12",  # (unnamed)
]


async def main():
    from sqlalchemy import select, func, and_, or_, text as sql_text, update
    from app.db import async_session_maker
    from app.models.contact import Contact, Project

    # ── Step 0: Load project ──
    async with async_session_maker() as session:
        project = await session.get(Project, PROJECT_ID)
        if not project:
            logger.error(f"Project {PROJECT_ID} not found!")
            return
        logger.info(f"Project: {project.name} (id={project.id})")
        logger.info(f"Campaign filters: {project.campaign_filters}")
        campaign_filters = project.campaign_filters or []

    # ── Step 1: Assign SmartLead contacts by campaign match ──
    logger.info("\n=== Step 1: Assign SmartLead contacts to project 40 ===")
    async with async_session_maker() as session:
        # Find contacts whose campaigns JSON contains any of the campaign filter names
        # and that don't already have project_id = 40
        total_assigned_sl = 0
        for camp_name in campaign_filters:
            result = await session.execute(
                sql_text("""
                    UPDATE contacts
                    SET project_id = :pid, updated_at = now()
                    WHERE deleted_at IS NULL
                    AND (project_id IS NULL OR project_id != :pid)
                    AND campaigns::text ILIKE :pattern
                    RETURNING id
                """),
                {"pid": PROJECT_ID, "pattern": f"%{camp_name}%"}
            )
            count = len(result.fetchall())
            if count > 0:
                logger.info(f"  Assigned {count} contacts matching campaign '{camp_name}'")
                total_assigned_sl += count
        await session.commit()
        logger.info(f"Total SmartLead contacts assigned: {total_assigned_sl}")

    # ── Step 2: Assign GetSales contacts by sender profile UUIDs ──
    logger.info("\n=== Step 2: Assign GetSales contacts by sender profiles ===")
    async with async_session_maker() as session:
        total_assigned_gs = 0
        for uuid in EASYSTAFF_SENDER_PROFILES:
            result = await session.execute(
                sql_text("""
                    UPDATE contacts
                    SET project_id = :pid, updated_at = now()
                    WHERE deleted_at IS NULL
                    AND (project_id IS NULL OR project_id != :pid)
                    AND (getsales_raw::text LIKE :pattern OR campaigns::text LIKE :pattern)
                    RETURNING id
                """),
                {"pid": PROJECT_ID, "pattern": f"%{uuid}%"}
            )
            count = len(result.fetchall())
            if count > 0:
                logger.info(f"  Assigned {count} contacts with sender profile {uuid[:12]}...")
                total_assigned_gs += count
        await session.commit()
        logger.info(f"Total GetSales contacts assigned: {total_assigned_gs}")

    # ── Step 3: Count current state ──
    async with async_session_maker() as session:
        result = await session.execute(
            sql_text("""
                SELECT count(*) as total,
                       count(*) FILTER (WHERE has_replied) as replied,
                       count(*) FILTER (WHERE status = 'warm') as warm,
                       count(*) FILTER (WHERE status IN ('scheduled','qualified','not_qualified')) as meetings,
                       count(*) FILTER (WHERE source = 'smartlead') as smartlead,
                       count(*) FILTER (WHERE source = 'getsales') as getsales
                FROM contacts
                WHERE project_id = :pid AND deleted_at IS NULL
            """),
            {"pid": PROJECT_ID}
        )
        row = result.fetchone()
        logger.info(f"\nProject 40 contacts after assignment:")
        logger.info(f"  Total: {row[0]}, Replied: {row[1]}, Warm: {row[2]}, Meetings: {row[3]}")
        logger.info(f"  SmartLead: {row[4]}, GetSales: {row[5]}")

    # ── Step 4: Import missing contacts from Google Sheet ──
    logger.info("\n=== Step 4: Import contacts from Google Sheet ===")
    from app.services.google_sheets_service import google_sheets_service

    if not google_sheets_service.is_configured():
        logger.error("Google Sheets not configured! Skipping sheet import.")
    else:
        sheet_rows = google_sheets_service.read_sheet_raw(SHEET_ID, "Leads")
        if len(sheet_rows) < 2:
            logger.warning("No data in Leads tab")
        else:
            headers = sheet_rows[0]
            header_lower = [h.strip().lower() for h in headers]

            def find_col(name):
                try:
                    return header_lower.index(name.lower())
                except ValueError:
                    return -1

            email_idx = find_col("email #1")
            name_idx = find_col("name")
            position_idx = find_col("position")
            linkedin_idx = find_col("linkedin/contact")
            company_idx = find_col("company")
            website_idx = find_col("website")
            location_idx = find_col("company location")
            status_idx = find_col("status")
            qualification_idx = find_col("qualification")
            comment_es_idx = find_col("comment easystaff")
            comment_sally_idx = find_col("comment sally")

            logger.info(f"Sheet has {len(sheet_rows) - 1} data rows, email col={email_idx}")

            if email_idx < 0:
                logger.error("Email #1 column not found!")
            else:
                # Status mapping from sheet to CRM
                sheet_to_crm = {
                    "заинтересован": "warm",
                    "пингануть": "warm",
                    "запланирована": "scheduling",
                    "была встреча": "scheduled",
                    "not interested": "not_interested",
                }
                qual_to_status = {
                    "засчитываем": "qualified",
                    "не засчитываем": "not_qualified",
                }

                async with async_session_maker() as session:
                    # Get existing emails in project 40
                    existing_result = await session.execute(
                        select(func.lower(Contact.email)).where(
                            and_(
                                Contact.project_id == PROJECT_ID,
                                Contact.deleted_at.is_(None),
                            )
                        )
                    )
                    existing_emails = {r[0] for r in existing_result.fetchall()}
                    logger.info(f"Existing contacts in project 40: {len(existing_emails)}")

                    created = 0
                    updated_qual = 0
                    for row_num, row in enumerate(sheet_rows[1:], start=2):
                        def get_cell(idx):
                            if idx < 0 or idx >= len(row):
                                return ""
                            return (row[idx] or "").strip()

                        email = get_cell(email_idx).lower()
                        if not email or "@" not in email:
                            continue

                        # Parse name
                        full_name = get_cell(name_idx)
                        parts = full_name.split(maxsplit=1) if full_name else ["", ""]
                        first_name = parts[0] if parts else ""
                        last_name = parts[1] if len(parts) > 1 else ""

                        # Parse status
                        sheet_status = get_cell(status_idx).lower()
                        crm_status = sheet_to_crm.get(sheet_status, "warm")

                        # Override with qualification
                        sheet_qual = get_cell(qualification_idx)
                        qual_status = qual_to_status.get(sheet_qual.lower(), None) if sheet_qual else None
                        if qual_status:
                            crm_status = qual_status

                        if email in existing_emails:
                            # Update qualification + client comment for existing contacts
                            if sheet_qual or get_cell(comment_es_idx):
                                result = await session.execute(
                                    select(Contact).where(
                                        and_(
                                            func.lower(Contact.email) == email,
                                            Contact.project_id == PROJECT_ID,
                                            Contact.deleted_at.is_(None),
                                        )
                                    )
                                )
                                contact = result.scalar_one_or_none()
                                if contact:
                                    changed = False
                                    if sheet_qual and contact.sheet_qualification != sheet_qual:
                                        contact.sheet_qualification = sheet_qual
                                        changed = True
                                    client_comment = get_cell(comment_es_idx)
                                    if client_comment and contact.sheet_client_comment != client_comment:
                                        contact.sheet_client_comment = client_comment
                                        changed = True
                                    sally_comment = get_cell(comment_sally_idx)
                                    if sally_comment and not contact.notes:
                                        contact.notes = sally_comment
                                        changed = True
                                    if qual_status and contact.status != qual_status:
                                        contact.status = qual_status
                                        changed = True
                                    if not contact.sheet_row:
                                        contact.sheet_row = row_num
                                        changed = True
                                    if changed:
                                        updated_qual += 1
                            continue

                        # Create new contact
                        contact = Contact(
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            job_title=get_cell(position_idx) or None,
                            linkedin_url=get_cell(linkedin_idx) or None,
                            company_name=get_cell(company_idx) or None,
                            domain=get_cell(website_idx) or None,
                            location=get_cell(location_idx) or None,
                            notes=get_cell(comment_sally_idx) or None,
                            project_id=PROJECT_ID,
                            company_id=project.company_id,
                            source="sheet_import",
                            status=crm_status,
                            has_replied=True,
                            reply_sentiment="warm" if crm_status in ("warm", "scheduling", "scheduled", "qualified") else "cold",
                            sheet_row=row_num,
                            sheet_qualification=sheet_qual if sheet_qual else None,
                            sheet_client_comment=get_cell(comment_es_idx) or None,
                        )
                        session.add(contact)
                        created += 1
                        existing_emails.add(email)

                    await session.commit()
                    logger.info(f"Sheet import: {created} new contacts created, {updated_qual} updated with qualification")

    # ── Step 5: Final stats ──
    logger.info("\n=== Final Stats ===")
    async with async_session_maker() as session:
        result = await session.execute(
            sql_text("""
                SELECT status, count(*)
                FROM contacts
                WHERE project_id = :pid AND deleted_at IS NULL
                GROUP BY status ORDER BY count(*) DESC
            """),
            {"pid": PROJECT_ID}
        )
        for status, count in result.fetchall():
            logger.info(f"  {status}: {count}")

        result = await session.execute(
            sql_text("""
                SELECT count(*) as total,
                       count(sheet_qualification) as with_qual,
                       count(sheet_client_comment) as with_comment,
                       count(sheet_row) as with_row
                FROM contacts
                WHERE project_id = :pid AND deleted_at IS NULL
            """),
            {"pid": PROJECT_ID}
        )
        row = result.fetchone()
        logger.info(f"\n  Total: {row[0]}")
        logger.info(f"  With sheet_qualification: {row[1]}")
        logger.info(f"  With sheet_client_comment: {row[2]}")
        logger.info(f"  With sheet_row: {row[3]}")

    # ── Step 6: Enable sheet sync ──
    logger.info("\n=== Step 6: Enable sheet sync ===")
    async with async_session_maker() as session:
        project = await session.get(Project, PROJECT_ID)
        config = project.sheet_sync_config or {}
        config.update({
            "enabled": True,
            "sheet_id": SHEET_ID,
            "leads_tab": "Leads",
            "replies_tab": "Replies",
        })
        project.sheet_sync_config = config
        await session.commit()
        logger.info(f"Sheet sync enabled for project {PROJECT_ID}")
        logger.info(f"Config: {config}")

    logger.info("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
