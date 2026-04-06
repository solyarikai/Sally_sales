#!/usr/bin/env python3.11
"""
Read Sequences | IMAGENCY_EU format, then create 2 INFPLAT sheets in the same spreadsheet.
"""

import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "/Users/sofia/Documents/GitHub/Sally_sales/.claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"

# ── Auth ──────────────────────────────────────────────────────────────────────
creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

service = build("sheets", "v4", credentials=creds)
sheets = service.spreadsheets()

# ── Read IMAGENCY_EU to understand format ────────────────────────────────────
print("Reading Sequences | IMAGENCY_EU...")
result = sheets.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range="Sequences | IMAGENCY_EU"
).execute()
existing = result.get("values", [])
print(f"  {len(existing)} rows found")
for i, row in enumerate(existing[:5]):
    print(f"  Row {i}: {row}")

# ── Data for INFPLAT sheets ───────────────────────────────────────────────────
# Sheet 1: Sequences | INFPLAT — reply analytics from 4 campaigns
# Sheet 2: Sequences | INFPLAT_ALLGEO — final sequence set for ALL GEO campaign

INFPLAT_ANALYTICS = [
    ["INFLUENCER PLATFORMS — Reply Analytics", "", "", "", "", ""],
    ["Campaign", "Campaign ID", "Sent", "Replies", "Reply Rate", "Notes"],
    ["Global", "3050419", "299", "5", "1.67%", "Best absolute volume"],
    ["MENA+APAC", "3065429", "114", "2", "1.75%", "Best rate, small sample"],
    ["Americas", "3065159", "62", "1", "1.61%", "Small sample"],
    ["India", "3064966", "99", "0", "0%", "No replies"],
    ["", "", "", "", "", ""],
    ["TOTAL", "", "574", "8", "1.39%", ""],
    ["", "", "", "", "", ""],
    ["Step Attribution", "", "", "", "", ""],
    ["Step", "Day", "Replies", "% of Total", "Conclusion", ""],
    ["Step 1", "0", "8", "100%", "All replies came from Step 1 only", ""],
    ["Step 2", "3", "0", "0%", "", ""],
    ["Step 3", "6", "0", "0%", "", ""],
    ["Step 4", "10", "0", "0%", "", ""],
    ["Step 5", "15", "0", "0%", "", ""],
    ["", "", "", "", "", ""],
    ["Variant Attribution", "", "", "", "", ""],
    ["Variant", "Subject", "Source Campaign", "Replies", "Rate", "Decision"],
    ["Variant A (proven)", "Creator data API for {{company_name}}", "Global #3050419", "5", "1.67% (n=299)", "SET as base in ALL GEO via API"],
    ["Variant B (hypothesis)", "creator data - {{company_name}}", "MENA+APAC #3065429", "2", "1.75% (n=114)", "Add manually in SmartLead UI"],
    ["", "", "", "", "", ""],
    ["A/B Hypothesis", "", "", "", "", ""],
    ["", "Variant A", "Variant B", "", "", ""],
    ["Subject", "Creator data API for {{company_name}}", "creator data - {{company_name}}", "", "", ""],
    ["Opener angle", "Checked {{co}} - data layer yours or vendor?", "Where does your creator data come from?", "", "", ""],
    ["Pain", "Technical: breaks every TikTok update", "Client-facing: nothing to show on transparency", "", "", ""],
    ["Proof", "6 named clients (Modash, Lefty, etc.)", "platforms like yours", "", "", ""],
    ["CTA", "run creator live - 15 min", "Worth a look?", "", "", ""],
    ["Geo hypothesis", "Stronger EU/US (CTOs, technical buyers)", "Stronger LATAM/MENA/India (business founders)", "", "", ""],
]

INFPLAT_ALLGEO_SEQUENCE = [
    ["INFLUENCER PLATFORMS ALL GEO — Sequence (campaign #3096747)", "", "", ""],
    ["Status: DRAFTED — Variant A set via API | Variant B: add manually in SmartLead UI", "", "", ""],
    ["", "", "", ""],
    ["Step", "Day", "Subject", "Body"],
    ["Step 1 — Variant A (base)", "0", "Creator data API for {{company_name}}",
     "Hey {{first_name}},\n\nChecked {{company_name}} - you're giving clients creator analytics. Quick question: is the data layer yours, or do you pull from a vendor?\n\nModash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API. Building creator data in-house breaks every time TikTok changes something - our endpoint handles that, 450M+ profiles, city-level demographics.\n\nCan run any creator through the API live - 15 min?\n\nKind regards,\nBhaskar Vishnu from OnSocial\nTrusted by Traackr, Audiense, and Upfluence"],
    ["Step 1 — Variant B (hypothesis)", "0", "creator data - {{company_name}}",
     "Hey {{first_name}},\n\nQuick question - when your team is looking for creators, where does the data come from? Is it your own layer or a vendor?\n\nWe work with influencer platforms like yours and see a gap pretty often: the platform runs on vendor data, so when clients ask for transparency or custom segments, there is not much to show. OnSocial builds the data layer directly - 450M+ creators, real engagement metrics, audience insights.\n\nSome platforms use it to power their own search and reporting instead of renting access.\n\nWorth a look?\n\nKind regards,\nBhaskar Vishnu from OnSocial\nTrusted by Traackr, Audiense, and Upfluence"],
    ["Step 2", "3", "(thread)",
     "{{first_name}}, quick add.\n\nWhen Lefty moved to our API, they freed 2 eng roles that were just maintaining data - and expanded from 3 to 5 social networks in a week.\n\nFor platforms like {{company_name}} it's not about another data provider. It's about what your engineers spend time on.\n\nDrop any creator handle in reply - I'll run it and send the output. No call needed.\n\nBhaskar"],
    ["Step 3", "6", "(thread)",
     "Hi {{first_name}},\n\nOne data point: platforms that build their own creator data layer spend 4-6 months before they have coverage beyond Instagram. We cover IG, TikTok, and YouTube from day one - 450M+ profiles.\n\nMany platforms started with the same decision. Happy to share what they learned.\n\nBhaskar"],
    ["Step 4", "10", "(thread)",
     "Hi {{first_name}},\n\nTwo things most creator data vendors won't tell you: their profiles update weekly (ours update every 24-48h), and their regional coverage has gaps. We cover IG, TikTok, and YouTube across 50+ countries at city level.\n\nIf data freshness or regional coverage matters for {{company_name}} - worth comparing. Happy to walk you through it. 15 min.\n\nBhaskar"],
    ["Step 5", "15", "(thread)",
     "Hi {{first_name}}, last one from me.\n\nIf creator data isn't on the roadmap - totally fine. But if I'm reaching the wrong person, who handles data infrastructure at {{company_name}}? Usually CTO or Head of Product.\n\nEither way - good luck with what you're building.\n\nBhaskar"],
    ["", "", "", ""],
    ["Source", "", "", ""],
    ["Variant A source", "Global campaign #3050419", "5 replies / 299 sent = 1.67%", "Proven — uploaded via API 2026-04-02"],
    ["Variant B source", "MENA+APAC campaign #3065429", "2 replies / 114 sent = 1.75%", "Hypothesis — add manually in SmartLead UI"],
    ["Delays", "0, 3, 3, 4, 5 days", "", ""],
    ["Sequence IDs", "7004560, 7004561, 7004562, 7004563, 7004564", "", ""],
]

# ── Create / clear sheets ─────────────────────────────────────────────────────
# Get existing sheet list
meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
existing_sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
print(f"\nExisting sheets: {list(existing_sheets.keys())}")

requests = []

for title in ["Sequences | INFPLAT", "Sequences | INFPLAT_ALLGEO"]:
    if title in existing_sheets:
        print(f"  Sheet '{title}' exists — will clear")
    else:
        print(f"  Sheet '{title}' not found — will create")
        requests.append({"addSheet": {"properties": {"title": title}}})

if requests:
    result = sheets.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests}
    ).execute()
    # Refresh sheet IDs
    meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
    existing_sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    print("  Sheets created.")

# ── Write data ────────────────────────────────────────────────────────────────
def write_sheet(title, data):
    # Clear first
    sheets.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=title
    ).execute()
    # Write
    sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": data}
    ).execute()
    print(f"  Written {len(data)} rows to '{title}'")

write_sheet("Sequences | INFPLAT", INFPLAT_ANALYTICS)
write_sheet("Sequences | INFPLAT_ALLGEO", INFPLAT_ALLGEO_SEQUENCE)

# ── Format: bold headers ──────────────────────────────────────────────────────
def bold_row(sheet_id, row_index):
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold"
        }
    }

format_requests = []
for title, bold_rows in [
    ("Sequences | INFPLAT", [0, 1, 9, 10, 17, 18, 22, 23]),
    ("Sequences | INFPLAT_ALLGEO", [0, 1, 3, 11, 12])
]:
    sid = existing_sheets[title]
    for r in bold_rows:
        format_requests.append(bold_row(sid, r))

sheets.batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={"requests": format_requests}
).execute()
print("\nFormatting applied.")

print("\nDone. Open:")
print("  Sequences | INFPLAT:       https://docs.google.com/spreadsheets/d/1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E/edit")
print(f"  Sequences | INFPLAT_ALLGEO: same sheet, different tab")
