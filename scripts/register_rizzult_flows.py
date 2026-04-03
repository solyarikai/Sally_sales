"""
Register all Rizzult GetSales flows in the campaigns table.
This enables the flow cache for auto-project-assignment during sync.
"""
import asyncio, os, httpx

RIZZULT_FLOW_UUIDS = [
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
]

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    api_key = os.environ.get("GETSALES_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Fetch flow names from API (with dedup across pages)
    uuid_to_name = {}
    async with httpx.AsyncClient(timeout=15) as client:
        seen_uuids = set()
        for pg in range(1, 20):
            resp = await client.post(
                "https://amazing.getsales.io/flows/c3/api/flows/list",
                headers=headers,
                json={"page": pg, "per_page": 100, "order_field": "created_at", "order_type": "desc"}
            )
            flows = resp.json().get("data", [])
            new_in_page = 0
            for f in flows:
                uuid = f.get("uuid", "")
                if uuid not in seen_uuids:
                    seen_uuids.add(uuid)
                    new_in_page += 1
                    if uuid in RIZZULT_FLOW_UUIDS:
                        uuid_to_name[uuid] = f.get("name", f"rizzult_flow_{uuid[:8]}")
            if new_in_page == 0:
                break  # No new flows, pagination loop

    print(f"Found names for {len(uuid_to_name)}/{len(RIZZULT_FLOW_UUIDS)} Rizzult flows")
    for uuid, name in sorted(uuid_to_name.items(), key=lambda x: x[1]):
        print(f"  {uuid} → {name}")

    # Check which are already registered
    async with Session() as session:
        result = await session.execute(text(
            "SELECT external_id FROM campaigns WHERE platform = 'getsales' AND external_id = ANY(:uuids)"
        ), {"uuids": RIZZULT_FLOW_UUIDS})
        existing = {row[0] for row in result.fetchall()}
        print(f"\nAlready registered: {len(existing)}")

        # Register missing flows
        missing = set(RIZZULT_FLOW_UUIDS) - existing
        registered = 0
        for uuid in missing:
            name = uuid_to_name.get(uuid, f"Rizzult flow {uuid[:8]}")
            await session.execute(text("""
                INSERT INTO campaigns (company_id, project_id, platform, external_id, name, status, created_at, updated_at)
                VALUES (1, 22, 'getsales', :ext_id, :name, 'active', NOW(), NOW())
                ON CONFLICT (external_id, platform) DO UPDATE SET
                    name = EXCLUDED.name,
                    project_id = COALESCE(campaigns.project_id, 22)
            """), {"ext_id": uuid, "name": name})
            registered += 1
            print(f"  Registered: {name} ({uuid})")

        await session.commit()
        print(f"\nNewly registered: {registered}")

        # Verify
        result = await session.execute(text(
            "SELECT external_id, name, project_id FROM campaigns WHERE platform = 'getsales' AND project_id = 22 ORDER BY name"
        ))
        all_rizzult = result.fetchall()
        print(f"\nAll Rizzult GetSales campaigns: {len(all_rizzult)}")
        for ext, name, pid in all_rizzult:
            print(f"  {ext[:12]}... {name}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
