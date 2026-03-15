"""
Discover ALL list UUIDs (including deleted ones) from lead data.
1. Scan first 10K leads to collect unique list_uuids
2. Compare with current 20 lists
3. For each discovered list, scan for Rizzult contacts
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

    # Get current lists
    current_lists = await gs.get_lists()
    current_uuids = {l["uuid"] for l in current_lists}
    print(f"Current lists: {len(current_uuids)}")

    # Scan first 10K to discover all list UUIDs
    print("Scanning first 10K leads to discover list UUIDs...", flush=True)
    all_list_uuids = {}
    for offset in range(0, 10000, 100):
        leads, _ = await gs.search_leads({}, limit=100, offset=offset)
        if not leads:
            break
        for item in leads:
            lead = item.get("lead", item)
            luuid = lead.get("list_uuid", "")
            if luuid:
                if luuid not in all_list_uuids:
                    all_list_uuids[luuid] = {"count": 0, "is_current": luuid in current_uuids}
                all_list_uuids[luuid]["count"] += 1

    print(f"Discovered {len(all_list_uuids)} unique list UUIDs")
    old_lists = {k: v for k, v in all_list_uuids.items() if not v["is_current"]}
    print(f"Old/deleted lists: {len(old_lists)}")

    # For each list (current + old), scan and count Rizzult contacts
    print(f"\nScanning ALL lists ({len(all_list_uuids)} total) for Rizzult contacts...", flush=True)
    rizzult_uuids = set()
    total_scanned = 0

    all_list_ids = list(all_list_uuids.keys())
    for i, luuid in enumerate(all_list_ids):
        info = all_list_uuids[luuid]
        # Get total for this list
        _, total = await gs.search_leads({"list_uuid": luuid}, limit=1, offset=0)
        if total == 0:
            continue

        list_rizzult = 0
        list_scanned = 0
        offset = 0
        while offset < min(total, 9500):
            leads, _ = await gs.search_leads({"list_uuid": luuid}, limit=100, offset=offset)
            if not leads:
                break
            for item in leads:
                list_scanned += 1
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
                        list_rizzult += 1
            offset += 100

        marker = "(current)" if info["is_current"] else "(OLD)"
        if list_rizzult > 0 or total > 500:
            print(f"  [{i+1}/{len(all_list_ids)}] {luuid[:12]}... {marker:10s} total={total:>6} scanned={list_scanned:>6} rizzult={list_rizzult:>4} (cumul={len(rizzult_uuids)})", flush=True)

    print(f"\n{'='*80}")
    print(f"TOTAL UNIQUE RIZZULT LEADS FOUND: {len(rizzult_uuids)}")
    print(f"Total leads scanned: {total_scanned}")
    print(f"Lists scanned: {len(all_list_ids)} ({len(current_uuids)} current + {len(old_lists)} old)")

    await gs.close()

if __name__ == "__main__":
    asyncio.run(main())
