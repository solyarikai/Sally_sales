"""v5 — fix event calendar readability, add websites + ticket costs."""
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
    evt_id = tabs['Event Calendar 2026']

    # Clear
    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Event Calendar 2026'!A:H").execute()

    evt_data = [
        ['When', 'Event', 'Where', 'Website', 'Badge Cost (est.)', 'Notes'],
        ['May 19–21', 'Licensing Expo', 'Las Vegas, Mandalay Bay', 'licensingexpo.com', 'Free (qualified buyers). Exhibitor booths from $5K.', 'Licensing industry\'s #1 event. 16K attendees. IP-to-toy pipeline. Meet VP Licensing face-to-face. Start outreach NOW — 8 weeks out.'],
        ['Jun 15–20', 'Annecy / MIFA', 'Annecy, France', 'annecy.org', 'Festival: ~€150. MIFA market pass: €350–€700.', 'THE #1 animation event globally. 15K attendees. Studios pitch, buyers commission. Book 20+ meetings. Pre-outreach starts April.'],
        ['Jun', 'VidCon', 'Anaheim, CA', 'vidcon.com', 'Industry track: $1,000–$2,000.', 'Digital-first content market. Relevant for TheSoul\'s YouTube-native positioning and brand partnerships.'],
        ['Sep', 'Cartoon Forum', 'Toulouse, France', 'cartoon-media.eu/cartoon-forum', '~€1,200–€1,500 per delegate.', 'Invitation-based animation series pitching. ~950 attendees — all decision-makers. Highest signal-to-noise ratio.'],
        ['Sep–Oct', 'Brand Licensing Europe', 'London, ExCeL', 'brandlicensing.eu', 'Free (qualified). Walk-up ~£40.', 'European IP licensing. Same dynamic as Licensing Expo. Target EU toy and FMCG brands.'],
        ['Sep–Oct', 'Toy Fair New York', 'New York, Javits Center', 'toyfairny.com', 'Free–$100 (trade only).', 'New product reveals. 25K attendees. Spot toy launches without animation — pitch production partnership.'],
        ['Oct', 'MIPCOM / MIPJunior', 'Cannes, Palais des Festivals', 'mipcom.com', 'MIPJunior: ~€700. MIPCOM: ~€2,000. Combined: ~€2,500.', 'Global content marketplace. MIPJunior = kids. Where Hasbro, Mattel, Spin Master scout animation studios.'],
        ['Nov', 'CTN Animation Expo', 'Burbank, CA', 'ctnanimationexpo.com', 'Weekend pass: ~$80. Exhibitor: ~$500–$1,500.', 'Animation networking and recruiting. Affordable. Good for pipeline and relationship building.'],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Event Calendar 2026'!A1",
        valueInputOption='RAW',
        body={'values': evt_data}
    ).execute()
    print(f"Events: {len(evt_data)} rows")

    # Format
    fmt = []

    # Header row — dark, white
    fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 6},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
            'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
    }})

    # Freeze header
    fmt.append({'updateSheetProperties': {
        'properties': {'sheetId': evt_id, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'
    }})

    # Column widths: When, Event, Where, Website, Badge Cost, Notes
    for i, w in enumerate([80, 180, 180, 230, 220, 450]):
        fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': evt_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})

    # Wrap all
    fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 0, 'endRowIndex': len(evt_data), 'startColumnIndex': 0, 'endColumnIndex': 6},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # Alternating rows
    for r in range(1, len(evt_data)):
        if r % 2 == 0:
            fmt.append({'repeatCell': {
                'range': {'sheetId': evt_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 6},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': {'red': 0.96, 'green': 0.96, 'blue': 0.96},
                }},
                'fields': 'userEnteredFormat(backgroundColor)'
            }})

    # Bold event names
    fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 1, 'endRowIndex': len(evt_data), 'startColumnIndex': 1, 'endColumnIndex': 2},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})

    sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': fmt}).execute()
    print("Formatting applied")
    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")

if __name__ == '__main__':
    run()
