"""List latest Deliryo campaigns from SmartLead."""
import asyncio
import os
import httpx


async def main():
    api_key = os.environ.get("SMARTLEAD_API_KEY")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"https://server.smartlead.ai/api/v1/campaigns?api_key={api_key}")
        campaigns = r.json()
        deliryo = [c for c in campaigns if "deliryo" in (c.get("name", "") or "").lower()]

        # Sort by ID descending (higher ID = more recent)
        deliryo.sort(key=lambda x: x.get("id", 0), reverse=True)

        print(f"Latest 20 Deliryo campaigns (of {len(deliryo)} total):")
        print()
        for c in deliryo[:20]:
            cid = c["id"]
            name = c["name"]
            status = c.get("status", "?")
            created = c.get("created_at", "?")
            created_str = created[:10] if created and created != "?" else "?"
            print(f"  {cid} | {status:10s} | {created_str} | {name}")

        # Get lead counts for the latest 20
        print()
        print("Lead counts for latest 20:")
        for c in deliryo[:20]:
            cid = c["id"]
            name = c["name"]
            try:
                r2 = await client.get(
                    f"https://server.smartlead.ai/api/v1/campaigns/{cid}/leads",
                    params={"api_key": api_key, "offset": 0, "limit": 1},
                )
                data = r2.json()
                total = data.get("total_leads", "?") if isinstance(data, dict) else "?"
                print(f"  {cid} | {total:>6s} leads | {name}")
            except Exception as e:
                print(f"  {cid} | error | {name}: {e}")


asyncio.run(main())
