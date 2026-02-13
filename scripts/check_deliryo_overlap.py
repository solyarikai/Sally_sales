"""Check overlap between exported Deliryo targets and SmartLead Deliryo campaigns."""
import asyncio
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    # Load SmartLead Deliryo emails
    with open("/tmp/deliryo_sl_emails.txt") as f:
        sl_emails = set(line.strip().lower() for line in f if line.strip())
    print(f"SmartLead Deliryo emails (3 active campaigns): {len(sl_emails)}")

    async with async_session_maker() as s:
        # How many of these SmartLead emails are in our contacts table with smartlead_id
        r1 = await s.execute(
            text("SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL AND lower(email) = ANY(:emails)"),
            {"emails": list(sl_emails)},
        )
        with_sl_id = r1.scalar()
        print(f"Found in contacts DB (with smartlead_id): {with_sl_id}")

        r1b = await s.execute(
            text("SELECT COUNT(*) FROM contacts WHERE lower(email) = ANY(:emails)"),
            {"emails": list(sl_emails)},
        )
        any_in_db = r1b.scalar()
        print(f"Found in contacts DB (any): {any_in_db}")
        print(f"In DB but WITHOUT smartlead_id: {any_in_db - with_sl_id}")
        print(f"SmartLead emails NOT in our DB at all: {len(sl_emails) - any_in_db}")

        # Get all Deliryo target extracted emails
        r2 = await s.execute(text(
            "SELECT ec.email FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != ''"
        ))
        target_emails = set(row[0].lower() for row in r2.fetchall())
        print(f"\nTotal Deliryo target emails: {len(target_emails)}")

        # Direct overlap: target emails that exist in SmartLead Deliryo campaigns
        overlap = target_emails & sl_emails
        print(f"DIRECT OVERLAP with SmartLead Deliryo: {len(overlap)}")
        if overlap:
            for e in sorted(overlap)[:20]:
                print(f"  DUPLICATE: {e}")

        # Domain overlap
        sl_domains = set(e.split("@")[1] for e in sl_emails if "@" in e)
        target_domains_q = await s.execute(text(
            "SELECT DISTINCT lower(dc.domain) FROM discovered_companies dc "
            "JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != ''"
        ))
        target_domains = set(row[0] for row in target_domains_q.fetchall())
        domain_overlap = target_domains & sl_domains
        print(f"\nDomain overlap: {len(domain_overlap)} / {len(target_domains)} target domains")
        if domain_overlap:
            for d in sorted(domain_overlap)[:30]:
                print(f"  DOMAIN DUP: {d}")

        # The critical check: which of the EXPORTED contacts (our exclude_smartlead filter)
        # actually overlap with SmartLead Deliryo emails?
        r3 = await s.execute(text(
            "SELECT ec.email, dc.domain FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != '' "
            "AND lower(ec.email) NOT IN ("
            "  SELECT DISTINCT lower(c.email) FROM contacts c "
            "  WHERE c.smartlead_id IS NOT NULL AND c.email IS NOT NULL"
            ") "
            "AND lower(dc.domain) NOT IN ("
            "  SELECT DISTINCT lower(c.domain) FROM contacts c "
            "  WHERE c.smartlead_id IS NOT NULL AND c.domain IS NOT NULL AND c.domain != ''"
            ")"
        ))
        exported = r3.fetchall()
        exported_emails = set(row[0].lower() for row in exported)
        print(f"\nExported contacts (current exclude_smartlead filter): {len(exported_emails)}")

        # Check exported emails against SmartLead Deliryo directly
        exported_overlap = exported_emails & sl_emails
        print(f"!!! EXPORTED that ARE in SmartLead Deliryo: {len(exported_overlap)} !!!")
        if exported_overlap:
            for e in sorted(exported_overlap):
                print(f"  LEAKED: {e}")

        exported_domains = set(row[1].lower() for row in exported)
        exported_domain_overlap = exported_domains & sl_domains
        print(f"EXPORTED domains in SmartLead Deliryo: {len(exported_domain_overlap)}")
        if exported_domain_overlap:
            for d in sorted(exported_domain_overlap):
                print(f"  LEAKED DOMAIN: {d}")

        # What if we check against ALL contacts (not just smartlead_id)?
        r4 = await s.execute(text(
            "SELECT ec.email, dc.domain FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != '' "
            "AND lower(ec.email) NOT IN ("
            "  SELECT DISTINCT lower(c.email) FROM contacts c "
            "  WHERE c.email IS NOT NULL"
            ") "
            "AND lower(dc.domain) NOT IN ("
            "  SELECT DISTINCT lower(c.domain) FROM contacts c "
            "  WHERE c.domain IS NOT NULL AND c.domain != ''"
            ")"
        ))
        strict = r4.fetchall()
        strict_emails = set(row[0].lower() for row in strict)
        strict_overlap = strict_emails & sl_emails
        print(f"\nIf we checked against ALL contacts (not just smartlead_id): {len(strict_emails)}")
        print(f"Overlap with SmartLead Deliryo: {len(strict_overlap)}")


asyncio.run(main())
