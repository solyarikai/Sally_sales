"""
Scan ALL GetSales leads by chunking through data sources.
Each data source has its own 10K limit but should be under that.
Count unique Rizzult leads across all data sources.
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
    from app.services.crm_sync_service import GetSalesClient

    gs = GetSalesClient(os.environ.get("GETSALES_API_KEY", ""))

    # Get all data sources
    sources = await gs.get_data_sources()
    print(f"Total data sources: {len(sources)}")

    rizzult_uuids = set()
    total_scanned = 0
    sources_with_rizzult = []

    for i, src in enumerate(sources):
        src_uuid = src.get("uuid", "")
        src_name = src.get("name", "?")

        # Get total for this source
        leads, total = await gs.search_leads({"data_source_uuid": src_uuid}, limit=1, offset=0)
        if total == 0:
            continue

        # Scan all leads in this data source
        ds_rizzult = 0
        ds_scanned = 0
        offset = 0
        while offset < min(total, 9900):
            leads, _ = await gs.search_leads({"data_source_uuid": src_uuid}, limit=100, offset=offset)
            if not leads:
                break
            for item in leads:
                ds_scanned += 1
                total_scanned += 1
                flows = item.get("flows", [])
                if not flows:
                    continue
                flow_uuids = {f.get("flow_uuid", "") for f in flows}
                if flow_uuids & RIZZULT_FLOW_UUIDS:
                    lead = item.get("lead", item)
                    uuid = lead.get("uuid", "")
                    if uuid and uuid not in rizzult_uuids:
                        rizzult_uuids.add(uuid)
                        ds_rizzult += 1
            offset += 100

        if ds_rizzult > 0:
            sources_with_rizzult.append((src_name, ds_scanned, ds_rizzult))
            print(f"  [{i+1}/{len(sources)}] {src_name:55s} scanned={ds_scanned:>6} rizzult={ds_rizzult:>4} (cumul={len(rizzult_uuids)})", flush=True)
        elif ds_scanned > 500:
            print(f"  [{i+1}/{len(sources)}] {src_name:55s} scanned={ds_scanned:>6} rizzult=0", flush=True)

    print(f"\n{'='*80}")
    print(f"RESULT: {len(rizzult_uuids)} unique Rizzult leads found across {len(sources)} data sources")
    print(f"Total scanned: {total_scanned}")
    print(f"\nData sources with Rizzult contacts:")
    for name, scanned, count in sources_with_rizzult:
        print(f"  {name:55s} scanned={scanned:>6} rizzult={count:>4}")

    await gs.close()

if __name__ == "__main__":
    asyncio.run(main())
