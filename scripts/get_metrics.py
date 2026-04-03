"""Fetch flows/metrics for Rizzult flows and output JSON."""
import asyncio, os, json, httpx

RIZZULT_FLOW_UUIDS = [
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
]

# Flow UUID → name mapping (from /flows/c3/api/flows/list)
FLOW_NAMES = {
    "9515a70b-0020-4955-8bea-9c2f7b904be8": "RIzzult big 5 agencies 27 02 26",
    "779377b5-4856-4f0e-b028-19ebff994dce": "RIzzult Telemed 20 02 26",
    "3323b4f3-d0e9-427e-9540-191e10b8d4d7": "RIzzult partner agencies Miami 20 02 26 networking msg",
    "5a8628e0-f8b5-43f7-9477-0bd825bb7ee5": "RIzzult partner agencies 15 02 26",
    "0089aa05-f8a3-4a0b-ab94-00db9603dd7d": "RIzzult Farmacies 14 02 26",
    "df157019-c1fb-4562-b136-b92c9a9c99ab": "RIzzult Streaming 14 02 26",
    "60b1ab51-5139-4256-a2fa-92bd88252d7d": "RIzzult Cleaning 14 02 26",
    "8c164da8-d63c-42b9-9a83-1c5e7194d5ba": "RIzzult_Food&Drink apps 02 02 26",
    "65a4fa58-434a-4760-a6e7-dc6ce3903ff6": "Rizzult_fintech_new",
    "4bbd26d3-706b-4168-9262-d70fe09a5b25": "RIzzult_Fintech_FU2+_20.11.25",
    "23f9f8fa-a1e3-4871-8ca9-8bdb983c9342": "RIzzult_Fintech_LVPR_20.11.25",
    "822cb361-7b5f-4432-bef1-5408ae1b1d8b": "RIzzult_Fintech_LPR_20.11.25",
    "b88fda57-2d47-46a5-91bc-01cc33f73c90": "RIzzult_QSR_LPR_20.11.25",
    "0e9ecb75-919a-4491-b7ac-6e774028722b": "RIzzult_QSR_LVPR_20.11.25",
    "6bfeca8c-23a6-49da-a8e8-b0dacae88857": "RIzzult_Foodtech_LPR_23.11.25",
    "1e18fad6-2d9d-4ec8-8256-9850a6ea43bc": "RIzzult_Foodtech_FU_18.01.26",
    "10120436-8605-448b-80f0-f2a25730163d": "RIzzult_Agencies_20.11.25",
    "ef930f4c-c113-4d80-bea6-492ff60b68cf": "Rizzult_shopping_apps",
    "f917f58a-2b77-4613-9adb-63ca94183dac": "RIzzult_Foodtech_LVPR_23.11.25",
    "1450e076-dd6f-4d10-a193-eb6a1a92e692": "RIzzult_Fintech_FU_18.01.26",
    "497cae2b-1b79-40cf-84d7-4c92bb0ace64": "Rizzult_QSR",
    "b002e2fc-d647-491f-808f-89af1ac671f0": "Rizzult_Foodtech",
    "b2182d2f-45d2-4174-b388-d43f644b84b4": "RIzzult_Shopping_FU2+_20.11.25",
}

async def main():
    api_key = os.environ.get("GETSALES_API_KEY", "")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://amazing.getsales.io/flows/c3/api/flows/metrics",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"uuids": RIZZULT_FLOW_UUIDS}
        )
        resp.raise_for_status()
        data = resp.json()

    grand_total = 0
    grand_active = 0
    grand_done = 0
    grand_fail = 0
    rows = []
    for uuid in RIZZULT_FLOW_UUIDS:
        m = data.get(uuid, {})
        total = m.get("leads_count", 0)
        active = m.get("in_progress_leads_count", 0)
        done = m.get("finished_leads_count", 0)
        fail = m.get("failed_leads_count", 0)
        name = FLOW_NAMES.get(uuid, uuid[:20])
        rows.append((name, total, active, done, fail))
        grand_total += total
        grand_active += active
        grand_done += done
        grand_fail += fail

    rows.sort(key=lambda r: -r[1])
    print(f"{'Flow Name':55s} {'Total':>6} {'Active':>7} {'Done':>6} {'Fail':>6}")
    print("-" * 85)
    for name, total, active, done, fail in rows:
        print(f"{name:55s} {total:>6} {active:>7} {done:>6} {fail:>6}")
    print("-" * 85)
    print(f"{'GRAND TOTAL':55s} {grand_total:>6} {grand_active:>7} {grand_done:>6} {grand_fail:>6}")

if __name__ == "__main__":
    asyncio.run(main())
