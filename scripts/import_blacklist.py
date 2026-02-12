"""Import outreach domains into ProjectBlacklist for project 24 (Archistruct).
These domains were already contacted via SmartLead campaigns."""
import asyncio
import json
import sys
import os
import logging

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import_blacklist")

async def main():
    from app.db import async_session_maker
    from app.models.domain import ProjectBlacklist
    from sqlalchemy import select

    # Load domains
    with open("/scripts/archistruct_outreach_domains.json") as f:
        data = json.load(f)

    all_domains = data["all_domains"]
    logger.info(f"Loaded {len(all_domains)} domains from outreach campaigns")

    async with async_session_maker() as session:
        # Check existing blacklist entries
        result = await session.execute(
            select(ProjectBlacklist.domain).where(ProjectBlacklist.project_id == 24)
        )
        existing = {row[0] for row in result.fetchall()}
        logger.info(f"Existing blacklist entries: {len(existing)}")

        # Add new entries
        added = 0
        for domain in all_domains:
            domain = domain.strip().lower()
            if domain and domain not in existing:
                bl = ProjectBlacklist(
                    project_id=24,
                    domain=domain,
                    reason="outreach_campaign",
                )
                session.add(bl)
                added += 1

        await session.commit()
        logger.info(f"Added {added} new domains to blacklist (skipped {len(all_domains) - added} existing)")

if __name__ == "__main__":
    asyncio.run(main())
