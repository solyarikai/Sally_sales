"""Validate Rizzult (project 22) DB coverage against reference Google Sheet.

Reads the reference sheet (gid=124573624, tab "Replies 10.02"), matches by
target_lead_email (column J) against contacts table, and:
  - Reports coverage %
  - Backfills missing contacts from sheet data
  - Enriches existing contacts with empty fields that sheet has

Usage:
    python scripts/validate_rizzult_coverage.py [--dry-run]
"""
import asyncio
import argparse
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select, func, and_
from app.db import async_session_maker
from app.models.contact import Contact, Project
from app.services.google_sheets_service import google_sheets_service


PROJECT_ID = 22
COMPANY_ID = 1
SHEET_ID = "1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s"
REFERENCE_TAB = "Replies 10.02"

# Rizzult external status → internal status mapping
EXTERNAL_TO_INTERNAL = {
    "Interested": "interested",
    "To Sales": "qualified",
    "Recommended": "interested",
    "Positive": "interested",
    "Not Interested": "not_interested",
    "Irrelevant": "not_interested",
    "OOO": "ooo",
    "Wrong Person": "not_interested",
    "Unsubscribe": "unsubscribed",
    "Meeting Scheduled": "scheduled",
    "Negotiating": "negotiating_meeting",
}


async def run(dry_run: bool = False):
    # Read reference sheet
    print(f"Reading reference sheet '{REFERENCE_TAB}'...")
    rows = google_sheets_service.read_sheet_raw(SHEET_ID, REFERENCE_TAB)
    if not rows or len(rows) < 2:
        print("ERROR: Reference sheet is empty")
        return

    headers = [h.strip().lower() for h in rows[0]]
    data_rows = rows[1:]
    print(f"Found {len(data_rows)} data rows, headers: {headers[:10]}...")

    # Column indices (0-based)
    def col(name):
        try:
            return headers.index(name.lower())
        except ValueError:
            return -1

    idx_email = col("target_lead_email")
    idx_updated_email = col("updated email")
    idx_first_name = col("first name")
    idx_last_name = col("last name")
    idx_position = col("position")
    idx_linkedin = col("linkedin")
    idx_company = col("company")
    idx_website = col("website")
    idx_location = col("company location")
    idx_segment = col("segment")
    idx_status = col("status")  # Column Y — the second "Status" or last one
    idx_source = col("source")

    # The header has two "status" columns — column C and column Y (index 24).
    # We want the later one (column Y = index 24) for status_external.
    # Find the LAST occurrence of "status"
    status_indices = [i for i, h in enumerate(headers) if h == "status"]
    if len(status_indices) >= 2:
        idx_status = status_indices[-1]  # Last "status" column = Y
    elif status_indices:
        idx_status = status_indices[0]

    print(f"Email col: {idx_email}, Status col: {idx_status}")

    if idx_email < 0:
        print("ERROR: target_lead_email column not found")
        return

    def get_cell(row, idx):
        if idx < 0 or idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    # Build email → sheet row data
    sheet_contacts = {}
    for row in data_rows:
        email = get_cell(row, idx_email).lower()
        if not email or "@" not in email:
            continue
        sheet_contacts[email] = {
            "email": get_cell(row, idx_email),
            "updated_email": get_cell(row, idx_updated_email),
            "first_name": get_cell(row, idx_first_name),
            "last_name": get_cell(row, idx_last_name),
            "job_title": get_cell(row, idx_position),
            "linkedin_url": get_cell(row, idx_linkedin),
            "company_name": get_cell(row, idx_company),
            "domain": get_cell(row, idx_website),
            "location": get_cell(row, idx_location),
            "segment": get_cell(row, idx_segment),
            "status_external": get_cell(row, idx_status),
            "source_label": get_cell(row, idx_source),
        }

    print(f"\nUnique emails in reference sheet: {len(sheet_contacts)}")

    # Query DB
    async with async_session_maker() as session:
        result = await session.execute(
            select(Contact).where(
                and_(
                    Contact.project_id == PROJECT_ID,
                    Contact.deleted_at.is_(None),
                )
            )
        )
        db_contacts = {c.email.lower(): c for c in result.scalars().all() if c.email}

        print(f"Contacts in DB for project {PROJECT_ID}: {len(db_contacts)}")

        # Coverage analysis
        found = 0
        missing = []
        enriched = 0

        for email, sheet_data in sheet_contacts.items():
            contact = db_contacts.get(email)
            if contact:
                found += 1
                # Enrich empty fields
                fields_updated = []
                if not contact.first_name and sheet_data["first_name"]:
                    if not dry_run:
                        contact.first_name = sheet_data["first_name"]
                    fields_updated.append("first_name")
                if not contact.last_name and sheet_data["last_name"]:
                    if not dry_run:
                        contact.last_name = sheet_data["last_name"]
                    fields_updated.append("last_name")
                if not contact.job_title and sheet_data["job_title"]:
                    if not dry_run:
                        contact.job_title = sheet_data["job_title"]
                    fields_updated.append("job_title")
                if not contact.linkedin_url and sheet_data["linkedin_url"]:
                    if not dry_run:
                        contact.linkedin_url = sheet_data["linkedin_url"]
                    fields_updated.append("linkedin_url")
                if not contact.company_name and sheet_data["company_name"]:
                    if not dry_run:
                        contact.company_name = sheet_data["company_name"]
                    fields_updated.append("company_name")
                if not contact.domain and sheet_data["domain"]:
                    if not dry_run:
                        contact.domain = sheet_data["domain"]
                    fields_updated.append("domain")
                if not contact.location and sheet_data["location"]:
                    if not dry_run:
                        contact.location = sheet_data["location"]
                    fields_updated.append("location")
                if not contact.segment and sheet_data["segment"]:
                    if not dry_run:
                        contact.segment = sheet_data["segment"]
                    fields_updated.append("segment")
                if not contact.status_external and sheet_data["status_external"]:
                    if not dry_run:
                        contact.status_external = sheet_data["status_external"]
                    fields_updated.append("status_external")

                if fields_updated:
                    enriched += 1
                    if enriched <= 5:
                        print(f"  Enriched {email}: {', '.join(fields_updated)}")
            else:
                missing.append((email, sheet_data))

        coverage = found / len(sheet_contacts) * 100 if sheet_contacts else 0
        print(f"\n=== Coverage Report ===")
        print(f"Reference contacts: {len(sheet_contacts)}")
        print(f"Found in DB:        {found} ({coverage:.1f}%)")
        print(f"Missing from DB:    {len(missing)}")
        print(f"Enriched:           {enriched}")

        if missing:
            print(f"\n--- Missing contacts (first 20) ---")
            for email, data in missing[:20]:
                print(f"  {email} | {data['first_name']} {data['last_name']} | {data['company_name']} | {data['status_external']}")

        # Backfill missing contacts
        if missing and not dry_run:
            print(f"\nBackfilling {len(missing)} missing contacts...")
            created = 0
            for email, data in missing:
                # Derive internal status from external
                internal_status = EXTERNAL_TO_INTERNAL.get(data["status_external"], "interested")

                new_contact = Contact(
                    email=data["updated_email"] or data["email"],
                    first_name=data["first_name"] or None,
                    last_name=data["last_name"] or None,
                    job_title=data["job_title"] or None,
                    linkedin_url=data["linkedin_url"] or None,
                    company_name=data["company_name"] or None,
                    domain=data["domain"] or None,
                    location=data["location"] or None,
                    segment=data["segment"] or None,
                    status=internal_status,
                    status_external=data["status_external"] or None,
                    source="sheet_import",
                    project_id=PROJECT_ID,
                    company_id=COMPANY_ID,
                )
                session.add(new_contact)
                created += 1

            await session.commit()
            print(f"Created {created} new contacts")
        elif dry_run and missing:
            print(f"\n[DRY RUN] Would create {len(missing)} contacts")
        else:
            if not dry_run:
                await session.commit()
                print(f"\nEnrichment committed ({enriched} contacts updated)")

        # Final status distribution
        result = await session.execute(
            select(Contact.status_external, func.count(Contact.id)).where(
                and_(
                    Contact.project_id == PROJECT_ID,
                    Contact.deleted_at.is_(None),
                    Contact.status_external.isnot(None),
                )
            ).group_by(Contact.status_external)
        )
        print(f"\n=== Status Distribution (project {PROJECT_ID}) ===")
        for status, count in result.all():
            print(f"  {status}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report only, don't modify DB")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))
