"""Targeted Rizzult-only SmartLead contact sync.
Run inside the backend container: python3 /app/scripts/sync_rizzult.py
"""
import asyncio
import os
import sys

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.services.crm_sync_service import CRMSyncService

    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        svc = CRMSyncService()

        # Get Rizzult SmartLead campaigns from DB
        result = await session.execute(text(
            "SELECT id, external_id, name, project_id, synced_leads_count "
            "FROM campaigns WHERE project_id = 22 AND platform = 'smartlead' ORDER BY name"
        ))
        campaigns = result.fetchall()

        print(f"Found {len(campaigns)} SmartLead Rizzult campaigns", flush=True)

        grand_created = 0
        grand_updated = 0
        grand_skipped = 0

        for row in campaigns:
            cid, ext_id, name, pid, synced = row

            class CampObj:
                pass
            camp = CampObj()
            camp.id = cid
            camp.external_id = ext_id
            camp.name = name
            camp.project_id = pid
            camp.leads_count = 0
            camp.synced_leads_count = synced or 0

            r = await svc._sync_smartlead_campaign_contacts(
                session, 1, camp, max_leads=999999, start_offset=0
            )
            await session.commit()
            total = r["created"] + r["updated"] + r["skipped"]
            grand_created += r["created"]
            grand_updated += r["updated"]
            grand_skipped += r["skipped"]
            print(f"  {name:55s} +{r['created']} ~{r['updated']} skip={r['skipped']} total={total}", flush=True)

        print(f"DONE: created={grand_created} updated={grand_updated} skipped={grand_skipped}", flush=True)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
