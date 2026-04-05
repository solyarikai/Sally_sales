"""
Apollo.io MCP Server
Search, enrich, and manage contacts/accounts/sequences via Apollo API.
"""

import os
import csv
import json
import httpx
from fastmcp import FastMCP

API_KEY = os.environ.get("APOLLO_API_KEY", "")
BASE_URL = "https://api.apollo.io/api/v1"

mcp = FastMCP("Apollo")


def headers():
    key = API_KEY or os.environ.get("APOLLO_API_KEY", "")
    return {
        "X-Api-Key": key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }


def api_get(path: str, params: dict = None) -> dict:
    resp = httpx.get(f"{BASE_URL}{path}", headers=headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, data: dict = None) -> dict:
    resp = httpx.post(f"{BASE_URL}{path}", headers=headers(), json=data or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# Maps endpoint key (as in usage_stats response) to human-readable name
_CREDIT_ENDPOINTS = {
    '["api/v1/people", "match"]': "enrich_person",
    '["api/v1/people", "bulk_match"]': "bulk_enrich_people",
    '["api/v1/organizations", "enrich"]': "enrich_organization",
    '["api/v1/mixed_companies", "search"]': "search_organizations",
}


def _fetch_call_counts() -> dict[str, int]:
    """Return {endpoint_key: consumed_today} for credit-consuming endpoints."""
    try:
        data = api_post("/usage_stats/api_usage_stats")
        result = {}
        for key in _CREDIT_ENDPOINTS:
            entry = data.get(key, {})
            result[key] = entry.get("day", {}).get("consumed", 0)
        return result
    except Exception:
        return {}


def _credit_footer(before: dict, after: dict) -> str:
    """Build a usage summary line comparing before/after snapshots."""
    if not before or not after:
        return ""
    lines = ["\n--- API calls used ---"]
    for key, name in _CREDIT_ENDPOINTS.items():
        delta = after.get(key, 0) - before.get(key, 0)
        if delta > 0:
            lines.append(f"  {name}: +{delta} call(s) | used today: {after.get(key,0)}/600")
    if len(lines) == 1:
        lines.append("  (no credit-consuming calls detected)")
    lines.append("  Note: Apollo email/phone enrichment credits are tracked separately in Billing settings.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SEARCH (no credits for people search, credits consumed for org search)
# ---------------------------------------------------------------------------

@mcp.tool()
def search_people(
    titles: list[str] = None,
    include_similar_titles: bool = False,
    seniorities: list[str] = None,
    person_locations: list[str] = None,
    organization_locations: list[str] = None,
    organization_domains: list[str] = None,
    organization_ids: list[str] = None,
    employee_ranges: list[str] = None,
    organization_keyword_tags: list[str] = None,
    keywords: str = None,
    contact_email_status: list[str] = None,
    revenue_min: int = None,
    revenue_max: int = None,
    technologies: list[str] = None,
    technologies_all: list[str] = None,
    not_technologies: list[str] = None,
    job_titles: list[str] = None,
    job_locations: list[str] = None,
    job_count_min: int = None,
    job_count_max: int = None,
    job_posted_at_min: str = None,
    job_posted_at_max: str = None,
    page: int = 1,
    per_page: int = 25,
) -> str:
    """
    Search Apollo database for people. Does NOT consume email/enrichment credits.
    Returns first_name + obfuscated last_name + title + org but NOT emails.
    Use enrich_person to get full name, email, linkedin (costs credits).

    Args:
        titles: Job titles, e.g. ["CEO", "Founder", "VP of Sales"]
        include_similar_titles: Also match similar titles (default False)
        seniorities: owner, founder, c_suite, partner, vp, head, director, manager, senior, entry, intern
        person_locations: Personal location, e.g. ["germany", "london", "california"]
        organization_locations: Company HQ location, e.g. ["united states", "united kingdom"]
        organization_domains: Company domains, e.g. ["stripe.com", "notion.so"] — up to 1,000
        organization_ids: Apollo organization IDs to search within
        employee_ranges: Employee count ranges, e.g. ["1,50", "51,200", "201,500"]
        organization_keyword_tags: Company keyword tags — BEST way to filter by industry/niche.
            e.g. ["influencer marketing", "creator platform", "e-commerce"]
            WARNING: Do NOT use 'keywords' param for company filtering — it searches person profiles.
        keywords: Free text on PERSON profile (usually not what you want — use organization_keyword_tags)
        contact_email_status: Filter by email status: "verified", "unverified", "likely_to_engage", "unavailable"
        revenue_min: Min company revenue in USD, e.g. 1000000
        revenue_max: Max company revenue in USD, e.g. 50000000
        technologies: Companies using ANY of these technologies, e.g. ["salesforce", "hubspot"]
            Format: underscores for spaces/dots — "google_analytics", "wordpress_org"
        technologies_all: Companies using ALL of these technologies (stricter filter)
        not_technologies: EXCLUDE companies using any of these technologies
        job_titles: Filter by active job posting titles at the company
        job_locations: Filter by job posting locations
        job_count_min: Min number of active job postings
        job_count_max: Max number of active job postings
        job_posted_at_min: Min job posting date (YYYY-MM-DD)
        job_posted_at_max: Max job posting date (YYYY-MM-DD)
        page: Page number (default 1)
        per_page: Results per page, max 100 (default 25)
    """
    payload: dict = {"page": page, "per_page": per_page}
    if titles:
        payload["person_titles"] = titles
    if include_similar_titles:
        payload["include_similar_titles"] = True
    if seniorities:
        payload["person_seniorities"] = seniorities
    if person_locations:
        payload["person_locations"] = person_locations
    if organization_locations:
        payload["organization_locations"] = organization_locations
    if organization_domains:
        payload["q_organization_domains_list"] = organization_domains
    if organization_ids:
        payload["organization_ids"] = organization_ids
    if employee_ranges:
        payload["organization_num_employees_ranges"] = employee_ranges
    if organization_keyword_tags:
        payload["q_organization_keyword_tags"] = organization_keyword_tags
    if keywords:
        payload["q_keywords"] = keywords
    if contact_email_status:
        payload["contact_email_status"] = contact_email_status
    if revenue_min is not None:
        payload.setdefault("revenue_range", {})["min"] = revenue_min
    if revenue_max is not None:
        payload.setdefault("revenue_range", {})["max"] = revenue_max
    if technologies:
        payload["currently_using_any_of_technology_uids"] = technologies
    if technologies_all:
        payload["currently_using_all_of_technology_uids"] = technologies_all
    if not_technologies:
        payload["currently_not_using_any_of_technology_uids"] = not_technologies
    if job_titles:
        payload["q_organization_job_titles"] = job_titles
    if job_locations:
        payload["organization_job_locations"] = job_locations
    if job_count_min is not None:
        payload.setdefault("organization_num_jobs_range", {})["min"] = job_count_min
    if job_count_max is not None:
        payload.setdefault("organization_num_jobs_range", {})["max"] = job_count_max
    if job_posted_at_min:
        payload.setdefault("organization_job_posted_at_range", {})["min"] = job_posted_at_min
    if job_posted_at_max:
        payload.setdefault("organization_job_posted_at_range", {})["max"] = job_posted_at_max

    data = api_post("/mixed_people/api_search", payload)
    total = data.get("total_entries", 0)
    people = data.get("people", [])

    lines = [f"Found {total} people (page {page}, showing {len(people)})\n"]
    for p in people:
        org = p.get("organization") or {}
        lines.append(
            f"- {p.get('first_name', '')} {p.get('last_name_obfuscated', '')} | "
            f"{p.get('title', 'N/A')} @ {org.get('name', 'N/A')} | "
            f"id: {p.get('id')} | has_email: {p.get('has_email')}"
        )
    return "\n".join(lines)


@mcp.tool()
def search_organizations(
    locations: list[str] = None,
    exclude_locations: list[str] = None,
    employee_ranges: list[str] = None,
    domains: list[str] = None,
    organization_ids: list[str] = None,
    name: str = None,
    keywords: list[str] = None,
    technologies: list[str] = None,
    revenue_min: int = None,
    revenue_max: int = None,
    latest_funding_amount_min: int = None,
    latest_funding_amount_max: int = None,
    total_funding_min: int = None,
    total_funding_max: int = None,
    latest_funding_date_min: str = None,
    latest_funding_date_max: str = None,
    job_titles: list[str] = None,
    job_locations: list[str] = None,
    job_count_min: int = None,
    job_count_max: int = None,
    job_posted_at_min: str = None,
    job_posted_at_max: str = None,
    page: int = 1,
    per_page: int = 25,
) -> str:
    """
    Search Apollo database for companies. Consumes credits.

    Args:
        locations: HQ locations, e.g. ["united states", "germany", "london"]
        exclude_locations: Locations to EXCLUDE, e.g. ["russia", "china"]
        employee_ranges: Employee count ranges, e.g. ["1,50", "51,200", "201,500"]
        domains: Company domains to find, e.g. ["stripe.com"]
        organization_ids: Apollo organization IDs
        name: Company name search (partial match ok), e.g. "apollo"
        keywords: Keyword tags, e.g. ["saas", "fintech", "e-commerce"]
        technologies: Tech stack filter, e.g. ["salesforce", "hubspot", "stripe"]
            Format: underscores for spaces/dots — "google_analytics", "wordpress_org"
        revenue_min: Min revenue in USD, e.g. 1000000
        revenue_max: Max revenue in USD, e.g. 50000000
        latest_funding_amount_min: Min latest funding round in USD
        latest_funding_amount_max: Max latest funding round in USD
        total_funding_min: Min total funding in USD
        total_funding_max: Max total funding in USD
        latest_funding_date_min: Min funding date (YYYY-MM-DD)
        latest_funding_date_max: Max funding date (YYYY-MM-DD)
        job_titles: Active job posting titles, e.g. ["Sales Engineer", "SDR"]
        job_locations: Job posting locations
        job_count_min: Min number of active job postings
        job_count_max: Max number of active job postings
        job_posted_at_min: Min job posting date (YYYY-MM-DD)
        job_posted_at_max: Max job posting date (YYYY-MM-DD)
        page: Page number (default 1)
        per_page: Results per page, max 100 (default 25)
    """
    payload: dict = {"page": page, "per_page": per_page}
    if locations:
        payload["organization_locations[]"] = locations
    if exclude_locations:
        payload["organization_not_locations[]"] = exclude_locations
    if employee_ranges:
        payload["organization_num_employees_ranges[]"] = employee_ranges
    if domains:
        payload["q_organization_domains_list[]"] = domains
    if organization_ids:
        payload["organization_ids[]"] = organization_ids
    if name:
        payload["q_organization_name"] = name
    if keywords:
        payload["q_organization_keyword_tags[]"] = keywords
    if technologies:
        payload["currently_using_any_of_technology_uids[]"] = technologies
    if revenue_min is not None:
        payload["revenue_range[min]"] = revenue_min
    if revenue_max is not None:
        payload["revenue_range[max]"] = revenue_max
    if latest_funding_amount_min is not None:
        payload["latest_funding_amount_range[min]"] = latest_funding_amount_min
    if latest_funding_amount_max is not None:
        payload["latest_funding_amount_range[max]"] = latest_funding_amount_max
    if total_funding_min is not None:
        payload["total_funding_range[min]"] = total_funding_min
    if total_funding_max is not None:
        payload["total_funding_range[max]"] = total_funding_max
    if latest_funding_date_min:
        payload["latest_funding_date_range[min]"] = latest_funding_date_min
    if latest_funding_date_max:
        payload["latest_funding_date_range[max]"] = latest_funding_date_max
    if job_titles:
        payload["q_organization_job_titles[]"] = job_titles
    if job_locations:
        payload["organization_job_locations[]"] = job_locations
    if job_count_min is not None:
        payload["organization_num_jobs_range[min]"] = job_count_min
    if job_count_max is not None:
        payload["organization_num_jobs_range[max]"] = job_count_max
    if job_posted_at_min:
        payload["organization_job_posted_at_range[min]"] = job_posted_at_min
    if job_posted_at_max:
        payload["organization_job_posted_at_range[max]"] = job_posted_at_max

    before = _fetch_call_counts()
    data = api_post("/mixed_companies/search", payload)
    after = _fetch_call_counts()

    pagination = data.get("pagination", {})
    total = pagination.get("total_entries", 0)
    orgs = data.get("organizations", [])

    lines = [f"Found {total} organizations (page {page}, showing {len(orgs)})\n"]
    for o in orgs:
        lines.append(
            f"- {o.get('name', 'N/A')} | {o.get('primary_domain', 'N/A')} | "
            f"id: {o.get('id')} | employees: ~{o.get('estimated_num_employees', 'N/A')} | "
            f"{o.get('city', '')}, {o.get('country', '')}"
        )
    lines.append(_credit_footer(before, after))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ENRICHMENT (consumes credits)
# ---------------------------------------------------------------------------

@mcp.tool()
def enrich_person(
    name: str = None,
    first_name: str = None,
    last_name: str = None,
    email: str = None,
    domain: str = None,
    linkedin_url: str = None,
    apollo_id: str = None,
    reveal_personal_emails: bool = False,
    reveal_phone: bool = False,
    webhook_url: str = None,
) -> str:
    """
    Enrich data for 1 person — returns full profile with email. Consumes credits.
    Provide as much info as possible for best match (name + domain is usually enough).

    Args:
        name: Full name, e.g. "Tim Zheng"
        first_name: First name
        last_name: Last name
        email: Known email address
        domain: Company domain, e.g. "apollo.io"
        linkedin_url: LinkedIn profile URL
        apollo_id: Apollo person ID from search_people results
        reveal_personal_emails: Include personal email addresses (extra credits)
        reveal_phone: Include phone numbers — requires webhook_url (async delivery)
        webhook_url: Required if reveal_phone=True
    """
    payload: dict = {}
    if name:
        payload["name"] = name
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if email:
        payload["email"] = email
    if domain:
        payload["domain"] = domain
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if apollo_id:
        payload["id"] = apollo_id
    if reveal_personal_emails:
        payload["reveal_personal_emails"] = True
    if reveal_phone:
        payload["reveal_phone_number"] = True
        if webhook_url:
            payload["webhook_url"] = webhook_url

    before = _fetch_call_counts()
    data = api_post("/people/match", payload)
    after = _fetch_call_counts()

    person = data.get("person") or {}
    if not person:
        return "No match found." + _credit_footer(before, after)

    org = person.get("organization") or {}
    contact = person.get("contact") or {}
    phones = contact.get("phone_numbers") or []

    lines = [
        f"Name: {person.get('name')}",
        f"Title: {person.get('title')}",
        f"Email: {person.get('email') or contact.get('email', 'N/A')}",
        f"Email status: {person.get('email_status')}",
        f"LinkedIn: {person.get('linkedin_url', 'N/A')}",
        f"Location: {person.get('city', '')}, {person.get('country', '')}",
        f"Company: {org.get('name', 'N/A')} ({org.get('primary_domain', '')})",
        f"Company size: ~{org.get('estimated_num_employees', 'N/A')} employees",
        f"Apollo ID: {person.get('id')}",
    ]
    if phones:
        lines.append(f"Phone: {phones[0].get('sanitized_number', 'N/A')}")
    lines.append(_credit_footer(before, after))
    return "\n".join(lines)


@mcp.tool()
def bulk_enrich_people(details: list[dict]) -> str:
    """
    Enrich data for up to 10 people in one request. Consumes credits.
    Each person needs at minimum name + domain, or linkedin_url, or email.

    Args:
        details: List of dicts, each with: first_name, last_name, domain, email, linkedin_url
                 Example: [{"first_name": "Tim", "last_name": "Zheng", "domain": "apollo.io"},
                           {"linkedin_url": "https://linkedin.com/in/someone"}]
    """
    payload = {"details": details, "reveal_personal_emails": False}
    before = _fetch_call_counts()
    data = api_post("/people/bulk_match", payload)
    after = _fetch_call_counts()

    matches = data.get("matches") or []

    lines = [f"Enriched {len(matches)} / {len(details)} people\n"]
    for m in matches:
        lines.append(
            f"- {m.get('name', 'N/A')} | {m.get('title', 'N/A')} | "
            f"email: {m.get('email', 'N/A')} | status: {m.get('email_status', 'N/A')}"
        )
    lines.append(_credit_footer(before, after))
    return "\n".join(lines)


@mcp.tool()
def enrich_organization(domain: str) -> str:
    """
    Enrich full company profile by domain. Returns industry, size, funding, tech stack.

    Args:
        domain: Company domain, e.g. "stripe.com"
    """
    before = _fetch_call_counts()
    data = api_get("/organizations/enrich", params={"domain": domain})
    after = _fetch_call_counts()

    org = data.get("organization") or {}
    if not org:
        return "No match found." + _credit_footer(before, after)

    techs = [t.get("name") for t in (org.get("current_technologies") or [])[:10]]
    keywords = org.get("keywords") or []
    lines = [
        f"Name: {org.get('name')}",
        f"Domain: {org.get('primary_domain')}",
        f"Website: {org.get('website_url', 'N/A')}",
        f"Industry: {org.get('industry')}",
        f"Employees: ~{org.get('estimated_num_employees')}",
        f"Revenue: {org.get('annual_revenue_printed', 'N/A')}",
        f"Location: {org.get('city', '')}, {org.get('country', '')}",
        f"LinkedIn: {org.get('linkedin_url', 'N/A')}",
        f"Founded: {org.get('founded_year', 'N/A')}",
        f"Total funding: {org.get('total_funding_printed', 'N/A')}",
        f"Latest round: {org.get('latest_funding_stage', 'N/A')} ({str(org.get('latest_funding_round_date', ''))[:10]})",
        f"Tech stack: {', '.join(techs) if techs else 'N/A'}",
        f"Keywords: {', '.join(keywords) if keywords else 'N/A'}",
        f"Apollo ID: {org.get('id')}",
    ]
    lines.append(_credit_footer(before, after))
    return "\n".join(lines)


@mcp.tool()
def bulk_enrich_organizations(domains: list[str]) -> str:
    """
    Enrich up to 10 companies in one request. Consumes credits.

    Args:
        domains: List of company domains, e.g. ["stripe.com", "notion.so"]
                 Max 10 per request.
    """
    before = _fetch_call_counts()
    data = api_post("/organizations/bulk_enrich", {"domains": domains})
    after = _fetch_call_counts()

    orgs = data.get("organizations") or []
    lines = [f"Enriched {len(orgs)} / {len(domains)} organizations\n"]
    for org in orgs:
        lines.append(
            f"- {org.get('name', 'N/A')} | {org.get('primary_domain', 'N/A')} | "
            f"~{org.get('estimated_num_employees', '?')} employees | "
            f"{org.get('industry', 'N/A')} | {org.get('city', '')}, {org.get('country', '')}"
        )
    lines.append(_credit_footer(before, after))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CONTACTS (CRM)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_contact(
    first_name: str,
    last_name: str,
    email: str = None,
    title: str = None,
    organization_name: str = None,
    phone: str = None,
    linkedin_url: str = None,
    label_names: list[str] = None,
) -> str:
    """
    Create a single contact in Apollo CRM.

    Args:
        first_name: Contact's first name
        last_name: Contact's last name
        email: Email address
        title: Job title
        organization_name: Company name
        phone: Phone number
        linkedin_url: LinkedIn profile URL
        label_names: Tags to apply, e.g. ["VIP", "Crona-import"]
    """
    payload: dict = {"first_name": first_name, "last_name": last_name}
    if email:
        payload["email"] = email
    if title:
        payload["title"] = title
    if organization_name:
        payload["organization_name"] = organization_name
    if phone:
        payload["phone"] = phone
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if label_names:
        payload["label_names"] = label_names

    data = api_post("/contacts", payload)
    contact = data.get("contact") or {}
    return f"Created: {contact.get('name')} | id: {contact.get('id')} | email: {contact.get('email')}"


@mcp.tool()
def bulk_create_contacts(contacts: list[dict], run_dedupe: bool = True) -> str:
    """
    Create up to 100 contacts in Apollo CRM in one request.
    Use to import contacts from Crona or CSV exports.

    Args:
        contacts: List of contact dicts. Supported fields per contact:
                  first_name, last_name, email, title, organization_name,
                  phone, linkedin_url, append_label_names (list of tags)
                  Example: [{"first_name": "John", "last_name": "Doe",
                             "email": "john@stripe.com", "title": "CEO",
                             "organization_name": "Stripe",
                             "append_label_names": ["Crona-Q1"]}]
        run_dedupe: Skip duplicates matching by email (default True)
    """
    payload = {"contacts": contacts, "run_dedupe": run_dedupe}
    data = api_post("/contacts/bulk_create", payload)
    created = data.get("created_contacts") or []
    existing = data.get("existing_contacts") or []
    return (
        f"Created: {len(created)} | Already existed (skipped): {len(existing)} | "
        f"Total submitted: {len(contacts)}"
    )


@mcp.tool()
def search_contacts(
    q_keywords: str = None,
    email: str = None,
    organization_name: str = None,
    label_names: list[str] = None,
    sort_by: str = None,
    sort_ascending: bool = False,
    page: int = 1,
    per_page: int = 25,
) -> str:
    """
    Search contacts already in your Apollo CRM.

    Args:
        q_keywords: Free text search
        email: Search by email address
        organization_name: Filter by company name
        label_names: Filter by label/tag names, e.g. ["Crona-Q1"]
        sort_by: Sort field: "contact_last_activity_date", "contact_created_at",
                 "contact_updated_at", "contact_email_last_opened_at"
        sort_ascending: Sort ascending (default False = newest first)
        page: Page number
        per_page: Results per page (max 100)
    """
    payload: dict = {"page": page, "per_page": per_page}
    if q_keywords:
        payload["q_keywords"] = q_keywords
    if email:
        payload["q_email"] = email
    if organization_name:
        payload["q_organization_name"] = organization_name
    if label_names:
        payload["label_names[]"] = label_names
    if sort_by:
        payload["sort_by_field"] = sort_by
        payload["sort_ascending"] = sort_ascending

    data = api_post("/contacts/search", payload)
    pagination = data.get("pagination") or {}
    total = pagination.get("total_entries", 0)
    contacts = data.get("contacts") or []

    lines = [f"Found {total} contacts in CRM (page {page}, showing {len(contacts)})\n"]
    for c in contacts:
        lines.append(
            f"- {c.get('name', 'N/A')} | {c.get('title', 'N/A')} @ "
            f"{c.get('organization_name', 'N/A')} | "
            f"email: {c.get('email', 'N/A')} | id: {c.get('id')}"
        )
    return "\n".join(lines)


@mcp.tool()
def update_contact(
    contact_id: str,
    first_name: str = None,
    last_name: str = None,
    email: str = None,
    title: str = None,
    organization_name: str = None,
    phone: str = None,
    linkedin_url: str = None,
    label_names: list[str] = None,
) -> str:
    """
    Update an existing contact in Apollo CRM.

    Args:
        contact_id: Apollo contact ID (from search_contacts)
        first_name: New first name
        last_name: New last name
        email: New email
        title: New job title
        organization_name: New company name
        phone: New phone
        linkedin_url: New LinkedIn URL
        label_names: Replace all labels with these
    """
    payload: dict = {}
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if email:
        payload["email"] = email
    if title:
        payload["title"] = title
    if organization_name:
        payload["organization_name"] = organization_name
    if phone:
        payload["phone"] = phone
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if label_names is not None:
        payload["label_names"] = label_names

    resp = httpx.patch(
        f"{BASE_URL}/contacts/{contact_id}",
        headers=headers(), json=payload, timeout=30,
    )
    resp.raise_for_status()
    contact = resp.json().get("contact") or {}
    return f"Updated: {contact.get('name')} | id: {contact.get('id')} | email: {contact.get('email')}"


@mcp.tool()
def export_contacts_csv(
    output_path: str,
    q_keywords: str = None,
    organization_name: str = None,
    label_names: list[str] = None,
    per_page: int = 100,
    max_pages: int = 5,
) -> str:
    """
    Search CRM contacts and save results to CSV file.
    Up to 500 contacts per call (5 pages x 100).

    Args:
        output_path: Absolute path for the CSV, e.g. "/Users/user/Desktop/leads.csv"
        q_keywords: Free text filter
        organization_name: Filter by company
        label_names: Filter by label/tag, e.g. ["Crona-Q1"]
        per_page: Results per page (max 100)
        max_pages: Max pages to fetch (default 5 = up to 500 contacts)
    """
    all_contacts = []
    for page in range(1, max_pages + 1):
        payload: dict = {"page": page, "per_page": per_page}
        if q_keywords:
            payload["q_keywords"] = q_keywords
        if organization_name:
            payload["q_organization_name"] = organization_name
        if label_names:
            payload["label_names[]"] = label_names

        data = api_post("/contacts/search", payload)
        contacts = data.get("contacts") or []
        all_contacts.extend(contacts)

        pagination = data.get("pagination") or {}
        if page >= pagination.get("total_pages", 1):
            break

    if not all_contacts:
        return "No contacts found matching criteria."

    fields = [
        "id", "first_name", "last_name", "email", "email_status",
        "title", "organization_name", "sanitized_phone",
        "city", "country", "linkedin_url",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_contacts)

    return f"Exported {len(all_contacts)} contacts -> {output_path}"


# ---------------------------------------------------------------------------
# ACCOUNTS (CRM)
# ---------------------------------------------------------------------------

@mcp.tool()
def bulk_create_accounts(accounts: list[dict]) -> str:
    """
    Create up to 100 company accounts in Apollo CRM.
    Import company lists from Crona, CSV, or any other source.
    After importing, use search_people with organization_domains to find people inside them.

    Args:
        accounts: List of account dicts. Each should have: name, domain
                  Optional: phone, industry, city, country
                  Example: [{"name": "Stripe", "domain": "stripe.com"},
                            {"name": "Notion", "domain": "notion.so", "industry": "saas"}]
    """
    payload = {"accounts": accounts}
    data = api_post("/accounts/bulk_create", payload)
    created = data.get("accounts") or []
    return f"Created {len(created)} accounts"


@mcp.tool()
def search_accounts(
    q_organization_name: str = None,
    label_names: list[str] = None,
    sort_by: str = None,
    sort_ascending: bool = False,
    page: int = 1,
    per_page: int = 25,
) -> str:
    """
    Search company accounts in your Apollo CRM.

    Args:
        q_organization_name: Filter by company name (partial match)
        label_names: Filter by label/tag names
        sort_by: Sort field: "account_last_activity_date", "account_created_at", "account_updated_at"
        sort_ascending: Sort ascending (default False = newest first)
        page: Page number
        per_page: Results per page (max 100)
    """
    payload: dict = {"page": page, "per_page": per_page}
    if q_organization_name:
        payload["q_organization_name"] = q_organization_name
    if label_names:
        payload["label_names[]"] = label_names
    if sort_by:
        payload["sort_by_field"] = sort_by
        payload["sort_ascending"] = sort_ascending

    data = api_post("/accounts/search", payload)
    pagination = data.get("pagination") or {}
    total = pagination.get("total_entries", 0)
    accounts = data.get("accounts") or []

    lines = [f"Found {total} accounts in CRM (page {page}, showing {len(accounts)})\n"]
    for a in accounts:
        lines.append(
            f"- {a.get('name', 'N/A')} | {a.get('domain', 'N/A')} | id: {a.get('id')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SEQUENCES
# ---------------------------------------------------------------------------

@mcp.tool()
def search_sequences(q_name: str = None, per_page: int = 25) -> str:
    """
    List sequences in your Apollo account.
    Returns sequence IDs needed for add_to_sequence.

    Args:
        q_name: Filter sequences by name keyword
        per_page: Number of results (default 25)
    """
    payload: dict = {"per_page": per_page}
    if q_name:
        payload["q_name"] = q_name

    data = api_post("/emailer_campaigns/search", payload)
    campaigns = data.get("emailer_campaigns") or []

    lines = [f"Found {len(campaigns)} sequences\n"]
    for c in campaigns:
        status = "active" if c.get("active") else "paused"
        lines.append(
            f"- [{status}] {c.get('name', 'N/A')} | "
            f"id: {c.get('id')} | "
            f"steps: {c.get('num_steps', 0)} | "
            f"sent: {c.get('unique_delivered', 0)} | "
            f"open_rate: {c.get('open_rate', 0)}% | "
            f"reply_rate: {c.get('reply_rate', 0)}%"
        )
    return "\n".join(lines)


@mcp.tool()
def get_email_accounts() -> str:
    """
    Get list of connected email accounts.
    Returns email_account_id needed for add_to_sequence.
    """
    data = api_get("/email_accounts")
    accounts = data.get("email_accounts") or []

    lines = [f"Found {len(accounts)} email accounts\n"]
    for a in accounts:
        status = "active" if a.get("active") else "inactive"
        lines.append(
            f"- [{status}] {a.get('email')} ({a.get('provider_display_name', 'N/A')}) | "
            f"id: {a.get('id')} | "
            f"daily_limit: {a.get('email_daily_threshold', 'N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
def add_to_sequence(
    sequence_id: str,
    contact_ids: list[str],
    email_account_id: str,
    allow_unverified_email: bool = False,
) -> str:
    """
    Add contacts to an Apollo sequence (email campaign).

    Args:
        sequence_id: Sequence ID from search_sequences
        contact_ids: Contact IDs from search_contacts or bulk_create_contacts
        email_account_id: Email account ID from get_email_accounts
        allow_unverified_email: Add contacts with unverified emails (default False)
    """
    payload = {
        "emailer_campaign_id": sequence_id,
        "contact_ids[]": contact_ids,
        "send_email_from_email_account_id": email_account_id,
        "sequence_unverified_email": allow_unverified_email,
    }
    data = api_post(f"/emailer_campaigns/{sequence_id}/add_contact_ids", payload)
    contacts_added = data.get("contacts") or []
    skipped = data.get("skipped_contact_ids") or {}
    campaign = data.get("emailer_campaign") or {}
    statuses = campaign.get("contact_statuses") or {}

    return (
        f"Added to '{campaign.get('name', sequence_id)}': {len(contacts_added)} contacts | "
        f"Skipped: {len(skipped)} | "
        f"Active in sequence: {statuses.get('active', 'N/A')}"
    )


@mcp.tool()
def remove_from_sequence(
    sequence_ids: list[str],
    contact_ids: list[str],
    mode: str = "mark_as_finished",
) -> str:
    """
    Remove or stop contacts in a sequence.

    Args:
        sequence_ids: Sequence IDs
        contact_ids: Contact IDs to remove/stop
        mode: "mark_as_finished", "remove", or "stop"
    """
    payload = {
        "emailer_campaign_ids[]": sequence_ids,
        "contact_ids[]": contact_ids,
        "mode": mode,
    }
    data = api_post("/emailer_campaigns/remove_or_stop_contact_ids", payload)
    return f"Done. Mode: {mode} | Contacts: {len(contact_ids)}"


# ---------------------------------------------------------------------------
# MISC
# ---------------------------------------------------------------------------

@mcp.tool()
def view_api_usage() -> str:
    """Check Apollo API credit and request usage statistics."""
    data = api_get("/usage_stats")
    stats = data.get("usage_stats") or data
    return json.dumps(stats, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
