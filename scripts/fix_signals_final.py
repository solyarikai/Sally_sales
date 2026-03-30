"""Nuke and rebuild signals tab — delete sheet and recreate."""
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDS_PATH = Path(__file__).resolve().parent.parent / 'google-credentials.json'
SHEET_ID = '1XlCV5ObWykGopw2qLmDwxO3hvekGugeBXLg9AA_TsXI'

def run():
    creds = service_account.Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    sheets = build('sheets', 'v4', credentials=creds)

    sp = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tabs = {s['properties']['title']: s['properties']['sheetId'] for s in sp['sheets']}

    # Delete old tab, create fresh one
    old_id = tabs['Trackable Signals']
    # Find its index
    old_index = None
    for s in sp['sheets']:
        if s['properties']['title'] == 'Trackable Signals':
            old_index = s['properties']['index']
            break

    sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': [
        {'deleteSheet': {'sheetId': old_id}},
        {'addSheet': {'properties': {'title': 'Trackable Signals', 'index': old_index}}},
    ]}).execute()
    print("Deleted and recreated Trackable Signals")

    # Get new sheet ID
    sp = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sig_id = None
    for s in sp['sheets']:
        if s['properties']['title'] == 'Trackable Signals':
            sig_id = s['properties']['sheetId']
            break

    sig_data = [
        ['Priority', 'Signal', 'What It Means', 'Outreach Move'],
        ['High', 'New VP/Director of Content or Entertainment hired', 'New content strategy incoming — they were hired to build something', 'Congratulate within 30 days. Offer industry briefing on animation production landscape.'],
        ['High', 'Animation job openings (Producer, Head of Animation, EP) at a non-studio company', 'Building internal team to manage external production — commissioning is imminent', '"You build the team, we bring the studio." Position as production partner.'],
        ['High', 'Multiple animation/content hires at same company within weeks', 'Major production initiative launching — budget is allocated', 'Move fast. Pitch capacity and speed. They\'re already behind schedule.'],
        ['High', 'RFP or production tender published', 'Active procurement — decision in weeks', 'Respond immediately with tailored pitch + reel.'],
        ['High', 'New IP or character launch announced without animation', 'Product coming but content strategy is missing', '"We noticed [IP] launches in Q3. Here\'s how animation accelerates adoption."'],
        ['High', 'Existing animated series gets cancelled or ends', 'Still need content — relationship with previous studio may be broken', '"We saw [series] wrapped. If you\'re evaluating next steps for [IP], we\'d love to discuss."'],
        ['High', 'Company hires showrunner or head writer but no studio announced', 'Pre-production started — they need a production partner now', 'Reach the showrunner AND the Content VP. "We can be in production within weeks."'],
        ['Strong', 'First-time registration for Annecy, Kidscreen, or MIPCOM', 'Entering the animation market — scouting studios', 'Pre-event outreach 8 weeks before. Book a meeting. Send reel for their segment.'],
        ['Strong', 'Streaming deal announced (Netflix, Apple TV+, Amazon)', 'Need animation produced — platform deal doesn\'t include a studio', '"Congratulations on the deal. We can deliver the production."'],
        ['Strong', 'Brand refresh or franchise relaunch announced', 'Legacy IP being revived — new animation is almost always part of it', 'Reference their specific IP history. Show what a modern version looks like.'],
        ['Strong', 'Earnings call mentions "content strategy" or "entertainment segment"', 'Executive mandate from the top — VP will be tasked with finding studios', 'Email the VP of Content directly. Reference the CEO\'s comments.'],
        ['Strong', 'Competitor launches animated series for similar product', 'Competitive pressure — board-level conversations are happening', '"[Competitor] just launched [series]. Here\'s how you respond."'],
        ['Strong', 'Company acquires new IP (book series, comic, game)', 'Animated adaptation will follow within 12–24 months', '"We\'d love to discuss bringing [IP] to animation." Get in early.'],
        ['Strong', 'Licensing revenue drops in quarterly earnings', 'Animation drives awareness which drives licensing — decline = pressure to invest', '"Licensing depends on visibility. Here\'s how animation reverses the trend."'],
        ['Strong', 'Animation studio partner gets acquired or merges', 'Production capacity disrupted — may lose priority or face delays', 'Reach the company (not the studio). "We can step in with zero gap."'],
        ['Early', 'YouTube channel views declining quarter-over-quarter', 'Content is stale — internal pressure to fix it', '"Your channel is down [X]%. Here\'s what [competitor] is doing differently."'],
        ['Early', 'Company posts first animated shorts on social media', 'Testing the waters before committing to full series', '"Great first short. Here\'s how to scale to a full series at 10x efficiency."'],
        ['Early', 'New product line announced at Toy Fair / Spielwarenmesse', 'New products need content support over 12–18 months', 'Plant the seed. Reference the specific product. Follow up after launch.'],
        ['Early', 'Executive posts about animation trends on LinkedIn', 'Thinking about it — pre-decision phase', 'Engage with their post. Add value in comments. DM with related insight.'],
        ['Early', 'Company raises funding or goes public', 'Fresh capital — content and marketing budgets expand', 'Reach out within 2 weeks of announcement.'],
        ['Early', 'Key creative executive or Content VP leaves', 'Strategy reset incoming — new hire will want fresh initiatives', 'Monitor for replacement hire (that\'s the High signal). Meanwhile reach CMO directly.'],
        ['Early', 'Company starts posting behind-the-scenes content', 'Building a content identity — animation is a natural next step', 'Engage with content. Position animation as the premium evolution.'],
        ['Early', 'Toy company wins a major new license (Disney, Marvel, Nintendo)', 'Licensed IP often comes with content obligations or opportunities', '"Congratulations on [licensor]. Here\'s how animation maximizes that license."'],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Trackable Signals'!A1",
        valueInputOption='RAW',
        body={'values': sig_data}
    ).execute()
    print(f"Written {len(sig_data)} rows")

    fmt = []

    # Header
    fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
            'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
    }})
    fmt.append({'updateSheetProperties': {
        'properties': {'sheetId': sig_id, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'
    }})

    # Column widths
    for i, w in enumerate([70, 340, 300, 350]):
        fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': sig_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})

    # Wrap + top align
    fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': len(sig_data), 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # Color priority column only
    colors = {
        'High': {'red': 0.95, 'green': 0.85, 'blue': 0.85},
        'Strong': {'red': 0.98, 'green': 0.93, 'blue': 0.82},
        'Early': {'red': 0.85, 'green': 0.92, 'blue': 0.97},
    }
    for r, row in enumerate(sig_data[1:], 1):
        p = row[0]
        if p in colors:
            fmt.append({'repeatCell': {
                'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 1},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': colors[p],
                    'textFormat': {'bold': True, 'fontSize': 9},
                    'horizontalAlignment': 'CENTER',
                }},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
            }})

    # Subtle alternating on B-D
    for r in range(1, len(sig_data)):
        if r % 2 == 0:
            fmt.append({'repeatCell': {
                'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 1, 'endColumnIndex': 4},
                'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.97, 'green': 0.97, 'blue': 0.97}}},
                'fields': 'userEnteredFormat(backgroundColor)'
            }})

    # =============================================
    # FIX EVENTS TAB — remove alternating row bg, clean white
    # =============================================
    evt_id = None
    sp2 = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    for s in sp2['sheets']:
        if s['properties']['title'] == 'Event Calendar 2026':
            evt_id = s['properties']['sheetId']
            break

    if evt_id is not None:
        # Reset ALL data rows to white background
        fmt.append({'repeatCell': {
            'range': {'sheetId': evt_id, 'startRowIndex': 1, 'endRowIndex': 20, 'startColumnIndex': 0, 'endColumnIndex': 6},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 1, 'green': 1, 'blue': 1},
            }},
            'fields': 'userEnteredFormat(backgroundColor)'
        }})

    sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': fmt}).execute()
    print("Formatting applied")
    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")

if __name__ == '__main__':
    run()
