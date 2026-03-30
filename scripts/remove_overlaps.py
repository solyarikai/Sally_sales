import asyncio, httpx

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"
CAMPS = [3070912, 3070913, 3070915, 3070916, 3070917, 3070918, 3070919, 3070920]

OVERLAPS = [
    "ahmed@sharafmedia.ae","algert@sula.me","bj@bjoneal.com","brad@fullhousemedia.com.au",
    "branden@harmonymarketing.us","david@scratchmarketing.com","eduard@braind.am",
    "fletcher@thebrandproject.co","jay@racketmn.com","jesus@lowcode.agency",
    "jmar@thejmarketing.com","kareem@primedigital.me","keryn@toned.co.za",
    "luis@atomodigital.com.ar","marchant@prosperdigital.co.za","max@spinbrands.co.uk",
    "m.maru@bluechipgulf.com","mparks@lsus.edu","mukti@innoventurefintech.com",
    "pradeep@primedigital.asia","rakz@pouncemarketing.com.au","rs@thedigital-agency.com",
    "shaan@chillybin.com.sg","shafyq@wearebellow.com","yulia.antonova@leadex.systems",
]

async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        removed = 0
        for cid in CAMPS:
            for email in OVERLAPS:
                r = await c.post(
                    f"{BASE}/campaigns/{cid}/leads/remove?api_key={API_KEY}",
                    json={"email": email})
                if r.status_code == 200:
                    removed += 1
        print(f"Removed {removed} overlapping leads across {len(CAMPS)} campaigns")

asyncio.run(main())
