"""Check if GetSales leads/search API returns flows data per contact."""
import asyncio, os, json

async def main():
    from app.services.crm_sync_service import GetSalesClient
    gs = GetSalesClient(os.environ.get("GETSALES_API_KEY", ""))

    # Get lists
    lists = await gs.get_lists()
    rizzult_list = None
    non_rizzult_list = None
    for l in lists:
        name = l.get("name", "").lower()
        if "rizzult" in name and not rizzult_list:
            rizzult_list = l
        elif "rizzult" not in name and not non_rizzult_list:
            non_rizzult_list = l

    for label, lst in [("RIZZULT", rizzult_list), ("NON-RIZZULT", non_rizzult_list)]:
        if not lst:
            continue
        print(f"\n=== {label} list: {lst['name']} ===")
        leads, total = await gs.search_leads({"list_uuid": lst["uuid"]}, limit=2, offset=0)
        if leads:
            lead = leads[0]
            print(f"Keys: {list(lead.keys())}")
            print(f"HAS 'flows': {'flows' in lead}")
            print(f"HAS 'lead': {'lead' in lead}")
            if "flows" in lead:
                print(f"Flows count: {len(lead['flows'])}")
                for f in lead["flows"][:3]:
                    print(f"  Flow: {json.dumps(f)[:200]}")
            if "lead" in lead:
                sub = lead["lead"]
                print(f"lead sub-keys: {list(sub.keys())[:15]}")

    await gs.close()

if __name__ == "__main__":
    asyncio.run(main())
