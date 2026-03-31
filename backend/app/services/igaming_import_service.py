"""
iGaming CSV/Excel import service.

Handles file parsing, column mapping, deduplication,
company normalization, and auto-enrichment from existing data.
"""
import csv
import io
import logging
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func, and_, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.igaming import (
    IGamingContact, IGamingCompany, IGamingImport, IGamingImportStatus,
    BusinessType, normalize_business_type, normalize_website,
)

logger = logging.getLogger(__name__)

# Temporary upload storage (in production, use Redis or disk)
_upload_cache: dict[str, dict] = {}


def parse_csv_content(content: bytes, filename: str) -> tuple[list[str], list[dict]]:
    """Parse CSV bytes into headers and rows."""
    text_content = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text_content))
    columns = reader.fieldnames or []
    rows = list(reader)
    return columns, rows


def parse_semicolon_list(value: str | None) -> list[str] | None:
    """Parse 'Europe; North America; Asia' into ['Europe', 'North America', 'Asia']."""
    if not value or not value.strip():
        return None
    items = [item.strip() for item in value.split(";") if item.strip()]
    return items if items else None


async def upload_file(content: bytes, filename: str) -> dict:
    """Parse uploaded file and store in cache. Returns preview data."""
    columns, rows = parse_csv_content(content, filename)
    file_id = str(uuid.uuid4())

    _upload_cache[file_id] = {
        "filename": filename,
        "columns": columns,
        "rows": rows,
        "uploaded_at": datetime.utcnow(),
    }

    preview = rows[:10] if len(rows) >= 10 else rows
    return {
        "file_id": file_id,
        "filename": filename,
        "rows_preview": len(rows),
        "columns": columns,
        "preview": preview,
    }


def proper_case(name: str | None) -> str | None:
    """Convert a name to proper case (capitalize first letter of each word)."""
    if not name or not name.strip():
        return name
    # Handle names that are all caps or all lower
    return " ".join(word.capitalize() for word in name.strip().split())


async def run_import(
    session: AsyncSession,
    file_id: str,
    column_mapping: dict[str, str],
    source_conference: str | None = None,
    update_existing: bool = False,
) -> IGamingImport:
    """
    Import contacts from cached upload. Optimized for bulk import (100K+ rows).

    Uses in-memory deduplication instead of per-row SQL queries.
    """
    cached = _upload_cache.get(file_id)
    if not cached:
        raise ValueError(f"Upload {file_id} not found or expired")

    rows = cached["rows"]
    filename = cached["filename"]

    # Create import log
    import_log = IGamingImport(
        filename=filename,
        source_conference=source_conference,
        status=IGamingImportStatus.PROCESSING,
        rows_total=len(rows),
    )
    session.add(import_log)
    await session.flush()

    # ── Pre-load existing data for in-memory dedup ─────────────────────

    # Load existing emails into set (and optionally map to contact IDs for update)
    existing_emails: set[str] = set()
    email_to_contact: dict[str, int] = {}
    email_rows = await session.execute(
        select(IGamingContact.id, IGamingContact.email).where(IGamingContact.email.isnot(None))
    )
    for cid, email in email_rows.all():
        if email:
            existing_emails.add(email.lower())
            if update_existing:
                email_to_contact[email.lower()] = cid

    # Load existing name+org combos into set
    existing_name_org: set[str] = set()
    name_org_to_contact: dict[str, int] = {}
    name_rows = await session.execute(
        select(
            IGamingContact.id,
            IGamingContact.first_name,
            IGamingContact.last_name,
            IGamingContact.organization_name,
        ).where(IGamingContact.first_name.isnot(None))
    )
    for cid, fn, ln, org in name_rows.all():
        if fn and ln and org:
            key = f"{fn.lower()}|{ln.lower()}|{org.lower()}"
            existing_name_org.add(key)
            if update_existing:
                name_org_to_contact[key] = cid

    # Load existing companies into cache
    company_cache: dict[str, IGamingCompany] = {}
    existing_companies = await session.execute(select(IGamingCompany))
    for co in existing_companies.scalars().all():
        company_cache[co.name_normalized] = co

    logger.info(
        f"Import pre-load: {len(existing_emails)} emails, "
        f"{len(existing_name_org)} name+org combos, "
        f"{len(company_cache)} companies"
    )

    # ── Process rows ───────────────────────────────────────────────────

    imported = 0
    skipped = 0
    updated = 0
    companies_created = 0
    errors = []
    batch: list[IGamingContact] = []
    BATCH_SIZE = 1000

    for row_idx, row in enumerate(rows):
        try:
            # Map CSV columns to model fields
            mapped = {}
            for csv_col, model_field in column_mapping.items():
                if csv_col in row and model_field:
                    mapped[model_field] = row[csv_col]

            # Skip rows with no useful data
            has_name = mapped.get("first_name") or mapped.get("last_name")
            has_contact = mapped.get("email") or mapped.get("linkedin_url")
            if not has_name and not has_contact:
                skipped += 1
                continue

            # Normalize
            raw_website = mapped.get("website_url")
            clean_website = normalize_website(raw_website)
            raw_type = mapped.get("business_type_raw") or mapped.get("business_type")
            norm_type = normalize_business_type(raw_type)
            regions = parse_semicolon_list(mapped.get("regions"))
            new_regions = parse_semicolon_list(mapped.get("new_regions_targeting"))
            sector = mapped.get("sector")
            if sector and "null" in sector.lower():
                sector = None

            email = (mapped.get("email") or "").strip() or None
            first_name = proper_case((mapped.get("first_name") or "").strip() or None)
            last_name = proper_case((mapped.get("last_name") or "").strip() or None)
            org_name = (mapped.get("organization_name") or "").strip() or None

            # ── In-memory dedup (no SQL queries!) ──────────────────────
            is_duplicate = False
            existing_contact_id: int | None = None
            if email:
                if email.lower() in existing_emails:
                    is_duplicate = True
                    if update_existing:
                        existing_contact_id = email_to_contact.get(email.lower())
                else:
                    existing_emails.add(email.lower())
            elif first_name and last_name and org_name:
                key = f"{first_name.lower()}|{last_name.lower()}|{org_name.lower()}"
                if key in existing_name_org:
                    is_duplicate = True
                    if update_existing:
                        existing_contact_id = name_org_to_contact.get(key)
                else:
                    existing_name_org.add(key)

            if is_duplicate:
                if update_existing and existing_contact_id:
                    # Update empty fields on existing contact
                    try:
                        result = await session.execute(
                            select(IGamingContact).where(IGamingContact.id == existing_contact_id)
                        )
                        existing_c = result.scalar_one_or_none()
                        if existing_c:
                            fields_updated = False
                            updatable_fields = [
                                ("first_name", first_name),
                                ("last_name", last_name),
                                ("email", email),
                                ("phone", (mapped.get("phone") or "").strip() or None),
                                ("linkedin_url", (mapped.get("linkedin_url") or "").strip() or None),
                                ("job_title", (mapped.get("job_title") or "").strip() or None),
                                ("bio", (mapped.get("bio") or "").strip() or None),
                                ("other_contact", (mapped.get("other_contact") or "").strip() or None),
                                ("organization_name", org_name),
                                ("website_url", clean_website),
                                ("sector", sector),
                                ("channel", (mapped.get("channel") or "").strip() or None),
                                ("products_services", (mapped.get("products_services") or "").strip() or None),
                            ]
                            for field_name, new_value in updatable_fields:
                                if new_value and not getattr(existing_c, field_name, None):
                                    setattr(existing_c, field_name, new_value)
                                    fields_updated = True
                            if not existing_c.business_type and norm_type and norm_type != BusinessType.OTHER:
                                existing_c.business_type = norm_type
                                existing_c.business_type_raw = raw_type
                                fields_updated = True
                            if not existing_c.regions and regions:
                                existing_c.regions = regions
                                fields_updated = True
                            if fields_updated:
                                updated += 1
                            else:
                                skipped += 1
                    except Exception:
                        skipped += 1
                else:
                    updated += 1  # Count as "seen but skipped"
                continue

            # ── Find or create company (in-memory cache, no per-row flush) ─
            company_id = None
            if org_name:
                norm_name = IGamingCompany.normalize_name(org_name)
                if norm_name in company_cache:
                    company = company_cache[norm_name]
                    company_id = company.id
                    # Enrich existing company
                    if not company.website and clean_website:
                        company.website = clean_website
                    if not company.business_type and norm_type != BusinessType.OTHER:
                        company.business_type = norm_type
                        company.business_type_raw = raw_type
                    if not company.sector and sector:
                        company.sector = sector
                    if not company.regions and regions:
                        company.regions = regions
                else:
                    company = IGamingCompany(
                        name=org_name,
                        name_normalized=norm_name,
                        name_aliases=[],
                        website=clean_website,
                        business_type=norm_type if norm_type != BusinessType.OTHER else None,
                        business_type_raw=raw_type,
                        sector=sector,
                        regions=regions,
                        contacts_count=0,
                    )
                    session.add(company)
                    await session.flush()
                    company_cache[norm_name] = company
                    company_id = company.id
                    companies_created += 1

            # ── Create contact ─────────────────────────────────────────
            contact = IGamingContact(
                source_id=mapped.get("source_id") or row.get("id"),
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=(mapped.get("phone") or "").strip() or None,
                linkedin_url=(mapped.get("linkedin_url") or "").strip() or None,
                job_title=(mapped.get("job_title") or "").strip() or None,
                bio=(mapped.get("bio") or "").strip() or None,
                other_contact=(mapped.get("other_contact") or "").strip() or None,
                organization_name=org_name,
                website_url=clean_website,
                business_type_raw=raw_type,
                business_type=norm_type,
                company_id=company_id,
                source_conference=source_conference,
                source_file=filename,
                import_id=import_log.id,
                sector=sector,
                regions=regions,
                new_regions_targeting=new_regions,
                channel=(mapped.get("channel") or "").strip() or None,
                products_services=(mapped.get("products_services") or "").strip() or None,
            )
            batch.append(contact)
            imported += 1

            # Flush batch
            if len(batch) >= BATCH_SIZE:
                session.add_all(batch)
                await session.flush()
                batch.clear()
                logger.info(f"Import progress: {row_idx + 1}/{len(rows)} ({imported} imported, {companies_created} companies)")

        except Exception as e:
            skipped += 1
            if len(errors) < 50:
                errors.append({"row": row_idx, "error": str(e)})

    # Final batch
    if batch:
        session.add_all(batch)
        await session.flush()

    # Update company contacts_count in bulk
    await session.execute(text("""
        UPDATE igaming_companies c
        SET contacts_count = sub.cnt
        FROM (
            SELECT company_id, count(*) as cnt
            FROM igaming_contacts
            WHERE company_id IS NOT NULL AND is_active = true
            GROUP BY company_id
        ) sub
        WHERE c.id = sub.company_id
    """))

    # Update import log
    import_log.rows_imported = imported
    import_log.rows_skipped = skipped
    import_log.rows_updated = updated
    import_log.companies_created = companies_created
    import_log.status = IGamingImportStatus.COMPLETED
    import_log.error_log = errors if errors else None

    await session.flush()

    # Clean up cache
    _upload_cache.pop(file_id, None)

    logger.info(
        f"Import completed: {imported} imported, {updated} duplicates, "
        f"{skipped} skipped, {companies_created} companies created"
    )
    return import_log


async def run_autofill(session: AsyncSession) -> dict:
    """
    Auto-fill missing website and business_type from other contacts in the same company.
    Uses bulk UPDATE — no per-row queries.
    """
    # Bulk update website from company
    website_result = await session.execute(text("""
        UPDATE igaming_contacts c
        SET website_url = co.website
        FROM igaming_companies co
        WHERE c.company_id = co.id
          AND c.website_url IS NULL
          AND co.website IS NOT NULL
    """))
    contacts_website = website_result.rowcount

    # Bulk update business_type from company
    type_result = await session.execute(text("""
        UPDATE igaming_contacts c
        SET business_type = co.business_type
        FROM igaming_companies co
        WHERE c.company_id = co.id
          AND c.business_type IS NULL
          AND co.business_type IS NOT NULL
    """))
    contacts_type = type_result.rowcount

    await session.flush()
    return {
        "contacts_website_updated": contacts_website,
        "contacts_type_updated": contacts_type,
    }
