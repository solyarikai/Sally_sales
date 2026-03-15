"""
Scan ALL GetSales leads using the search API and count unique Rizzult leads.
Uses /leads/api/leads/search which supports list_uuid filter.
Also tries no filter to see if we can paginate beyond 10K.
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

    # Test: search without list filter, see total and if we can get flows
    leads, total = await gs.search_leads({}, limit=5, offset=0)
    print(f"Total leads (no filter): {total}")
    if leads:
        item = leads[0]
        has_flows = "flows" in item
        flow_count = len(item.get("flows", []))
        print(f"First item has flows: {has_flows}, flow count: {flow_count}")

    # Test: can we paginate to offset 9900?
    leads_9k, total_9k = await gs.search_leads({}, limit=100, offset=9900)
    print(f"Offset 9900: got {len(leads_9k)} leads, total={total_9k}")

    # Test: offset 10000 (should fail with 10K limit)
    try:
        leads_10k, total_10k = await gs.search_leads({}, limit=100, offset=10000)
        print(f"Offset 10000: got {len(leads_10k)} leads, total={total_10k}")
    except Exception as e:
        print(f"Offset 10000: ERROR {e}")

    # Key insight: we need to scan by list. Get ALL lists including potential hidden ones.
    lists = await gs.get_lists()
    print(f"\nTotal lists: {len(lists)}")

    # Scan first 10K without filter to count Rizzult contacts
    print("\n=== Scanning first 10K leads (no filter) for Rizzult flows ===")
    rizzult_uuids = set()
    non_rizzult_count = 0
    no_flows_count = 0
    scanned = 0

    for offset in range(0, 10000, 100):
        leads, total = await gs.search_leads({}, limit=100, offset=offset)
        if not leads:
            break
        for item in leads:
            scanned += 1
            flows = item.get("flows", [])
            if not flows:
                no_flows_count += 1
                continue
            flow_uuids = {f.get("flow_uuid", "") for f in flows}
            if flow_uuids & RIZZULT_FLOW_UUIDS:
                lead = item.get("lead", item)
                rizzult_uuids.add(lead.get("uuid", ""))
            else:
                non_rizzult_count += 1

        if scanned % 1000 == 0:
            print(f"  Scanned {scanned}: rizzult={len(rizzult_uuids)}, non_rizzult={non_rizzult_count}, no_flows={no_flows_count}", flush=True)

    print(f"\nFinal (first 10K): scanned={scanned}, rizzult={len(rizzult_uuids)}, non_rizzult={non_rizzult_count}, no_flows={no_flows_count}")

    await gs.close()

if __name__ == "__main__":
    asyncio.run(main())
