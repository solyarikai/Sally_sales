"""
Test that the auto-assignment works in sync_getsales_contacts.
1. Refresh flow cache
2. Pick a Rizzult contact from GetSales API
3. Process it via _process_getsales_lead WITHOUT explicit campaign_project_id
4. Verify it gets assigned to project 22
"""
import asyncio, os

RIZZULT_FLOW_UUIDS = {
    "9515a70b-0020-4955-8bea-9c2f7b904be8", "779377b5-4856-4f0e-b028-19ebff994dce",
    "3323b4f3-d0e9-427e-9540-191e10b8d4d7",
}

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.services.crm_sync_service import CRMSyncService, refresh_getsales_flow_cache, refresh_project_prefixes, _getsales_flow_cache

    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Refresh caches
    await refresh_getsales_flow_cache()
    await refresh_project_prefixes()
    print(f"Flow cache has {len(_getsales_flow_cache)} entries")

    # Check Rizzult flows in cache
    rizzult_in_cache = {k: v for k, v in _getsales_flow_cache.items() if 'rizzult' in v.lower()}
    print(f"Rizzult flows in cache: {len(rizzult_in_cache)}")
    for uuid, name in list(rizzult_in_cache.items())[:5]:
        print(f"  {uuid[:12]}... → {name}")

    svc = CRMSyncService()
    gs = svc.getsales

    # Find a Rizzult contact from the API
    lists = await gs.get_lists()
    rizzult_list = next((l for l in lists if 'rizzult' in l.get('name', '').lower()), None)
    if not rizzult_list:
        print("No rizzult list found!")
        return

    leads, total = await gs.search_leads({"list_uuid": rizzult_list["uuid"]}, limit=1, offset=0)
    if not leads:
        print("No leads found!")
        return

    item = leads[0]
    lead = item.get("lead", {})
    uuid = lead.get("uuid", "")
    flows = item.get("flows", [])
    flow_uuids = [f.get("flow_uuid", "") for f in flows]
    print(f"\nTest lead: {lead.get('name', '?')} ({uuid[:12]}...)")
    print(f"  Flows: {flow_uuids}")

    async with Session() as session:
        # Process WITHOUT explicit campaign_project_id
        result = await svc._process_getsales_lead(
            session, 1, item, rizzult_list.get("name"),
            campaign_project_id=None  # NOT explicitly set!
        )
        print(f"  Process result: {result}")

        # Check what project was assigned
        r = await session.execute(text(
            f"SELECT project_id FROM contacts WHERE getsales_id = '{uuid}' AND deleted_at IS NULL"
        ))
        row = r.fetchone()
        if row:
            pid = row[0]
            print(f"  Project assigned: {pid}")
            if pid == 22:
                print("  AUTO-ASSIGNMENT WORKS!")
            else:
                print(f"  WARNING: Expected project 22, got {pid}")
        else:
            print("  Contact not found (might need commit)")

        await session.rollback()  # Don't persist test changes

    await gs.close()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
