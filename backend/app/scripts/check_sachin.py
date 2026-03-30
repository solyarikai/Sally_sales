"""Quick check: does Sachin Singh's reply exist in SmartLead?"""
import asyncio
import httpx
import json
import sys

async def check():
    api_key = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
    url = f"https://server.smartlead.ai/api/v1/campaigns/3050419/leads/3485866127/message-history?api_key={api_key}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        print(f"Status: {r.status_code}, Length: {len(r.text)}")
        try:
            data = r.json()
            if isinstance(data, list):
                print(f"Messages: {len(data)}")
                for msg in data:
                    t = msg.get("type", "?")
                    time_val = msg.get("time", "?")
                    body = str(msg.get("message_text") or msg.get("text") or msg.get("body") or "")[:120]
                    print(f"  [{t}] {time_val}: {body}")
            else:
                print(json.dumps(data, indent=2, default=str)[:500])
        except Exception as e:
            print(f"Parse error: {e}")
            print(r.text[:500])

asyncio.run(check())
