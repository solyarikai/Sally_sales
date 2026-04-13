"""Build contacts.json for TECH_LEADERS pipeline run from filtered Apollo people."""

import csv
import json
from pathlib import Path

PEOPLE = "/Users/user/sales_engineer/sofia/input/imagency_europe_people_filtered.json"
COMPANIES_CSV = "/Users/user/sales_engineer/sofia/OS _ Targets _ IMAGENCY EUROPE - IM_FIRST_AGENCIES_EUROPE.csv"
OUT = (
    "/Users/user/sales_engineer/sofia/input/imagency_europe_tech_leaders_contacts.json"
)

people = json.loads(Path(PEOPLE).read_text())

company_meta = {}
with open(COMPANIES_CSV) as f:
    for row in csv.DictReader(f):
        d = row["Domain"].strip().lower()
        if d:
            company_meta[d] = {
                "company_country": row.get("Country", "").strip(),
                "employees": row.get("Employees", "").strip(),
                "industry": row.get("Industry", "").strip(),
            }

contacts = []
for p in people:
    domain = (p.get("domain") or "").lower()
    meta = company_meta.get(domain, {})
    contacts.append(
        {
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "email": p.get("email", "") or "",
            "title": p.get("title", ""),
            "company_name": p.get("company_name", ""),
            "domain": domain,
            "segment": "TECH_LEADERS",
            "linkedin_url": p.get("linkedin_url", ""),
            "country": p.get("country", ""),
            "company_country": meta.get("company_country", "") or p.get("country", ""),
            "city": p.get("city", ""),
            "employees": meta.get("employees", ""),
            "industry": meta.get("industry", ""),
            "social_proof": "",
        }
    )

Path(OUT).write_text(json.dumps(contacts, indent=2))
print(f"Wrote {len(contacts)} contacts → {OUT}")
print(f"Companies: {len({c['domain'] for c in contacts})}")
print(f"With company_country: {sum(1 for c in contacts if c['company_country'])}")
