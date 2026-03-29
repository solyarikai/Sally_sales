import asyncio, json, httpx, os

APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "9yIx2mZegixXHeDf6mWVqA")
BASE = "https://api.apollo.io/api/v1"

domains = ["bluecoding.com", "exsis.co", "flatiron.software", "kenility.com", "koombea.com", "nativapps.com", "nybblegroup.com", "oceanscode.com", "ocp.tech", "rooftop.dev", "shokworks.io", "smxusa.com", "theflock.com", "therocketcode.com", "avalith.net", "venon.solutions"]

async def search_people(domain):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(BASE + "/mixed_people/search", json={
            "api_key": APOLLO_KEY,
            "q_organization_domains": domain,
            "person_titles": ["CEO", "CTO", "CFO", "COO", "VP", "Director", "Managing Director", "Founder"],
            "per_page": 3,
            "page": 1,
        })
        data = resp.json()
        return [{"name": p.get("name"), "title": p.get("title"), "email": p.get("email"), "email_status": p.get("email_status"), "domain": domain, "company": p.get("organization", {}).get("name")} for p in data.get("people", [])[:3]]

async def main():
    all_contacts = []
    for d in domains:
        try:
            people = await search_people(d)
            all_contacts.extend(people)
            v = len([p for p in people if p.get("email_status") == "verified" and p.get("email")])
            print(f"{d}: {len(people)} found, {v} verified")
            for p in people:
                print(f"  {p['name']} | {p['title']} | {p['email']} ({p.get('email_status','?')})")
        except Exception as e:
            print(f"{d}: ERROR {e}")
        await asyncio.sleep(0.3)
    verified = [c for c in all_contacts if c.get("email_status") == "verified" and c.get("email")]
    print(f"\nTOTAL: {len(all_contacts)} contacts, {len(verified)} verified")
    with open("/tmp/target_contacts.json", "w") as f:
        json.dump(all_contacts, f, indent=2)

asyncio.run(main())
