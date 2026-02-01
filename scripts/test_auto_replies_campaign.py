#!/usr/bin/env python3
"""
Test Auto-Replies Campaign Script
Creates a Smartlead campaign with Slack workspace members to test auto-replies flow.

Usage: cd ~/magnum-opus-project/repo && source .env && python3 scripts/test_auto_replies_campaign.py
"""

import os
import requests
from datetime import datetime

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
BASE_URL = "https://server.smartlead.ai/api/v1"

def get_slack_members():
    print("Fetching Slack members...")
    resp = requests.get(
        "https://slack.com/api/users.list",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        params={"limit": 100}
    )
    data = resp.json()
    if not data.get("ok"):
        print(f"Slack error: {data.get('error')}")
        return []
    
    members = []
    for m in data.get("members", []):
        if m.get("is_bot") or m.get("deleted"):
            continue
        email = m.get("profile", {}).get("email")
        if email:
            members.append({
                "email": email,
                "first_name": m.get("profile", {}).get("first_name", m.get("real_name", "").split()[0] if m.get("real_name") else ""),
                "last_name": m.get("profile", {}).get("last_name", ""),
                "company": "GetSally"
            })
    print(f"Found {len(members)} members")
    return members

def get_email_accounts(tag_id="164782"):
    print(f"Fetching email accounts with tag {tag_id}...")
    resp = requests.get(f"{BASE_URL}/email-accounts", params={"api_key": SMARTLEAD_API_KEY})
    accounts = resp.json()
    
    filtered = []
    for acc in accounts:
        tags = acc.get("tags", [])
        if any(str(t.get("id")) == tag_id for t in tags):
            sent = acc.get("emails_sent_today", 0)
            limit = acc.get("daily_limit", 50)
            if sent < limit:
                filtered.append({"id": acc["id"], "email": acc["from_email"], "available": limit - sent})
    
    print(f"Found {len(filtered)} accounts with capacity")
    return filtered

def create_campaign(name, accounts):
    print(f"Creating campaign: {name}")
    data = {
        "name": name,
        "timezone": "Europe/Moscow",
        "track_opens": True,
        "track_clicks": True,
        "stop_on_reply": True
    }
    resp = requests.post(f"{BASE_URL}/campaigns/create", params={"api_key": SMARTLEAD_API_KEY}, json=data)
    if resp.status_code != 200:
        print(f"Failed: {resp.text}")
        return None
    campaign = resp.json()
    print(f"Campaign ID: {campaign.get(id)}")
    return campaign

def add_email_accounts(campaign_id, accounts):
    print("Adding email accounts...")
    account_ids = [acc["id"] for acc in accounts[:3]]
    resp = requests.post(
        f"{BASE_URL}/campaigns/{campaign_id}/email-accounts",
        params={"api_key": SMARTLEAD_API_KEY},
        json={"email_account_ids": account_ids}
    )
    print(f"Email accounts: {resp.status_code}")
    return resp.status_code == 200

def add_sequence(campaign_id):
    print("Adding email sequence...")
    seq = {
        "sequences": [{
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": "Sally testing auto-replies",
            "email_body": "<p>Hi {{first_name}},</p><p>Testing Sally auto-replies. <b>Please reply to this email!</b></p><p>Your reply will appear in Slack with AI classification.</p><p>Thanks!<br>Sally Team</p>"
        }]
    }
    resp = requests.post(f"{BASE_URL}/campaigns/{campaign_id}/sequences", params={"api_key": SMARTLEAD_API_KEY}, json=seq)
    print(f"Sequence: {resp.status_code}")
    return resp.status_code == 200

def set_schedule(campaign_id):
    print("Setting schedule (all days, 00:00-23:59)...")
    schedule = {
        "timezone": "Europe/Moscow",
        "days_of_the_week": [0, 1, 2, 3, 4, 5, 6],
        "start_hour": "00:01",
        "end_hour": "23:59",
        "min_time_btw_emails": 1,
        "max_new_leads_per_day": 100
    }
    resp = requests.post(f"{BASE_URL}/campaigns/{campaign_id}/schedule", params={"api_key": SMARTLEAD_API_KEY}, json=schedule)
    print(f"Schedule: {resp.status_code} - {resp.text[:100] if resp.text else ok}")
    return resp.status_code == 200

def add_leads(campaign_id, leads):
    print(f"Adding {len(leads)} leads...")
    lead_list = [{"email": l["email"], "first_name": l.get("first_name", ""), "last_name": l.get("last_name", ""), "company_name": l.get("company", "")} for l in leads]
    resp = requests.post(f"{BASE_URL}/campaigns/{campaign_id}/leads", params={"api_key": SMARTLEAD_API_KEY}, json={"lead_list": lead_list})
    print(f"Leads: {resp.status_code} - {resp.text[:100] if resp.text else ok}")
    return resp.status_code == 200

def start_campaign(campaign_id):
    print("Starting campaign...")
    resp = requests.post(f"{BASE_URL}/campaigns/{campaign_id}/status", params={"api_key": SMARTLEAD_API_KEY}, json={"status": "ACTIVE"})
    print(f"Start: {resp.status_code}")
    return resp.status_code == 200

def main():
    print("=" * 50)
    print("Sally Auto-Replies Test Campaign")
    print("=" * 50)
    
    members = get_slack_members()
    if not members:
        return
    
    accounts = get_email_accounts("164782")
    if not accounts:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    name = f"Sally Auto-Replies Test {timestamp}"
    
    campaign = create_campaign(name, accounts)
    if not campaign:
        return
    
    cid = campaign.get("id")
    add_email_accounts(cid, accounts)
    add_sequence(cid)
    set_schedule(cid)
    add_leads(cid, members)
    start_campaign(cid)
    
    print()
    print("=" * 50)
    print("DONE!")
    print("=" * 50)
    print(f"Campaign: {name}")
    print(f"ID: {cid}")
    print(f"Leads: {len(members)}")
    print()
    print("NEXT: Go to http://46.62.210.24:3000/replies")
    print("Create automation with this campaign -> #c-replies-test")
    print()

if __name__ == "__main__":
    main()
