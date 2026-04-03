"""Check GetSales flows and their sender profiles."""
import asyncio
import json
import os
from app.services.crm_sync_service import GetSalesClient


async def main():
    gs = GetSalesClient(os.environ["GETSALES_API_KEY"])
    try:
        flows = await gs.get_flows()
        print(f"Total flows: {len(flows)}")
        print("=" * 140)
        for f in flows:
            uuid = f.get("uuid", "?")
            name = f.get("name", "?")
            status = f.get("status", "?")
            sender_uuid = f.get("sender_profile_uuid") or "none"
            sender = f.get("sender_profile")
            if isinstance(sender, dict):
                sp_name = f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip()
            else:
                sp_name = "?"
            print(f"  flow={uuid}  sender={sender_uuid}  [{status:10s}]  {name:45s}  (profile: {sp_name})")
    finally:
        await gs.close()


asyncio.run(main())
