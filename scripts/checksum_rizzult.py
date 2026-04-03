"""
Build checksum: GetSales flows/metrics FACT vs CRM contacts per flow.
"""
import asyncio, os, json, httpx

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
    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient(timeout=30) as client:
        # Get flow names
        flows_resp = await client.post(
            "https://amazing.getsales.io/flows/c3/api/flows/list",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"page": 1, "per_page": 100, "order_field": "created_at", "order_type": "desc"}
        )
        flows_data = flows_resp.json().get("data", [])
        uuid_to_name = {}
        for f in flows_data:
            if f.get("uuid") in RIZZULT_FLOW_UUIDS:
                uuid_to_name[f["uuid"]] = f.get("name", f["uuid"][:20])

        # Also check pages 2-5 for any missed flows
        for pg in range(2, 6):
            resp = await client.post(
                "https://amazing.getsales.io/flows/c3/api/flows/list",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"page": pg, "per_page": 100, "order_field": "created_at", "order_type": "desc"}
            )
            for f in resp.json().get("data", []):
                if f.get("uuid") in RIZZULT_FLOW_UUIDS:
                    uuid_to_name[f["uuid"]] = f.get("name", f["uuid"][:20])

        # Get metrics
        metrics_resp = await client.post(
            "https://amazing.getsales.io/flows/c3/api/flows/metrics",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"uuids": RIZZULT_FLOW_UUIDS}
        )
        metrics = metrics_resp.json()

    # Get CRM counts per flow name
    async with Session() as session:
        result = await session.execute(text("""
            SELECT
                flow_name,
                COUNT(*) as cnt
            FROM (
                SELECT
                    TRIM(unnest(string_to_array(getsales_raw->>'active_flows', ','))) as flow_name
                FROM contacts
                WHERE project_id = 22 AND getsales_id IS NOT NULL AND deleted_at IS NULL
                    AND getsales_raw->>'active_flows' IS NOT NULL AND getsales_raw->>'active_flows' != ''
            ) sub
            WHERE flow_name != ''
            GROUP BY flow_name
        """))
        crm_per_flow = {row[0]: row[1] for row in result.fetchall()}

        # Total CRM counts
        r = await session.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE project_id=22 AND getsales_id IS NOT NULL AND deleted_at IS NULL"
        ))
        total_gs_crm = r.scalar()

        r = await session.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE project_id=22 AND deleted_at IS NULL"
        ))
        total_crm = r.scalar()

    # Build checksum table
    print()
    print(f"{'Flow Name':55s} {'GS Total':>9} {'GS Active':>10} {'CRM':>6} {'Gap':>6}")
    print("=" * 90)

    rows = []
    for uuid in RIZZULT_FLOW_UUIDS:
        m = metrics.get(uuid, {})
        name = uuid_to_name.get(uuid, uuid[:30])
        total = m.get("leads_count", 0)
        active = m.get("in_progress_leads_count", 0)
        crm_count = crm_per_flow.get(name, 0)
        rows.append((name, total, active, crm_count))

    rows.sort(key=lambda r: -r[1])
    grand_gs = 0
    grand_active = 0
    grand_crm = 0
    for name, total, active, crm_count in rows:
        gap = total - crm_count
        print(f"{name:55s} {total:>9} {active:>10} {crm_count:>6} {gap:>+6}")
        grand_gs += total
        grand_active += active
        grand_crm += crm_count

    print("=" * 90)
    print(f"{'CUMULATIVE FLOW SLOTS':55s} {grand_gs:>9} {grand_active:>10} {grand_crm:>6}")
    print()
    print(f"NOTE: Cumulative = same contact counted once per flow.")
    print(f"      CRM column = contacts whose CSV active_flows field mentions this flow name.")
    print(f"      Many contacts have NO active_flows data (imported via list-based API sync).")
    print()
    print(f"CRM Rizzult contacts with getsales_id: {total_gs_crm}")
    print(f"CRM Rizzult contacts total (incl SmartLead): {total_crm}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
