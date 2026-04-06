#!/usr/bin/env python3
"""
Generate personalized follow-up emails for unchecked leads
=========================================================
Uses combined_leads_data.json + Claude Haiku API to generate smart follow-ups
that reference the lead's last message and their company context.

"""

import json
import re
import anthropic

# Load combined data
with open("sofia/scripts/combined_leads_data.json") as f:
    leads_data = json.load(f)

# Filter for unchecked leads (status = "Time to ping", "Need update", "Stopped responding", or no status)
unchecked_statuses = ["Time to ping", "Need update", "Stoped responding", "Stopped responding", ""]

client = anthropic.Anthropic()

FOLLOWUP_PROMPT = """You are Sofia, Head of Growth at OnSocial. Generate a personalized follow-up email for a prospect.

LEAD CONTEXT:
- Name: {name}
- Title: {title}
- Company: {company}
- Website: {website}

CONVERSATION HISTORY:
Their last message to us:
"{last_message}"

Our reply:
"{our_reply}"

STATUS: {status}

TASK:
Write a brief, personalized follow-up email that:
1. References something specific from their last message (what they asked about)
2. Addresses their company's specific need (be smart about what they do)
3. Shows concrete value for THEIR use case (not generic)
4. Has a clear, non-pushy CTA (suggest a 15-min call/demo)
5. Signed from Sofia

TONE: Professional, friendly, smart (show you understand their business), no templates.
LENGTH: 3-4 sentences max
NO em-dashes or markdown formatting - plain text only.

Generate ONLY the email body. No subject line, no formatting, no explanations.""".strip()

followups = {}
print("=" * 70)
print("GENERATING PERSONALIZED FOLLOW-UP EMAILS")
print("=" * 70)

for email, data in sorted(leads_data.items()):
    sheet = data.get("sheet", {})
    status = sheet.get("status", "").strip()

    # Skip leads with completed calls or scheduled meetings
    if status in ["Had a call", "Scheduled", "Confirmed"]:
        continue

    # Check if unchecked
    if not any(status.lower().startswith(s.lower()) for s in unchecked_statuses):
        continue

    name = sheet.get("name", "")
    title = sheet.get("title", "")
    company = sheet.get("company", "")
    website = sheet.get("website", "")
    last_message = sheet.get("last_message", "").strip()
    our_reply = sheet.get("reply", "").strip()

    if not last_message:
        last_message = "(No prior message - cold outreach follow-up)"
    if not our_reply:
        our_reply = "(Initial outreach)"

    print(f"\n{name} ({company}) — {status}")
    print(f"  Generating follow-up...")

    prompt = FOLLOWUP_PROMPT.format(
        name=name,
        title=title,
        company=company,
        website=website,
        last_message=last_message,
        our_reply=our_reply,
        status=status,
    )

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        followup_text = message.content[0].text.strip()
        followups[email] = {
            "name": name,
            "company": company,
            "email": email,
            "title": title,
            "status": status,
            "last_message": last_message,
            "our_reply": our_reply,
            "followup": followup_text,
        }

        print(f"  ✓ Generated")
        print(f"  Preview: {followup_text[:100]}...")

    except Exception as e:
        print(f"  ✗ Error: {e}")
        followups[email] = {
            "name": name,
            "company": company,
            "email": email,
            "error": str(e),
        }

# Save results
output_path = "sofia/scripts/followup_emails.json"
with open(output_path, "w") as f:
    json.dump(followups, f, indent=2, ensure_ascii=False)

print(f"\n\n{'='*70}")
print(f"Generated {len([f for f in followups.values() if 'followup' in f])} follow-ups")
print(f"Saved to {output_path}")
print(f"{'='*70}")

# Print summary
for email, data in sorted(followups.items()):
    if "followup" in data:
        print(f"\n{data['name']} <{email}>")
        print(f"  {data['followup']}")
