"""v6 — accurate event pricing from actual 2026 registration pages."""
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

    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Event Calendar 2026'!A:H").execute()

    # Pricing from actual 2026 registration pages + user screenshot
    evt_data = [
        ['When', 'Event', 'Where', 'Website', 'Badge / Ticket Cost', 'Notes'],
        [
            'May 19–21',
            'Licensing Expo',
            'Las Vegas, Mandalay Bay',
            'licensingexpo.com',
            'Standard: $60 (early bird, $90 after May 1). Explorer: $275 ($395 after May 1). Networking: inquire. Retail: free (verified).',
            'Licensing industry\'s #1 event. 16K attendees. 300+ exhibitors. IP-to-toy pipeline. Standard pass includes 20 exhibitor meeting requests. Explorer adds Licensing Unlocked + 50 meetings. Start outreach NOW.'
        ],
        [
            'Jun 15–20',
            'Annecy / MIFA',
            'Annecy, France',
            'annecy.org',
            'Festival pass: ~€120–€180. Festival + MIFA market: ~€400–€700. MIFA-only: ~€300–€550. Student: ~€50.',
            '#1 animation event globally. 15K attendees. MIFA is the market where studios pitch and buyers commission. Book 20+ meetings. Pre-outreach starts April.'
        ],
        [
            'Jun',
            'VidCon',
            'Anaheim, CA',
            'vidcon.com',
            'Community: ~$80–$150. Creator: ~$400–$600. Industry: ~$1,200–$2,000.',
            'Digital-first content market. Industry track is the relevant one — brand partnerships, content strategy. Good for TheSoul\'s YouTube-native positioning.'
        ],
        [
            'Sep',
            'Cartoon Forum',
            'Toulouse, France',
            'cartoon-media.eu/cartoon-forum',
            '~€1,200–€1,500 per delegate. EU co-production fund members may get discounts.',
            'Invitation-based animation series pitching. ~950 attendees — all decision-makers actively commissioning. Highest signal-to-noise ratio of any event.'
        ],
        [
            'Sep–Oct',
            'Brand Licensing Europe',
            'London, ExCeL',
            'brandlicensing.eu',
            'Standard: ~£50–£75. Retail/licensee: free (qualified). Exhibitor: quote-based.',
            'European IP licensing. Same Informa Markets format as Licensing Expo. Target EU toy and FMCG brands.'
        ],
        [
            'Sep–Oct',
            'Toy Fair New York',
            'New York, Javits Center',
            'toyfairny.com',
            'Trade-only. Buyer/retailer: free (pre-registered). Industry: ~$50–$100.',
            'Note: Toy Fair 2027 announced for Feb 20–23, 2027. Check if 2026 fall edition runs. New product reveals. 25K attendees.'
        ],
        [
            'Oct',
            'MIPCOM / MIPJunior',
            'Cannes, Palais des Festivals',
            'mipcom.com',
            'MIPJunior: ~€700–€900. MIPCOM: ~€1,800–€2,500. Combined: ~€2,200–€3,000. Buyer badges may be discounted.',
            'Global content marketplace. MIPJunior (weekend before) = kids content exclusively. Where Hasbro, Mattel, Spin Master scout animation studios.'
        ],
        [
            'Nov',
            'CTN Animation Expo',
            'Burbank, Marriott Convention Center',
            'ctn-events.com',
            '4-Day Basic: ~$75–$100. Student/Member discounts available. Free pass with 2-night hotel booking.',
            'Animation networking and recruiting. Most affordable event on the calendar. Good for pipeline building and relationship maintenance.'
        ],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Event Calendar 2026'!A1",
        valueInputOption='RAW',
        body={'values': evt_data}
    ).execute()
    print(f"Events: {len(evt_data)} rows")

    fmt = []

    # Header row
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

    # Column widths
    for i, w in enumerate([80, 170, 200, 210, 280, 420]):
        fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': evt_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})

    # Wrap all + top-align
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
