"""Update TheSoul Group sheet v3 — rework remaining tabs."""
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDS_PATH = Path(__file__).resolve().parent.parent / 'google-credentials.json'
SHEET_ID = '1XlCV5ObWykGopw2qLmDwxO3hvekGugeBXLg9AA_TsXI'

def get_services():
    creds = service_account.Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def update():
    sheets = get_services()

    # Get all tabs
    sp = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tabs = {s['properties']['title']: s['properties']['sheetId'] for s in sp['sheets']}

    # ---- Delete Competitive Landscape ----
    delete_reqs = []
    if 'Competitive Landscape' in tabs:
        delete_reqs.append({'deleteSheet': {'sheetId': tabs['Competitive Landscape']}})
    if delete_reqs:
        sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': delete_reqs}).execute()
        print("Deleted Competitive Landscape")

    # ---- Rewrite ABM Outreach Plan ----
    abm_id = tabs.get('ABM Outreach Plan')
    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'ABM Outreach Plan'!A:H").execute()

    abm_data = [
        ['Outreach Plan'],
        [''],
        ['Phase', 'Timing', 'What We Do'],
        ['Account Selection', 'Week 1–2', 'Select 50–80 accounts from target segments. Prioritize companies with active buying signals (new hires, IP launches, competitor moves). Build contact lists: 3–5 decision-makers per account.'],
        ['Deep Research', 'Per account, before first touch', 'Audit each company: existing animation, YouTube presence, recent announcements, open roles. Identify the specific IP or product line that needs animation. Write a custom angle for each account.'],
        ['First Touch', 'Day 1', 'LinkedIn connection request to Content VP / Head of Entertainment with personalized note referencing their specific IP. Parallel email to 2–3 contacts with role-specific angles (Content VP = creative, CMO = ROI, Licensing VP = revenue).'],
        ['Value Drop', 'Day 7', 'Send a 1-page custom brief: "How [Company] could use animation for [their specific IP]." Show Crayola numbers. Reference their competitor who already has a series.'],
        ['Social Proof', 'Day 14', 'Share relevant industry data or competitor case. Ask for 15-min call. If primary contact is silent, reach the Executive Producer or Head of Production.'],
        ['Multi-Thread', 'Day 21–30', 'Voice message on LinkedIn. Forward the custom brief to a second decision-maker. Reference upcoming trade show: "We\'ll be at Licensing Expo / Annecy — happy to meet there."'],
        ['Break-up / Event', 'Day 45', '"Last note for now" — or pivot to event-based meeting request.'],
        ['Quarterly Nurture', 'Ongoing', 'New case studies, industry insights, signal-triggered re-engagement. Not generic newsletters — specific to their segment.'],
        [''],
        ['Channels'],
        [''],
        ['Channel', 'Monthly Volume', 'Purpose'],
        ['LinkedIn (personalized)', '100–150 touches', 'Primary channel. Decision-makers in animation live on LinkedIn.'],
        ['Email sequences', '200–300 sends', 'Custom briefs, case studies, competitor intelligence.'],
        ['Trade show meetings', '15–25 per event', 'Face-to-face is critical for animation deals. 3–4 events/year.'],
        ['Custom video (Loom)', '10–20', '60-second reels showing how TheSoul would approach their specific IP.'],
        ['Direct mail (top tier)', '5–10', 'Physical storyboards or character concepts for their IP. High-touch for $5B+ accounts.'],
        [''],
        ['Entry Points'],
        [''],
        ['Offer', 'What It Is', 'Why It Works'],
        ['Pilot project', 'Produce 1 animated pilot episode or proof-of-concept for their IP', 'Low risk for buyer. Proves TheSoul\'s quality before larger commitment. Gets foot in door.'],
        ['YouTube-first series', 'Short-form animated series distributed on TheSoul\'s channels + client\'s', 'Fast delivery (weeks, not years). Measurable views/engagement. Low budget vs. broadcast.'],
        ['Localization package', 'Dub existing animated content into 10–20 languages', 'Quick win if they already have animation. Opens door to original production.'],
        ['Co-production', 'Shared investment + shared revenue on a new animated property', 'For companies that want animation but can\'t fully fund alone. TheSoul brings distribution.'],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'ABM Outreach Plan'!A1",
        valueInputOption='RAW',
        body={'values': abm_data}
    ).execute()
    print(f"ABM: {len(abm_data)} rows")

    # Format ABM
    abm_fmt = []
    # Title
    abm_fmt.append({'repeatCell': {
        'range': {'sheetId': abm_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {
            'textFormat': {'bold': True, 'fontSize': 14},
        }},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Section headers (rows with Phase/Channel/Offer headers)
    for r in [2, 14, 23]:
        abm_fmt.append({'repeatCell': {
            'range': {'sheetId': abm_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
                'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }})
    # Sub-section titles (Channels, Entry Points)
    for r in [12, 21]:
        abm_fmt.append({'repeatCell': {
            'range': {'sheetId': abm_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
            'cell': {'userEnteredFormat': {
                'textFormat': {'bold': True, 'fontSize': 12},
            }},
            'fields': 'userEnteredFormat(textFormat)'
        }})
    # Column widths
    for i, w in enumerate([180, 180, 650]):
        abm_fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': abm_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    # Wrap + freeze
    abm_fmt.append({'repeatCell': {
        'range': {'sheetId': abm_id, 'startRowIndex': 0, 'endRowIndex': len(abm_data), 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # ---- Rewrite Trackable Signals ----
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
        ['Company posts animation job openings (Producer, Head of Animation, EP) — and they\'re NOT a studio', 'Building internal team to manage external production. Commissioning is imminent.', 'Position as the production partner they\'ll need. "You build the team, we bring the studio."'],
        ['Multiple animation/content hires at the same company within weeks', 'Major production initiative is launching. Budget is allocated.', 'Move fast. Pitch capacity and speed. They\'re already behind schedule.'],
        ['RFP or production tender published', 'Active procurement. Decision in weeks.', 'Drop everything. Respond immediately with tailored pitch + reel.'],
        ['New IP or character launch announced — no animation mentioned', 'Product is coming but content strategy is missing or delayed.', '"We noticed [IP name] launches in Q3. Here\'s how animation accelerates adoption." Attach a concept mock-up.'],
        [''],
        ['STRONG INTENT', '', ''],
        ['Company registers for Annecy, Kidscreen, or MIPCOM for the first time', 'They\'re entering the animation market. Scouting studios.', 'Pre-event outreach 8 weeks before. Book a meeting. Send TheSoul\'s reel tailored to their segment.'],
        ['Streaming deal announced (Netflix, Apple TV+, Amazon)', 'They need animation produced. The platform deal doesn\'t include a studio.', 'Pitch immediately. "Congratulations on the [platform] deal. We can deliver the production."'],
        ['Brand refresh or franchise relaunch announced', 'Legacy IP being revived. New animation is almost always part of it.', 'Reference their specific IP history. "The original [series name] ran for [X] seasons. Here\'s what a modern version looks like."'],
        ['Earnings call mentions "content strategy" or "entertainment segment" growth', 'Executive mandate from the top. VP will be tasked with finding production partners.', 'Email the VP of Content directly. "Saw [CEO name]\'s comments on content investment. Here\'s how we work with companies at your scale."'],
        ['Competitor launches an animated series for a similar product', 'Competitive pressure. Board-level conversations are happening.', '"[Competitor] just launched [series]. Their toy sales are up [X]%. Here\'s how you respond."'],
        ['Company acquires new IP (buys a book series, comic, game)', 'Animated adaptation will follow. 12–24 month window.', 'Get in early. "We\'d love to discuss bringing [IP name] to animation."'],
        [''],
        ['EARLY INDICATORS', '', ''],
        ['Company\'s YouTube channel views declining quarter-over-quarter', 'Content is stale. Internal pressure to fix it.', '"Your channel is down [X]% this quarter. Here\'s what [competitor] is doing differently — and how we can help."'],
        ['Company experiments with animated content on social (first animated shorts appear)', 'Testing the waters before committing to a full series.', '"We saw your first animated short. Great start. Here\'s how to scale that to a full series at 10x the efficiency."'],
        ['New product line announced at Toy Fair / Spielwarenmesse', 'New products need content support over the next 12–18 months.', 'Plant the seed. Reference the specific product. Follow up after launch.'],
        ['Executive posts about animation or content trends on LinkedIn', 'They\'re thinking about it. Pre-decision phase.', 'Engage with their post. Add value in comments. DM with related insight. Build relationship.'],
        ['Company raises funding or goes public', 'Fresh capital. Content and marketing budgets expand.', 'Reach out within 2 weeks of announcement. Reference their growth plans.'],
        ['Key animation vendor gets acquired, shuts down, or loses capacity', 'Their current production partner is disrupted. They need a replacement.', 'Reach out to the vendor\'s known clients. "We heard about [vendor change]. We can step in with no gap."'],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Trackable Signals'!A1",
        valueInputOption='RAW',
        body={'values': sig_data}
    ).execute()
    print(f"Signals: {len(sig_data)} rows")

    # Format signals
    sig_fmt = []
    # Title
    sig_fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True, 'fontSize': 14}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Subtitle
    sig_fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 1, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'textFormat': {'italic': True, 'fontSize': 10, 'foregroundColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Column header row
    sig_fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 3, 'endRowIndex': 4, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
            'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
    }})
    # Tier headers (HIGH INTENT, STRONG INTENT, EARLY INDICATORS)
    for r in [5, 12, 20]:
        sig_fmt.append({'mergeCells': {
            'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
            'mergeType': 'MERGE_ALL'
        }})
        sig_fmt.append({'repeatCell': {
            'range': {'sheetId': sig_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 1.0, 'green': 0.95, 'blue': 0.8},
                'textFormat': {'bold': True, 'fontSize': 11, 'foregroundColor': {'red': 0.15, 'green': 0.15, 'blue': 0.15}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }})
    # Column widths
    for i, w in enumerate([350, 300, 400]):
        sig_fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': sig_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    # Wrap
    sig_fmt.append({'repeatCell': {
        'range': {'sheetId': sig_id, 'startRowIndex': 0, 'endRowIndex': len(sig_data), 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # ---- Rewrite Event Calendar ----
    evt_id = tabs.get('Event Calendar 2026')
    sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Event Calendar 2026'!A:H").execute()

    evt_data = [
        ['Upcoming Industry Events'],
        ['Key events where animation buyers meet production studios.'],
        [''],
        ['When', 'Event', 'Where', 'Notes'],
        ['May 19–21', 'Licensing Expo', 'Las Vegas', 'Licensing industry\'s main event. 16K attendees. IP-to-toy pipeline. Meet VP Licensing face-to-face. Start outreach NOW — 8 weeks out.'],
        ['Jun 15–20', 'Annecy / MIFA', 'Annecy, France', 'THE #1 animation event globally. 15K attendees. Studios pitch, buyers commission. Book 20+ meetings. Pre-outreach starts April.'],
        ['Jun', 'VidCon', 'Anaheim, CA', 'Digital-first content market. Relevant for TheSoul\'s YouTube-native positioning and brand partnerships.'],
        ['Sep', 'Cartoon Forum', 'Toulouse, France', 'Invitation-based animation series pitching. ~950 attendees — all decision-makers. Highest signal-to-noise ratio of any event.'],
        ['Sep–Oct', 'Brand Licensing Europe', 'London, ExCeL', 'European IP licensing. Target EU toy and FMCG brands. Same dynamic as Licensing Expo.'],
        ['Sep–Oct', 'Toy Fair New York', 'New York, Javits', 'New product line reveals. 25K attendees. Spot toy launches without animation — pitch partnership.'],
        ['Oct', 'MIPCOM / MIPJunior', 'Cannes, France', 'Global content marketplace. MIPJunior = kids content. Where Hasbro, Mattel, Spin Master scout animation studios.'],
        ['Nov', 'CTN Animation Expo', 'Los Angeles', 'Animation networking. Relationship building. Not primary deal-making but good for pipeline.'],
        [''],
        ['Preparation Timeline'],
        [''],
        ['Weeks Before', 'Action'],
        ['8 weeks', 'Get exhibitor/attendee lists. Begin LinkedIn outreach to target attendees.'],
        ['6 weeks', 'Send personalized email: "Happy to meet at [Event] to discuss [their IP]."'],
        ['4 weeks', 'Follow up. Share a reel or custom brief relevant to their IP.'],
        ['2 weeks', 'Confirm meetings. Send calendar invites.'],
        ['At event', 'Take meetings. Note action items within 24 hours.'],
        ['1 week after', 'Follow up with promised materials. Send custom treatment if discussed.'],
    ]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Event Calendar 2026'!A1",
        valueInputOption='RAW',
        body={'values': evt_data}
    ).execute()
    print(f"Events: {len(evt_data)} rows")

    # Format events
    evt_fmt = []
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True, 'fontSize': 14}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 1, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {'textFormat': {'italic': True, 'fontSize': 10, 'foregroundColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Header rows
    for r in [3, 15]:
        evt_fmt.append({'repeatCell': {
            'range': {'sheetId': evt_id, 'startRowIndex': r, 'endRowIndex': r + 1, 'startColumnIndex': 0, 'endColumnIndex': 4},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 0.13, 'green': 0.13, 'blue': 0.13},
                'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
        }})
    # "Preparation Timeline" sub-title
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 13, 'endRowIndex': 14, 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True, 'fontSize': 12}}},
        'fields': 'userEnteredFormat(textFormat)'
    }})
    # Column widths
    for i, w in enumerate([100, 200, 160, 580]):
        evt_fmt.append({'updateDimensionProperties': {
            'range': {'sheetId': evt_id, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    # Wrap
    evt_fmt.append({'repeatCell': {
        'range': {'sheetId': evt_id, 'startRowIndex': 0, 'endRowIndex': len(evt_data), 'startColumnIndex': 0, 'endColumnIndex': 4},
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment)'
    }})

    # ---- Apply all formatting ----
    all_fmt = abm_fmt + sig_fmt + evt_fmt
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': all_fmt}
    ).execute()
    print("All formatting applied")

    print(f"\nDone! https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == '__main__':
    update()
