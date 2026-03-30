import asyncio, httpx

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"
CAMPS = [3070912, 3070913, 3070915, 3070916, 3070917, 3070918, 3070919, 3070920]

STEP1 = "Hi {{first_name}},<br><br>We at Easystaff help companies pay freelancers globally with fees under 1% - zero fees for your freelancers.<br><br>You can pay contractors via cards, PayPal, and USDT wallets - all paperwork handled by us.<br><br>Recently helped a {{city}} agency switch from Deel to paying 50 contractors across 8 countries, saving them $4,000/month on platform fees and exchange rates.<br><br>Would you like to calculate the cost benefit for your case?<br><br>%sender_name%<br>BDM, Easystaff<br>Trusted by 5,000+ teams worldwide"

async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        for cid in CAMPS:
            r = await c.get(f"{BASE}/campaigns/{cid}/sequences?api_key={API_KEY}")
            if r.status_code != 200 or not r.json():
                print(f"{cid}: skip")
                continue
            seqs = r.json()
            # Build clean sequences for POST (only allowed fields)
            clean = []
            for s in seqs:
                dets = s.get("seq_delay_details", {})
                delay = dets.get("delay_in_days", dets.get("delayInDays", 0))
                body = s.get("email_body", "")
                if s.get("seq_number") == 1:
                    body = STEP1
                clean.append({
                    "seq_number": s["seq_number"],
                    "seq_delay_details": {"delay_in_days": delay},
                    "subject": s.get("subject", ""),
                    "email_body": body,
                })
            r2 = await c.post(f"{BASE}/campaigns/{cid}/sequences?api_key={API_KEY}", json={"sequences": clean})
            print(f"{cid}: {'OK' if r2.status_code == 200 else r2.text[:80]}")

asyncio.run(main())
