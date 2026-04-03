"""
Pull Rizzult contacts from GetSales by iterating all lists.
Uses the list-based approach (bypasses 10K offset limit per list).
Checks each contact's flows to see if they're in any Rizzult flow.

Run on server: docker exec -it leadgen-backend python3 /app/scripts/sync_getsales_rizzult.py
"""
import asyncio
import json
import os
import sys

RIZZULT_FLOW_UUIDS = {
    "9515a70b-0020-4955-8bea-9c2f7b904be8", "779377b5-4856-4f0e-b028-19ebff994dce",
    "3323b4f3-d0e9-427e-9540-191e10b8d4d7", "5a8628e0-f8b5-43f7-9477-0bd825bb7ee5",
    "0089aa05-f8a3-4a0b-ab94-00db9603dd7d", "df157019-c1fb-4562-b136-b92c9a9c99ab",
    "60b1ab51-5139-4256-a2fa-92bd88252d7d", "8c164da8-d63c-42b9-9a83-1c5e7194d5ba",
    "65a4fa58-434a-4760-a6e7-dc6ce3903ff6", "4bbd26d3-706b-4168-9262-d70fe09a5b25",
    "23f9f8fa-a1e3-4871-8ca9-8bdb983c9342", "822cb361-7b5f-4432-bef1-5408ae1b1d8b",
    "b88fda57-2d47-46a5-91bc-01cc33f73c90", "0e9ecb75-919a-4491-b7ac-6e774028722b",
    "6bfeca8c-23a6-49da-a8e8-b0dacae88857", "1e18fad6-2d9d-4ec8-8256-9850a6ea43bc",
    "10120436-8605-448b-80f0-f2a25730163d", "ef930f4c-c113-4d80-bea6-492ff60b68cf",
    "f917f58a-2b77-4613-9adb-63ca94183dac", "1450e076-dd6f-4d10-a193-eb6a1a92e692",
    "497cae2b-1b79-40cf-84d7-4c92bb0ace64", "b002e2fc-d647-491f-808f-89af1ac671f0",
    "b2182d2f-45d2-4174-b388-d43f644b84b4",
}
PROJECT_ID = 22


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.services.crm_sync_service import CRMSyncService

    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    svc = CRMSyncService()
    gs = svc.getsales
    if not gs:
        print("ERROR: GetSales not configured")
        return

    print("=== GetSales → CRM Rizzult Contact Sync (List-Based) ===", flush=True)

    # Step 1: Get all lists
    lists = await gs.get_lists()
    print(f"Found {len(lists)} lists", flush=True)

    # Step 2: Iterate each list and find Rizzult contacts
    rizzult_uuids = set()
    total_scanned = 0
    rizzult_found = 0

    async with Session() as session:
        for lst in lists:
            list_uuid = lst.get("uuid")
            list_name = lst.get("name", "?")
            offset = 0
            list_total = 0
            list_rizzult = 0

            while True:
                leads, total = await gs.get_leads_by_list(list_uuid, limit=100, offset=offset)
                if not leads:
                    break

                for item in leads:
                    lead = item.get("lead", item)
                    lead_uuid = lead.get("uuid", "")
                    total_scanned += 1

                    # Check flows
                    flows = item.get("flows", [])
                    flow_uuids = {f.get("flow_uuid", "") for f in flows}
                    is_rizzult = bool(flow_uuids & RIZZULT_FLOW_UUIDS)

                    # Also check by list name
                    if not is_rizzult and "rizzult" in list_name.lower():
                        is_rizzult = True

                    if is_rizzult and lead_uuid not in rizzult_uuids:
                        rizzult_uuids.add(lead_uuid)
                        rizzult_found += 1
                        list_rizzult += 1

                        # Process this lead through the CRM sync
                        result = await svc._process_getsales_lead(
                            session, 1, item, list_name, campaign_project_id=PROJECT_ID
                        )

                list_total += len(leads)
                offset += 100
                if offset >= total or offset >= 9500:
                    break

            if list_total > 0:
                print(f"  {list_name:55s} scanned={list_total:>5} rizzult={list_rizzult:>4}", flush=True)
            await session.commit()

        # Step 3: Also assign any existing unassigned contacts with rizzult in getsales_raw
        print("\nStep 3: Assigning unassigned contacts with rizzult in getsales_raw...", flush=True)
        result = await session.execute(text(
            "UPDATE contacts SET project_id = 22 "
            "WHERE project_id IS NULL AND getsales_id IS NOT NULL AND deleted_at IS NULL "
            "AND LOWER(getsales_raw::text) LIKE '%rizzult%'"
        ))
        assigned = result.rowcount
        await session.commit()
        print(f"  Assigned {assigned} orphan contacts", flush=True)

        # Step 4: Verify
        print("\nStep 4: Final verification...", flush=True)
        r = await session.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE project_id = 22 AND deleted_at IS NULL"
        ))
        total = r.scalar()
        r = await session.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE project_id = 22 AND getsales_id IS NOT NULL AND deleted_at IS NULL"
        ))
        gs_count = r.scalar()
        r = await session.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE project_id = 22 AND smartlead_id IS NOT NULL AND deleted_at IS NULL"
        ))
        sl_count = r.scalar()

        print(f"  Total Rizzult contacts: {total}", flush=True)
        print(f"  With getsales_id: {gs_count}", flush=True)
        print(f"  With smartlead_id: {sl_count}", flush=True)
        print(f"  GetSales API unique Rizzult leads found: {rizzult_found}", flush=True)
        print(f"  Total contacts scanned: {total_scanned}", flush=True)

    await engine.dispose()
    print("\nDONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
