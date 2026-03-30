"""Update TheSoul Group sheet v2 — better readability."""
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDS_PATH = Path(__file__).resolve().parent.parent / 'google-credentials.json'
SHEET_ID = '1XlCV5ObWykGopw2qLmDwxO3hvekGugeBXLg9AA_TsXI'
TAB_TITLE = 'Target Segments & Companies'

def get_services():
    creds = service_account.Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def update_sheet():
    sheets = get_services()

    # Get tab ID
    sp = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tab_id = None
    for s in sp['sheets']:
        if s['properties']['title'] == TAB_TITLE:
            tab_id = s['properties']['sheetId']
            break

    # Clear existing content and groups
    # First remove existing groups
    try:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [
                {'deleteDimensionGroup': {
                    'range': {'sheetId': tab_id, 'dimension': 'ROWS', 'startIndex': 0, 'endIndex': 100}
                }}
            ] * 6}  # remove up to 6 groups
        ).execute()
    except:
        pass  # no groups to remove

    # Clear all
    sheets.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB_TITLE}'!A:F"
    ).execute()

    # ---- Data structure ----
    # Segment rows: merged A-E, readable text, light colored bg
    # Company rows: indented under segment, grouped

    segments = [
        {
            'name': 'Toy Companies Without Animated Series',
            'why': 'Series sell toys. Competitors with content outsell those without.',
            'companies': [
                ['ZURU', 'zuru.com', 'None', '$2B+ revenue. Fastest-growing toy co. Zero animated series.'],
                ['Jazwares (Squishmallows)', 'jazwares.com', 'None', '485M toys sold. Cultural phenomenon. No animation.'],
                ['MGA Entertainment', 'mgae.com', 'Late start, inconsistent', 'L.O.L. Surprise!, Bratz, Rainbow High — multiple IPs need animation.'],
                ['Moose Toys', 'moosetoys.com', 'Minimal', 'Shopkins, Magic Mixies — hit toy lines with no series.'],
                ['Funko', 'funko.com', 'None (original)', '8M+ collector community. Creating original IP.'],
                ['Playmobil', 'playmobil.com', 'Movie flopped (2019)', 'LEGO has Ninjago/City/Friends. Playmobil has nothing.'],
                ['Basic Fun!', 'basicfun.com', 'Stalled reboot', 'Owns Care Bears, Tonka, K\'NEX, Lite-Brite.'],
                ['VTech', 'vtech.com', 'Short clips only', 'Educational toy characters with no animated series.'],
                ['Simba Dickie Group', 'simba-dickie-group.de', 'Almost none', 'Largest EU toy co ($1B). No animation strategy.'],
                ['Epoch (Sylvanian Families)', 'epoch.jp', 'Very limited', 'Beloved character world. Underdeveloped animation.'],
                ['IMC Toys', 'imctoys.com', 'Kitoons YT (700K)', 'Cry Babies, VIP Pets — needs production scale-up.'],
                ['Giochi Preziosi', 'giochipreziosi.it', 'Expired Gormiti series', 'Gormiti was proven IP. Needs digital revival.'],
                ['Ty Inc.', 'ty.com', 'None', 'Beanie Boos — massive recognition, zero content.'],
                ['Schleich', 'schleich-s.com', 'None', 'Bayala, Eldrador — fantasy worlds built for animation.'],
                ['Melissa & Doug', 'melissaanddoug.com', 'None', 'Premium educational. Animation bridges play + digital.'],
            ]
        },
        {
            'name': 'Toy Companies Needing More Production Capacity',
            'why': 'Proven animation buyers. Need more studios for new IPs, volume, and localization.',
            'companies': [
                ['Spin Master', 'spinmaster.com', 'PAW Patrol only', 'Tech Deck, Kinetic Sand, Hatchimals = no animation.'],
                ['Hasbro', 'hasbro.com', 'Multiple studios', 'Massive pipeline. Always needs additional capacity.'],
                ['Mattel', 'mattel.com', 'Multiple studios', 'Expanding aggressively (Mattel Films). Needs more partners.'],
                ['Bandai Namco', 'bandainamco.com', 'Toei, Sunrise', 'Western expansion needs localized content.'],
                ['Takara Tomy', 'takaratomy.co.jp', 'Japanese studios', 'Beyblade, Tomica — weak Western/YouTube presence.'],
                ['Alpha Group', 'alphagroup.cn', 'In-house (China)', 'Super Wings — inconsistent outside China.'],
                ['WildBrain', 'wildbrain.com', 'In-house + partners', 'Peanuts, Teletubbies — struggles with production scale.'],
                ['Sanrio', 'sanrio.com', 'Fragmented', 'Hello Kitty, Kuromi — 50+ years IP, no unified partner.'],
            ]
        },
        {
            'name': 'Consumer Brands with Character IP',
            'why': 'Own iconic animated mascots. Produce animation ad-hoc via agencies. Need always-on production partner.',
            'companies': [
                ['Ferrero / Kinder', 'ferrero.com', 'Limited', 'Kinder Surprise = YouTube\'s #1 kids genre. Ferrero should own it.'],
                ['Haribo', 'haribo.com', 'Ads only, no series', 'Goldbears — globally recognized. Zero long-form content.'],
                ['Kellogg\'s', 'kelloggs.com', 'Sporadic spots', 'Tony the Tiger, Toucan Sam — barely used in modern formats.'],
                ['General Mills', 'generalmills.com', 'Seasonal only', 'Lucky Charms, Trix Rabbit, Count Chocula — no digital home.'],
                ['Mondelez', 'mondelezinternational.com', 'None', 'Sour Patch Kids — massive Gen-Z following, no series.'],
                ['PepsiCo (Cheetos)', 'pepsico.com', 'Spots + live-action film', 'Chester Cheetah underused. Animated is cheaper + scalable.'],
                ['McDonald\'s', 'mcdonalds.com', 'Grimace revival (viral)', 'Proved the model. Needs consistent animated pipeline.'],
                ['Bazooka Candy', 'bazooka-candy.com', 'Dormant comics', 'Bazooka Joe, Ring Pop, Push Pop — 70+ years of IP.'],
                ['Perfetti Van Melle', 'perfettivanmelle.com', 'Historical', 'Chupa Chups (Dali logo) — ripe for animated revival.'],
                ['PEZ', 'pez.com', 'None', 'Collecting is a YouTube genre. Needs official content.'],
                ['Jollibee Foods', 'jollibeefoods.com', 'Philippines TV only', 'Asia\'s most beloved mascot. Global expansion needs animation.'],
                ['Jelly Belly', 'jellybelly.com', 'None', 'BeanBoozled = YouTube challenge format in candy form.'],
            ]
        },
        {
            'name': 'Gaming Companies (Post-Arcane)',
            'why': 'Arcane proved animated content drives player engagement. Studios want it, few can produce in-house.',
            'companies': [
                ['Supercell', 'supercell.com', 'Clash-A-Rama, cinematics', 'Proven buyer. High volume. Always needs new partners.'],
                ['HoYoverse / miHoYo', 'hoyoverse.com', 'Outsourced shorts', 'New character every 6 weeks — each needs a trailer.'],
                ['Riot Games', 'riotgames.com', 'Arcane (Fortiche)', 'Fortiche has years-long waitlist. 5+ IPs need content.'],
                ['Epic Games', 'epicgames.com', 'Season trailers', 'Fortnite: constant need — seasons, crossovers, Lego Fortnite.'],
                ['Blizzard', 'blizzard.com', 'OW shorts (Blur)', 'Massive hits but production slowed. Multiple franchises.'],
                ['Ubisoft', 'ubisoft.com', 'Rabbids, Captain Laserhawk', 'Rabbids perfect for high-volume. AC needs companion content.'],
                ['Krafton', 'krafton.com', 'Trailers only', 'PUBG: 400M+ players. Almost no narrative animation.'],
                ['Roblox Corp', 'roblox.com', 'Minimal', '70M+ daily users. Brands need animated content at scale.'],
            ]
        },
        {
            'name': 'EdTech & Educational Companies',
            'why': 'Animation IS the product. Need it produced at massive scale, cost-effectively. Recurring relationships.',
            'companies': [
                ['Age of Learning (ABCmouse)', 'ageoflearning.com', 'Thousands of modules', 'One of largest edtech animation buyers. Always needs capacity.'],
                ['Duolingo', 'duolingo.com', 'Social clips, TikTok', 'Duo the owl is cultural phenomenon. Ready for animated series.'],
                ['PBS Kids', 'pbskids.org', 'Major commissioner', 'World\'s largest educational animation commissioner.'],
                ['Sesame Workshop', 'sesameworkshop.org', 'Puppetry + animation', 'Increasing animation ratio. International co-productions.'],
                ['Khan Academy', 'khanacademy.org', 'Basic', 'Kids version needs professional animation.'],
                ['Lingokids', 'lingokids.com', 'Growing', 'Scaling animation for multiple languages.'],
                ['Tonies', 'tonies.com', 'Audio, some video', 'Each character could have an animated series.'],
            ]
        },
        {
            'name': 'IP Owners (Publishing, Licensing, Apps)',
            'why': 'Own valuable characters but animation isn\'t their competency. Need external production to unlock value.',
            'companies': [
                ['Scholastic', 'scholastic.com', 'Minimal', 'Dog Man (10M+ copies/yr), Clifford, Captain Underpants.'],
                ['Pop Mart', 'popmart.com', 'Very limited', 'Labubu viral on TikTok. Designer toys need animated content.'],
                ['Penguin Random House', 'penguinrandomhouse.com', 'Minimal', 'Very Hungry Caterpillar, Wimpy Kid — iconic kids\' IP.'],
                ['Hachette Children\'s', 'hachette.com', 'Paddington films', 'Paddington needs YouTube-scale ongoing animation.'],
                ['Toca Boca', 'tocaboca.com', 'User-generated only', 'Kids make Toca content — official production owns the narrative.'],
                ['Kakao Entertainment', 'kakaoent.com', 'Limited', 'Kakao Friends — massive in Asia. Global expansion needs quality.'],
                ['Egmont Publishing', 'egmont.com', 'Some Bamse', 'Scandinavia\'s #1 kids character. Needs international animation.'],
            ]
        },
    ]

    # ---- Build rows ----
    rows = []
    # Header
    rows.append(['', 'Company', 'Website', 'Current Animation', 'Opportunity'])
    current_row = 1

    groups = []
    segment_rows = []

    for seg in segments:
        # Segment header — text spans across columns using merge later
        rows.append([f"{seg['name']}  —  {seg['why']}", '', '', '', ''])
        segment_rows.append(current_row)
        current_row += 1

        group_start = current_row
        for co in seg['companies']:
            rows.append([''] + co)
            current_row += 1
        groups.append((group_start, current_row))

    # ---- Write ----
    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB_TITLE}'!A1",
        valueInputOption='RAW',
        body={'values': rows}
    ).execute()
    print(f"Written {len(rows)} rows")

    # ---- Formatting ----
    fmt = []

    # Freeze header
    fmt.append({
        'updateSheetProperties': {
            'properties': {'sheetId': tab_id, 'gridProperties': {'frozenRowCount': 1}},
            'fields': 'gridProperties.frozenRowCount'
        }
    })

    # Header row — dark, white text
    fmt.append({
        'repeatCell': {
            'range': {'sheetId': tab_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 5},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
                'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }
    })

    # Segment header rows — merge A-E, bold, light gold bg, dark text, bigger font
    for sr in segment_rows:
        # Merge across all columns
        fmt.append({
            'mergeCells': {
                'range': {'sheetId': tab_id, 'startRowIndex': sr, 'endRowIndex': sr + 1, 'startColumnIndex': 0, 'endColumnIndex': 5},
                'mergeType': 'MERGE_ALL'
            }
        })
        # Style — light gold background, dark text, bold
        fmt.append({
            'repeatCell': {
                'range': {'sheetId': tab_id, 'startRowIndex': sr, 'endRowIndex': sr + 1, 'startColumnIndex': 0, 'endColumnIndex': 5},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': {'red': 1.0, 'green': 0.95, 'blue': 0.8},
                    'textFormat': {'bold': True, 'fontSize': 11, 'foregroundColor': {'red': 0.15, 'green': 0.15, 'blue': 0.15}},
                    'wrapStrategy': 'WRAP',
                    'verticalAlignment': 'MIDDLE',
                    'padding': {'top': 8, 'bottom': 8, 'left': 8},
                }},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment,padding)'
            }
        })
        # Row height for segment headers
        fmt.append({
            'updateDimensionProperties': {
                'range': {'sheetId': tab_id, 'dimension': 'ROWS', 'startIndex': sr, 'endIndex': sr + 1},
                'properties': {'pixelSize': 40},
                'fields': 'pixelSize'
            }
        })

    # Company rows — normal text, wrap
    fmt.append({
        'repeatCell': {
            'range': {'sheetId': tab_id, 'startRowIndex': 1, 'endRowIndex': len(rows), 'startColumnIndex': 0, 'endColumnIndex': 5},
            'cell': {'userEnteredFormat': {
                'wrapStrategy': 'WRAP',
                'verticalAlignment': 'TOP',
            }},
            'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
        }
    })

    # Column widths: A (empty/indent), B (Company), C (Website), D (Current Animation), E (Opportunity)
    widths = [30, 220, 200, 200, 420]
    for i, w in enumerate(widths):
        fmt.append({
            'updateDimensionProperties': {
                'range': {'sheetId': tab_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
                'properties': {'pixelSize': w},
                'fields': 'pixelSize'
            }
        })

    # Row grouping
    for (start, end) in groups:
        fmt.append({
            'addDimensionGroup': {
                'range': {'sheetId': tab_id, 'dimension': 'ROWS', 'startIndex': start, 'endIndex': end}
            }
        })

    # Alternate row coloring for company rows (very light grey)
    for (start, end) in groups:
        for r in range(start, end):
            if (r - start) % 2 == 1:
                fmt.append({
                    'repeatCell': {
                        'range': {'sheetId': tab_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 5},
                        'cell': {'userEnteredFormat': {
                            'backgroundColor': {'red': 0.96, 'green': 0.96, 'blue': 0.96},
                        }},
                        'fields': 'userEnteredFormat(backgroundColor)'
                    }
                })

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': fmt}
    ).execute()
    print("Formatting applied")

    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == '__main__':
    update_sheet()
