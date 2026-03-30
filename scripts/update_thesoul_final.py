"""Final cleanup — fix all tabs to be sales-ready."""
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

    # =============================================
    # SIGNALS TAB — complete rewrite
    # =============================================
    sig_id = tabs['Trackable Signals']
    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Trackable Signals'!A:D").execute()

    # No empty rows, no merged cells, no yellow banners.
    # Tier labels go in column A as a category, signals flow cleanly.
    sig_data = [
        ['Priority', 'Signal', 'What It Means', 'Outreach Move'],
        # HIGH INTENT
        ['High', 'New VP/Director of Content or Entertainment hired', 'New content strategy incoming — they were hired to build something', 'Congratulate within 30 days. Offer industry briefing on animation production landscape.'],
        ['High', 'Animation job openings (Producer, Head of Animation, EP) at a non-studio company', 'Building internal team to manage external production — commissioning is imminent', '"You build the team, we bring the studio." Position as production partner.'],
        ['High', 'Multiple animation/content hires at same company within weeks', 'Major production initiative launching — budget is allocated', 'Move fast. Pitch capacity and speed. They\'re already behind schedule.'],
        ['High', 'RFP or production tender published', 'Active procurement — decision in weeks', 'Respond immediately with tailored pitch + reel.'],
        ['High', 'New IP or character launch announced without animation', 'Product coming but content strategy is missing', '"We noticed [IP] launches in Q3. Here\'s how animation accelerates adoption."'],
        ['High', 'Existing animated series gets cancelled or ends', 'Still need content — relationship with previous studio may be broken', '"We saw [series] wrapped. If you\'re evaluating next steps for [IP], we\'d love to discuss."'],
        ['High', 'Company hires showrunner or head writer but no studio announced', 'Pre-production started — they need a production partner now', 'Reach the showrunner AND the Content VP. "We can be in production within weeks."'],
        # STRONG INTENT
        ['Strong', 'First-time registration for Annecy, Kidscreen, or MIPCOM', 'Entering the animation market — scouting studios', 'Pre-event outreach 8 weeks before. Book a meeting. Send reel for their segment.'],
        ['Strong', 'Streaming deal announced (Netflix, Apple TV+, Amazon)', 'Need animation produced — platform deal doesn\'t include a studio', '"Congratulations on the deal. We can deliver the production."'],
        ['Strong', 'Brand refresh or franchise relaunch announced', 'Legacy IP being revived — new animation is almost always part of it', 'Reference their specific IP history. Show what a modern version looks like.'],
        ['Strong', 'Earnings call mentions "content strategy" or "entertainment segment"', 'Executive mandate from the top — VP will be tasked with finding studios', 'Email the VP of Content directly. Reference the CEO\'s comments.'],
        ['Strong', 'Competitor launches animated series for similar product', 'Competitive pressure — board-level conversations are happening', '"[Competitor] just launched [series]. Here\'s how you respond."'],
        ['Strong', 'Company acquires new IP (book series, comic, game)', 'Animated adaptation will follow within 12–24 months', '"We\'d love to discuss bringing [IP] to animation." Get in early.'],
        ['Strong', 'Licensing revenue drops in quarterly earnings', 'Animation drives awareness which drives licensing — decline = pressure to invest', '"Licensing depends on visibility. Here\'s how animation reverses the trend."'],
        ['Strong', 'Animation studio partner gets acquired or merges', 'Production capacity disrupted — may lose priority or face delays', 'Reach the company (not the studio). "We can step in with zero gap."'],
        # EARLY
        ['Early', 'YouTube channel views declining quarter-over-quarter', 'Content is stale — internal pressure to fix it', '"Your channel is down [X]%. Here\'s what [competitor] is doing differently."'],
        ['Early', 'Company posts first animated shorts on social media', 'Testing the waters before committing to full series', '"Great first short. Here\'s how to scale to a full series at 10x efficiency."'],
        ['Early', 'New product line announced at Toy Fair / Spielwarenmesse', 'New products need content support over 12–18 months', 'Plant the seed. Reference the specific product. Follow up after launch.'],
        ['Early', 'Executive posts about animation or content trends on LinkedIn', 'Thinking about it — pre-decision phase', 'Engage with their post. Add value in comments. DM with related insight.'],
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
    print(f"Signals: {len(sig_data)} rows")

    sig_fmt = []
    # Header row
    sig_fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
            'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
    }})
    sig_fmt.append({'updateSheetProperties': {
        'properties': {'sheetId': sig_id, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'
    }})

    # Column widths
    for i, w in enumerate([70, 340, 300, 350]):
        sig_fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': sig_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})

    # Wrap + top align all
    sig_fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': len(sig_data), 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # Color-code the Priority column
    # High = red tint, Strong = orange tint, Early = blue tint
    priority_colors = {
        'High': {'red': 0.95, 'green': 0.85, 'blue': 0.85},
        'Strong': {'red': 0.98, 'green': 0.93, 'blue': 0.82},
        'Early': {'red': 0.85, 'green': 0.92, 'blue': 0.97},
    }
    for r, row in enumerate(sig_data[1:], 1):
        priority = row[0]
        if priority in priority_colors:
            # Color just column A
            sig_fmt.append({'repeatCell': {
                'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 1},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': priority_colors[priority],
                    'textFormat': {'bold': True, 'fontSize': 9},
                    'horizontalAlignment': 'CENTER',
                }},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
            }})

    # Alternating row bg (very subtle, columns B-D only)
    for r in range(1, len(sig_data)):
        if r % 2 == 0:
            sig_fmt.append({'repeatCell': {
                'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 1, 'endColumnIndex': 4},
                'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.97, 'green': 0.97, 'blue': 0.97}}},
                'fields': 'userEnteredFormat(backgroundColor)'
            }})

    # =============================================
    # EVENTS TAB — TheSoul-specific pricing only
    # =============================================
    evt_id = tabs['Event Calendar 2026']
    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Event Calendar 2026'!A:H").execute()

    evt_data = [
        ['When', 'Event', 'Where', 'Website', 'Pass for TheSoul', 'Why Attend'],
        [
            'May 19–21',
            'Licensing Expo',
            'Las Vegas, Mandalay Bay',
            'licensingexpo.com',
            'Explorer Pass: $275 (early bird before May 1, then $395). Includes Licensing Unlocked + 50 meeting requests.',
            '16K attendees. IP-to-toy pipeline. Meet VP Licensing at toy and FMCG brands face-to-face. Highest concentration of ICP1 decision-makers in one place.'
        ],
        [
            'Jun 15–20',
            'Annecy / MIFA',
            'Annecy, France',
            'annecy.org',
            'MIFA professional accreditation: €350–€700 (includes festival). MIFA-only: €300–€550.',
            '#1 animation event globally. 15K attendees. MIFA is the market — studios pitch, buyers commission. Book 20+ meetings. Pre-outreach starts April.'
        ],
        [
            'Jun',
            'VidCon',
            'Anaheim, CA',
            'vidcon.com',
            'Industry Track: $1,200–$2,000.',
            'Digital-first content market. Brand partnerships and content strategy discussions. Relevant for TheSoul\'s YouTube-native production model.'
        ],
        [
            'Sep',
            'Cartoon Forum',
            'Toulouse, France',
            'cartoon-media.eu/cartoon-forum',
            'Delegate: ~€1,200–€1,500.',
            'Invitation-based animation series pitching. ~950 attendees — all actively commissioning. Highest signal-to-noise ratio of any industry event.'
        ],
        [
            'Sep–Oct',
            'Brand Licensing Europe',
            'London, ExCeL',
            'brandlicensing.eu',
            'Standard: ~£50–£75.',
            'European IP licensing. Target EU toy and FMCG brands looking for animation production partners.'
        ],
        [
            'Oct',
            'MIPCOM / MIPJunior',
            'Cannes, Palais des Festivals',
            'mipcom.com',
            'Combined MIPJunior + MIPCOM: ~€2,200–€3,000. MIPJunior only: ~€700–€900.',
            'Global content marketplace. MIPJunior (weekend before) is exclusively kids content. Where Hasbro, Mattel, Spin Master scout animation studios.'
        ],
        [
            'Nov',
            'CTN Animation Expo',
            'Burbank, Marriott Convention Center',
            'ctn-events.com',
            '4-Day Pass: ~$75–$100.',
            'Animation networking. Most affordable event. Good for pipeline building and meeting mid-level production contacts.'
        ],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Event Calendar 2026'!A1",
        valueInputOption='RAW',
        body={'values': evt_data}
    ).execute()
    print(f"Events: {len(evt_data)} rows")

    evt_fmt = []
    # Header
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 6},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
            'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
    }})
    evt_fmt.append({'updateSheetProperties': {
        'properties': {'sheetId': evt_id, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'
    }})

    # Column widths
    for i, w in enumerate([75, 170, 195, 200, 300, 400]):
        evt_fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': evt_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})

    # Wrap + top align
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 0, 'endRowIndex': len(evt_data), 'startColumnIndex': 0, 'endColumnIndex': 6},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # Bold event names
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 1, 'endRowIndex': len(evt_data), 'startColumnIndex': 1, 'endColumnIndex': 2},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})

    # Alternating rows
    for r in range(1, len(evt_data)):
        if r % 2 == 0:
            evt_fmt.append({'repeatCell': {
                'range': {'sheetId': evt_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 6},
                'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.97, 'green': 0.97, 'blue': 0.97}}},
                'fields': 'userEnteredFormat(backgroundColor)'
            }})

    # =============================================
    # ROLES TAB — quick cleanup
    # =============================================
    roles_id = tabs.get('Target Roles & Decision Unit')
    if roles_id:
        sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Target Roles & Decision Unit'!A:F").execute()

        roles_data = [
            ['Role', 'Priority', 'Why Target', 'What They Care About'],
            ['VP / Director of Content Development', 'Primary', 'Owns content strategy. Writes the brief. Runs studio selection.', 'Creative quality, production reliability, on-time delivery, cultural fit'],
            ['VP / Director of Brand Entertainment', 'Primary', 'Drives animation commissioning for brand IP.', 'Brand vision execution, franchise value growth'],
            ['Head of Animation / Executive Producer', 'Primary', 'Evaluates technical capability. Reviews reels. Visits studios.', 'Animation quality, pipeline tools, team depth, scalability'],
            ['SVP / EVP of Entertainment', 'Primary', 'Final budget approval at large toy/media companies.', 'ROI — will animation drive toy sales, licensing revenue, streaming deals'],
            ['CMO / VP Brand Marketing', 'Secondary', 'Budget authority at consumer brands. Brand guardian — can veto.', 'Brand consistency, audience alignment, marketing ROI'],
            ['VP of Licensing & Partnerships', 'Secondary', 'Content drives licensing revenue. Signs partnership deals.', 'IP ownership terms, territory rights, merchandising splits'],
            ['VP of eCommerce / DTC', 'Secondary', 'Animation drives product discovery and direct sales.', 'Conversion metrics, content-to-purchase attribution'],
            ['Creative Director', 'Secondary', 'Validates creative quality and style match.', 'Showreel quality, style versatility, brand understanding'],
            ['CEO / President', 'Approver', 'Final sign-off at companies under $500M revenue.', 'Total investment vs. expected franchise revenue uplift'],
            ['Division President / EVP', 'Approver', 'Signs off at large companies (Hasbro, Mattel, Bandai scale).', 'Division P&L impact'],
        ]

        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="'Target Roles & Decision Unit'!A1",
            valueInputOption='RAW',
            body={'values': roles_data}
        ).execute()
        print(f"Roles: {len(roles_data)} rows")

        roles_fmt = []
        # Header
        roles_fmt.append({'repeatCell': {
            'range': {'sheetId': roles_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 4},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
                'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }})
        roles_fmt.append({'updateSheetProperties': {
            'properties': {'sheetId': roles_id, 'gridProperties': {'frozenRowCount': 1}},
            'fields': 'gridProperties.frozenRowCount'
        }})
        for i, w in enumerate([280, 80, 340, 340]):
            roles_fmt.append({'updateDimensionProperties': {
                'range': {'sheetId': roles_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
                'properties': {'pixelSize': w}, 'fields': 'pixelSize'
            }})
        roles_fmt.append({'repeatCell': {
            'range': {'sheetId': roles_id, 'startRowIndex': 0, 'endRowIndex': len(roles_data), 'startColumnIndex': 0, 'endColumnIndex': 4},
            'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
            'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
        }})
        # Bold role names
        roles_fmt.append({'repeatCell': {
            'range': {'sheetId': roles_id, 'startRowIndex': 1, 'endRowIndex': len(roles_data), 'startColumnIndex': 0, 'endColumnIndex': 1},
            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat(textFormat)'
        }})
        # Color-code priority
        priority_colors_roles = {
            'Primary': {'red': 0.85, 'green': 0.92, 'blue': 0.85},
            'Secondary': {'red': 0.93, 'green': 0.93, 'blue': 0.93},
            'Approver': {'red': 0.92, 'green': 0.88, 'blue': 0.95},
        }
        for r, row in enumerate(roles_data[1:], 1):
            p = row[1]
            if p in priority_colors_roles:
                roles_fmt.append({'repeatCell': {
                    'range': {'sheetId': roles_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 1, 'endColumnIndex': 2},
                    'cell': {'userEnteredFormat': {
                        'backgroundColor': priority_colors_roles[p],
                        'textFormat': {'bold': True, 'fontSize': 9},
                        'horizontalAlignment': 'CENTER',
                    }},
                    'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
                }})
        # Alternating
        for r in range(1, len(roles_data)):
            if r % 2 == 0:
                roles_fmt.append({'repeatCell': {
                    'range': {'sheetId': roles_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 1},
                    'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.97, 'green': 0.97, 'blue': 0.97}}},
                    'fields': 'userEnteredFormat(backgroundColor)'
                }})
                for ci in [2, 3]:
                    roles_fmt.append({'repeatCell': {
                        'range': {'sheetId': roles_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': ci, 'endColumnIndex': ci + 1},
                        'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.97, 'green': 0.97, 'blue': 0.97}}},
                        'fields': 'userEnteredFormat(backgroundColor)'
                    }})
    else:
        roles_fmt = []

    # =============================================
    # Apply all
    # =============================================
    all_fmt = sig_fmt + evt_fmt + roles_fmt
    sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': all_fmt}).execute()
    print("All formatting applied")
    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")

if __name__ == '__main__':
    run()
