#!/usr/bin/env python3
import warnings; warnings.filterwarnings("ignore")
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "/Users/sofia/Documents/GitHub/Sally_sales/.claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"

creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
service = build("sheets", "v4", credentials=creds)
sheets = service.spreadsheets()

# ── Variant A — verbatim Global (3050462), signature → {{social_proof}}, typo fixed ──
VA_S1_SUBJ = "{{first_name}}, 450M influencer profiles ready for your API"
VA_S1_BODY = """Hey {{first_name}},

When a client asks show me data on this creator - do you show something of yours, or a screenshot from HypeAuditor/Modash?

That is a trap. Once they figure out your tool - they buy it themselves and start wondering why they need an agency.

We power creator data for IM-first agencies: 450M+ profiles across Instagram, TikTok, YouTube. Your reports, your branding, your insight - not ours.

Would you like to see how it works for your current setup?

Kind regards,
Bhaskar Vishnu from OnSocial
Trusted by {{social_proof}}"""

VA_S2_BODY = """Hey {{first_name}},

Two things agencies we work with care about most:

- Your reports stay under your brand. Our data plugs in via API - your clients see your logo, your analysis. Not ours.

We cover what clients actually question: real vs. fake audience, location down to city level, brand affinities, creator overlap across campaigns.

Modash, Obviously, and Ykone already run on our data for exactly this reason.

Open to a 15-min walkthrough based on your current setup?

Kind regards,
Bhaskar Vishnu from OnSocial
Trusted by {{social_proof}}"""

VA_S3_BODY = """Hey,

Quick note on how it works: for any creator, one API call returns: credibility breakdown (real vs. mass followers vs. bots), audience by country, city, age, gender, language, brand affinities, engagement rates, creator overlap. All real-time.

Your team puts it in your own reports - clients see it as your data, not a third-party tool.

Worth 15 minutes this week to see it live on a creator you are currently evaluating?

Kind regards,
Bhaskar Vishnu from OnSocial
Trusted by {{social_proof}}"""

VA_S4_BODY = """{{first_name}} - easier on LinkedIn?

Happy to pull a live breakdown on any creator you are currently evaluating.

Bhaskar
Sent from my iPhone"""

VA_S5_BODY = """Hey {{first_name}}, last one.

If building a proprietary data layer is not on the agenda right now - no problem.

We are at onsocial.io if it ever comes up.

Bhaskar from OnSocial"""

# ── Variant B — v4 Email 1A body, strongest followups ──
VB_S1_SUBJ = "creator analytics - {{company_name}}"
VB_S1_BODY = """Hi {{first_name}},

When a client asks "show me the data on this creator" - what does {{company_name}} show them? Your own branded report, or a screenshot from HypeAuditor?

Leading agencies white-label our data as their own. Clients see the agency's tool, not ours.

Happy to mock up a report with {{company_name}}'s branding - worth a look?

Kind regards,
Bhaskar Vishnu from OnSocial
Trusted by {{social_proof}}"""

VB_S2_BODY = """Hi {{first_name}}, quick follow-up.

67% of brands are considering bringing influencer marketing in-house. The agencies that keep clients give them something they can't build alone - proprietary analytics under their own brand.

Top agencies already do this. Want me to mock up what it looks like for {{company_name}}?

Bhaskar"""

VB_S3_BODY = """Hi {{first_name}},

One pattern we see: agencies that give clients access to branded analytics have 40% higher retention. The client builds workflows around YOUR tool - switching cost goes up.

Happy to show you how they set it up.

Bhaskar"""

VB_S4_BODY = """Hi {{first_name}},

Some agencies try building their own analytics dashboard. Typical timeline: 3-4 months of dev work, covers one platform (usually just Instagram), and needs constant maintenance.

Our white-label covers IG, TikTok, and YouTube - 450M+ profiles, fraud scoring, audience demographics. Zero dev work on your side.

If worth comparing - happy to walk you through it. 15 min.

Bhaskar"""

VB_S5_BODY = """Hi {{first_name}}, last one from me.

If white-label analytics aren't a priority right now - no worries. But if I'm reaching the wrong person, who handles tool decisions at {{company_name}}?

Either way - wishing {{company_name}} continued growth.

Bhaskar"""

# ── Sheet data ──
TITLE = "Sequences | IMAGENCY_ALLGEO"

data = [
    ["IM-FIRST AGENCIES ALL GEO — Sequence (campaign #3096746)", "", "", "", ""],
    ["Status: DRAFTED | Variant A: update via API | Variant B: add manually in SmartLead UI", "", "", "", ""],
    ["", "", "", "", ""],
    ["REPLY DATA — Source campaigns", "", "", "", ""],
    ["Campaign", "ID", "Sent", "Replies", "Rate"],
    ["Global", "3050462", "545", "5", "0.92%"],
    ["Europe", "3064335", "1935", "12", "0.62%"],
    ["India", "3063527", "730", "5", "0.68%"],
    ["US/LATAM", "3071851", "1611", "10", "0.62%"],
    ["TOTAL", "", "4821", "32", "0.66%"],
    ["", "", "", "", ""],
    ["NOTE: Europe had 7 replies from Steps 2-5 (only campaign where thread replies occurred)", "", "", "", ""],
    ["", "", "", "", ""],
    ["A/B DECISION", "", "", "", ""],
    ["", "Variant A", "Variant B", "", ""],
    ["Source", "Global #3050462 (best rate 0.92%)", "v4 Email 1A (not yet tested)", "", ""],
    ["Subject", VA_S1_SUBJ, VB_S1_SUBJ, "", ""],
    ["Angle", "Screenshot trap — client buys tool themselves", "Branded report vs HypeAuditor screenshot", "", ""],
    ["Steps 2-5", "Proven Global sequence", "v4 sequence (stat-driven)", "", ""],
    ["Status", "Upload via API", "Add manually in SmartLead UI", "", ""],
    ["", "", "", "", ""],
    ["FULL SEQUENCES", "", "", "", ""],
    ["Step", "Day", "Subject", "Variant A body", "Variant B body"],
    ["Step 1", "0", VA_S1_SUBJ + " / " + VB_S1_SUBJ, VA_S1_BODY, VB_S1_BODY],
    ["Step 2", "3", "(thread)", VA_S2_BODY, VB_S2_BODY],
    ["Step 3", "3*", "(thread)", VA_S3_BODY, VB_S3_BODY],
    ["Step 4", "4", "(thread)", VA_S4_BODY, VB_S4_BODY],
    ["Step 5", "5*", "(thread)", VA_S5_BODY, VB_S5_BODY],
    ["", "", "", "", ""],
    ["* Original Global delays: 0,3,1,3,0 — Step 3 delay=1, Step 5 delay=0 (bug). Using 0,3,3,4,5 for ALL GEO.", "", "", "", ""],
]

# Create or clear sheet
meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

if TITLE not in existing:
    sheets.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": [{"addSheet": {"properties": {"title": TITLE}}}]}).execute()
    meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    print(f"Created sheet '{TITLE}'")
else:
    sheets.values().clear(spreadsheetId=SPREADSHEET_ID, range=TITLE).execute()
    print(f"Cleared sheet '{TITLE}'")

sheets.values().update(
    spreadsheetId=SPREADSHEET_ID,
    range=f"{TITLE}!A1",
    valueInputOption="RAW",
    body={"values": data}
).execute()
print(f"Written {len(data)} rows")

# Bold headers
sid = existing[TITLE]
bold_rows = [0, 1, 3, 4, 13, 14, 21, 22]
requests_fmt = [{"repeatCell": {
    "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r+1},
    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
    "fields": "userEnteredFormat.textFormat.bold"
}} for r in bold_rows]
sheets.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests_fmt}).execute()
print("Formatting done")
print(f"\nSheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
