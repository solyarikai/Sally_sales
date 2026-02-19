"""
Fill missing contacts for OnSocial (project 42) target companies.

Strategy (in priority order):
1. Scrape website contact/about/team pages — keep ALL emails including generic
2. FindyMail find_by_name — for names scraped without emails
3. FindyMail verify — for every email found
4. Update extracted_contacts + re-export Google Sheet

Efficient: skips companies that already have contacts,
uses FindyMail cache (90-day TTL), parallelizes scraping.
"""
import asyncio
import json
import re
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("fill_contacts")

PROJECT_ID = 42
FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
SHEET_ID = "1lxO7hF9RZ7OIAAF2Xyw1S3H4Yv87LbPAnFTc9lIfwZA"
SHARE_WITH = ["pn@getsally.io"]

CONTACT_PATHS = [
    "/contact", "/contact-us", "/contacts",
    "/about", "/about-us", "/team", "/our-team",
    "/kontakty", "/kontakt", "/equipo", "/contacto",
    "/o-nas", "/uber-uns", "/qui-sommes-nous",
]

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Truly junk prefixes — NOT outreach-worthy
JUNK_PREFIXES = {"noreply@", "no-reply@", "webmaster@", "postmaster@", "abuse@", "mailer-daemon@"}

# Generic but outreach-worthy — keep as fallback
GENERIC_PREFIXES = {
    "info@", "hello@", "contact@", "hi@", "hey@", "office@",
    "sales@", "marketing@", "team@", "hola@", "mail@",
    "support@", "help@", "service@", "feedback@",
}


def classify_email(email: str) -> str:
    """Returns 'personal', 'generic', or 'junk'."""
    e = email.lower()
    if any(e.startswith(p) for p in JUNK_PREFIXES):
        return "junk"
    if any(e.startswith(p) for p in GENERIC_PREFIXES):
        return "generic"
    return "personal"


def email_matches_domain(email: str, domain: str) -> bool:
    """Check if email domain roughly matches company domain."""
    if "@" not in email:
        return False
    email_domain = email.split("@")[1].lower()
    # Exact match or subdomain
    return email_domain == domain.lower() or email_domain.endswith("." + domain.lower())


async def scrape_page(domain: str, path: str) -> str | None:
    import httpx
    url = f"https://{domain}{path}"
    try:
        async with httpx.AsyncClient(
            timeout=12, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.text) > 200:
                return resp.text[:15000]
    except Exception:
        pass
    return None


async def gpt_extract(domain: str, html: str, api_key: str) -> list[dict]:
    """GPT-4o-mini: extract ALL people + emails from page."""
    import httpx
    if not html or len(html.strip()) < 100:
        return []

    prompt = f"""Extract contact information from this website page for domain: {domain}

PAGE CONTENT:
{html[:10000]}

Extract ALL people and email addresses:
- Team members, founders, executives, managers — with name, title, email if visible
- Generic emails (hello@, info@, contact@) — include them too, mark job_title as "General"
- If a person appears without email, still include them (we'll find their email separately)

Return JSON array only:
[{{"email": "...", "first_name": "...", "last_name": "...", "job_title": "...", "phone": null}}]
For generic emails without a person: [{{"email": "hello@example.com", "first_name": "", "last_name": "", "job_title": "General", "phone": null}}]"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "Extract contacts from website HTML. Return only valid JSON array. Include ALL emails found, even generic ones."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content)
            return result if isinstance(result, list) else []
    except Exception as e:
        logger.debug(f"GPT extraction failed for {domain}: {e}")
        return []


async def main():
    from app.db import async_session_maker
    from app.services.findymail_service import findymail_service
    from app.services.email_verification_service import email_verification_service
    from app.services.google_sheets_service import google_sheets_service
    from app.core.config import settings
    from sqlalchemy import text

    # Setup FindyMail
    findymail_service.set_api_key(FINDYMAIL_API_KEY)
    credits = await findymail_service.get_credits()
    logger.info(f"FindyMail credits: {credits}")
    openai_key = settings.OPENAI_API_KEY

    async with async_session_maker() as session:
        # 1. Get target companies with 0 usable contacts
        result = await session.execute(text("""
            SELECT dc.id, dc.domain, dc.name
            FROM discovered_companies dc
            WHERE dc.project_id = :pid AND dc.is_target = true
            AND (
                dc.contacts_count = 0 OR dc.contacts_count IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM extracted_contacts ec
                    WHERE ec.discovered_company_id = dc.id AND ec.email IS NOT NULL AND ec.email != ''
                )
            )
            ORDER BY dc.domain
        """), {"pid": PROJECT_ID})
        companies = result.fetchall()
        logger.info(f"Companies needing contacts: {len(companies)}")

        sem = asyncio.Semaphore(8)
        total_personal = 0
        total_generic = 0
        total_findymail_found = 0
        companies_filled = 0

        async def process_company(dc_id: int, domain: str, name: str):
            nonlocal total_personal, total_generic, total_findymail_found, companies_filled

            async with sem:
                all_contacts = []  # {email, first_name, last_name, job_title, phone, source, email_type}
                seen_emails = set()

                # --- Step 1: Scrape website pages ---
                for path in CONTACT_PATHS:
                    html = await scrape_page(domain, path)
                    if not html:
                        continue

                    # Regex extraction
                    for m in EMAIL_RE.finditer(html):
                        email = m.group().lower().rstrip(".")
                        if email in seen_emails:
                            continue
                        if not email_matches_domain(email, domain):
                            continue
                        etype = classify_email(email)
                        if etype == "junk":
                            continue
                        seen_emails.add(email)
                        all_contacts.append({
                            "email": email, "first_name": "", "last_name": "",
                            "job_title": "General" if etype == "generic" else "",
                            "phone": None, "source": "WEBSITE_SCRAPE", "email_type": etype,
                        })

                    # GPT extraction
                    gpt_contacts = await gpt_extract(domain, html, openai_key)
                    for gc in gpt_contacts:
                        email = (gc.get("email") or "").lower().strip().rstrip(".")
                        if email and "@" in email and email not in seen_emails and email_matches_domain(email, domain):
                            etype = classify_email(email)
                            if etype != "junk":
                                seen_emails.add(email)
                                all_contacts.append({
                                    "email": email,
                                    "first_name": gc.get("first_name", ""),
                                    "last_name": gc.get("last_name", ""),
                                    "job_title": gc.get("job_title", ""),
                                    "phone": gc.get("phone"),
                                    "source": "WEBSITE_SCRAPE",
                                    "email_type": etype,
                                })
                        elif not email and gc.get("first_name") and gc.get("last_name"):
                            # Name without email — try FindyMail
                            full_name = f"{gc['first_name']} {gc['last_name']}".strip()
                            if full_name and len(full_name) > 3:
                                fm_result = await findymail_service.find_email_by_name(full_name, domain)
                                if fm_result.get("success") and fm_result.get("email"):
                                    found_email = fm_result["email"].lower()
                                    if found_email not in seen_emails:
                                        seen_emails.add(found_email)
                                        all_contacts.append({
                                            "email": found_email,
                                            "first_name": gc.get("first_name", ""),
                                            "last_name": gc.get("last_name", ""),
                                            "job_title": gc.get("job_title", ""),
                                            "phone": gc.get("phone"),
                                            "source": "FINDYMAIL",
                                            "email_type": "personal",
                                        })
                                        total_findymail_found += 1

                    if all_contacts:
                        break  # Got contacts from this page, skip remaining paths

                if not all_contacts:
                    return  # Nothing found anywhere

                # --- Step 2: Store contacts ---
                for c in all_contacts:
                    if c["email_type"] == "personal":
                        total_personal += 1
                    else:
                        total_generic += 1

                    await session.execute(text("""
                        INSERT INTO extracted_contacts
                            (discovered_company_id, email, first_name, last_name, job_title, phone,
                             source, is_verified, created_at)
                        VALUES (:dc_id, :email, :fn, :ln, :title, :phone, :source, false, now())
                        ON CONFLICT DO NOTHING
                    """), {
                        "dc_id": dc_id, "email": c["email"],
                        "fn": c["first_name"], "ln": c["last_name"],
                        "title": c["job_title"], "phone": c["phone"] or None,
                        "source": c["source"],
                    })

                # Update contacts_count
                await session.execute(text("""
                    UPDATE discovered_companies
                    SET contacts_count = (
                        SELECT count(*) FROM extracted_contacts
                        WHERE discovered_company_id = :dc_id AND email IS NOT NULL AND email != ''
                    ),
                    status = 'CONTACTS_EXTRACTED'
                    WHERE id = :dc_id
                """), {"dc_id": dc_id})

                companies_filled += 1
                logger.info(f"  {domain}: +{len(all_contacts)} contacts "
                            f"({sum(1 for c in all_contacts if c['email_type']=='personal')}p + "
                            f"{sum(1 for c in all_contacts if c['email_type']=='generic')}g)")

        # Process all companies
        tasks = [process_company(c.id, c.domain, c.name) for c in companies]
        await asyncio.gather(*tasks)
        await session.commit()

        logger.info(f"\nScraping done: {companies_filled}/{len(companies)} companies got contacts")
        logger.info(f"  Personal emails: {total_personal}")
        logger.info(f"  Generic emails: {total_generic}")
        logger.info(f"  FindyMail name lookups: {total_findymail_found}")

        # --- Step 3: Verify ALL new emails via FindyMail ---
        logger.info("\nVerifying new emails via FindyMail...")
        new_emails_result = await session.execute(text("""
            SELECT ec.id, ec.email
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
              AND ec.email IS NOT NULL AND ec.email != ''
              AND ec.is_verified = false
              AND ec.verification_method IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM email_verifications ev
                  WHERE ev.email = ec.email AND ev.expires_at > now() AND ev.result != 'error'
              )
        """), {"pid": PROJECT_ID})
        new_emails = new_emails_result.fetchall()
        logger.info(f"New unverified emails to check: {len(new_emails)}")

        if new_emails:
            email_list = [r.email.lower().strip() for r in new_emails]
            email_to_extracted = {r.email.lower().strip(): r.id for r in new_emails}
            batch_result = await email_verification_service.verify_batch(
                session=session,
                emails=email_list,
                project_id=PROJECT_ID,
                max_credits=len(email_list) + 10,
                email_to_extracted=email_to_extracted,
            )
            await session.commit()
            vstats = batch_result["stats"]
            logger.info(f"Verified: {vstats['valid']} valid, {vstats['invalid']} invalid, "
                        f"{vstats['cached']} cached, cost=${vstats['cost_usd']:.2f}")

        # --- Step 4: Re-export Google Sheet ---
        logger.info("\nExporting to Google Sheet...")
        campaign_emails_result = await session.execute(text("""
            SELECT DISTINCT lower(email) as email FROM contacts
            WHERE campaigns::text ILIKE '%onsocial%' AND email IS NOT NULL AND email != ''
        """))
        campaign_emails = {row.email for row in campaign_emails_result.fetchall()}

        targets = await session.execute(text("""
            SELECT DISTINCT ON (dc.domain)
                dc.domain, dc.name as company_name, dc.confidence,
                sr.company_info->>'description' as description,
                sr.company_info->>'services' as services,
                sr.company_info->>'location' as location,
                sr.company_info->>'industry' as industry,
                sr.scores->>'language_match' as language_match,
                sr.scores->>'industry_match' as industry_match,
                sr.scores->>'service_match' as service_match,
                sr.scores->>'company_type' as company_type_score,
                sr.scores->>'geography_match' as geography_match,
                sr.review_status, sr.reasoning, sr.matched_segment,
                'https://' || dc.domain as url
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.domain = dc.domain AND sr.project_id = dc.project_id AND sr.is_target = true
            WHERE dc.project_id = :pid AND dc.is_target = true
            ORDER BY dc.domain, dc.confidence DESC NULLS LAST
        """), {"pid": PROJECT_ID})
        target_map = {row.domain: row for row in targets.fetchall()}

        contacts_result = await session.execute(text("""
            SELECT dc.domain, ec.first_name, ec.last_name, ec.email, ec.phone,
                ec.job_title, ec.linkedin_url, ec.source, ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
                AND ec.email IS NOT NULL AND ec.email != ''
            ORDER BY dc.domain, ec.is_verified DESC, ec.source DESC
        """), {"pid": PROJECT_ID})
        domain_contacts = {}
        for c in contacts_result.fetchall():
            domain_contacts.setdefault(c.domain, []).append(c)

        verif_result = await session.execute(text("""
            SELECT email, result, is_valid, provider, verified_at
            FROM email_verifications WHERE project_id = :pid
            ORDER BY email, verified_at DESC
        """), {"pid": PROJECT_ID})
        verif_map = {}
        for v in verif_result.fetchall():
            if v.email not in verif_map:
                verif_map[v.email] = v

        meta_result = await session.execute(text("""
            SELECT sr.domain, sq.query_text, sj.search_engine, sr.matched_segment
            FROM search_results sr
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            LEFT JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sr.project_id = :pid AND sr.is_target = true
        """), {"pid": PROJECT_ID})
        domain_meta = {}
        for row in meta_result.fetchall():
            d = row.domain
            if d not in domain_meta:
                domain_meta[d] = {"queries": [], "engines": set(), "segments": set()}
            if row.query_text: domain_meta[d]["queries"].append(row.query_text)
            if row.search_engine: domain_meta[d]["engines"].add(str(row.search_engine))
            if row.matched_segment: domain_meta[d]["segments"].add(row.matched_segment)

        headers = [
            "First Name", "Last Name", "Email", "Job Title", "LinkedIn",
            "Phone", "Contact Source", "Apollo Verified",
            "FindyMail Result", "FindyMail Valid", "Email Provider", "Verified At",
            "In Campaign",
            "Domain", "URL", "Company Name", "Description",
            "Industry", "Services", "Location",
            "Confidence", "Language", "Industry Match", "Service Match",
            "Company Type", "Geography",
            "Review Status", "Search Engine", "Segment", "Source Query",
            "Reasoning",
        ]
        data = [headers]
        new_ct = 0
        camp_ct = 0
        no_ct = 0

        for domain in sorted(target_map.keys()):
            row = target_map[domain]
            contacts = domain_contacts.get(domain, [])

            services = row.services
            if services:
                try:
                    sl = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(sl) if isinstance(sl, list) else str(services)
                except Exception:
                    pass

            meta = domain_meta.get(domain, {})
            engines = ", ".join(meta.get("engines", set()))
            segments = ", ".join(meta.get("segments", set()))
            queries = meta.get("queries", [])
            source_query = queries[0] if queries else ""

            company_cols = [
                row.domain, row.url, row.company_name or "", row.description or "",
                row.industry or "", services or "", row.location or "",
            ]
            score_cols = [
                str(row.confidence or ""), str(row.language_match or ""),
                str(row.industry_match or ""), str(row.service_match or ""),
                str(row.company_type_score or ""), str(row.geography_match or ""),
            ]
            search_cols = [row.review_status or "", engines, segments, source_query]
            reasoning_col = [row.reasoning or ""]

            if not contacts:
                contact_cols = ["", "", "NO CONTACTS", "", "", "", "", "", "", "", "", "", ""]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                no_ct += 1
                continue

            for c in contacts:
                email_lower = c.email.lower().strip()
                in_campaign = "YES" if email_lower in campaign_emails else ""
                verif = verif_map.get(email_lower)
                contact_cols = [
                    c.first_name or "", c.last_name or "", c.email, c.job_title or "",
                    c.linkedin_url or "", c.phone or "", str(c.source or ""),
                    "Yes" if c.is_verified else "",
                    verif.result if verif else "",
                    "Yes" if verif and verif.is_valid else ("No" if verif and verif.is_valid is False else ""),
                    verif.provider if verif else "",
                    str(verif.verified_at)[:19] if verif else "",
                    in_campaign,
                ]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                if in_campaign:
                    camp_ct += 1
                else:
                    new_ct += 1

        logger.info(f"Sheet: {len(data)-1} rows ({new_ct} new, {camp_ct} in campaigns, {no_ct} no-contacts)")

        google_sheets_service._initialize()
        sheets = google_sheets_service.sheets_service
        if sheets:
            try:
                sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="Sheet1").execute()
                sheets.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID, range="Sheet1!A1",
                    valueInputOption="RAW", body={"values": data},
                ).execute()
                logger.info(f"SUCCESS: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
            except Exception as e:
                logger.error(f"Sheet failed: {e}")
                url = google_sheets_service.create_and_populate(
                    title=f"OnSocial Contacts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                    data=data, share_with=SHARE_WITH,
                )
                logger.info(f"New sheet: {url}")

        print("\n" + "=" * 60)
        print("ONSOCIAL CONTACT FILL SUMMARY")
        print("=" * 60)
        print(f"Companies processed: {len(companies)}")
        print(f"Companies filled: {companies_filled}")
        print(f"Personal emails found: {total_personal}")
        print(f"Generic emails found: {total_generic}")
        print(f"FindyMail name lookups: {total_findymail_found}")
        print(f"\nSheet: {new_ct} new + {camp_ct} in campaigns + {no_ct} no-contacts = {len(data)-1} rows")
        print(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
