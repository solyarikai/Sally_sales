#!/usr/bin/env python3
"""
SmartLead — Fetch conversation history for unchecked Leads booking_Sofia
=========================================================================
Uses /leads?email=xxx to find lead_id, then /leads/{id}/messages for history.

Run on Hetzner:
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_fetch_booking_leads.py"
"""

import os
import json
import time
import httpx
import re

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# Unchecked leads (Checked = FALSE or empty, excluding already had a call)
UNCHECKED_LEADS = {
    "roland@styleranking.de": {"name": "Roland Schweins", "company": "styleranking media GmbH", "title": "Founder", "status": "Need update"},
    "nader@linqia.com": {"name": "Nader Alizadeh", "company": "Linqia", "title": "CEO", "status": "Time to ping"},
    "natalie@glistenmgmt.com": {"name": "Natalie", "company": "glisten mgmt", "title": "MD", "status": "Time to ping"},
    "urban@influee.co": {"name": "Urban Cvek", "company": "Influee", "title": "CEO", "status": "Stopped responding"},
    "ernest@runwayinfluence.com": {"name": "Ernest Sturm", "company": "Runway Influence", "title": "Owner", "status": "Stopped responding"},
    "yunus@yagency.dk": {"name": "Yunus Yousefi", "company": "Yagency", "title": "Founder", "status": "Stopped responding"},
    "hola@brandmanic.com": {"name": "Luis Soldevila", "company": "Brandmanic", "title": "CEO", "status": "Time to ping"},
    "atul@theshelf.com": {"name": "Atul Singh", "company": "The Shelf", "title": "CEO", "status": "Warm/interested"},
    "johan@impact.com": {"name": "Johan Venter", "company": "impact.com", "title": "Sr. Director Eng.", "status": "Time to ping"},
    "ronit@berolling.in": {"name": "Ronit Thakur", "company": "Be Rolling Media", "title": "Founder", "status": "Stopped responding"},
    "georg@gamesforest.club": {"name": "Georg Broxtermann", "company": "GameInfluencer", "title": "CEO", "status": "Info request"},
    "jacob@kjmarketingsweden.com": {"name": "Jacob Yngvesson", "company": "KJ Marketing Sweden", "title": "Head of Partnership", "status": "Info request"},
    "salvador@grg.co": {"name": "Salvador Klein", "company": "Global Rev Gen", "title": "MD", "status": "Info request"},
    "anne-julie@clarkinfluence.com": {"name": "Anne-Julie Karcher", "company": "Clark Influence", "title": "Director", "status": "Info request"},
    "daniel.schotland@linqia.com": {"name": "Daniel Schotland", "company": "Linqia", "title": "COO", "status": "Info request"},
    "eviteri@publifyer.com": {"name": "Eduardo Viteri Fernandez", "company": "Publifyer", "title": "Head of Strategy", "status": "Info request"},
    "williamj@fanstories.com": {"name": "William Jourdain", "company": "Fanstories", "title": "CEO", "status": "Info request"},
    "dominique@loudpixels.se": {"name": "Dominique Grubestedt", "company": "LoudPixels", "title": "Owner", "status": "Info request"},
}


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_lead_by_email(email):
    try:
        return api_get("/leads", {"email": email})
    except Exception as e:
        print(f"  Error finding lead {email}: {e}")
        return None


def get_lead_messages(lead_id):
    try:
        return api_get(f"/leads/{lead_id}/messages")
    except Exception as e:
        print(f"  Error fetching messages for lead {lead_id}: {e}")
        return None


def format_messages(messages):
    """Format message history into readable text."""
    if not messages:
        return "(no messages)"

    lines = []
    if isinstance(messages, list):
        for m in messages:
            direction = m.get("type", m.get("direction", "?"))
            time_sent = m.get("time", m.get("created_at", ""))
            subject = m.get("subject", "")
            body = strip_html(m.get("body") or m.get("message") or m.get("text") or "")
            lines.append(f"[{direction}] {time_sent}")
            if subject and subject.lower() not in ["(thread)", "re:", ""]:
                lines.append(f"Subject: {subject}")
            if body:
                lines.append(body[:1500])
            lines.append("")
    elif isinstance(messages, dict):
        for k, v in messages.items():
            if isinstance(v, list):
                for item in v:
                    body = strip_html(item.get("body") or item.get("message") or "")
                    lines.append(f"[{k}] {body[:1000]}")
            else:
                lines.append(f"{k}: {str(v)[:300]}")

    return "\n".join(lines)


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    results = {}

    for email, lead_info in UNCHECKED_LEADS.items():
        print(f"\nLooking up: {lead_info['name']} ({email})")

        # Get lead by email
        lead_data = get_lead_by_email(email)
        time.sleep(0.5)

        if not lead_data:
            print(f"  NOT FOUND")
            results[email] = {**lead_info, "email": email, "found": False, "messages": None}
            continue

        lead_id = lead_data.get("id")
        campaign_data = lead_data.get("lead_campaign_data", [])
        campaigns = [c.get("campaign_id") for c in campaign_data] if campaign_data else []

        print(f"  Found: id={lead_id}, campaigns={campaigns}")

        # Get messages
        messages_raw = get_lead_messages(lead_id)
        time.sleep(0.5)

        messages_formatted = format_messages(messages_raw)

        results[email] = {
            **lead_info,
            "email": email,
            "found": True,
            "lead_id": lead_id,
            "campaigns": campaigns,
            "messages_raw": messages_raw,
            "messages_text": messages_formatted,
        }

        print(f"  Messages preview: {messages_formatted[:200]}")

    # Print full results
    print(f"\n\n{'='*70}")
    print(f"RESULTS: {sum(1 for r in results.values() if r.get('found'))} / {len(UNCHECKED_LEADS)} found")
    print(f"{'='*70}")

    for email, data in results.items():
        print(f"\n{'='*70}")
        print(f"NAME:    {data['name']}")
        print(f"COMPANY: {data['company']} | {data['title']}")
        print(f"EMAIL:   {email}")
        print(f"STATUS:  {data['status']}")
        if data.get('found'):
            print(f"LEAD ID: {data['lead_id']}")
            print(f"\nCONVERSATION:")
            print(data.get('messages_text', '(no messages)'))
        else:
            print("NOT FOUND IN SMARTLEAD")

    # Save
    out_path = "sofia/scripts/booking_leads_conversations.json"
    # Remove non-serializable raw messages for size
    save_data = {k: {kk: vv for kk, vv in v.items() if kk != "messages_raw"} for k, v in results.items()}
    with open(out_path, "w") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n\nSaved to {out_path}")

    not_found = [v for v in results.values() if not v.get("found")]
    if not_found:
        print(f"\nNOT IN SMARTLEAD ({len(not_found)}):")
        for l in not_found:
            print(f"  - {l['name']} ({l['company']})")


if __name__ == "__main__":
    main()
