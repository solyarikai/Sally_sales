#!/usr/bin/env python3
"""
Backfill contact.domain from email addresses.

Populates the domain field for all contacts where it's NULL/empty
by extracting the domain part from the email address.

Usage:
    python scripts/backfill_contact_domains.py
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import text
from app.db import async_session_maker, engine


async def backfill():
    async with async_session_maker() as session:
        # Count contacts needing backfill
        result = await session.execute(text(
            "SELECT count(*) FROM contacts "
            "WHERE email IS NOT NULL AND email LIKE '%@%' "
            "AND (domain IS NULL OR domain = '')"
        ))
        count = result.scalar()
        print(f"Contacts needing domain backfill: {count}")

        if count == 0:
            print("Nothing to do.")
            return

        # Backfill domain from email
        result = await session.execute(text(
            "UPDATE contacts "
            "SET domain = lower(split_part(email, '@', 2)) "
            "WHERE email IS NOT NULL AND email LIKE '%@%' "
            "AND (domain IS NULL OR domain = '') "
            "AND email NOT LIKE '%@placeholder.local'"
        ))
        updated = result.rowcount
        await session.commit()
        print(f"Updated {updated} contacts with domain from email.")

        # Verify
        result = await session.execute(text(
            "SELECT count(*) FROM contacts WHERE domain IS NOT NULL AND domain != ''"
        ))
        total_with_domain = result.scalar()
        print(f"Total contacts with domain: {total_with_domain}")

        # Create index if not exists
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_contacts_domain_not_null "
            "ON contacts(domain) WHERE domain IS NOT NULL"
        ))
        await session.commit()
        print("Index ix_contacts_domain_not_null created (or already exists).")


async def main():
    try:
        await backfill()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
