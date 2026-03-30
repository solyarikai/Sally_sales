"""Fix EVERYTHING on ALL campaigns - inboxes, settings, sequences.
Covers both old IDs (3070908-3070920) and new IDs (3070912-3070920)."""
import asyncio, httpx

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"

# ALL possible campaign IDs (covering duplicates)
ALL_CAMPS = {
    3070908: "America/New_York",    # duplicate US-East
    3070912: "America/New_York",
    3070909: "America/Los_Angeles", # possible duplicate
    3070913: "America/Los_Angeles",
    3070910: "Europe/London",       # possible duplicate
    3070915: "Europe/London",
    3070911: "Asia/Dubai",          # possible duplicate
    3070916: "Asia/Dubai",
    3070917: "Asia/Kolkata",
    3070918: "Asia/Singapore",
    3070919: "Australia/Sydney",
    3070920: "America/Sao_Paulo",
}

# Inbox IDs we already found
INBOX_IDS = []  # Will be populated

SEQS = [
    {"seq_number": 1, "seq_delay_details": {"delay_in_days": 0},
     "subject": "{{first_name}} - paying freelancers abroad?",
     "email_body": "Hi {{first_name}},<br><br>We at Easystaff help companies pay freelancers globally with fees under 1% - zero fees for your freelancers.<br><br>You can pay contractors via cards, PayPal, and USDT wallets - all paperwork handled by us.<br><br>Recently helped a {{city}} agency switch from Deel to paying 50 contractors across 8 countries, saving them $4,000/month on platform fees and exchange rates.<br><br>Would you like to calculate the cost benefit for your case?<br><br>{{sender_name}}<br>BDM, Easystaff<br>Trusted by 5,000+ teams worldwide"},
    {"seq_number": 2, "seq_delay_details": {"delay_in_days": 3}, "subject": "",
     "email_body": "Hi {{first_name}},<br><br>Following up. Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility.<br><br>We offer a better way:<br>- Cut out the middleman: Save the 10-20% freelance marketplace fees<br>- No annual contracts: Pay only for what you use<br>- Same-day payouts to any country, real human support (no bots)<br>- One compliant B2B invoice for all freelancer payments<br><br>Open to a quick demo call this week?"},
    {"seq_number": 3, "seq_delay_details": {"delay_in_days": 4}, "subject": "",
     "email_body": "Hi {{first_name}},<br><br>Just making sure my emails are getting through.<br><br>Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.<br><br>For 50+ contractors/month, we offer custom rates below any competitor.<br><br>Can I send you a 2-minute walkthrough video?"},
    {"seq_number": 4, "seq_delay_details": {"delay_in_days": 7}, "subject": "",
     "email_body": "Would it be easier to connect on LinkedIn or Telegram?<br><br>If you already have a payment solution, happy to compare - many clients switch after seeing the total cost difference.<br><br>Sent from my iPhone"},
]

TARGET_EMAILS = {
    "rinat.k@crona-hq.com","rinat.k@growwith-crona.com","petr@crona-track.com","petr@prospects-crona.com",
    "rinat@crona-b2b.com","rinat@crona-base.com","rinat@crona-force.com","rinat@crona-flow.com",
    "rinat@segment-crona.com","rinat@leads-crona.com","rinat@prospects-crona.com","rinat@crona-stack.com",
    "rinat@crona-track.com","rinat@growth-crona.com","petr@cronaaidata.com","petr@cronaaisegment.com",
    "petr@cronaaitarget.com","rinat@cronaaidata.com","rinat@cronaaitarget.com","rinat@cronaaileads.com",
    "rinat@cronaaipipeline.com","rinat@cronaaiprospects.com","petr@cronaaiedge.com","petr@cronaaiflow.com",
    "petr@cronaaiforce.com","petr@cronaaihq.com","petr@cronaaireach.com","petr@cronaaisales.com",
    "petr@cronaaisync.com","petr@cronaaitrack.com","petr@growthcronaai.com","petr@growwithcronaai.com",
    "petr@leadscronaai.com","petr@scalecronaai.com","petr@usecronaai.com","rinat@cronaaiedge.com",
    "rinat@cronaaiflow.com","rinat@cronaaiforce.com","rinat@cronaaihq.com","rinat@cronaaireach.com",
    "rinat@cronaaisales.com","rinat@cronaaisync.com","rinat@cronaaitrack.com","rinat@growthcronaai.com",
    "rinat@growwithcronaai.com","rinat@leadscronaai.com","rinat@scalecronaai.com","rinat@usecronaai.com",
}


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        # 1. Get ALL inbox IDs
        print("Getting inboxes...")
        all_accs = []
        for offset in range(0, 600, 100):
            r = await c.get(f"{BASE}/email-accounts?api_key={API_KEY}&limit=100&offset={offset}")
            if r.status_code != 200:
                break
            data = r.json()
            if not isinstance(data, list) or not data:
                break
            all_accs.extend(data)
            if len(data) < 100:
                break

        inbox_ids = []
        for a in all_accs:
            if not isinstance(a, dict):
                continue
            email = a.get("from_email", "").lower().strip()
            if email in TARGET_EMAILS:
                aid = a.get("id")
                if aid:
                    inbox_ids.append(aid)

        print(f"Found {len(inbox_ids)} matching inboxes out of {len(all_accs)} total")

        # 2. For each campaign, check if it exists and apply everything
        for cid, tz in ALL_CAMPS.items():
            r = await c.get(f"{BASE}/campaigns/{cid}?api_key={API_KEY}")
            if r.status_code != 200:
                continue
            name = r.json().get("name", "")
            if "Petr ES" not in name:
                continue

            print(f"\n=== {cid}: {name} ===")

            # Sequences
            r1 = await c.post(f"{BASE}/campaigns/{cid}/sequences?api_key={API_KEY}", json={"sequences": SEQS})
            print(f"  Sequences: {'OK' if r1.status_code == 200 else r1.status_code}")

            # Schedule
            r2 = await c.post(f"{BASE}/campaigns/{cid}/schedule?api_key={API_KEY}", json={
                "timezone": tz, "days_of_the_week": [1,2,3,4,5],
                "start_hour": "09:00", "end_hour": "18:00",
                "min_time_btw_emails": 3, "max_new_leads_per_day": 1500,
            })
            print(f"  Schedule: {'OK' if r2.status_code == 200 else r2.status_code}")

            # Settings
            r3 = await c.post(f"{BASE}/campaigns/{cid}/settings?api_key={API_KEY}", json={
                "follow_up_percentage": 40, "stop_lead_settings": "REPLY_TO_AN_EMAIL",
                "track_settings": [], "send_as_plain_text": True,
            })
            print(f"  Settings: {'OK' if r3.status_code == 200 else r3.status_code}")

            # Connect inboxes
            if inbox_ids:
                r4 = await c.post(f"{BASE}/campaigns/{cid}/email-accounts?api_key={API_KEY}",
                    json={"email_account_ids": inbox_ids})
                print(f"  Inboxes: {'OK' if r4.status_code == 200 else r4.status_code}")
            else:
                print(f"  Inboxes: SKIP (0 found)")

            # Verify
            r5 = await c.get(f"{BASE}/campaigns/{cid}?api_key={API_KEY}")
            if r5.status_code == 200:
                d = r5.json()
                print(f"  Verified: min_time={d.get('min_time_btwn_emails')} max_leads={d.get('max_leads_per_day')} plain={d.get('send_as_plain_text')}")

asyncio.run(main())
