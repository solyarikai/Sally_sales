#!/usr/bin/env python3
"""
Enrich UAE-PK target companies via Clay browser (Puppeteer).
Finds up to 3 UAE-located decision-makers per company using domains filter.

Runs 5 batches of ~200 domains sequentially through Clay People Search with:
- Domains: company domain list
- Location: United Arab Emirates
- Titles: decision-maker filter (CFO, COO, HR, CEO, CTO, etc.)

Also launches Apollo scraper in parallel (separate process).
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/app')
from app.services.clay_service import ClayService
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
BATCH_COUNT = 5


async def run_clay_batch(batch_num: int, clay: ClayService):
    """Run one Clay People Search batch with domain + UAE + title filters."""
    domains_file = f"/tmp/uae_pk_enrich_batch_{batch_num}.txt"
    if not os.path.exists(domains_file):
        print(f"[Clay batch {batch_num}] File not found: {domains_file}")
        return []

    domains = [d.strip() for d in open(domains_file).readlines() if d.strip()]
    print(f"\n[Clay batch {batch_num}] {len(domains)} domains")

    try:
        result = await clay.run_people_search(
            domains=domains,
            use_titles=True,
            countries=["United Arab Emirates"],
        )
        people = result.get("people", [])
        print(f"[Clay batch {batch_num}] Found {len(people)} contacts")
        return people
    except Exception as e:
        print(f"[Clay batch {batch_num}] ERROR: {e}")
        return []


async def run_apollo_parallel():
    """Launch Apollo scraper as a background process."""
    # Build Apollo URL with UAE location filter
    # Apollo People search URL format with location filter
    domains_file = "/tmp/uae_pk_all_enrich_domains.txt"
    output_file = "/tmp/uae_pk_apollo_enriched.json"

    if not os.path.exists(domains_file):
        print("[Apollo] No domains file")
        return

    domains = [d.strip() for d in open(domains_file).readlines() if d.strip()]

    # Apollo URL with UAE location + company domains
    # We'll batch domains into the URL (Apollo supports up to ~50 domains per search)
    # For 951 domains, we need ~19 searches
    apollo_script = "/app/scripts/apollo_scraper.js"
    if not os.path.exists(apollo_script):
        print("[Apollo] Scraper script not found")
        return

    # Build Apollo search URL with UAE filter
    # Apollo's people search URL pattern:
    # https://app.apollo.io/#/people?organizationDomains[]=domain1&organizationDomains[]=domain2&locations[]=United%20Arab%20Emirates
    batch_size = 40  # Apollo URL limit
    all_contacts = []

    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(domains) + batch_size - 1) // batch_size

        # Build URL
        domain_params = "&".join(f"organizationDomains[]={d}" for d in batch)
        url = f"https://app.apollo.io/#/people?{domain_params}&locations[]=United%20Arab%20Emirates&personSeniorities[]=vp&personSeniorities[]=c_suite&personSeniorities[]=director&personSeniorities[]=owner&personSeniorities[]=founder&personSeniorities[]=head"

        batch_output = f"/tmp/uae_pk_apollo_batch_{batch_num}.json"
        print(f"[Apollo batch {batch_num}/{total_batches}] {len(batch)} domains")

        try:
            proc = await asyncio.create_subprocess_exec(
                "node", apollo_script,
                "--url", url,
                "--max-pages", "3",  # ~75 contacts per batch
                "--output", batch_output,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/app/scripts",
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)

            if os.path.exists(batch_output):
                batch_data = json.load(open(batch_output))
                contacts = batch_data if isinstance(batch_data, list) else batch_data.get("contacts", [])
                all_contacts.extend(contacts)
                print(f"[Apollo batch {batch_num}] {len(contacts)} contacts")
            else:
                print(f"[Apollo batch {batch_num}] No output file")
                if stderr:
                    print(f"  stderr: {stderr.decode()[:200]}")

        except asyncio.TimeoutError:
            print(f"[Apollo batch {batch_num}] Timeout")
        except Exception as e:
            print(f"[Apollo batch {batch_num}] Error: {e}")

    # Save combined
    with open(output_file, "w") as f:
        json.dump(all_contacts, f, indent=2)
    print(f"\n[Apollo] Total: {len(all_contacts)} contacts -> {output_file}")
    return all_contacts


async def main():
    t0 = time.time()
    clay = ClayService()
    gs = GoogleSheetsService()

    # Run Clay batches and Apollo in parallel
    print("=== LAUNCHING CLAY + APOLLO BROWSER ENRICHMENT ===")
    print(f"Clay: 5 batches x ~200 domains, filters: UAE + decision-makers")
    print(f"Apollo: 24 batches x 40 domains, filters: UAE + VP/C-suite/Director")

    # Launch all concurrently
    tasks = []

    # Clay batches (sequential — shares browser)
    async def run_all_clay():
        all_people = []
        for i in range(1, BATCH_COUNT + 1):
            people = await run_clay_batch(i, clay)
            all_people.extend(people)
        return all_people

    clay_task = asyncio.create_task(run_all_clay())
    apollo_task = asyncio.create_task(run_apollo_parallel())

    clay_people, apollo_people = await asyncio.gather(clay_task, apollo_task, return_exceptions=True)

    if isinstance(clay_people, Exception):
        print(f"Clay failed: {clay_people}")
        clay_people = []
    if isinstance(apollo_people, Exception):
        print(f"Apollo failed: {apollo_people}")
        apollo_people = []

    apollo_people = apollo_people or []

    print(f"\n=== RESULTS ===")
    print(f"Clay: {len(clay_people)} contacts")
    print(f"Apollo: {len(apollo_people)} contacts")

    # Combine and dedup
    all_enriched = []
    seen = set()

    for source, people in [("clay", clay_people), ("apollo", apollo_people)]:
        for p in people:
            if source == "clay":
                key = (p.get("linkedin_url") or f"{p.get('name', '')}|{p.get('company', '')}").lower()
                row = {
                    "first_name": p.get("first_name", ""),
                    "last_name": p.get("last_name", ""),
                    "email": p.get("email", ""),
                    "title": p.get("title", ""),
                    "company": p.get("company", ""),
                    "domain": p.get("domain", ""),
                    "location": p.get("location", ""),
                    "linkedin_url": p.get("linkedin_url", ""),
                    "source": "clay_browser",
                }
            else:
                key = (p.get("linkedin_url") or p.get("linkedinUrl") or
                       f"{p.get('name', '')}|{p.get('company', '')}").lower()
                name = p.get("name", "")
                parts = name.split(" ", 1)
                row = {
                    "first_name": parts[0] if parts else "",
                    "last_name": parts[1] if len(parts) > 1 else "",
                    "email": p.get("email", ""),
                    "title": p.get("title", ""),
                    "company": p.get("company", ""),
                    "domain": p.get("domain", ""),
                    "location": p.get("location", ""),
                    "linkedin_url": p.get("linkedin_url") or p.get("linkedinUrl", ""),
                    "source": "apollo_browser",
                }

            if key not in seen:
                seen.add(key)
                all_enriched.append(row)

    print(f"Combined (deduped): {len(all_enriched)} contacts")

    # Write to new sheet tab
    ts = datetime.now().strftime("%m%d_%H%M")
    tab_name = f"UAE-PK Enriched Contacts {ts}"

    headers = ["First Name", "Last Name", "Email", "Title", "Company",
               "Domain", "Location", "LinkedIn URL", "Source"]
    sheet_rows = [headers]
    for r in all_enriched:
        sheet_rows.append([r[h.lower().replace(" ", "_")] for h in headers])

    gs._initialize()
    try:
        gs.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        ).execute()
    except Exception as e:
        print(f"Tab warning: {e}")

    for i in range(0, len(sheet_rows), 500):
        batch = sheet_rows[i:i + 500]
        gs.sheets_service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A{i + 1}",
            valueInputOption="RAW",
            body={"values": batch}
        ).execute()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")
    print(f"Tab: '{tab_name}'")
    print(f"Contacts: {len(all_enriched)}")

    # Save JSON backup
    with open(f"/tmp/uae_pk_enriched_all.json", "w") as f:
        json.dump(all_enriched, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
