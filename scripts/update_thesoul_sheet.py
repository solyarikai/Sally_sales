"""Update TheSoul Group sheet — single grouped tab for all segments."""
import json
import os
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDS_PATH = Path(__file__).resolve().parent.parent / 'google-credentials.json'
SHEET_ID = '1XlCV5ObWykGopw2qLmDwxO3hvekGugeBXLg9AA_TsXI'

def get_services():
    creds = service_account.Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    sheets = build('sheets', 'v4', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)
    return sheets, drive

def update_sheet():
    sheets, drive = get_services()

    # ---- Get current sheet structure ----
    sp = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing_tabs = {s['properties']['title']: s['properties']['sheetId'] for s in sp['sheets']}
    print(f"Existing tabs: {list(existing_tabs.keys())}")

    # ---- Delete old segment tabs + executive summary ----
    tabs_to_delete = [
        'Executive Summary',
        '1A. Toys — No Animation',
        '1B. Toys — Need More Capacity',
        '1C. Consumer Brands with Characters',
        '1D. Gaming (Post-Arcane)',
        '1E. EdTech & Educational',
        '1F. IP Owners (Publishing, Licensing)',
    ]

    delete_requests = []
    for tab_name in tabs_to_delete:
        if tab_name in existing_tabs:
            delete_requests.append({'deleteSheet': {'sheetId': existing_tabs[tab_name]}})

    # ---- Add new "Target Segments & Companies" tab at index 0 ----
    NEW_TAB_TITLE = 'Target Segments & Companies'
    # Delete if already exists from a previous run
    if NEW_TAB_TITLE in existing_tabs:
        delete_requests.append({'deleteSheet': {'sheetId': existing_tabs[NEW_TAB_TITLE]}})

    add_requests = [{'addSheet': {'properties': {'title': NEW_TAB_TITLE, 'index': 0}}}]

    if delete_requests or add_requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': add_requests + delete_requests}
        ).execute()
        print(f"Deleted {len(delete_requests)} old tabs, added '{NEW_TAB_TITLE}'")

    # ---- Get the new tab's sheetId ----
    sp = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    new_tab_id = None
    for s in sp['sheets']:
        if s['properties']['title'] == NEW_TAB_TITLE:
            new_tab_id = s['properties']['sheetId']
            break
    print(f"New tab sheetId: {new_tab_id}")

    # ---- Build data ----
    # Structure: segment header rows + company detail rows (grouped under each segment)

    HEADER = ['Segment', 'Company', 'Website', 'Current Animation', 'Opportunity']

    segments = [
        {
            'name': 'Toy Companies Without Animated Series',
            'why': 'Animated series sell toys. Companies without animation leave revenue on the table — competitors with content outsell those without.',
            'companies': [
                ['', 'ZURU', 'zuru.com', 'None', 'Fastest-growing toy company ($2B+). Zero animated series. Greenfield.'],
                ['', 'Jazwares', 'jazwares.com', 'None (for Squishmallows)', 'Squishmallows — 485M toys sold, cultural phenomenon, no animation. Series is inevitable.'],
                ['', 'MGA Entertainment', 'mgae.com', 'Launched late, inconsistent quality', 'Multiple IPs (L.O.L. Surprise!, Bratz, Rainbow High) need animation simultaneously.'],
                ['', 'Moose Toys', 'moosetoys.com', 'Minimal YouTube content', 'Hit toy lines (Shopkins, Magic Mixies) with no proper animated series.'],
                ['', 'Funko', 'funko.com', 'None (original content)', '8M+ collector community. Started original IP — animation would differentiate.'],
                ['', 'Playmobil', 'playmobil.com', 'Movie flopped (2019), minimal series', 'LEGO has Ninjago, City, Friends. Playmobil has almost nothing.'],
                ['', 'Basic Fun!', 'basicfun.com', 'Care Bears reboot stalled', 'Owns Care Bears, Tonka, K\'NEX, Lite-Brite — classic IPs with no new animation.'],
                ['', 'VTech', 'vtech.com', 'Very limited clips', 'Educational toys with characters (Go! Go! Smart Wheels) that have zero animated series.'],
                ['', 'Simba Dickie Group', 'simba-dickie-group.de', 'Almost none', 'One of Europe\'s largest toy companies ($1B). Minimal animation strategy.'],
                ['', 'Epoch Co.', 'epoch.jp', 'Very limited', 'Sylvanian Families — beloved character world, severely underdeveloped animation.'],
                ['', 'IMC Toys', 'imctoys.com', 'Kitoons YouTube (700K subs)', 'Cry Babies, VIP Pets — already invested in animation, needs production scale-up.'],
                ['', 'Giochi Preziosi', 'giochipreziosi.it', 'Gormiti series expired', 'Gormiti was proven IP. Needs digital-era animated revival.'],
                ['', 'Ty Inc.', 'ty.com', 'None', 'Beanie Boos, Beanie Babies — massive brand recognition, zero content.'],
                ['', 'Schleich', 'schleich-s.com', 'None', 'Fantasy worlds (Bayala, Eldrador) purpose-built for animated series.'],
                ['', 'Melissa & Doug', 'melissaanddoug.com', 'None', 'Premium educational brand. Animation could bridge play philosophy with digital discovery.'],
            ]
        },
        {
            'name': 'Toy Companies Needing More Production Capacity',
            'why': 'Already proven animation buyers. Need additional studios for volume, new IPs, digital-first content, and localization.',
            'companies': [
                ['', 'Spin Master', 'spinmaster.com', 'PAW Patrol (Guru Studio), Bakugan', 'Only PAW Patrol has animation. Tech Deck, Kinetic Sand, Hatchimals = zero.'],
                ['', 'Hasbro', 'hasbro.com', 'Multiple studios (eOne, Allspark, Boulder Media)', 'Massive pipeline. Always needs additional capacity for launches and streaming.'],
                ['', 'Mattel', 'mattel.com', 'Multiple studios', 'Aggressively expanding into content (Mattel Films). Needs more partners.'],
                ['', 'Bandai Namco', 'bandainamco.com', 'Toei (Dragon Ball), Sunrise (Gundam)', 'Western expansion needs localized animated content and digital-first formats.'],
                ['', 'Takara Tomy', 'takaratomy.co.jp', 'Various Japanese studios', 'Weak Western/YouTube presence despite massive kid appeal (Beyblade, Tomica).'],
                ['', 'Alpha Group', 'alphagroup.cn', 'In-house + Chinese studios', 'Super Wings global distribution inconsistent outside China. Needs quality partner.'],
                ['', 'WildBrain', 'wildbrain.com', 'In-house + partners', 'Peanuts, Teletubbies — struggles with production scale. Overflow partnership.'],
                ['', 'Sanrio', 'sanrio.com', 'Various, fragmented', 'Hello Kitty, Kuromi — 50+ years of IP, no unified animation production partner.'],
            ]
        },
        {
            'name': 'Consumer Brands with Character IP',
            'why': 'Own iconic animated mascots but produce animation ad-hoc through agencies. A dedicated production partner offering always-on content at scale is a new model.',
            'companies': [
                ['', 'Ferrero / Kinder', 'ferrero.com', 'Limited. Doesn\'t own the unboxing ecosystem.', 'Kinder Surprise is YouTube\'s #1 kids unboxing genre — Ferrero should own the content.'],
                ['', 'Haribo', 'haribo.com', 'Goldbears animated ads, no long-form', 'Globally recognized characters. Zero series or YouTube content.'],
                ['', 'Kellogg\'s', 'kelloggs.com', 'Legacy mascots in sporadic spots', 'Tony the Tiger, Toucan Sam barely used in modern formats. Massive IP.'],
                ['', 'General Mills', 'generalmills.com', 'Seasonal spots only', 'Lucky Charms, Trix Rabbit, Count Chocula — beloved characters, no digital home.'],
                ['', 'Mondelez', 'mondelezinternational.com', 'No animation', 'Sour Patch Kids has massive Gen-Z following. No animated series.'],
                ['', 'PepsiCo (Cheetos)', 'pepsico.com', 'Animated spots, live-action movie', 'Chester Cheetah is underused. Animated shorts are cheaper and more scalable.'],
                ['', 'McDonald\'s', 'mcdonalds.com', 'Grimace revival went viral (2023)', 'Proved the model. Needs consistent animated content pipeline.'],
                ['', 'Bazooka Candy', 'bazooka-candy.com', 'Dormant Bazooka Joe comics', '70+ years of recognition (Ring Pop, Push Pop). Interactive candy = interactive content.'],
                ['', 'Perfetti Van Melle', 'perfettivanmelle.com', 'Historical licensed animation', 'Chupa Chups (Dali logo) — pop-art heritage ripe for animated revival.'],
                ['', 'PEZ', 'pez.com', 'None', 'Collecting is already a YouTube genre. Needs official animated content partner.'],
                ['', 'Jollibee Foods', 'jollibeefoods.com', 'TV ads (Philippines only)', 'Most beloved fast-food mascot in Asia. Global expansion needs animation.'],
                ['', 'Jelly Belly', 'jellybelly.com', 'None', 'BeanBoozled IS a YouTube challenge format. Official animated content is natural.'],
            ]
        },
        {
            'name': 'Gaming Companies (Post-Arcane)',
            'why': 'Arcane proved animated companion content drives player engagement. Every major studio wants it — few have in-house production capability.',
            'companies': [
                ['', 'Supercell', 'supercell.com', 'Clash-A-Rama (YouTube), game cinematics', 'Proven animation buyer. High volume. Always needs new production partners.'],
                ['', 'HoYoverse / miHoYo', 'hoyoverse.com', 'Animated shorts/trailers (outsourced)', 'New character every 6 weeks — each needs animated trailer. Insatiable appetite.'],
                ['', 'Riot Games', 'riotgames.com', 'Arcane (Fortiche), music videos', 'Fortiche has years-long waitlist. 5+ IPs need animated content.'],
                ['', 'Epic Games', 'epicgames.com', 'Season trailers, crossover reveals', 'Fortnite: constant need — new seasons, crossovers, Lego Fortnite.'],
                ['', 'Blizzard', 'blizzard.com', 'Overwatch shorts (Blur Studio)', 'OW shorts were massive hits but production slowed. Multiple franchises.'],
                ['', 'Ubisoft', 'ubisoft.com', 'Rabbids Invasion, Captain Laserhawk', 'Rabbids perfect for high-volume production. AC needs companion content.'],
                ['', 'Krafton', 'krafton.com', 'Minimal — trailers only', 'PUBG: 400M+ players, almost no narrative animated content.'],
                ['', 'Roblox Corp', 'roblox.com', 'Minimal', '70M+ daily users. Rising quality bar. Brands need animated content at scale.'],
            ]
        },
        {
            'name': 'EdTech & Educational Companies',
            'why': 'Animation is core to the educational product. These companies need it produced at massive scale, cost-effectively. Recurring production relationships.',
            'companies': [
                ['', 'Age of Learning (ABCmouse)', 'ageoflearning.com', 'Thousands of animated modules', 'One of the largest animation buyers in edtech. Always needs more capacity.'],
                ['', 'Duolingo', 'duolingo.com', 'Short social animations, TikTok', 'Duo the owl is a cultural phenomenon. Ready for a proper animated series.'],
                ['', 'PBS Kids', 'pbskids.org', 'Major commissioner (Daniel Tiger, Wild Kratts)', 'One of the world\'s largest educational animation commissioners. Always developing.'],
                ['', 'Sesame Workshop', 'sesameworkshop.org', 'Mix of puppetry and animation', 'Increasing animation ratio. International co-productions need partners.'],
                ['', 'Khan Academy', 'khanacademy.org', 'Moving toward polished content', 'Kids version needs professional animation.'],
                ['', 'Lingokids', 'lingokids.com', 'Animated characters and episodes', 'Growing fast. Needs to scale animation for multiple languages.'],
                ['', 'Tonies', 'tonies.com', 'Audio content, some video', 'Each Tonie character could have an animated series companion.'],
            ]
        },
        {
            'name': 'IP Owners (Publishing, Licensing, Apps)',
            'why': 'Own valuable characters and IP but animation production is not their core competency. Need it produced externally to unlock licensing and merchandise revenue.',
            'companies': [
                ['', 'Scholastic', 'scholastic.com', 'Minimal YouTube strategy', 'Dog Man sells 10M+ copies/year. Clifford, Captain Underpants — animation multiplies licensing.'],
                ['', 'Pop Mart', 'popmart.com', 'Very limited', 'Labubu viral on TikTok. Designer toy characters need structured animated content.'],
                ['', 'Penguin Random House', 'penguinrandomhouse.com', 'Minimal', 'Very Hungry Caterpillar, Wimpy Kid — iconic children\'s IP with global recognition.'],
                ['', 'Hachette Children\'s', 'hachette.com', 'Paddington films exist', 'Paddington needs YouTube-scale animated content for ongoing engagement.'],
                ['', 'Toca Boca', 'tocaboca.com', 'User-generated on YouTube', 'Kids already make Toca Life content — official production would own the narrative.'],
                ['', 'Kakao Entertainment', 'kakaoent.com', 'Short animations, limited', 'Kakao Friends — massive IP in Asia. Global expansion needs quality animation.'],
                ['', 'Egmont Publishing', 'egmont.com', 'Some Bamse animation', 'Bamse is Scandinavia\'s #1 kids character. Needs international animated content.'],
            ]
        },
    ]

    rows = []
    rows.append(HEADER)

    # Track where each segment's companies start/end for grouping
    groups = []  # (start_row_index, end_row_index) — 0-based sheet rows

    current_row = 1  # row 0 = header

    for seg in segments:
        # Segment header row
        rows.append([seg['name'], '', '', '', seg['why']])
        seg_header_row = current_row
        current_row += 1

        # Company rows
        group_start = current_row
        for company in seg['companies']:
            rows.append(company)
            current_row += 1
        group_end = current_row

        groups.append((group_start, group_end))

    # ---- Write data ----
    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{NEW_TAB_TITLE}'!A1",
        valueInputOption='RAW',
        body={'values': rows}
    ).execute()
    print(f"Written {len(rows)} rows")

    # ---- Formatting + row grouping ----
    format_requests = []

    # Freeze header row
    format_requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': new_tab_id,
                'gridProperties': {'frozenRowCount': 1}
            },
            'fields': 'gridProperties.frozenRowCount'
        }
    })

    # Header row styling
    format_requests.append({
        'repeatCell': {
            'range': {'sheetId': new_tab_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 5},
            'cell': {
                'userEnteredFormat': {
                    'backgroundColor': {'red': 0.15, 'green': 0.15, 'blue': 0.15},
                    'textFormat': {'bold': True, 'fontSize': 11, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                }
            },
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }
    })

    # Segment header row styling (bold, colored background)
    seg_row = 1  # start after header
    for seg in segments:
        format_requests.append({
            'repeatCell': {
                'range': {'sheetId': new_tab_id, 'startRowIndex': seg_row, 'endRowIndex': seg_row + 1, 'startColumnIndex': 0, 'endColumnIndex': 5},
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.3},
                        'textFormat': {'bold': True, 'fontSize': 11, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat)'
            }
        })
        seg_row += 1 + len(seg['companies'])

    # Row grouping (collapsible) for company rows under each segment
    for (start, end) in groups:
        format_requests.append({
            'addDimensionGroup': {
                'range': {
                    'sheetId': new_tab_id,
                    'dimension': 'ROWS',
                    'startIndex': start,
                    'endIndex': end,
                }
            }
        })

    # Column widths
    col_widths = [320, 180, 220, 280, 450]
    for i, width in enumerate(col_widths):
        format_requests.append({
            'updateDimensionProperties': {
                'range': {'sheetId': new_tab_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
                'properties': {'pixelSize': width},
                'fields': 'pixelSize'
            }
        })

    # Wrap text in all cells
    format_requests.append({
        'repeatCell': {
            'range': {'sheetId': new_tab_id, 'startRowIndex': 0, 'endRowIndex': len(rows), 'startColumnIndex': 0, 'endColumnIndex': 5},
            'cell': {
                'userEnteredFormat': {
                    'wrapStrategy': 'WRAP',
                    'verticalAlignment': 'TOP',
                }
            },
            'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
        }
    })

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': format_requests}
    ).execute()
    print("Formatting + row grouping applied")

    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == '__main__':
    update_sheet()
