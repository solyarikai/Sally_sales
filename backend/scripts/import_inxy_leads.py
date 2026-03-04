"""Import Inxy leads from Google Sheet into contacts table.

Sheet: 1x7qXLxolby-u3kL6D835ElQGYNQJH6kUDJxMpWZedX4, tab: Leads
Project ID: 10, Company ID: 1
"""
import asyncio
import re
from app.db import async_session_maker
from app.services.google_sheets_service import GoogleSheetsService
from sqlalchemy import text

SHEET_ID = "1x7qXLxolby-u3kL6D835ElQGYNQJH6kUDJxMpWZedX4"
TAB = "Leads"
PROJECT_ID = 10
COMPANY_ID = 1

# Status mapping from sheet values to our funnel statuses
STATUS_MAP = {
    "была встреча": "qualified",
    "not interested": "not_interested",
    "interested": "warm",
    "no response": "lead",
    "bounced": "bounced",
}


def parse_email(raw: str) -> str | None:
    """Extract first valid email from field. Handles 'email1 / email2' and newlines."""
    if not raw or raw.strip() in ("-", "", "N/A", "n/a"):
        return None
    # Take the first email if multiple separated by / , ; or newlines
    parts = re.split(r"[/,;\n]", raw)
    for part in parts:
        candidate = part.strip()
        if "@" in candidate and "." in candidate:
            return candidate.lower()
    return None


def split_name(full_name: str) -> tuple[str | None, str | None]:
    """Split 'First Last' into (first, last). Single word -> (first, None).
    Takes only the first line if multiline."""
    if not full_name or full_name.strip() in ("-", ""):
        return None, None
    # Take only first line (rest may be notes)
    first_line = full_name.strip().split("\n")[0].strip()
    if not first_line:
        return None, None
    parts = first_line.split(None, 1)
    first = parts[0] if parts else None
    last = parts[1] if len(parts) > 1 else None
    return first, last


def extract_linkedin(s: str) -> str | None:
    """Extract LinkedIn URL from field. May contain phone numbers on separate lines."""
    if not s:
        return None
    # Take only the first line (rest may be phone numbers)
    first_line = s.strip().split("\n")[0].strip()
    if not first_line:
        return None
    lower = first_line.lower()
    if "linkedin.com" not in lower:
        return None
    url = first_line
    if not url.startswith("http"):
        url = "https://" + url
    return url


def extract_domain(website: str) -> str | None:
    """Extract domain from a website URL."""
    if not website or website.strip() in ("-", "", "N/A"):
        return None
    w = website.strip()
    # Remove protocol
    w = re.sub(r"^https?://", "", w)
    # Remove path
    w = w.split("/")[0]
    return w.lower() if w else None


def map_status(raw_status: str) -> str:
    """Map sheet status to our funnel status."""
    if not raw_status or raw_status.strip() in ("-", ""):
        return "lead"
    normalized = raw_status.strip().lower()
    return STATUS_MAP.get(normalized, "lead")


def build_notes(row: dict) -> str | None:
    """Concatenate Qualification, Stage, Hypothesis, Company Description into notes."""
    parts = []
    for key in ("qualification", "stage", "hypothesis", "company description"):
        val = row.get(key, "").strip()
        if val and val != "-":
            label = key.replace("_", " ").title()
            parts.append(f"{label}: {val}")
    return "\n".join(parts) if parts else None


async def main():
    # 1. Read sheet data
    gs = GoogleSheetsService()
    data = gs.read_sheet_data(SHEET_ID, TAB)
    print(f"Read {len(data)} rows from Google Sheet")

    if not data:
        print("ERROR: No data read from sheet!")
        return

    # 2. Process rows
    contacts_to_insert = []
    skipped_no_email = 0
    skipped_bad_email = 0

    for i, row in enumerate(data):
        raw_email = row.get("email #1", "")
        email = parse_email(raw_email)
        if not email:
            skipped_no_email += 1
            continue

        first_name, last_name = split_name(row.get("name", ""))
        company_name = row.get("company", "").strip() or None
        if company_name == "-":
            company_name = None
        job_title = row.get("position", "").strip() or None
        if job_title == "-":
            job_title = None

        website = row.get("website", "")
        domain = extract_domain(website)

        location = row.get("company location", "").strip() or None
        if location == "-":
            location = None

        linkedin_raw = row.get("linkedin / contacts", "")
        linkedin_url = extract_linkedin(linkedin_raw)

        status = map_status(row.get("status", ""))
        source_val = row.get("source", "").strip() or None
        notes = build_notes(row)

        contacts_to_insert.append({
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name,
            "job_title": job_title,
            "domain": domain,
            "location": location,
            "linkedin_url": linkedin_url,
            "status": status,
            "source": "google_sheet",
            "source_id": source_val,
            "notes": notes,
            "project_id": PROJECT_ID,
            "company_id": COMPANY_ID,
        })

    print(f"Prepared {len(contacts_to_insert)} contacts for import")
    print(f"Skipped {skipped_no_email} rows without valid email")

    # 3. Insert into database, deduplicating by email (global unique constraint)
    async with async_session_maker() as session:
        # Get ALL existing emails (global unique constraint on lower(email))
        result = await session.execute(
            text("SELECT lower(email) FROM contacts")
        )
        existing_emails = {row[0] for row in result.fetchall()}
        print(f"Found {len(existing_emails)} existing contacts globally")

        inserted = 0
        skipped_dup = 0
        seen_emails = set()

        for c in contacts_to_insert:
            email_lower = c["email"].lower()

            # Skip duplicates within this batch
            if email_lower in seen_emails:
                skipped_dup += 1
                continue
            seen_emails.add(email_lower)

            # Skip if already exists in DB (global uniqueness)
            if email_lower in existing_emails:
                skipped_dup += 1
                continue

            await session.execute(
                text("""
                    INSERT INTO contacts (
                        email, first_name, last_name, company_name, job_title,
                        domain, location, linkedin_url, status, source, source_id,
                        notes, project_id, company_id, is_active, created_at, updated_at
                    ) VALUES (
                        :email, :first_name, :last_name, :company_name, :job_title,
                        :domain, :location, :linkedin_url, :status, :source, :source_id,
                        :notes, :project_id, :company_id, true, NOW(), NOW()
                    )
                """),
                c
            )
            inserted += 1

        await session.commit()
        print(f"\nIMPORT COMPLETE:")
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (duplicate email): {skipped_dup}")
        print(f"  Skipped (no email): {skipped_no_email}")
        print(f"  Total rows in sheet: {len(data)}")

        # Verify
        result = await session.execute(
            text("SELECT COUNT(*) FROM contacts WHERE project_id = :pid"),
            {"pid": PROJECT_ID}
        )
        total = result.scalar()
        print(f"  Total contacts for project {PROJECT_ID} now: {total}")


asyncio.run(main())
