"""v4 — delete ABM, add new signals."""
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

    # Delete ABM
    reqs = []
    if 'ABM Outreach Plan' in tabs:
        reqs.append({'deleteSheet': {'sheetId': tabs['ABM Outreach Plan']}})
    if reqs:
        sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': reqs}).execute()
        print("Deleted ABM Outreach Plan")

    # Rewrite Signals with additions
    sig_id = tabs.get('Trackable Signals')
    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Trackable Signals'!A:H").execute()

    sig_data = [
        ['Buying Signals'],
        ['Observable events that indicate a company is about to commission animation production.'],
        [''],
        ['Signal', 'What It Means', 'Outreach Move'],
        [''],
        ['HIGH INTENT', '', ''],
        ['New VP/Director of Content or Entertainment hired', 'New content strategy incoming. They were hired to build something.', 'Congratulate. Offer an industry briefing on animation production landscape within 30 days of their start.'],
        ['Animation job openings at a NON-studio company (Producer, Head of Animation, EP)', 'Building internal team to manage external production. Commissioning is imminent.', 'Position as the production partner they\'ll need. "You build the team, we bring the studio."'],
        ['Multiple animation/content hires at same company within weeks', 'Major production initiative is launching. Budget is allocated.', 'Move fast. Pitch capacity and speed. They\'re already behind schedule.'],
        ['RFP or production tender published', 'Active procurement. Decision in weeks.', 'Drop everything. Respond immediately with tailored pitch + reel.'],
        ['New IP or character launch announced — no animation mentioned', 'Product is coming but content strategy is missing or delayed.', '"We noticed [IP name] launches in Q3. Here\'s how animation accelerates adoption."'],
        ['Company\'s existing animated series gets cancelled or ends', 'They still need content. Relationship with previous studio may be broken.', '"We saw [series] wrapped. If you\'re evaluating next steps for [IP], we\'d love to discuss."'],
        ['Company hires a showrunner or head writer — but has no studio announced', 'Pre-production has started. They need a production partner yesterday.', 'Reach out directly to the showrunner AND the Content VP. "We can be in production within weeks of greenlight."'],
        [''],
        ['STRONG INTENT', '', ''],
        ['Company registers for Annecy, Kidscreen, or MIPCOM for the first time', 'Entering the animation market. Scouting studios.', 'Pre-event outreach 8 weeks before. Book a meeting. Send reel tailored to their segment.'],
        ['Streaming deal announced (Netflix, Apple TV+, Amazon)', 'Need animation produced. Platform deal doesn\'t include a studio.', '"Congratulations on the [platform] deal. We can deliver the production."'],
        ['Brand refresh or franchise relaunch announced', 'Legacy IP being revived. New animation is almost always part of it.', 'Reference their specific IP history. Show what a modern version looks like.'],
        ['Earnings call mentions "content strategy" or "entertainment segment" growth', 'Executive mandate from the top. VP will be tasked with finding studios.', 'Email the VP of Content directly. Reference the CEO\'s comments.'],
        ['Competitor launches an animated series for a similar product', 'Competitive pressure. Board-level conversations are happening.', '"[Competitor] just launched [series]. Here\'s how you respond."'],
        ['Company acquires new IP (book series, comic, game property)', 'Animated adaptation will follow. 12–24 month window.', 'Get in early. "We\'d love to discuss bringing [IP name] to animation."'],
        ['Licensing revenue drops in quarterly earnings', 'Animation drives brand awareness which drives licensing. Decline = pressure to invest in content.', '"Licensing depends on brand visibility. Here\'s how animation reverses the trend — with the Crayola numbers."'],
        ['Company\'s animation studio partner gets acquired or merges', 'Production capacity is disrupted. They may lose priority or face delays.', 'Reach out to the company (not the studio). "We heard about [studio change]. We can step in with zero gap."'],
        [''],
        ['EARLY INDICATORS', '', ''],
        ['Company\'s YouTube channel views declining quarter-over-quarter', 'Content is stale. Internal pressure to fix it.', '"Your channel is down [X]% this quarter. Here\'s what [competitor] is doing differently."'],
        ['Company posts first animated shorts on social (testing the waters)', 'Experimenting before committing to full series.', '"Great first short. Here\'s how to scale that to a full series at 10x the efficiency."'],
        ['New product line announced at Toy Fair / Spielwarenmesse', 'New products need content support over the next 12–18 months.', 'Plant the seed. Reference the specific product. Follow up after launch.'],
        ['Executive posts about animation or content trends on LinkedIn', 'They\'re thinking about it. Pre-decision phase.', 'Engage with their post. Add value in comments. DM with a related insight.'],
        ['Company raises funding or goes public', 'Fresh capital. Content and marketing budgets expand.', 'Reach out within 2 weeks of announcement.'],
        ['Key creative executive or Content VP leaves the company', 'Strategy reset incoming. New hire will want to make their mark with a fresh initiative.', 'Monitor for the replacement hire — that\'s the Tier 1 signal. Meanwhile, reach the CMO or CEO directly.'],
        ['Company starts posting behind-the-scenes or "making of" content', 'They\'re building a content identity. Animation is a logical next step.', 'Engage with the content. Position animation as the premium evolution of what they\'re already doing.'],
        ['Toy company wins a major new license (Disney, Marvel, Nintendo, etc.)', 'Licensed IP often comes with content obligations or opportunities. Animation supports the license.', '"Congratulations on the [licensor] deal. Here\'s how animation maximizes the value of that license."'],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Trackable Signals'!A1",
        valueInputOption='RAW',
        body={'values': sig_data}
    ).execute()
    print(f"Signals: {len(sig_data)} rows")

    # Format
    fmt = []
    # Title
    fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True, 'fontSize': 14}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Subtitle
    fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 1, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'textFormat': {'italic': True, 'fontSize': 10, 'foregroundColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Column header
    fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 3, 'endRowIndex': 4, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
            'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
    }})
    # Tier headers
    for r in [5, 13, 23]:
        fmt.append({'mergeCells': {
            'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
            'mergeType': 'MERGE_ALL'
        }})
        fmt.append({'repeatCell': {
            'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 1.0, 'green': 0.95, 'blue': 0.8},
                'textFormat': {'bold': True, 'fontSize': 11, 'foregroundColor': {'red': 0.15, 'green': 0.15, 'blue': 0.15}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }})
    # Column widths
    for i, w in enumerate([380, 320, 380]):
        fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': sig_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    # Wrap
    fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': len(sig_data), 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})
    # Freeze header area
    fmt.append({'updateSheetProperties': {
        'properties': {'sheetId': sig_id, 'gridProperties': {'frozenRowCount': 4}},
        'fields': 'gridProperties.frozenRowCount'
    }})

    sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': fmt}).execute()
    print("Formatting applied")
    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")

if __name__ == '__main__':
    run()
