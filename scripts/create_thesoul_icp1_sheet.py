"""Create TheSoul Group ICP1 Target Companies Google Sheet.

Client-facing document for pitching outreach services to TheSoul Group.
Creates a multi-tab spreadsheet with subsegments, roles, ABM plan, and signals.
"""
import json
import os
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDS_PATH = Path(__file__).resolve().parent.parent / 'google-credentials.json'
SHARED_DRIVE_ID = '0AEvTjlJFlWnZUk9PVA'
SHARE_WITH = ['pn@getsally.io', 'rk@getsally.io']

def get_credentials():
    creds = service_account.Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    return creds

def create_sheet():
    creds = get_credentials()
    drive_svc = build('drive', 'v3', credentials=creds)

    # ---- Create sheet via Drive API (on shared drive) ----
    file_metadata = {
        'name': 'TheSoul Group — ICP #1 Animation Production Targets (March 2026)',
        'mimeType': 'application/vnd.google-apps.spreadsheet',
        'parents': [SHARED_DRIVE_ID],
    }
    file = drive_svc.files().create(
        body=file_metadata,
        fields='id,webViewLink',
        supportsAllDrives=True
    ).execute()
    sheet_id = file.get('id')
    print(f"Created spreadsheet: {sheet_id}")

    # Now build sheets service to populate
    sheets_svc = build('sheets', 'v4', credentials=creds)

    # ---- Add tabs ----
    tab_names = [
        'Executive Summary',
        '1A. Toys — No Animation',
        '1B. Toys — Need More Capacity',
        '1C. Consumer Brands with Characters',
        '1D. Gaming (Post-Arcane)',
        '1E. EdTech & Educational',
        '1F. IP Owners (Publishing, Licensing)',
        'Target Roles & Decision Unit',
        'ABM Outreach Plan',
        'Trackable Signals',
        'Event Calendar 2026',
        'Competitive Landscape',
    ]

    # Rename Sheet1 and add the rest
    existing = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    first_sheet_id = existing['sheets'][0]['properties']['sheetId']

    tab_requests = [
        {'updateSheetProperties': {
            'properties': {'sheetId': first_sheet_id, 'title': tab_names[0]},
            'fields': 'title'
        }}
    ]
    for i, name in enumerate(tab_names[1:], 1):
        tab_requests.append({'addSheet': {'properties': {'title': name, 'index': i}}})

    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': tab_requests}
    ).execute()
    print(f"Created {len(tab_names)} tabs")

    # ---- Share with team ----
    for email in SHARE_WITH:
        try:
            drive_svc.permissions().create(
                fileId=sheet_id,
                supportsAllDrives=True,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email}
            ).execute()
            print(f"Shared with {email}")
        except Exception as e:
            print(f"Warning: Could not share with {email}: {e}")

    # ---- Populate data ----
    updates = []

    # --- TAB: Executive Summary ---
    updates.append({
        'range': 'Executive Summary!A1',
        'values': [
            ['TheSoul Group — ICP #1: Companies Needing Animation Production'],
            [''],
            ['Prepared by', 'Sally (getsally.io)', '', 'Date', 'March 2026'],
            [''],
            ['OVERVIEW'],
            ['TheSoul Group has the world\'s largest digital content production infrastructure — 2,000+ videos/month,'],
            ['animation studios, dubbing into 20+ languages, and a distribution network of 2.5B followers.'],
            [''],
            ['ICP #1 targets companies that need animation produced — for series, shorts, trailers, ads, and localization.'],
            ['These companies own valuable IP but animation production is NOT their core competency.'],
            [''],
            ['KEY METRICS'],
            ['Metric', 'Value'],
            ['Total addressable companies', '150–200'],
            ['Year 1 target list', '50–80 companies'],
            ['Contacts per company', '3–5 decision-makers'],
            ['Total outreach contacts', '200–400'],
            ['Average deal size (digital-first)', '$200K–$500K'],
            ['Average deal size (full series)', '$2M–$10M'],
            ['Sales cycle (digital-first)', '2–4 months'],
            ['Sales cycle (full series)', '6–18 months'],
            ['Year 1 pipeline target', '$5M–$15M'],
            [''],
            ['SUBSEGMENTS'],
            ['#', 'Segment', 'Companies', 'Why They Buy Animation'],
            ['1A', 'Toy companies WITHOUT animated series', '12+', 'Series sells toys. Competitors with animation outsell those without.'],
            ['1B', 'Toy companies needing MORE production capacity', '7+', 'Already buying animation — need additional studios for new IPs and volume.'],
            ['1C', 'Consumer brands with character IP', '12+', 'Own animated mascots but produce ad-hoc through agencies. Need always-on content.'],
            ['1D', 'Gaming companies (post-Arcane)', '8+', 'Arcane proved animated companion content drives player engagement. Every studio wants it.'],
            ['1E', 'EdTech / educational companies', '6+', 'Animation is core to the product. Need it produced at scale, affordably.'],
            ['1F', 'IP owners (publishing, licensing, apps)', '7+', 'Own characters/IP, need animation to unlock licensing and merchandise revenue.'],
            [''],
            ['PROOF POINT'],
            ['Crayola partnership: 600M views, 652K subscribers in 7 months — TheSoul took over content production and distribution.'],
            [''],
            ['See each tab for detailed company lists, target roles, outreach plan, and trackable signals.'],
        ]
    })

    # --- TAB: 1A. Toys — No Animation ---
    updates.append({
        'range': "'1A. Toys — No Animation'!A1",
        'values': [
            ['SEGMENT 1A: Toy Companies Without Animated Series'],
            ['These companies have significant toy revenue but NO animated content. Animation drives toy sales — they\'re leaving money on the table.'],
            [''],
            ['Company', 'Est. Revenue', 'HQ', 'Key IP / Brands', 'Current Animation', 'Production Gap / Opportunity'],
            ['ZURU', '$2B+', 'New Zealand', 'Mini Brands, X-Shot, Bunch O Balloons, Rainbocorns', 'None', 'Fastest-growing toy company globally. Zero animated series despite massive toy revenue. Greenfield opportunity.'],
            ['Jazwares', '$1B+', 'USA', 'Squishmallows, Roblox toys, Pokémon toys', 'None (for Squishmallows)', 'Squishmallows is a cultural phenomenon — 485M toys sold — with NO original animation. Series is inevitable.'],
            ['MGA Entertainment', '$4B', 'USA', 'L.O.L. Surprise!, Bratz, Rainbow High, Little Tikes', 'Launched late, inconsistent quality', 'Multiple IPs need animation simultaneously. Current production can\'t keep up with brand portfolio.'],
            ['Moose Toys', '$800M', 'Australia', 'Shopkins, Magic Mixies, Heroes of Goo Jit Zu, Akedo', 'Minimal YouTube content', 'Growing IP portfolio, no proper animated series. Australian HQ = timezone gap with current studios.'],
            ['Funko', '$1.1B', 'USA', 'Funko Pop!, Loungefly', 'None (original)', '8M+ collector community. Started original IP (Funko Fusion). Animation would differentiate from pure licensing model.'],
            ['Playmobil (Brandstatter)', '$800M', 'Germany', 'Playmobil universe', 'Movie flopped (2019), minimal series', 'LEGO has Ninjago, City, Friends series. Playmobil has almost nothing. Needs digital-first animated reboot.'],
            ['Basic Fun!', '$500M+', 'USA', 'Care Bears, Tonka, K\'NEX, Lite-Brite', 'Care Bears reboot stalled', 'Acquired classic IPs with massive nostalgia value. No investment in new animated content.'],
            ['VTech', '~$270M', 'Hong Kong', 'Go! Go! Smart Wheels, KidiZoom', 'Very limited clips', 'Educational toys for toddlers with characters that have zero animated series. Natural fit for educational animation.'],
            ['Simba Dickie Group', '$1B EUR', 'Germany', 'Simba, Dickie Toys, Majorette, Smoby', 'Almost none', 'One of Europe\'s largest toy companies. Minimal animation strategy. Needs localized EU content.'],
            ['Epoch Co.', '$550M', 'Japan', 'Sylvanian Families / Calico Critters, Aquabeads', 'Very limited', 'Beloved character world with decades of IP. Severely underdeveloped animation despite global fanbase.'],
            ['IMC Toys', '$500M', 'Spain', 'Cry Babies, Bloopies, VIP Pets', 'Runs Kitoons YouTube (700K subs)', 'Already invested in YouTube animation — needs professional production upgrade and scale.'],
            ['Giochi Preziosi', '$700M', 'Italy', 'Gormiti, Cicciobello, Trashies', 'Gormiti had animated history', 'Gormiti series expired. Needs digital-era animated revival for this proven IP.'],
            ['Ty Inc.', '$600M', 'USA', 'Beanie Boos, Beanie Babies, Squish-a-Boos', 'None', 'Revival of collector culture. Zero content strategy despite massive brand recognition.'],
            ['Schleich', '$600M', 'Germany', 'Schleich figurines, Bayala, Eldrador Creatures', 'None', 'Rich fantasy worlds (Bayala, Eldrador) purpose-built for animated series. No production partner.'],
            ['Melissa & Doug', '$500M', 'USA', 'Melissa & Doug educational toys', 'None', 'Premium educational brand. Animation could bridge screen-free play philosophy with digital discovery.'],
        ]
    })

    # --- TAB: 1B. Toys — Need More Capacity ---
    updates.append({
        'range': "'1B. Toys — Need More Capacity'!A1",
        'values': [
            ['SEGMENT 1B: Toy Companies That Already Buy Animation — Need More Production Capacity'],
            ['These companies are proven animation buyers. They need additional studios for volume, new IPs, and digital-first content.'],
            [''],
            ['Company', 'Est. Revenue', 'HQ', 'Key IP', 'Current Animation Partner(s)', 'Expansion Need'],
            ['Spin Master', '$2B CAD', 'Canada', 'PAW Patrol, Bakugan, Hatchimals, Tech Deck, Kinetic Sand', 'Guru Studio (PAW Patrol)', 'Only PAW Patrol has animation. Tech Deck, Kinetic Sand, Hatchimals = zero. Need partner for secondary IPs.'],
            ['Hasbro', '$5.1B', 'USA', 'Transformers, MLP, Peppa Pig, Power Rangers, D&D', 'Multiple (eOne, Allspark, Boulder Media)', 'Massive pipeline. Always needs additional production capacity for new launches and streaming content.'],
            ['Mattel', '$5.4B', 'USA', 'Barbie, Hot Wheels, Monster High, Fisher-Price, UNO', 'Multiple studios', 'Aggressively expanding into content (Mattel Films). Needs partners beyond current vendor list.'],
            ['Bandai Namco', '$7B', 'Japan', 'Dragon Ball, Gundam, Tamagotchi, PAC-MAN', 'Toei (Dragon Ball), Sunrise (Gundam)', 'Western market expansion needs localized animated content and new digital-first formats.'],
            ['Takara Tomy', '$1.5B', 'Japan', 'Beyblade, Tomica, Plarail, Transformers (co-owner)', 'Various Japanese studios', 'Weak Western YouTube/digital presence despite massive kid appeal. Need production partner for global content.'],
            ['Alpha Group', '$800M', 'China', 'Super Wings, Balala the Fairies, Blazing Teens', 'In-house + Chinese studios', 'Global distribution inconsistent outside China. Needs quality partner for international versions.'],
            ['WildBrain', '$500M', 'Canada', 'Peanuts/Snoopy, Teletubbies, Strawberry Shortcake', 'In-house + partners', 'Content company that struggles with production scale and monetization. Partnership/overflow model.'],
            ['Sanrio', '$800M', 'Japan', 'Hello Kitty, Kuromi, My Melody, Cinnamoroll', 'Various', '50+ years of IP. Fragmented digital content strategy. Needs unified animation production partner.'],
        ]
    })

    # --- TAB: 1C. Consumer Brands ---
    updates.append({
        'range': "'1C. Consumer Brands with Characters'!A1",
        'values': [
            ['SEGMENT 1C: Consumer Brands with Character IP'],
            ['These brands own iconic animated mascots/characters but produce animation ad-hoc through agencies.'],
            ['A dedicated production partner offering always-on animated content at scale is a new model most haven\'t adopted.'],
            [''],
            ['Company', 'Est. Revenue', 'HQ', 'Characters / IP', 'Current Animation Usage', 'Production Opportunity'],
            ['Ferrero / Kinder', '$17B', 'Italy', 'Kinderino, Kinder Surprise collectibles, Natoons', 'Limited. Kinder unboxing dominates YouTube — Ferrero doesn\'t own it', 'Kinder Surprise is YouTube\'s #1 kids unboxing genre. Ferrero should own the animated content ecosystem.'],
            ['Haribo', '$4B', 'Germany', 'Goldbears, Starmix characters', 'Iconic Goldbears animated ads, no long-form', 'Globally recognized animated characters. Zero series or YouTube content. Animated Goldbears series is obvious.'],
            ['Kellogg\'s / Kellanova', '$13B+', 'USA', 'Tony the Tiger, Toucan Sam, Snap/Crackle/Pop', 'Legacy mascots used in sporadic spots', 'Iconic characters barely used in modern formats. Social/streaming animated shorts would revive them.'],
            ['General Mills', '$20B', 'USA', 'Lucky (Lucky Charms), Trix Rabbit, Count Chocula', 'Minimal — seasonal spots only', 'Beloved characters with no digital home. Monster Cereal line is cult brand begging for animated series.'],
            ['Mondelez', '$36B', 'USA', 'Sour Patch Kids, Cadbury Freddo', 'Brand personality exists, no animation', 'Sour Patch Kids has massive Gen-Z following and distinct character — no animated series.'],
            ['PepsiCo', '$91B', 'USA', 'Chester Cheetah (Cheetos)', 'Animated spots, Cheetos live-action movie (2023)', 'Chester Cheetah is underused animated IP. Animated shorts are cheaper and more scalable than live-action.'],
            ['McDonald\'s', '$25B', 'USA', 'Grimace, Hamburglar, Happy Meal characters', 'Grimace Birthday Meal went mega-viral (2023)', 'Grimace revival proved the model. Needs consistent animated content pipeline for characters + Happy Meal tie-ins.'],
            ['Bazooka Candy', '$700M', 'USA', 'Bazooka Joe, Ring Pop, Push Pop, Baby Bottle Pop', 'Dormant Bazooka Joe comic strip', 'Bazooka Joe has 70+ years of recognition. Ring Pop/Push Pop = interactive candy suited for animated content.'],
            ['Perfetti Van Melle', '$3B', 'Italy/Netherlands', 'Chupa Chups, Mentos, Airheads', 'Chupa Chups had licensed animation historically', 'Chupa Chups (Dali-designed logo) has pop-art heritage. Ripe for animated brand content revival.'],
            ['PEZ', '$250M', 'Austria', 'PEZ dispensers, collector culture', 'None', 'PEZ unboxing/collecting is already a YouTube genre. Needs official animated content partner.'],
            ['Jollibee Foods', '$6B', 'Philippines', 'Jollibee mascot', 'TV ads (Philippines), limited global', 'Most beloved fast-food mascot in Asia. Global expansion (US, EU, ME) needs animated content for new markets.'],
            ['Jelly Belly', '$500M', 'USA', 'BeanBoozled, Jelly Belly brand', 'None', 'BeanBoozled IS a YouTube challenge format in candy form. Official animated content is natural extension.'],
        ]
    })

    # --- TAB: 1D. Gaming ---
    updates.append({
        'range': "'1D. Gaming (Post-Arcane)'!A1",
        'values': [
            ['SEGMENT 1D: Gaming Companies — The Post-Arcane Opportunity'],
            ['Arcane (Riot/Fortiche) proved animated companion series drive player engagement and new audience acquisition.'],
            ['Every major game company now wants animated content — but few have in-house production capability.'],
            [''],
            ['Company', 'Est. Revenue', 'HQ', 'Key IP', 'Current Animation', 'Production Gap'],
            ['Supercell', '$1.8B', 'Finland', 'Clash of Clans, Clash Royale, Brawl Stars, Squad Busters', 'Clash-A-Rama series (YouTube), game cinematics', 'Proven animation buyer, high volume. Always needs new production partners for launches.'],
            ['HoYoverse / miHoYo', '$4B+', 'China', 'Genshin Impact, Honkai: Star Rail, Zenless Zone Zero', 'Animated shorts, trailers (outsourced)', 'New character every 6 weeks — each needs animated trailer. Insatiable content appetite.'],
            ['Riot Games', '$2B+', 'USA', 'League of Legends, Valorant, TFT, LoR, 2XKO', 'Arcane (Fortiche), music videos', 'Fortiche is capacity-constrained (years-long waitlist). 5+ IPs that need animated content.'],
            ['Epic Games', '$5.6B', 'USA', 'Fortnite, Rocket League, Fall Guys', 'Season trailers, crossover reveal videos', 'Constant need — new seasons, crossover events, Lego Fortnite, Fortnite Festival each need animated content.'],
            ['Blizzard (ABK/Microsoft)', '$8B (ABK)', 'USA', 'Overwatch, Diablo, WoW, StarCraft', 'Overwatch animated shorts (outsourced to Blur Studio)', 'OW shorts were massive hits but production slowed. Multiple franchises need consistent output.'],
            ['Ubisoft', '$1.7B EUR', 'France', 'Rabbids, Assassin\'s Creed, Just Dance', 'Rabbids Invasion (TV), Captain Laserhawk (Netflix)', 'Rabbids are perfect for high-volume animated production. AC and Just Dance need companion content.'],
            ['Krafton', '$1.5B', 'South Korea', 'PUBG / Battlegrounds', 'Minimal — trailers only', 'Huge game (400M+ players), almost no narrative animated content. Launched PUBG Universe but lacks capacity.'],
            ['Roblox Corp', '$2.7B', 'USA', 'Roblox platform', 'Minimal', '70M+ daily users. Rising quality bar. Brands inside Roblox need animated intros and cinematics at scale.'],
        ]
    })

    # --- TAB: 1E. EdTech ---
    updates.append({
        'range': "'1E. EdTech & Educational'!A1",
        'values': [
            ['SEGMENT 1E: Educational & EdTech Companies'],
            ['Animation is core to the educational product. These companies need it produced at massive scale, cost-effectively.'],
            ['High-volume, recurring production relationships — ideal for TheSoul\'s factory model.'],
            [''],
            ['Company', 'Est. Revenue', 'HQ', 'Key Products / IP', 'Current Animation', 'Production Gap'],
            ['Age of Learning (ABCmouse)', '$500M+', 'USA', 'ABCmouse, Adventure Academy', 'Thousands of animated learning modules', 'One of the largest animation buyers in edtech. Always needs additional capacity.'],
            ['Duolingo', '$530M', 'USA', 'Duo the owl, Duolingo app characters', 'Short social animations, TikTok', 'Duo is a cultural phenomenon. Character is ready for a proper animated series.'],
            ['PBS Kids', '$500M (PBS total)', 'USA', 'Daniel Tiger, Wild Kratts, Odd Squad, Alma\'s Way', 'Major commissioner — outsources all production', 'One of the world\'s largest commissioners of educational animation. Always developing new series.'],
            ['Sesame Workshop', '$150M', 'USA', 'Sesame Street, Mecha Builders', 'Mix of puppetry and animation', 'Increasing animation ratio in content. International co-productions need partners globally.'],
            ['Khan Academy', '$80M', 'USA', 'Khan Academy, Khan Academy Kids', 'Moving toward polished content', 'Kids version especially needs professional animation for engagement.'],
            ['Lingokids', '$30M+', 'Spain', 'Lingokids characters, language learning', 'Animated characters and episodes', 'Growing fast, needs to scale animation production for multiple languages simultaneously.'],
            ['Tonies (Boxine)', '$400M EUR', 'Germany', 'Toniebox, Tonie audio characters', 'Audio content, some video', 'Each Tonie character could have an animated series companion. Audio→video expansion is natural.'],
        ]
    })

    # --- TAB: 1F. IP Owners ---
    updates.append({
        'range': "'1F. IP Owners (Publishing, Licensing)'!A1",
        'values': [
            ['SEGMENT 1F: IP Owners Needing Animation (Publishing, Licensing, Apps)'],
            ['These companies own valuable characters and IP. They need animation produced to unlock licensing, merchandise, and digital revenue.'],
            [''],
            ['Company', 'Est. Revenue', 'HQ', 'Key IP', 'Current Animation', 'Production Opportunity'],
            ['Scholastic', '$1.8B', 'USA', 'Dog Man, Clifford, Captain Underpants, Goosebumps, Magic School Bus', 'Minimal YouTube strategy', 'Massive kids\' IP portfolio. Dog Man sells 10M+ copies/year. Animation would multiply licensing revenue.'],
            ['Pop Mart', '$1.3B', 'China', 'Labubu, Molly, Dimoo, Skullpanda, The Monsters', 'Very limited', 'Exploding global brand (Labubu viral on TikTok). Designer toy characters need structured animated content.'],
            ['Penguin Random House', '$4.3B', 'USA/Germany', 'Very Hungry Caterpillar, Diary of a Wimpy Kid, Spot the Dog', 'Minimal', 'Iconic children\'s book characters with global recognition. Animation unlocks merchandising and streaming.'],
            ['Hachette Children\'s', '$3B (group)', 'France/UK', 'Paddington Bear, Asterix, Little Prince', 'Some (Paddington films exist)', 'Paddington is a global phenomenon post-movies. Needs YouTube-scale animated content for ongoing engagement.'],
            ['Toca Boca (Spin Master)', '$100M+', 'Sweden', 'Toca Life World characters', 'User-generated on YouTube', 'Kids already make Toca content organically — official production would own the narrative at quality.'],
            ['Kakao Entertainment', '$1B+', 'South Korea', 'Kakao Friends (Ryan, Apeach, Muzi)', 'Short animations, limited series', 'Massive IP in Asia. Global expansion needs high-quality animated content for Western audiences.'],
            ['Egmont Publishing', '$2B (group)', 'Denmark', 'Bamse (Scandinavia\'s #1 kids character), Disney Magazine IP', 'Some Bamse animation exists', 'Bamse is to Scandinavia what Mickey Mouse is to the US. Needs international animated content.'],
        ]
    })

    # --- TAB: Target Roles ---
    updates.append({
        'range': "'Target Roles & Decision Unit'!A1",
        'values': [
            ['TARGET ROLES — WHO COMMISSIONS ANIMATION PRODUCTION'],
            [''],
            ['ROLE', 'PRIORITY', 'WHY TARGET', 'WHAT THEY CARE ABOUT', 'SIGNAL THEY\'RE ACTIVE'],
            [''],
            ['PRIMARY TARGETS — Run the studio selection process'],
            ['VP / Director of Content Development', 'Primary', 'Owns content strategy, writes the brief, runs studio search', 'Creative quality, production reliability, on-time delivery, cultural fit', 'New hire at target company = new content strategy incoming'],
            ['VP / Director of Brand Entertainment', 'Primary', 'Drives animation commissioning for brand IP', 'Brand vision execution, franchise value growth', 'LinkedIn posts about Annecy, Kidscreen, MIPCOM attendance'],
            ['Head of Animation / Executive Producer', 'Primary', 'Evaluates technical capability, reviews reels, visits studios', 'Animation quality, pipeline tools, team depth, scalability', 'Job posting for this role at a NON-studio company = they\'re commissioning'],
            ['SVP / EVP of Entertainment', 'Primary', 'Final budget approval at large toy/media companies', 'ROI — will animation drive toy sales, licensing revenue, streaming deals', 'Earnings call mentions "content investment" or "entertainment segment"'],
            [''],
            ['SECONDARY TARGETS — Influence or block decisions'],
            ['CMO / VP Brand Marketing', 'Secondary', 'Budget authority at consumer brands. Brand guardian — can veto', 'Brand consistency, audience alignment, marketing ROI', 'New CMO = fresh marketing strategy, often includes content'],
            ['VP of Licensing & Partnerships', 'Secondary', 'Content drives licensing revenue. Signs partnership deals', 'IP ownership terms, territory rights, merchandising splits', 'New licensing deals announced = content needed to support'],
            ['VP of eCommerce / DTC', 'Secondary', 'Animation drives product discovery and direct sales', 'Conversion metrics, content-to-purchase attribution', 'DTC strategy shift = content investment follows'],
            ['Creative Director', 'Secondary', 'Validates creative quality and style match', 'Showreel quality, style versatility, brand understanding', 'New Creative Director = fresh creative direction'],
            [''],
            ['ECONOMIC BUYERS — Sign the check'],
            ['CEO / President', 'Approver', 'Final sign-off at companies under $500M revenue', 'Total investment vs. expected franchise revenue uplift', 'All deals at smaller companies'],
            ['Division President / EVP', 'Approver', 'Signs off at Hasbro/Mattel/Bandai scale', 'Division P&L impact', 'Deals over $1M at large companies'],
            [''],
            ['DECISION FLOW'],
            ['Step', 'Who', 'Action'],
            ['1', 'Brand / Marketing', 'Identifies need for animated content'],
            ['2', 'Content VP', 'Writes brief + budget request'],
            ['3', 'CEO / Division EVP', 'Approves budget allocation'],
            ['4', 'Content VP + EP', 'Run studio search (RFP or direct outreach)'],
            ['5', 'Studios', 'Pitch: creative + technical + budget'],
            ['6', 'Brand Management', 'Reviews creative direction (VETO gate)'],
            ['7', 'Technical team', 'Studio evaluation — pipeline review, capability check'],
            ['8', 'Business Affairs / Legal', 'Negotiates deal terms (IP, territory, payments)'],
            ['9', 'CEO + Brand VP + Content VP', 'Final sign-off'],
        ]
    })

    # --- TAB: ABM Outreach Plan ---
    updates.append({
        'range': "'ABM Outreach Plan'!A1",
        'values': [
            ['ABM OUTREACH PLAN — ANIMATION PRODUCTION MARKET'],
            ['Narrow market (150–200 companies). Every touchpoint must be personalized, researched, multi-channel.'],
            [''],
            ['OUTREACH CADENCE PER ACCOUNT'],
            [''],
            ['Timing', 'Channel', 'Action', 'Content'],
            ['Day 0', 'Research', 'Signal detected — begin account research', '30 min: current animation, competitors, gaps, recent news, 3–5 decision-makers identified'],
            ['Day 1', 'LinkedIn', 'Connection request to VP/Director of Content', 'Personalized note referencing specific signal (new hire, IP launch, competitor series, etc.)'],
            ['Day 1', 'Email', 'First email to 2–3 contacts (different angles per role)', 'Role-specific: Content VP gets creative angle, CMO gets ROI angle, Licensing VP gets revenue angle'],
            ['Day 3', 'LinkedIn', 'Engage with their content', 'Like/comment on recent posts. Build visibility before the pitch.'],
            ['Day 7', 'Email', 'Value drop — custom 1-page brief', '"How [Company] could leverage animation for [specific IP]." Include Crayola case study (600M views in 7 months).'],
            ['Day 14', 'LinkedIn', 'Share relevant industry insight', 'Trade show recap, competitor analysis, market data. Soft ask for 15-min call.'],
            ['Day 21', 'Email + LinkedIn', 'Multi-thread if primary hasn\'t responded', 'Reach the EP/Head of Production. Forward brief to second contact with role-specific framing.'],
            ['Day 30', 'LinkedIn', 'Voice message to champion', 'Personal, human touch. Reference specific IP or product by name.'],
            ['Day 45', 'Email', 'Break-up OR event trigger', '"Last note for now" — OR invite to upcoming trade show meeting (Annecy, MIPCOM, Kidscreen).'],
            ['Quarterly', 'Email', 'Nurture', 'Industry insights, new case studies, re-engage on any new signal.'],
            [''],
            ['DEAL STRUCTURES TO PITCH'],
            [''],
            ['Model', 'Description', 'Best For', 'Typical Sales Cycle', 'Price Range'],
            ['YouTube-first animated series', 'Lower budget, digital-native, fast delivery. TheSoul distributes via own channels.', 'Brands wanting fast, measurable results. Best entry point.', '2–4 months', '$200K–$500K'],
            ['Development deal', 'Fund pilot episode + series bible. Option for full series.', 'Risk-averse first-timers. Proves quality before commitment.', '3–6 months', '$50K–$150K (pilot)'],
            ['Work-for-hire series', 'TheSoul produces, client owns everything.', 'Toy companies wanting full IP control.', '6–12 months', '$2M–$10M'],
            ['Co-production', 'Shared IP, shared financing, shared revenue.', 'Mid-tier companies who can\'t fully fund alone.', '9–18 months', 'Varies'],
            ['Service + backend', 'Lower upfront fee, revenue share on licensing/merch.', 'Companies open to partnership model.', '9–18 months', 'Varies'],
            [''],
            ['RECOMMENDATION: Lead with YouTube-first or Development deal. Shortest cycle, lowest risk, fastest proof of value. Upsell to full series.'],
            [''],
            ['MULTI-CHANNEL MIX'],
            [''],
            ['Channel', 'Volume / Month', 'Purpose'],
            ['LinkedIn (connection + InMail)', '100–150 personalized touches', 'Primary relationship channel. Decision-makers in this market live on LinkedIn.'],
            ['Email (cold + warm)', '200–300 sends', 'Sequences with custom briefs, case studies, industry insights.'],
            ['Trade show meetings', '15–25 per event (3–4 events/year)', 'Face-to-face is critical in animation deals. Annecy, Kidscreen, MIPCOM, Licensing Expo.'],
            ['Video/Loom', '10–20 per month', 'Custom 60-second reels showing how TheSoul would animate their specific IP.'],
            ['Direct mail', '5–10 per month (top-tier accounts)', 'Physical package with printed storyboards or character concepts for their IP.'],
        ]
    })

    # --- TAB: Trackable Signals ---
    updates.append({
        'range': "'Trackable Signals'!A1",
        'values': [
            ['TRACKABLE PUBLIC SIGNALS — TRIGGER-BASED OUTREACH'],
            ['Each signal indicates a company is moving toward commissioning animation. Organized by urgency.'],
            [''],
            ['TIER 1 — HIGHEST INTENT (Act within 48 hours)'],
            [''],
            ['Signal', 'Where to Track', 'Time-to-Decision', 'Recommended Action'],
            ['New VP/Director of Content hired at target company', 'LinkedIn Sales Navigator alerts', '3–12 months', 'Congratulate + offer industry briefing within 30 days of start date'],
            ['Animation job postings (Producer, Head of Animation) at NON-studio company', 'LinkedIn Jobs, Indeed, Glassdoor', '3–6 months', 'They\'re building internal team. Reach out as production partner, not competitor.'],
            ['Multiple animation hires at same company in short period', 'LinkedIn, company careers page', '1–3 months', 'Production initiative is launching. Pitch capacity overflow — urgent.'],
            ['RFP/tender published for animation production', 'Industry networks, LinkedIn, trade press', '2–8 weeks', 'Respond immediately. Active procurement.'],
            ['Company announces new IP / character launch without animation', 'Press releases, Toy Fair announcements', '6–12 months', 'Pitch animated series as the missing piece for the new IP.'],
            [''],
            ['TIER 2 — STRONG INTENT (Act within 1 week)'],
            [''],
            ['Signal', 'Where to Track', 'Time-to-Decision', 'Recommended Action'],
            ['First-time attendance at Annecy, Kidscreen, or MIPCOM', 'Event exhibitor/attendee lists (published 4–8 weeks before)', '6–18 months', 'Pre-event outreach 2 months before. Book meeting at event.'],
            ['Streaming deal announced (Netflix, Apple TV+, Amazon partnership)', 'Deadline, Variety, press releases', '6–12 months', 'Animation partner may not be selected yet. Pitch immediately.'],
            ['Brand refresh / franchise relaunch announced', 'Press releases, trade press', '6–18 months', 'Legacy toy revivals always need new animation (Care Bears, He-Man, Transformers cycles).'],
            ['Earnings call mentions "content-led strategy" or "entertainment-driven brands"', 'SEC filings, Sentieo, AlphaSense', '6–12 months', 'Executive mandate to invest. VP will be tasked with finding studios.'],
            ['Company acquires new IP (book series, comic, game property)', 'Press releases, Crunchbase M&A alerts', '12–24 months', 'Animated adaptation likely follows. Get in early as production partner.'],
            ['Competitor launches animated series for similar toy line', 'YouTube, trade press, SocialBlade', '3–6 months', '"Your competitor just launched a series. Here\'s what it\'s doing for their sales."'],
            [''],
            ['TIER 3 — EARLY INDICATORS (Nurture)'],
            [''],
            ['Signal', 'Where to Track', 'Time-to-Decision', 'Recommended Action'],
            ['Company\'s YouTube channel metrics declining', 'SocialBlade, VidIQ, TubeBuddy', 'Ongoing', '"Your channel dropped 30% — here\'s what competitors are doing differently."'],
            ['Executive posts about animation trends on LinkedIn', 'LinkedIn feed monitoring', 'Pre-awareness', 'Engage with their content. Build relationship before pitching.'],
            ['Company experiments with first animated shorts on social', 'YouTube, TikTok monitoring', '3–12 months', '"We noticed your first animated short. Here\'s how to scale to a full series."'],
            ['New product line announced at toy fairs', 'Trade show coverage, press releases', '12–18 months', 'New toy lines need content. Plant the seed early.'],
            ['Company raises significant funding / IPO', 'Crunchbase, SEC filings', '6–24 months', 'Fresh capital often goes to content and marketing. Reach out with timing.'],
            [''],
            ['SIGNAL TRACKING STACK'],
            [''],
            ['Tool', 'Purpose', 'Est. Cost'],
            ['LinkedIn Sales Navigator', 'Job change alerts, saved searches, InMail for target accounts', '~$100/mo'],
            ['Google Alerts', 'Free monitoring for "[company name]" + "animation" keywords', 'Free'],
            ['SocialBlade', 'Track YouTube channel metrics decline for target companies', 'Free / Pro'],
            ['Crunchbase', 'M&A alerts, funding rounds for target companies', '~$50/mo'],
            ['Sentieo / AlphaSense', 'Search all public company earnings transcripts for "animation" and "content"', '~$500/mo'],
            ['Kidscreen.com / Animation Magazine / Cartoon Brew', 'Industry trade press — RSS/email alerts', 'Free'],
            ['Trade show exhibitor lists', 'Pre-event intelligence (Annecy, MIPCOM, Licensing Expo, Toy Fair)', 'Free–$200'],
            ['Clay', 'Automated workflows combining signals from multiple data sources', '~$150/mo'],
        ]
    })

    # --- TAB: Event Calendar ---
    updates.append({
        'range': "'Event Calendar 2026'!A1",
        'values': [
            ['EVENT CALENDAR 2026 — ANIMATION & TOY INDUSTRY'],
            ['Key events where animation buyers meet production studios. Start outreach 8 weeks before each event.'],
            [''],
            ['Month', 'Event', 'Location', 'What Happens', 'Action'],
            ['COMPLETED', '', '', '', ''],
            ['Jan', 'CES', 'Las Vegas', 'Toy-tech convergence. Connected toy + content bundle announcements.', 'Monitor announcements for new products needing animation.'],
            ['Jan-Feb', 'Spielwarenmesse (Nuremberg Toy Fair)', 'Nuremberg, Germany', 'World\'s largest toy trade fair. 2,800+ exhibitors, 65,000 attendees.', 'Identify EU toy companies announcing new lines without animation.'],
            ['Feb', 'Kidscreen Summit', 'San Diego/Miami', 'Kids\' entertainment — content, brands, digital. ~2,000 decision-makers.', 'HIGH PRIORITY. Speed-pitching sessions. Most concentrated buyer pool.'],
            ['Mar', 'Cartoon Movie', 'Bordeaux, France', 'Animated feature film co-production marketplace.', 'Feature-length pitches. Relevant for premium projects.'],
            ['', '', '', '', ''],
            ['UPCOMING', '', '', '', ''],
            ['May', 'Licensing Expo', 'Las Vegas', 'Licensing industry\'s main event. 16,000 attendees. IP-to-toy pipeline.', 'HIGH PRIORITY. Meet VP Licensing face-to-face. Start outreach NOW (8 weeks).'],
            ['Jun', 'Annecy / MIFA', 'Annecy, France', 'World\'s largest animation event + market. 15,000 attendees.', 'THE #1 EVENT. Animation studios pitch, buyers commission. Book 20+ meetings.'],
            ['Jun', 'VidCon', 'Anaheim, CA', 'Digital-first content. YouTube-native positioning.', 'Relevant for TheSoul\'s YouTube-first production model.'],
            ['Sep', 'Cartoon Forum', 'Toulouse, France (typical)', 'Animation TV series pitching. Invitation-based. 950 decision-makers.', 'Highest signal-to-noise. Every attendee is actively commissioning.'],
            ['Sep-Oct', 'Brand Licensing Europe', 'London, ExCeL', 'European IP licensing. Same dynamic as Licensing Expo.', 'EU-focused buyers. Target European toy and FMCG brands.'],
            ['Sep-Oct', 'Toy Fair New York', 'New York, Javits Center', 'New product line reveals. 25,000 attendees.', 'Spot toy launches without animation. Pitch production partnership.'],
            ['Oct', 'MIPCOM / MIPJunior', 'Cannes, France', 'Global TV/content marketplace. MIPJunior = kids content. 11,000 attendees.', 'HIGH PRIORITY. Where Hasbro, Mattel, Spin Master scout animation studios.'],
            ['Nov', 'CTN Animation Expo', 'Los Angeles', 'Animation networking and recruiting. Less deal-making.', 'Relationship building. Not primary deal-making venue.'],
            [''],
            ['PRE-EVENT OUTREACH TIMELINE'],
            ['Weeks Before', 'Action'],
            ['8 weeks', 'Identify target attendees from exhibitor/attendee lists. Begin LinkedIn outreach.'],
            ['6 weeks', 'Send personalized email: "I\'ll be at [Event] — would love 15 minutes to discuss [their IP]."'],
            ['4 weeks', 'Follow up. Share a custom brief or reel relevant to their IP.'],
            ['2 weeks', 'Confirm meeting times. Send calendar invites.'],
            ['At event', 'Take meetings. Collect cards. Note action items within 24 hours.'],
            ['1 week after', 'Follow up with promised materials. Send custom treatment if discussed.'],
        ]
    })

    # --- TAB: Competitive Landscape ---
    updates.append({
        'range': "'Competitive Landscape'!A1",
        'values': [
            ['COMPETITIVE LANDSCAPE — ANIMATION PRODUCTION STUDIOS'],
            ['Who TheSoul Group competes against for production deals. Each competitor has weaknesses TheSoul can exploit.'],
            [''],
            ['Studio', 'Known For', 'Strength', 'Weakness TheSoul Exploits'],
            ['Guru Studio', 'PAW Patrol, True and the Rainbow Kingdom', 'Proven hit-maker. Trusted by Spin Master.', 'Capacity-constrained. Long waitlists. Can\'t take new clients easily.'],
            ['9 Story Media Group', 'Daniel Tiger, Karma\'s World', 'Strong relationship with PBS/Netflix.', 'Broadcast-focused. Weak on YouTube-native and digital-first formats.'],
            ['WildBrain Studios', 'Peanuts, Teletubbies, Strawberry Shortcake', 'Large IP library. Established relationships.', 'Legacy approach. Slow production cycles. Struggles with volume.'],
            ['Xilam Animation', 'Oggy and the Cockroaches, Zig & Sharko', 'French tax incentives. Strong in slapstick.', 'Language/timezone barriers for US clients. Narrow style range.'],
            ['Technicolor Animation', 'Alvin and the Chipmunks, Sonic Prime', 'Premium broadcast quality.', 'Premium pricing. Not suited for high-volume digital content.'],
            ['Fortiche (Arcane)', 'Arcane (Riot Games)', 'Highest-quality game-to-animation studio.', 'Tiny studio. Years-long waitlist. Cannot scale. Only takes marquee projects.'],
            ['Atomic Cartoons (Thunderbird)', 'Netflix originals', 'Netflix relationship.', 'Netflix-first. May deprioritize non-Netflix clients.'],
            ['Blur Studio', 'Game cinematics (Overwatch, League)', 'Premium cinematic quality.', 'Extremely expensive. Project-based, not ongoing partnerships.'],
            [''],
            ['THESOUL GROUP\'S COMPETITIVE ADVANTAGES'],
            [''],
            ['Advantage', 'Detail'],
            ['Volume', '2,000+ videos/month production capacity vs. boutique studios producing 13–26 episodes/year.'],
            ['Speed', 'YouTube-native means delivery in weeks, not the 12–24 month production cycles of traditional studios.'],
            ['Built-in distribution', 'Content reaches 2.5B followers across TheSoul\'s own channels — no marketing spend needed.'],
            ['Localization', 'Dubbing into 20+ languages is a core capability, not an expensive add-on.'],
            ['Cost efficiency', 'Industrial-scale production = significantly lower per-minute cost than boutique animation studios.'],
            ['Proven ROI', 'Crayola case study: 600M views, 652K subscribers in 7 months of production partnership.'],
            [''],
            ['POSITIONING AGAINST EACH COMPETITOR TYPE'],
            [''],
            ['Scenario', 'Pitch'],
            ['Client has a boutique studio for hero series', '"We don\'t replace them. We handle the volume: digital shorts, social content, localization. They do the flagship series, we do everything else."'],
            ['Client has never commissioned animation', '"Our YouTube-first model is 1/10th the cost of broadcast-quality series. Start with a pilot, see measurable results in weeks, then scale."'],
            ['Client is cost-conscious', '"We produce at YouTube quality with industrial efficiency — $3K–$15K per minute vs. $30K–$80K+ at traditional studios. Same impact, fraction of the cost."'],
            ['Client needs speed', '"Traditional studios deliver in 12–24 months. We deliver in weeks. Your IP launch doesn\'t have to wait for animation."'],
        ]
    })

    # Batch update all data
    sheets_svc.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            'valueInputOption': 'RAW',
            'data': updates
        }
    ).execute()
    print("All data written")

    # ---- Formatting ----
    sheet_ids = {}
    spreadsheet = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    for s in spreadsheet['sheets']:
        sheet_ids[s['properties']['title']] = s['properties']['sheetId']

    format_requests = []

    # Bold + background for headers across all tabs
    header_color = {'red': 0.15, 'green': 0.15, 'blue': 0.15}
    header_text_color = {'red': 1.0, 'green': 1.0, 'blue': 1.0}

    for tab_name, sid in sheet_ids.items():
        # Bold row 1 (title) — dark bg, white text
        format_requests.append({
            'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 10},
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': header_color,
                        'textFormat': {'bold': True, 'fontSize': 13, 'foregroundColor': header_text_color},
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat)'
            }
        })

        # Auto-resize columns
        format_requests.append({
            'autoResizeDimensions': {
                'dimensions': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 10}
            }
        })

    # Special formatting for company data rows (header rows with column names)
    company_tabs = [
        ('1A. Toys — No Animation', 3),
        ('1B. Toys — Need More Capacity', 3),
        ('1C. Consumer Brands with Characters', 4),
        ('1D. Gaming (Post-Arcane)', 4),
        ('1E. EdTech & Educational', 4),
        ('1F. IP Owners (Publishing, Licensing)', 3),
        ('Target Roles & Decision Unit', 2),
        ('Trackable Signals', 4),
        ('Event Calendar 2026', 3),
        ('Competitive Landscape', 3),
        ('ABM Outreach Plan', 5),
    ]

    subheader_color = {'red': 0.85, 'green': 0.85, 'blue': 0.85}
    for tab_name, header_row in company_tabs:
        sid = sheet_ids.get(tab_name)
        if sid is not None:
            format_requests.append({
                'repeatCell': {
                    'range': {'sheetId': sid, 'startRowIndex': header_row, 'endRowIndex': header_row + 1, 'startColumnIndex': 0, 'endColumnIndex': 10},
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': subheader_color,
                            'textFormat': {'bold': True, 'fontSize': 10},
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            })

    # Freeze first row in all tabs
    for tab_name, sid in sheet_ids.items():
        format_requests.append({
            'updateSheetProperties': {
                'properties': {
                    'sheetId': sid,
                    'gridProperties': {'frozenRowCount': 1}
                },
                'fields': 'gridProperties.frozenRowCount'
            }
        })

    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': format_requests}
    ).execute()
    print("Formatting applied")

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    print(f"\nDone! Sheet URL: {url}")
    return url


if __name__ == '__main__':
    url = create_sheet()
