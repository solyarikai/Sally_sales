#!/usr/bin/env python3
"""Universal SmartLead API CLI tool.

Covers: campaigns, leads, sequences, email-accounts, analytics, webhooks, master-inbox.
"""

import argparse
import csv
import json
import ssl
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

_SSL_CTX = ssl._create_unverified_context()

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
RATE_LIMIT_PAUSE = 0.35


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def api_get(endpoint, params=None):
    """GET request to SmartLead API."""
    params = params or {}
    params["api_key"] = API_KEY
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
    return _request(url, method="GET")


def api_post(endpoint, body=None, params=None):
    """POST request to SmartLead API."""
    params = params or {}
    params["api_key"] = API_KEY
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
    return _request(url, method="POST", body=body)


def api_patch(endpoint, body=None, params=None):
    """PATCH request to SmartLead API."""
    params = params or {}
    params["api_key"] = API_KEY
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
    return _request(url, method="PATCH", body=body)


def api_delete(endpoint, params=None):
    """DELETE request to SmartLead API."""
    params = params or {}
    params["api_key"] = API_KEY
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
    return _request(url, method="DELETE")


def _request(url, method="GET", body=None, retries=3):
    """Execute HTTP request with retry on 429."""
    data_bytes = json.dumps(body).encode("utf-8") if body else None
    for attempt in range(retries):
        req = Request(url, data=data_bytes, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 SmartLead-CLI/1.0")
        try:
            with urlopen(req, context=_SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
                time.sleep(RATE_LIMIT_PAUSE)
                if not raw.strip():
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"raw": raw}
        except HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            body_text = e.read().decode() if e.fp else str(e)
            print(f"API Error {e.code}: {body_text}", file=sys.stderr)
            sys.exit(1)
        except URLError as e:
            print(f"Network error: {e.reason}", file=sys.stderr)
            sys.exit(1)


def out(data):
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# CAMPAIGNS
# ---------------------------------------------------------------------------


def cmd_campaigns_list(args):
    """List all campaigns."""
    data = api_get("/campaigns/", {"include_tags": "true"})
    campaigns = data if isinstance(data, list) else data.get("campaigns", data)

    if args.search:
        q = args.search.lower()
        campaigns = [c for c in campaigns if q in c.get("name", "").lower()]

    if args.status:
        campaigns = [
            c for c in campaigns if c.get("status", "").upper() == args.status.upper()
        ]

    if args.json:
        out(campaigns)
    else:
        print(f"\n{'ID':<10} {'Status':<10} {'Name'}")
        print("-" * 70)
        for c in campaigns:
            print(f"{c['id']:<10} {c.get('status', '?'):<10} {c.get('name', '')}")
        print(f"\nTotal: {len(campaigns)}")


def cmd_campaigns_get(args):
    """Get campaign by ID."""
    data = api_get(f"/campaigns/{args.campaign_id}")
    out(data)


def cmd_campaigns_create(args):
    """Create a new campaign (DRAFTED status)."""
    body = {"name": args.name}
    if args.client_id:
        body["client_id"] = args.client_id
    data = api_post("/campaigns/create", body)
    out(data)
    print(f"\nCampaign created: ID={data.get('id')}", file=sys.stderr)


def cmd_campaigns_status(args):
    """Update campaign status. NEVER sends START — safety rule."""
    status = args.status.upper()
    if status in ("START", "ACTIVE"):
        print(
            "ERROR: Activating campaigns via API is forbidden. Use SmartLead UI.",
            file=sys.stderr,
        )
        sys.exit(1)
    data = api_post(f"/campaigns/{args.campaign_id}/status", {"status": status})
    out(data)


def cmd_campaigns_settings(args):
    """Update campaign settings."""
    body = json.loads(args.settings_json)
    data = api_post(f"/campaigns/{args.campaign_id}/settings", body)
    out(data)


def cmd_campaigns_schedule(args):
    """Set campaign schedule."""
    body = json.loads(args.schedule_json)
    data = api_post(f"/campaigns/{args.campaign_id}/schedule", body)
    out(data)


# ---------------------------------------------------------------------------
# LEADS
# ---------------------------------------------------------------------------


def _fetch_all_leads(campaign_id, status=None, email_status=None, category_id=None):
    """Paginate through all leads."""
    all_leads = []
    offset = 0
    limit = 100

    while True:
        params = {"offset": offset, "limit": limit}
        if status:
            params["status"] = status
        if email_status:
            params["emailStatus"] = email_status
        if category_id:
            params["category_id"] = category_id

        data = api_get(f"/campaigns/{campaign_id}/leads", params)

        if isinstance(data, dict):
            leads = data.get("data", [])
            total = int(data.get("total_leads", data.get("total", 0)))
        elif isinstance(data, list):
            leads = data
            total = len(data)
        else:
            break

        if not leads:
            break

        all_leads.extend(leads)
        print(f"  Fetched {len(all_leads)}/{total}", file=sys.stderr)

        if len(all_leads) >= total or len(leads) < limit:
            break
        offset += limit

    return all_leads


def cmd_leads_list(args):
    """List leads in a campaign (JSON)."""
    leads = _fetch_all_leads(
        args.campaign_id,
        status=args.status,
        email_status=args.email_status,
        category_id=args.category_id,
    )
    if args.require_job_title:
        leads = [l for l in leads if _get_job_title(l)]
    out(leads)
    print(f"\nTotal: {len(leads)}", file=sys.stderr)


def cmd_leads_export(args):
    """Export leads to CSV with ALL fields."""
    leads = _fetch_all_leads(
        args.campaign_id,
        status=args.status,
        email_status=args.email_status,
        category_id=args.category_id,
    )

    if args.require_job_title:
        before = len(leads)
        leads = [l for l in leads if _get_job_title(l)]
        print(f"  Filtered: {len(leads)}/{before} with job title", file=sys.stderr)

    if not leads:
        print("No leads found.", file=sys.stderr)
        sys.exit(0)

    # Collect all custom field keys across all leads
    cf_keys = set()
    for item in leads:
        lead = item.get("lead", item)
        cf = lead.get("custom_fields") or {}
        if isinstance(cf, dict):
            cf_keys.update(cf.keys())
    cf_keys = sorted(cf_keys)

    # Build output path
    if args.output:
        output_path = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = f"leads_campaign_{args.campaign_id}_{ts}.csv"

    # Standard fields
    std_fields = [
        "campaign_lead_map_id",
        "status",
        "lead_category_id",
        "created_at",
        "lead_id",
        "email",
        "first_name",
        "last_name",
        "company_name",
        "job_title",
        "phone_number",
        "location",
        "linkedin_profile",
        "website",
        "company_url",
        "is_unsubscribed",
    ]
    all_fields = std_fields + [f"cf_{k}" for k in cf_keys]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()

        for item in leads:
            lead = item.get("lead", item)
            cf = lead.get("custom_fields") or {}
            if not isinstance(cf, dict):
                cf = {}

            row = {
                "campaign_lead_map_id": item.get("campaign_lead_map_id", ""),
                "status": item.get("status", lead.get("status", "")),
                "lead_category_id": item.get("lead_category_id", ""),
                "created_at": item.get("created_at", ""),
                "lead_id": lead.get("id", ""),
                "email": lead.get("email", ""),
                "first_name": lead.get("first_name", ""),
                "last_name": lead.get("last_name", ""),
                "company_name": lead.get("company_name", ""),
                "job_title": _get_job_title(item) or "",
                "phone_number": lead.get("phone_number", ""),
                "location": lead.get("location", ""),
                "linkedin_profile": lead.get("linkedin_profile", ""),
                "website": lead.get("website", ""),
                "company_url": lead.get("company_url", ""),
                "is_unsubscribed": lead.get("is_unsubscribed", False),
            }
            for k in cf_keys:
                row[f"cf_{k}"] = cf.get(k, "")

            writer.writerow(row)

    print(f"\nExported {len(leads)} leads → {output_path}", file=sys.stderr)


def cmd_leads_add(args):
    """Add leads to campaign from JSON file (max 400 per batch)."""
    with open(args.file, "r") as f:
        all_leads = json.load(f)

    batch_size = 400
    total_added = 0
    total_skipped = 0

    for i in range(0, len(all_leads), batch_size):
        batch = all_leads[i : i + batch_size]
        body = {"lead_list": batch}
        if args.skip_blocklist:
            body["settings"] = {"ignore_global_block_list": True}
        if args.allow_duplicates:
            body.setdefault("settings", {})[
                "ignore_duplicate_leads_in_other_campaign"
            ] = True

        result = api_post(f"/campaigns/{args.campaign_id}/leads", body)
        added = result.get("added_count", result.get("upload_count", 0))
        skipped = result.get("skipped_count", 0)
        total_added += added
        total_skipped += skipped
        print(
            f"  Batch {i // batch_size + 1}: +{added}, skipped {skipped}",
            file=sys.stderr,
        )

    print(f"\nTotal added: {total_added}, skipped: {total_skipped}", file=sys.stderr)


def cmd_leads_search(args):
    """Search lead by email."""
    data = api_get("/leads/", {"email": args.email})
    out(data)


def cmd_leads_update(args):
    """Update lead in campaign."""
    body = json.loads(args.update_json)
    data = api_post(f"/campaigns/{args.campaign_id}/leads/{args.lead_id}", body)
    out(data)


def cmd_leads_pause(args):
    """Pause lead in campaign."""
    data = api_post(f"/campaigns/{args.campaign_id}/leads/{args.lead_id}/pause")
    out(data)


def cmd_leads_resume(args):
    """Resume lead in campaign."""
    data = api_post(f"/campaigns/{args.campaign_id}/leads/{args.lead_id}/resume")
    out(data)


def cmd_leads_delete(args):
    """Delete a lead from a campaign."""
    data = api_delete(f"/campaigns/{args.campaign_id}/leads/{args.lead_id}")
    out(data)


def cmd_leads_bulk_delete(args):
    """Delete all leads in a campaign that match IDs from a file (one lead_id per line)."""
    with open(args.file) as f:
        lead_ids = [int(line.strip()) for line in f if line.strip()]
    total = len(lead_ids)
    print(
        f"Deleting {total} leads from campaign {args.campaign_id}...", file=sys.stderr
    )
    for i, lead_id in enumerate(lead_ids, 1):
        result = api_delete(f"/campaigns/{args.campaign_id}/leads/{lead_id}")
        ok = result.get("message") or result.get("status") or result
        if i % 50 == 0 or i == total:
            print(f"  {i}/{total} done", file=sys.stderr)


def cmd_leads_unsubscribe(args):
    """Unsubscribe lead globally."""
    data = api_post(f"/leads/{args.lead_id}/unsubscribe")
    out(data)


def cmd_leads_categories(args):
    """List all lead categories."""
    data = api_get("/leads/fetch-categories")
    out(data)


def cmd_leads_set_category(args):
    """Set lead category in campaign."""
    data = api_post(
        f"/campaigns/{args.campaign_id}/leads/{args.lead_id}/category",
        {"category_id": int(args.category_id)},
    )
    out(data)


def cmd_leads_history(args):
    """Get message history for lead in campaign."""
    data = api_get(
        f"/campaigns/{args.campaign_id}/leads/{args.lead_id}/message-history"
    )
    out(data)


# ---------------------------------------------------------------------------
# SEQUENCES
# ---------------------------------------------------------------------------


def cmd_sequences_get(args):
    """Get sequences for a campaign."""
    data = api_get(f"/campaigns/{args.campaign_id}/sequences")
    out(data)


def cmd_sequences_set(args):
    """Create/update sequences from JSON file."""
    with open(args.file, "r") as f:
        sequences = json.load(f)
    data = api_post(
        f"/campaigns/{args.campaign_id}/sequences", {"sequences": sequences}
    )
    out(data)


# ---------------------------------------------------------------------------
# EMAIL ACCOUNTS
# ---------------------------------------------------------------------------


def cmd_accounts_list(args):
    """List all email accounts."""
    params = {}
    if args.limit:
        params["limit"] = args.limit
    if args.offset:
        params["offset"] = args.offset
    if args.warmup_status:
        params["emailWarmupStatus"] = args.warmup_status
    data = api_get("/email-accounts/", params)
    accounts = data if isinstance(data, list) else data.get("data", [])

    if args.json:
        out(accounts)
    else:
        print(
            f"\n{'ID':<8} {'Email':<35} {'Type':<8} {'SMTP':<6} {'Warmup':<10} {'Campaigns'}"
        )
        print("-" * 90)
        for a in accounts:
            warmup = a.get("warmup_details") or {}
            print(
                f"{a.get('id', ''):<8} "
                f"{a.get('from_email', ''):<35} "
                f"{a.get('type', ''):<8} "
                f"{'OK' if a.get('is_smtp_success') else 'FAIL':<6} "
                f"{warmup.get('status', 'N/A'):<10} "
                f"{a.get('campaign_count', 0)}"
            )
        print(f"\nTotal: {len(accounts)}")


def cmd_accounts_campaign(args):
    """Get email accounts for a campaign."""
    data = api_get(f"/campaigns/{args.campaign_id}/email-accounts")
    out(data)


def cmd_accounts_add(args):
    """Add email accounts to a campaign."""
    ids = [int(x.strip()) for x in args.account_ids.split(",")]
    data = api_post(
        f"/campaigns/{args.campaign_id}/email-accounts", {"email_account_ids": ids}
    )
    out(data)


# ---------------------------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------------------------


def cmd_analytics_campaign(args):
    """Get campaign statistics."""
    data = api_get(f"/campaigns/{args.campaign_id}/statistics")
    out(data)


def cmd_analytics_sequences(args):
    """Get per-step sequence analytics."""
    data = api_get(f"/campaigns/{args.campaign_id}/sequence-analytics")
    out(data)


def cmd_analytics_by_date(args):
    """Get analytics by date range."""
    params = {}
    if args.start_date:
        params["start_date"] = args.start_date
    if args.end_date:
        params["end_date"] = args.end_date
    data = api_get(f"/campaigns/{args.campaign_id}/analytics-by-date", params)
    out(data)


# ---------------------------------------------------------------------------
# WEBHOOKS
# ---------------------------------------------------------------------------


def cmd_webhooks_list(args):
    """List all webhooks."""
    data = api_get("/webhooks")
    out(data)


def cmd_webhooks_create(args):
    """Create a webhook."""
    body = json.loads(args.webhook_json)
    data = api_post("/webhook/create", body)
    out(data)


def cmd_webhooks_update(args):
    """Update a webhook."""
    body = json.loads(args.update_json)
    data = api_patch(f"/webhooks/{args.webhook_id}", body)
    out(data)


def cmd_webhooks_delete(args):
    """Delete a webhook."""
    data = api_delete(f"/webhooks/{args.webhook_id}")
    out(data)


# ---------------------------------------------------------------------------
# MASTER INBOX
# ---------------------------------------------------------------------------


def cmd_inbox_replies(args):
    """Fetch replied leads from master inbox."""
    body = {}
    if args.campaign_id:
        body["campaign_id"] = int(args.campaign_id)
    if args.offset:
        body["offset"] = int(args.offset)
    if args.limit:
        body["limit"] = int(args.limit)
    data = api_post("/master-inbox/inbox-replies", body)
    out(data)


def cmd_inbox_reply(args):
    """Reply to a lead in campaign."""
    data = api_post(
        f"/campaigns/{args.campaign_id}/reply-email-thread",
        {"lead_id": int(args.lead_id), "message": args.message},
    )
    out(data)


def cmd_inbox_note(args):
    """Create a note for a lead."""
    data = api_post(
        "/master-inbox/create-note", {"lead_id": int(args.lead_id), "note": args.note}
    )
    out(data)


def cmd_inbox_category(args):
    """Update lead category in master inbox."""
    data = api_patch(
        "/master-inbox/update-category",
        {"lead_id": int(args.lead_id), "category_id": int(args.category_id)},
    )
    out(data)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _get_job_title(item):
    """Extract job title from lead structure."""
    lead = item.get("lead", item)
    cf = lead.get("custom_fields") or {}
    if isinstance(cf, dict):
        for key in (
            "job_title",
            "title",
            "position",
            "designation",
            "Job Title",
            "Title",
        ):
            val = cf.get(key)
            if val and str(val).strip():
                return str(val).strip()
    for key in ("job_title", "title", "position"):
        val = lead.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return None


# ---------------------------------------------------------------------------
# CLI PARSER
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="smartlead", description="Universal SmartLead API CLI"
    )
    sub = parser.add_subparsers(dest="command")

    # --- campaigns ---
    p = sub.add_parser("campaigns", help="List campaigns")
    p.add_argument("--search", help="Filter by name (case-insensitive)")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_campaigns_list)

    p = sub.add_parser("campaign-get", help="Get campaign by ID")
    p.add_argument("campaign_id", type=int)
    p.set_defaults(func=cmd_campaigns_get)

    p = sub.add_parser("campaign-create", help="Create campaign")
    p.add_argument("name")
    p.add_argument("--client-id", type=int)
    p.set_defaults(func=cmd_campaigns_create)

    p = sub.add_parser(
        "campaign-status", help="Update campaign status (PAUSED/STOPPED only)"
    )
    p.add_argument("campaign_id", type=int)
    p.add_argument("status", choices=["PAUSED", "STOPPED"])
    p.set_defaults(func=cmd_campaigns_status)

    p = sub.add_parser("campaign-settings", help="Update campaign settings")
    p.add_argument("campaign_id", type=int)
    p.add_argument("settings_json", help="JSON string with settings")
    p.set_defaults(func=cmd_campaigns_settings)

    p = sub.add_parser("campaign-schedule", help="Set campaign schedule")
    p.add_argument("campaign_id", type=int)
    p.add_argument("schedule_json", help="JSON string with schedule")
    p.set_defaults(func=cmd_campaigns_schedule)

    # --- leads ---
    p = sub.add_parser("leads", help="List leads (JSON)")
    p.add_argument("campaign_id", type=int)
    p.add_argument("--status", help="STARTED/INPROGRESS/COMPLETED/PAUSED/STOPPED")
    p.add_argument(
        "--email-status",
        help="is_replied/is_opened/is_clicked/is_bounced/is_unsubscribed",
    )
    p.add_argument("--category-id", type=int)
    p.add_argument("--require-job-title", action="store_true")
    p.set_defaults(func=cmd_leads_list)

    p = sub.add_parser("leads-export", help="Export leads to CSV")
    p.add_argument("campaign_id", type=int)
    p.add_argument("--status")
    p.add_argument("--email-status")
    p.add_argument("--category-id", type=int)
    p.add_argument("--require-job-title", action="store_true")
    p.add_argument("--output", "-o", help="Output CSV path")
    p.set_defaults(func=cmd_leads_export)

    p = sub.add_parser("leads-add", help="Add leads from JSON file")
    p.add_argument("campaign_id", type=int)
    p.add_argument("file", help="JSON file with lead_list array")
    p.add_argument("--skip-blocklist", action="store_true")
    p.add_argument("--allow-duplicates", action="store_true")
    p.set_defaults(func=cmd_leads_add)

    p = sub.add_parser("leads-search", help="Search lead by email")
    p.add_argument("email")
    p.set_defaults(func=cmd_leads_search)

    p = sub.add_parser("leads-update", help="Update lead in campaign")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.add_argument("update_json", help="JSON string with updates")
    p.set_defaults(func=cmd_leads_update)

    p = sub.add_parser("leads-pause", help="Pause lead")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.set_defaults(func=cmd_leads_pause)

    p = sub.add_parser("leads-resume", help="Resume lead")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.set_defaults(func=cmd_leads_resume)

    p = sub.add_parser("leads-delete", help="Delete a lead from a campaign")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.set_defaults(func=cmd_leads_delete)

    p = sub.add_parser(
        "leads-bulk-delete", help="Delete leads listed in a file (one lead_id per line)"
    )
    p.add_argument("campaign_id", type=int)
    p.add_argument("file", help="File with lead IDs, one per line")
    p.set_defaults(func=cmd_leads_bulk_delete)

    p = sub.add_parser("leads-unsubscribe", help="Unsubscribe lead globally")
    p.add_argument("lead_id", type=int)
    p.set_defaults(func=cmd_leads_unsubscribe)

    p = sub.add_parser("leads-categories", help="List all lead categories")
    p.set_defaults(func=cmd_leads_categories)

    p = sub.add_parser("leads-set-category", help="Set lead category")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.add_argument("category_id")
    p.set_defaults(func=cmd_leads_set_category)

    p = sub.add_parser("leads-history", help="Get message history")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.set_defaults(func=cmd_leads_history)

    # --- sequences ---
    p = sub.add_parser("sequences", help="Get campaign sequences")
    p.add_argument("campaign_id", type=int)
    p.set_defaults(func=cmd_sequences_get)

    p = sub.add_parser("sequences-set", help="Create/update sequences from JSON file")
    p.add_argument("campaign_id", type=int)
    p.add_argument("file", help="JSON file with sequences array")
    p.set_defaults(func=cmd_sequences_set)

    # --- email accounts ---
    p = sub.add_parser("accounts", help="List all email accounts")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--warmup-status", help="ACTIVE/INACTIVE")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_accounts_list)

    p = sub.add_parser("accounts-campaign", help="Get accounts for a campaign")
    p.add_argument("campaign_id", type=int)
    p.set_defaults(func=cmd_accounts_campaign)

    p = sub.add_parser("accounts-add", help="Add accounts to campaign")
    p.add_argument("campaign_id", type=int)
    p.add_argument("account_ids", help="Comma-separated account IDs")
    p.set_defaults(func=cmd_accounts_add)

    # --- analytics ---
    p = sub.add_parser("analytics", help="Campaign statistics")
    p.add_argument("campaign_id", type=int)
    p.set_defaults(func=cmd_analytics_campaign)

    p = sub.add_parser("analytics-sequences", help="Per-step sequence analytics")
    p.add_argument("campaign_id", type=int)
    p.set_defaults(func=cmd_analytics_sequences)

    p = sub.add_parser("analytics-dates", help="Analytics by date range")
    p.add_argument("campaign_id", type=int)
    p.add_argument("--start-date", help="ISO 8601 date")
    p.add_argument("--end-date", help="ISO 8601 date")
    p.set_defaults(func=cmd_analytics_by_date)

    # --- webhooks ---
    p = sub.add_parser("webhooks", help="List webhooks")
    p.set_defaults(func=cmd_webhooks_list)

    p = sub.add_parser("webhook-create", help="Create webhook")
    p.add_argument("webhook_json", help="JSON string with webhook config")
    p.set_defaults(func=cmd_webhooks_create)

    p = sub.add_parser("webhook-update", help="Update webhook")
    p.add_argument("webhook_id", type=int)
    p.add_argument("update_json", help="JSON string with updates")
    p.set_defaults(func=cmd_webhooks_update)

    p = sub.add_parser("webhook-delete", help="Delete webhook")
    p.add_argument("webhook_id", type=int)
    p.set_defaults(func=cmd_webhooks_delete)

    # --- master inbox ---
    p = sub.add_parser("inbox-replies", help="Fetch replied leads")
    p.add_argument("--campaign-id", type=int)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_inbox_replies)

    p = sub.add_parser("inbox-reply", help="Reply to a lead")
    p.add_argument("campaign_id", type=int)
    p.add_argument("lead_id", type=int)
    p.add_argument("message")
    p.set_defaults(func=cmd_inbox_reply)

    p = sub.add_parser("inbox-note", help="Create a note")
    p.add_argument("lead_id", type=int)
    p.add_argument("note")
    p.set_defaults(func=cmd_inbox_note)

    p = sub.add_parser("inbox-category", help="Update lead category in inbox")
    p.add_argument("lead_id", type=int)
    p.add_argument("category_id", type=int)
    p.set_defaults(func=cmd_inbox_category)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
