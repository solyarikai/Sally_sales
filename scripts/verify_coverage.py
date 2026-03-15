"""
Verify that Rizzult contacts found in GetSales are in CRM.
1. Scan first 10K leads, collect Rizzult lead UUIDs
2. Check which ones exist in CRM contacts table (by getsales_id)
3. Report coverage gap
"""
import asyncio, os, json

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

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.services.crm_sync_service import GetSalesClient, CRMSyncService

    gs = GetSalesClient(os.environ.get("GETSALES_API_KEY", ""))
    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Step 1: Scan first 10K leads for Rizzult contacts
    print("Step 1: Scanning first 10K leads from GetSales API...", flush=True)
    rizzult_leads = {}  # uuid -> lead data
    scanned = 0

    for offset in range(0, 10000, 100):
        leads, total = await gs.search_leads({}, limit=100, offset=offset)
        if not leads:
            break
        for item in leads:
            scanned += 1
            flows = item.get("flows", [])
            if not flows:
                continue
            flow_uuids = {f.get("flow_uuid", "") for f in flows}
            if flow_uuids & RIZZULT_FLOW_UUIDS:
                lead = item.get("lead", item)
                uuid = lead.get("uuid", "")
                if uuid:
                    rizzult_leads[uuid] = {
                        "name": lead.get("name", "?"),
                        "linkedin": lead.get("linkedin_id", ""),
                        "flows": [f.get("flow_uuid", "")[:8] for f in flows if f.get("flow_uuid", "") in RIZZULT_FLOW_UUIDS],
                    }

    print(f"  Scanned {scanned} leads, found {len(rizzult_leads)} unique Rizzult leads", flush=True)

    # Step 2: Check which are in CRM
    print("\nStep 2: Checking CRM coverage...", flush=True)
    async with Session() as session:
        uuids = list(rizzult_leads.keys())
        # Check in batches
        in_crm = set()
        for i in range(0, len(uuids), 100):
            batch = uuids[i:i+100]
            placeholders = ",".join(f"'{u}'" for u in batch)
            result = await session.execute(text(
                f"SELECT getsales_id FROM contacts WHERE getsales_id IN ({placeholders}) AND deleted_at IS NULL"
            ))
            for row in result.fetchall():
                in_crm.add(row[0])

        missing = [uuid for uuid in uuids if uuid not in in_crm]
        print(f"  In CRM: {len(in_crm)}/{len(rizzult_leads)}")
        print(f"  Missing from CRM: {len(missing)}")

        if missing:
            print(f"\n  Missing contacts (first 20):")
            for uuid in missing[:20]:
                info = rizzult_leads[uuid]
                print(f"    {uuid} | {info['name'][:40]} | LI:{info['linkedin'][:20] if info['linkedin'] else 'N/A'} | flows:{info['flows']}")

        # Step 3: Import missing contacts if any
        if missing:
            print(f"\nStep 3: Importing {len(missing)} missing contacts...", flush=True)
            svc = CRMSyncService()
            imported = 0
            for uuid in missing:
                # Re-fetch full lead data for import
                leads, _ = await gs.search_leads({}, limit=1, offset=0)
                # We need to find this specific lead - search by UUID
                # Actually, let's just note them for now
                pass

            # Try to import by re-scanning and processing
            # Actually, let's process them via the sync service
            for offset2 in range(0, 10000, 100):
                leads, _ = await gs.search_leads({}, limit=100, offset=offset2)
                if not leads:
                    break
                for item in leads:
                    lead = item.get("lead", item)
                    uuid = lead.get("uuid", "")
                    if uuid in missing:
                        # Determine list name
                        list_uuid = lead.get("list_uuid", "")
                        list_name = "unknown"
                        result2 = await svc._process_getsales_lead(
                            session, 1, item, list_name, campaign_project_id=22
                        )
                        if result2:
                            imported += 1
                            missing.remove(uuid)

                if not missing:
                    break

            await session.commit()
            print(f"  Imported: {imported}", flush=True)

        # Final count
        r = await session.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE project_id=22 AND getsales_id IS NOT NULL AND deleted_at IS NULL"
        ))
        final = r.scalar()
        print(f"\nFinal CRM Rizzult contacts with getsales_id: {final}")

    await gs.close()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
