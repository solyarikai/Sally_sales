"""
Fix: Re-upload all contacts with sender_name custom field.
Balanced split: ~55% Petr Nikolaev (petr@ inboxes), ~45% Rinat Karimov (rinat@ inboxes).
Also fix sequence to use {{sender_name}} variable.
"""
import asyncio, httpx, csv, io

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"
CAMPS = [3070912, 3070913, 3070915, 3070916, 3070917, 3070918, 3070919, 3070920]

# Sequence with {{sender_name}} custom variable
SEQS = [
    {"seq_number": 1, "seq_delay_details": {"delay_in_days": 0},
     "subject": "{{first_name}} - paying freelancers abroad?",
     "email_body": "Hi {{first_name}},<br><br>We at Easystaff help companies pay freelancers globally with fees under 1% - zero fees for your freelancers.<br><br>You can pay contractors via cards, PayPal, and USDT wallets - all paperwork handled by us.<br><br>Recently helped a {{city}} agency switch from Deel to paying 50 contractors across 8 countries, saving them $4,000/month on platform fees and exchange rates.<br><br>Would you like to calculate the cost benefit for your case?<br><br>{{sender_name}}<br>BDM, Easystaff<br>Trusted by 5,000+ teams worldwide"},
    {"seq_number": 2, "seq_delay_details": {"delay_in_days": 3},
     "subject": "",
     "email_body": "Hi {{first_name}},<br><br>Following up. Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility.<br><br>We offer a better way:<br>- Cut out the middleman: Save the 10-20% freelance marketplace fees<br>- No annual contracts: Pay only for what you use<br>- Same-day payouts to any country, real human support (no bots)<br>- One compliant B2B invoice for all freelancer payments<br><br>Open to a quick demo call this week?"},
    {"seq_number": 3, "seq_delay_details": {"delay_in_days": 4},
     "subject": "",
     "email_body": "Hi {{first_name}},<br><br>Just making sure my emails are getting through.<br><br>Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.<br><br>For 50+ contractors/month, we offer custom rates below any competitor.<br><br>Can I send you a 2-minute walkthrough video?"},
    {"seq_number": 4, "seq_delay_details": {"delay_in_days": 7},
     "subject": "",
     "email_body": "Would it be easier to connect on LinkedIn or Telegram?<br><br>If you already have a payment solution, happy to compare - many clients switch after seeing the total cost difference.<br><br>Sent from my iPhone"},
]


async def main():
    async with httpx.AsyncClient(timeout=120) as c:
        # 1. Fix sequences in all campaigns
        print("Fixing sequences...")
        for cid in CAMPS:
            r = await c.post(f"{BASE}/campaigns/{cid}/sequences?api_key={API_KEY}",
                             json={"sequences": SEQS})
            status = "OK" if r.status_code == 200 else f"ERR {r.status_code}"
            print(f"  {cid}: {status}")

        # 2. Load contacts from CSV and add sender_name
        print("\nLoading contacts...")
        leads_by_camp = {cid: [] for cid in CAMPS}

        # Map campaign IDs to cities
        camp_cities = {
            3070912: ["Boston", "Miami", "Toronto", "Chicago"],
            3070913: ["San Francisco", "Seattle", "Portland", "Denver", "Austin"],
            3070915: ["London", "Dublin", "Amsterdam", "Berlin", "Stockholm"],
            3070916: ["Dubai", "Abu Dhabi", "Riyadh", "Jeddah", "Doha"],
            3070917: ["Mumbai", "Bangalore"],
            3070918: ["Singapore"],
            3070919: ["Sydney", "Melbourne"],
            3070920: ["Sao Paulo", "Cape Town"],
        }
        city_to_camp = {}
        for cid, cities in camp_cities.items():
            for city in cities:
                city_to_camp[city] = cid

        with open("/tmp/es_contacts.csv") as f:
            counter = 0
            for line in f:
                p = line.strip().split(",", 9)
                if len(p) < 10 or "@" not in p[0]:
                    continue
                city = p[8]
                cid = city_to_camp.get(city, 3070916)  # default to Gulf

                # Alternate sender_name: Petr Nikolaev (55%) / Rinat Karimov (45%)
                sender = "Petr Nikolaev" if counter % 20 < 11 else "Rinat Karimov"
                counter += 1

                leads_by_camp[cid].append({
                    "email": p[0],
                    "first_name": p[1],
                    "last_name": p[2],
                    "company_name": p[3],
                    "custom_fields": {
                        "job_title": p[4],
                        "linkedin_url": p[5],
                        "domain": p[6],
                        "segment": p[7],
                        "city": p[8],
                        "email_source": p[9],
                        "sender_name": sender,
                    }
                })

        # 3. Re-upload leads (SmartLead dedupes by email, updates custom fields)
        print("\nRe-uploading leads with sender_name...")
        for cid in CAMPS:
            leads = leads_by_camp[cid]
            if not leads:
                continue
            total = 0
            for i in range(0, len(leads), 200):
                batch = leads[i:i+200]
                r = await c.post(f"{BASE}/campaigns/{cid}/leads?api_key={API_KEY}",
                                 json={"lead_list": batch}, timeout=120)
                if r.status_code == 200:
                    total += r.json().get("uploadCount", len(batch))
                else:
                    print(f"  {cid} batch ERR: {r.text[:80]}")
            print(f"  {cid}: {total} leads uploaded with sender_name")

        print("\nDONE")

asyncio.run(main())
