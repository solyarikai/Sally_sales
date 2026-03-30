"""Fix ALL settings on ALL 8 campaigns. Settings from user's screenshot:
- Timezone: per campaign
- Active days: Mon-Fri
- Sending window: 09:00-18:00
- Every: 3 minutes
- New leads/day: 1500
- Follow-up priority: 40%
- Stop on reply
- Plain text mode
- Don't track opens/clicks
"""
import asyncio, httpx

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"

CAMPS = [
    (3070912, "America/New_York"),
    (3070913, "America/Los_Angeles"),
    (3070915, "Europe/London"),
    (3070916, "Asia/Dubai"),
    (3070917, "Asia/Kolkata"),
    (3070918, "Asia/Singapore"),
    (3070919, "Australia/Sydney"),
    (3070920, "America/Sao_Paulo"),
]

async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        for cid, tz in CAMPS:
            # 1. Schedule endpoint
            r1 = await c.post(f"{BASE}/campaigns/{cid}/schedule?api_key={API_KEY}", json={
                "timezone": tz,
                "days_of_the_week": [1, 2, 3, 4, 5],
                "start_hour": "09:00",
                "end_hour": "18:00",
                "min_time_btw_emails": 3,
                "max_new_leads_per_day": 1500,
            })
            s1 = "OK" if r1.status_code == 200 else f"{r1.status_code} {r1.text[:80]}"

            # 2. Settings endpoint
            r2 = await c.post(f"{BASE}/campaigns/{cid}/settings?api_key={API_KEY}", json={
                "follow_up_percentage": 40,
                "stop_lead_settings": "REPLY_TO_AN_EMAIL",
                "track_settings": [],
                "send_as_plain_text": True,
            })
            s2 = "OK" if r2.status_code == 200 else f"{r2.status_code}"

            # 3. Try PATCH for fields that schedule endpoint might miss
            r3 = await c.patch(f"{BASE}/campaigns/{cid}?api_key={API_KEY}", json={
                "min_time_btwn_emails": 3,
                "max_leads_per_day": 1500,
            })
            s3 = "OK" if r3.status_code == 200 else f"{r3.status_code}"

            print(f"{cid} ({tz}): schedule={s1} | settings={s2} | patch={s3}")

            # 4. Verify
            r4 = await c.get(f"{BASE}/campaigns/{cid}?api_key={API_KEY}")
            if r4.status_code == 200:
                d = r4.json()
                print(f"  verify: min_time={d.get('min_time_btwn_emails')} max_leads={d.get('max_leads_per_day')} plain={d.get('send_as_plain_text')}")

asyncio.run(main())
