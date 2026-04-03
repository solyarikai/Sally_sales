"""
Enrich fintech funded people with:
1. Apollo org/enrich — funding round, employees, country
2. FindyMail — email by name+domain

Input:  gathering-data/fintech_funded_people.json
Output: gathering-data/fintech_funded_final.csv + .json
"""
import asyncio
import json
import csv
import os
import httpx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE_FILE = os.path.join(REPO, "gathering-data", "fintech_funded_people.json")
CSV_OUT = os.path.join(REPO, "gathering-data", "fintech_funded_final.csv")
JSON_OUT = os.path.join(REPO, "gathering-data", "fintech_funded_final.json")

APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
FINDYMAIL_KEY = os.environ.get("FINDYMAIL_API_KEY", "")


async def enrich_org(client, domain):
    try:
        resp = await client.get(
            "https://api.apollo.io/api/v1/organizations/enrich",
            params={"domain": domain},
            headers={"X-Api-Key": APOLLO_KEY},
        )
        if resp.status_code == 200:
            org = resp.json().get("organization", {})
            return {
                "funding_stage": org.get("latest_funding_stage", ""),
                "total_funding_printed": org.get("total_funding_printed", ""),
                "latest_funding_date": (org.get("latest_funding_round_date") or "")[:10],
                "employees": org.get("estimated_num_employees"),
                "country": org.get("country", ""),
                "industry": org.get("industry", ""),
            }
        elif resp.status_code == 429:
            print(f"  RATE LIMITED on {domain}, waiting 60s...")
            await asyncio.sleep(60)
            return await enrich_org(client, domain)  # retry once
    except Exception as e:
        print(f"  ERROR enriching {domain}: {e}")
    return None


async def find_email(client, name, domain):
    try:
        resp = await client.post(
            "https://app.findymail.com/api/search/name",
            json={"name": name, "domain": domain},
            headers={"Authorization": f"Bearer {FINDYMAIL_KEY}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("email") or data.get("contact", {}).get("email", "")
        elif resp.status_code == 429:
            print(f"  FindyMail rate limited, waiting 10s...")
            await asyncio.sleep(10)
            return await find_email(client, name, domain)
    except Exception as e:
        print(f"  ERROR findymail {name}@{domain}: {e}")
    return ""


async def main():
    with open(PEOPLE_FILE) as f:
        people = json.load(f)
    print(f"Loaded {len(people)} people")

    # Step 1: Enrich orgs via Apollo
    domains = list(set(p["company_domain"] for p in people if p.get("company_domain")))
    print(f"\n=== Step 1: Enrich {len(domains)} domains via Apollo org/enrich ===")

    org_data = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for i, domain in enumerate(domains):
            result = await enrich_org(client, domain)
            if result:
                org_data[domain] = result
            if (i + 1) % 50 == 0:
                funded = sum(1 for o in org_data.values() if o["funding_stage"])
                print(f"  {i+1}/{len(domains)} done ({len(org_data)} enriched, {funded} with funding)")
            await asyncio.sleep(0.3)

    funded = sum(1 for o in org_data.values() if o["funding_stage"])
    print(f"  DONE: {len(org_data)}/{len(domains)} enriched, {funded} with funding stage")

    # Merge into people
    for p in people:
        d = p.get("company_domain", "")
        org = org_data.get(d, {})
        p["funding_round"] = org.get("funding_stage", "")
        p["total_funding"] = org.get("total_funding_printed", "")
        p["funding_date"] = org.get("latest_funding_date", "")
        p["company_employees"] = org.get("employees") or p.get("company_employees")
        p["company_country"] = org.get("country") or p.get("company_country", "")
        p["company_industry"] = org.get("industry") or p.get("company_industry", "")

    # Step 2: FindyMail
    print(f"\n=== Step 2: Find emails for {len(people)} people via FindyMail ===")
    found_count = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i, p in enumerate(people):
            name = p.get("name", "")
            domain = p.get("company_domain", "")
            if name and domain:
                email = await find_email(client, name, domain)
                if email:
                    p["email"] = email
                    found_count += 1
                else:
                    p["email"] = ""
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(people)} done ({found_count} emails found)")
            await asyncio.sleep(0.15)

    print(f"  DONE: {found_count}/{len(people)} emails found")

    # Clean placeholders
    for p in people:
        e = p.get("email", "")
        if "not_unlocked" in e or "domain.com" in e:
            p["email"] = ""

    # Save JSON
    with open(JSON_OUT, "w") as f:
        json.dump(people, f, indent=2)

    # Save CSV
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "funding_round", "total_funding", "funding_date",
            "name", "title", "company", "website", "email", "linkedin",
            "country", "employees", "industry",
        ])
        for p in people:
            writer.writerow([
                p.get("funding_round", ""),
                p.get("total_funding", ""),
                p.get("funding_date", ""),
                p.get("name", ""),
                p.get("title", ""),
                p.get("company_name", ""),
                p.get("company_domain", ""),
                p.get("email", ""),
                p.get("linkedin_url", ""),
                p.get("company_country", ""),
                p.get("company_employees", ""),
                p.get("company_industry", ""),
            ])

    # Summary
    with_email = sum(1 for p in people if p.get("email"))
    with_funding = sum(1 for p in people if p.get("funding_round"))
    print(f"\n{'='*60}")
    print(f"RESULT: {len(people)} people")
    print(f"  With funding round: {with_funding}")
    print(f"  With email:         {with_email}")
    print(f"  CSV: {CSV_OUT}")
    print(f"  JSON: {JSON_OUT}")
    print(f"{'='*60}")

    # Show first 10
    for p in people[:10]:
        print(f"  {p.get('funding_round','?'):10s} | {p['name']:25s} | {p['title'][:28]:28s} | {p.get('company_domain',''):22s} | {p.get('email','') or '-'}")


if __name__ == "__main__":
    asyncio.run(main())
