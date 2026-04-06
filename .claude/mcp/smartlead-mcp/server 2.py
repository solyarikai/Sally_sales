"""
Smartlead MCP Server
Manage email campaigns, leads, and inbox via Smartlead API.
"""

import os
import re
import json
import httpx
from fastmcp import FastMCP

API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BASE_URL = "https://server.smartlead.ai/api/v1"

mcp = FastMCP("Smartlead")


def params(extra: dict = None) -> dict:
    key = API_KEY or os.environ.get("SMARTLEAD_API_KEY", "")
    p = {"api_key": key}
    if extra:
        p.update(extra)
    return p


def api_get(path: str, query: dict = None) -> dict:
    resp = httpx.get(f"{BASE_URL}{path}", params=params(query), timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict = None, query: dict = None) -> dict:
    resp = httpx.post(
        f"{BASE_URL}{path}",
        params=params(query),
        json=body or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def api_patch(path: str, body: dict = None) -> dict:
    resp = httpx.patch(f"{BASE_URL}{path}", params=params(), json=body or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# CAMPAIGN MANAGEMENT
# ---------------------------------------------------------------------------

@mcp.tool()
def create_campaign(name: str, client_id: int = None) -> str:
    """
    Create a new Smartlead campaign.

    Args:
        name: Campaign name
        client_id: Optional client ID to associate with the campaign
    """
    body: dict = {"name": name}
    if client_id is not None:
        body["client_id"] = client_id
    data = api_post("/campaigns/create", body)
    return f"Created campaign: {data.get('name')} | id: {data.get('id')} | created_at: {data.get('created_at')}"


@mcp.tool()
def list_campaigns(client_id: int = None, include_tags: bool = False) -> str:
    """
    List all campaigns in the account.

    Args:
        client_id: Filter by client ID
        include_tags: Include campaign tags in response
    """
    query: dict = {}
    if client_id is not None:
        query["client_id"] = client_id
    if include_tags:
        query["include_tags"] = "true"
    data = api_get("/campaigns", query)
    campaigns = data if isinstance(data, list) else data.get("data", [])
    lines = [f"Found {len(campaigns)} campaigns\n"]
    for c in campaigns:
        lines.append(
            f"- [{c.get('status', 'N/A')}] {c.get('name', 'N/A')} | id: {c.get('id')} | "
            f"leads/day: {c.get('max_leads_per_day', 'N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_campaign(campaign_id: int) -> str:
    """
    Get details of a specific campaign by ID.

    Args:
        campaign_id: Campaign ID
    """
    data = api_get(f"/campaigns/{campaign_id}")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def set_campaign_status(campaign_id: int, status: str) -> str:
    """
    Change the status of a campaign.

    Args:
        campaign_id: Campaign ID
        status: New status — one of: START, PAUSED, STOPPED
    """
    data = api_post(f"/campaigns/{campaign_id}/status", {"status": status})
    return f"Campaign {campaign_id} status set to {status} | ok: {data.get('ok')}"


@mcp.tool()
def update_campaign_schedule(
    campaign_id: int,
    timezone: str,
    days_of_the_week: list[int],
    start_hour: str,
    end_hour: str,
    min_time_btw_emails: int = 5,
    max_new_leads_per_day: int = 50,
    schedule_start_time: str = None,
) -> str:
    """
    Set the sending schedule for a campaign.

    Args:
        campaign_id: Campaign ID
        timezone: Timezone string, e.g. "Europe/Moscow", "America/New_York"
        days_of_the_week: Days to send (0=Sun, 1=Mon, ..., 6=Sat), e.g. [1,2,3,4,5]
        start_hour: Send start time in HH:MM format, e.g. "09:00"
        end_hour: Send end time in HH:MM format, e.g. "18:00"
        min_time_btw_emails: Min minutes between emails (default 5)
        max_new_leads_per_day: Max new leads to contact per day (default 50)
        schedule_start_time: Optional start date/time for campaign (ISO format)
    """
    body: dict = {
        "timezone": timezone,
        "days_of_the_week": days_of_the_week,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "min_time_btw_emails": min_time_btw_emails,
        "max_new_leads_per_day": max_new_leads_per_day,
    }
    if schedule_start_time:
        body["schedule_start_time"] = schedule_start_time
    data = api_post(f"/campaigns/{campaign_id}/schedule", body)
    return f"Schedule updated for campaign {campaign_id} | ok: {data.get('ok')}"


@mcp.tool()
def save_campaign_sequence(campaign_id: int, sequences: list[dict]) -> str:
    """
    Save email sequence (steps) for a campaign. Replaces existing sequence.

    Each sequence step is a dict with:
        seq_number: Step number (1, 2, 3...)
        seq_delay_details: {"delay_in_days": N}
        subject: Email subject (empty for follow-ups to keep thread)
        email_body: HTML or plain text email body
        id: Optional step ID for updating existing steps

    Example single-step sequence:
        [{"seq_number": 1, "seq_delay_details": {"delay_in_days": 0},
          "subject": "Quick question about {{company_name}}",
          "email_body": "Hi {{first_name}},<br>..."}]

    Args:
        campaign_id: Campaign ID
        sequences: List of sequence step dicts
    """
    data = api_post(f"/campaigns/{campaign_id}/sequences", {"sequences": sequences})
    return f"Sequence saved for campaign {campaign_id} | ok: {data.get('ok')} | data: {data.get('data')}"


@mcp.tool()
def get_campaign_statistics(campaign_id: int) -> str:
    """
    Get send/open/click/reply statistics for a campaign.

    Args:
        campaign_id: Campaign ID
    """
    data = api_get(f"/campaigns/{campaign_id}/statistics")
    stats = data if not isinstance(data, list) else {}
    lines = [f"Campaign {campaign_id} statistics:"]
    for k, v in (stats.items() if hasattr(stats, 'items') else []):
        lines.append(f"  {k}: {v}")
    if len(lines) == 1:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return "\n".join(lines)


@mcp.tool()
def get_campaign_analytics(
    campaign_id: int,
    start_date: str = None,
    end_date: str = None,
) -> str:
    """
    Get analytics for a campaign, optionally filtered by date range.

    Args:
        campaign_id: Campaign ID
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
    """
    if start_date and end_date:
        query = {"start_date": start_date, "end_date": end_date}
        data = api_get(f"/campaigns/{campaign_id}/analytics-by-date", query)
    else:
        data = api_get(f"/campaigns/{campaign_id}/analytics")
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# EMAIL ACCOUNTS
# ---------------------------------------------------------------------------

@mcp.tool()
def list_email_accounts(
    offset: int = 0,
    limit: int = 100,
    client_id: int = None,
) -> str:
    """
    List all email accounts connected to the Smartlead account.

    Args:
        offset: Pagination offset (default 0)
        limit: Results per page (default 100)
        client_id: Filter by client ID
    """
    query: dict = {"offset": offset, "limit": limit}
    if client_id is not None:
        query["client_id"] = client_id
    data = api_get("/email-accounts/", query)
    accounts = data if isinstance(data, list) else data.get("data", [])
    lines = [f"Found {len(accounts)} email accounts\n"]
    for a in accounts:
        warmup = a.get("warmup_details") or {}
        lines.append(
            f"- {a.get('from_email', 'N/A')} ({a.get('from_name', '')}) | "
            f"id: {a.get('id')} | type: {a.get('type', 'N/A')} | "
            f"msg/day: {a.get('message_per_day', 'N/A')} | "
            f"smtp_ok: {a.get('is_smtp_success')} | imap_ok: {a.get('is_imap_success')}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_campaign_email_accounts(campaign_id: int) -> str:
    """
    List email accounts assigned to a specific campaign.

    Args:
        campaign_id: Campaign ID
    """
    data = api_get(f"/campaigns/{campaign_id}/email-accounts")
    accounts = data if isinstance(data, list) else data.get("data", [])
    lines = [f"Email accounts for campaign {campaign_id}:\n"]
    for a in accounts:
        lines.append(f"- {a.get('from_email', 'N/A')} | id: {a.get('id')}")
    return "\n".join(lines)


@mcp.tool()
def add_email_accounts_to_campaign(
    campaign_id: int,
    email_account_ids: list[int],
) -> str:
    """
    Assign email accounts to a campaign for sending.

    Args:
        campaign_id: Campaign ID
        email_account_ids: List of email account IDs to add
    """
    data = api_post(
        f"/campaigns/{campaign_id}/email-accounts",
        {"email_account_ids": email_account_ids},
    )
    return f"Added {len(email_account_ids)} email accounts to campaign {campaign_id} | result: {json.dumps(data)}"


# ---------------------------------------------------------------------------
# LEAD MANAGEMENT
# ---------------------------------------------------------------------------

@mcp.tool()
def add_leads_to_campaign(
    campaign_id: int,
    leads: list[dict],
    ignore_global_block_list: bool = False,
    ignore_unsubscribe_list: bool = False,
    ignore_duplicate_leads_in_other_campaign: bool = False,
    return_lead_ids: bool = True,
) -> str:
    """
    Add leads to a campaign. Max 100 leads per request.

    Each lead dict must have "email" (required) and optionally:
        first_name, last_name, phone_number, company_name, website,
        location, linkedin_profile, company_url, custom_fields (dict)

    Example:
        [{"email": "john@stripe.com", "first_name": "John", "last_name": "Doe",
          "company_name": "Stripe", "custom_fields": {"industry": "fintech"}}]

    Args:
        campaign_id: Campaign ID
        leads: List of lead dicts (max 100)
        ignore_global_block_list: Skip global block list check (default False)
        ignore_unsubscribe_list: Skip unsubscribe list check (default False)
        ignore_duplicate_leads_in_other_campaign: Allow leads already in other campaigns (default False)
        return_lead_ids: Return lead IDs in response (default True)
    """
    body = {
        "lead_list": leads,
        "settings": {
            "ignore_global_block_list": ignore_global_block_list,
            "ignore_unsubscribe_list": ignore_unsubscribe_list,
            "ignore_community_bounce_list": False,
            "ignore_duplicate_leads_in_other_campaign": ignore_duplicate_leads_in_other_campaign,
            "return_lead_ids": return_lead_ids,
        },
    }
    data = api_post(f"/campaigns/{campaign_id}/leads", body)
    return (
        f"Uploaded: {data.get('upload_count', 0)} | "
        f"Duplicates: {data.get('duplicate_count', 0)} | "
        f"Invalid: {data.get('invalid_email_count', 0)} | "
        f"Unsubscribed: {data.get('unsubscribed_count', 0)}"
    )


@mcp.tool()
def list_campaign_leads(
    campaign_id: int,
    offset: int = 0,
    limit: int = 100,
    status: str = None,
) -> str:
    """
    List leads in a campaign with their current status.

    Args:
        campaign_id: Campaign ID
        offset: Pagination offset
        limit: Results per page (max 100, default 100)
        status: Filter by status: INPROGRESS, COMPLETED, STOPPED, PAUSED, REPLIED, BOUNCED, UNSUBSCRIBED
    """
    query: dict = {"offset": offset, "limit": limit}
    if status:
        query["status"] = status
    data = api_get(f"/campaigns/{campaign_id}/leads", query)
    leads = data if isinstance(data, list) else data.get("data", [])
    total = data.get("total_leads", len(leads)) if isinstance(data, dict) else len(leads)
    lines = [f"Campaign {campaign_id}: {total} total leads (showing {len(leads)})\n"]
    for entry in leads:
        # Lead data may be nested under "lead" key or at top level
        lead = entry.get("lead", entry) if isinstance(entry, dict) else entry
        lines.append(
            f"- {lead.get('email', 'N/A')} | "
            f"{lead.get('first_name', '')} {lead.get('last_name', '')} | "
            f"{lead.get('company_name', 'N/A')} | "
            f"status: {entry.get('status', 'N/A')} | "
            f"id: {lead.get('id')}"
        )
    return "\n".join(lines)


@mcp.tool()
def fetch_lead_by_email(email: str) -> str:
    """
    Find a lead across all campaigns by email address.

    Args:
        email: Lead's email address
    """
    data = api_get("/leads/", {"email": email})
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def update_lead(
    campaign_id: int,
    lead_id: int,
    first_name: str = None,
    last_name: str = None,
    email: str = None,
    phone_number: str = None,
    company_name: str = None,
    website: str = None,
    location: str = None,
    linkedin_profile: str = None,
    custom_fields: dict = None,
) -> str:
    """
    Update lead data in a campaign.

    Args:
        campaign_id: Campaign ID
        lead_id: Lead ID
        first_name: New first name
        last_name: New last name
        email: New email
        phone_number: New phone
        company_name: New company name
        website: New website
        location: New location
        linkedin_profile: New LinkedIn URL
        custom_fields: Dict of custom field updates
    """
    body: dict = {}
    if first_name is not None:
        body["first_name"] = first_name
    if last_name is not None:
        body["last_name"] = last_name
    if email is not None:
        body["email"] = email
    if phone_number is not None:
        body["phone_number"] = phone_number
    if company_name is not None:
        body["company_name"] = company_name
    if website is not None:
        body["website"] = website
    if location is not None:
        body["location"] = location
    if linkedin_profile is not None:
        body["linkedin_profile"] = linkedin_profile
    if custom_fields is not None:
        body["custom_fields"] = custom_fields
    data = api_post(f"/campaigns/{campaign_id}/leads/{lead_id}", body)
    return f"Updated lead {lead_id} in campaign {campaign_id} | ok: {data.get('ok')}"


@mcp.tool()
def pause_lead(campaign_id: int, lead_id: int) -> str:
    """
    Pause sending to a specific lead in a campaign.

    Args:
        campaign_id: Campaign ID
        lead_id: Lead ID
    """
    data = api_post(f"/campaigns/{campaign_id}/leads/{lead_id}/pause")
    return f"Lead {lead_id} paused | ok: {data.get('ok')}"


@mcp.tool()
def resume_lead(
    campaign_id: int,
    lead_id: int,
    resume_delay_days: int = 0,
) -> str:
    """
    Resume sending to a paused lead in a campaign.

    Args:
        campaign_id: Campaign ID
        lead_id: Lead ID
        resume_delay_days: Additional days to wait before resuming (default 0)
    """
    body: dict = {}
    if resume_delay_days:
        body["resume_lead_with_delay_days"] = resume_delay_days
    data = api_post(f"/campaigns/{campaign_id}/leads/{lead_id}/resume", body)
    return f"Lead {lead_id} resumed | ok: {data.get('ok')}"


@mcp.tool()
def unsubscribe_lead(lead_id: int) -> str:
    """
    Unsubscribe a lead from all campaigns globally.

    Args:
        lead_id: Lead ID
    """
    data = api_post(f"/leads/{lead_id}/unsubscribe")
    return f"Lead {lead_id} unsubscribed from all campaigns | ok: {data.get('ok')}"


@mcp.tool()
def get_lead_message_history(
    campaign_id: int,
    lead_id: int,
    event_time_gt: str = None,
) -> str:
    """
    Get full email conversation history for a lead in a campaign.

    Args:
        campaign_id: Campaign ID
        lead_id: Lead ID
        event_time_gt: Optional ISO date filter — only show messages after this time
    """
    query: dict = {}
    if event_time_gt:
        query["event_time_gt"] = event_time_gt
    data = api_get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history", query)
    messages = data if isinstance(data, list) else data.get("history", [])
    lines = [f"Message history for lead {lead_id} in campaign {campaign_id} ({len(messages)} messages)\n"]
    for msg in messages:
        lines.append(
            f"[{msg.get('type', 'N/A')}] {msg.get('time', 'N/A')}\n"
            f"  Subject: {msg.get('email_subject', 'N/A')}\n"
            f"  Opens: {msg.get('open_count', 0)} | Clicks: {msg.get('click_count', 0)}\n"
            f"  Body: {str(msg.get('email_body', ''))[:300]}..."
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LEAD CATEGORIES
# ---------------------------------------------------------------------------

@mcp.tool()
def fetch_lead_categories() -> str:
    """
    Fetch all lead categories (status tags) available in the account.
    Returns category IDs, names, and sentiment types (positive/negative/null).
    Use these IDs with update_lead_category.
    """
    data = api_get("/leads/fetch-categories")
    cats = data if isinstance(data, list) else []
    lines = [f"Found {len(cats)} categories\n"]
    for c in cats:
        lines.append(
            f"- id: {c.get('id')} | {c.get('name')} | sentiment: {c.get('sentiment_type', 'null')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CAMPAIGN SEQUENCES
# ---------------------------------------------------------------------------

@mcp.tool()
def get_campaign_sequences(campaign_id: int) -> str:
    """
    Fetch all email sequence steps and their A/B variants for a campaign.
    Returns subject lines, email bodies (HTML), variant labels, and delays.

    Args:
        campaign_id: Campaign ID
    """
    data = api_get(f"/campaigns/{campaign_id}/sequences")
    steps = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    lines = [f"Campaign {campaign_id}: {len(steps)} sequence steps\n"]
    for step in steps:
        seq_num = step.get("seq_number", "?")
        variants = step.get("sequence_variants") or []
        lines.append(f"--- Step {seq_num} (id: {step.get('id')}) ---")
        for v in variants:
            if v.get("is_deleted"):
                continue
            label = v.get("variant_label", "?")
            subject = v.get("subject", "")
            body = v.get("email_body", "")
            # Strip HTML tags for readability
            body_text = re.sub(r"<[^>]+>", " ", body).strip()
            body_text = re.sub(r"\s+", " ", body_text)
            lines.append(f"  Variant {label}: subject=\"{subject}\"")
            lines.append(f"    body: {body_text[:500]}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_sequence_analytics(
    campaign_id: int,
    start_date: str,
    end_date: str,
) -> str:
    """
    Get per-step sequence analytics: sent, opened, clicked, replied, bounced counts.

    Args:
        campaign_id: Campaign ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    query = {
        "start_date": f"{start_date} 00:00:00",
        "end_date": f"{end_date} 23:59:59",
    }
    data = api_get(f"/campaigns/{campaign_id}/sequence-analytics", query)
    items = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    lines = [f"Campaign {campaign_id} sequence analytics ({start_date} — {end_date}): {len(items)} steps\n"]
    for i, item in enumerate(items, 1):
        lines.append(
            f"  Step {i} (seq_id: {item.get('email_campaign_seq_id')}): "
            f"sent={item.get('sent_count', 0)} | "
            f"open={item.get('open_count', 0)} | "
            f"click={item.get('click_count', 0)} | "
            f"reply={item.get('reply_count', 0)} | "
            f"bounce={item.get('bounce_count', 0)} | "
            f"unsub={item.get('unsubscribed_count', 0)} | "
            f"positive_reply={item.get('positive_reply_count', 0)}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MASTER INBOX
# ---------------------------------------------------------------------------

@mcp.tool()
def fetch_inbox_replies(
    offset: int = 0,
    limit: int = 25,
    campaign_id: int = None,
    search: str = None,
    fetch_message_history: bool = False,
) -> str:
    """
    Fetch replied leads from the master inbox.

    Args:
        offset: Pagination offset
        limit: Results per page (default 25)
        campaign_id: Filter by campaign ID
        search: Free text search in email/name
        fetch_message_history: Include full email history (default False)
    """
    body: dict = {"offset": offset, "limit": min(limit, 20), "filters": {}}
    if campaign_id:
        body["filters"]["campaignId"] = [campaign_id]
    if search:
        body["filters"]["search"] = search
    query = {"fetch_message_history": "true" if fetch_message_history else "false"}
    data = api_post("/master-inbox/inbox-replies", body, query)
    replies = data if isinstance(data, list) else data.get("data", [])
    lines = [f"Inbox replies (showing {len(replies)})\n"]
    for r in replies:
        email = r.get("lead_email", r.get("lead", {}).get("email", "N/A"))
        first = r.get("lead_first_name", r.get("lead", {}).get("first_name", ""))
        last = r.get("lead_last_name", r.get("lead", {}).get("last_name", "")) or ""
        camp = r.get("email_campaign_name", r.get("campaign_name", r.get("campaign_id", "N/A")))
        cat_id = r.get("lead_category_id", "N/A")
        reply_time = r.get("last_reply_time", r.get("reply_time", "N/A"))
        lead_id = r.get("email_lead_id", "N/A")
        status = r.get("lead_status", "N/A")
        unread = r.get("has_new_unread_email", False)
        lines.append(
            f"- {email} | {first} {last} | "
            f"campaign: {camp} | category_id: {cat_id} | "
            f"status: {status} | replied: {reply_time} | "
            f"lead_id: {lead_id} | unread: {unread}"
        )
    return "\n".join(lines)


@mcp.tool()
def reply_to_lead(
    campaign_id: int,
    email_stats_id: int,
    email_body: str,
    reply_message_id: str,
    reply_email_time: str,
    reply_email_body: str,
    cc: list[str] = None,
    bcc: list[str] = None,
) -> str:
    """
    Reply to a lead's message from the master inbox.

    Args:
        campaign_id: Campaign ID
        email_stats_id: Email stats ID from inbox reply data
        email_body: Your reply body (HTML)
        reply_message_id: Message ID of the email being replied to
        reply_email_time: Time of the email being replied to (ISO format)
        reply_email_body: Body of the email being replied to (for threading)
        cc: CC email addresses
        bcc: BCC email addresses
    """
    body: dict = {
        "email_stats_id": email_stats_id,
        "email_body": email_body,
        "reply_message_id": reply_message_id,
        "reply_email_time": reply_email_time,
        "reply_email_body": reply_email_body,
    }
    if cc:
        body["cc"] = cc
    if bcc:
        body["bcc"] = bcc
    data = api_post(f"/campaigns/{campaign_id}/reply-email-thread", body)
    return f"Reply sent | ok: {data.get('ok')}"


@mcp.tool()
def create_lead_note(email_lead_map_id: int, note_message: str) -> str:
    """
    Add a note to a lead in the master inbox.

    Args:
        email_lead_map_id: Email-lead mapping ID from inbox data
        note_message: Note text
    """
    data = api_post("/master-inbox/create-note", {
        "email_lead_map_id": email_lead_map_id,
        "note_message": note_message,
    })
    return f"Note created | ok: {data.get('ok')}"


@mcp.tool()
def update_lead_category(email_lead_map_id: int, category_id: int = None) -> str:
    """
    Set or remove the category (status tag) for a lead in the master inbox.
    Common categories: Interested, Not Interested, Meeting Booked, Out of Office, etc.

    Args:
        email_lead_map_id: Email-lead mapping ID from inbox data
        category_id: Category ID to set, or None/null to remove category
    """
    data = api_patch("/master-inbox/update-category", {
        "email_lead_map_id": email_lead_map_id,
        "category_id": category_id,
    })
    return f"Category updated | ok: {data.get('ok')}"


if __name__ == "__main__":
    mcp.run()
