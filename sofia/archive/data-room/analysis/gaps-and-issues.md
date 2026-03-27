# OnSocial — Gaps & Issues Analysis

Date: 2026-03-16

## Data Gaps

### 1. Missing replies (SmartLead vs Sheet)
- SmartLead API: 143 email replies across 6 active campaigns
- Google Sheet: 77 email replies logged
- **Gap: ~66 replies not logged** — either from completed campaigns or not entered

### 2. Reply classification incomplete
- 35 out of 77 replies in "other" category — not classified
- Among them: at least 5-6 warm leads misclassified or ignored
- No systematic categorization (Interested / Not Now / Not Interested / OOO / Wrong Person)

### 3. Reply scripts not adapted for OnSocial
- Current scripts in "replies examples" sheet are from The Fashion People project
- Nastya responds without scripts or from memory
- 9 common reply types identified that need OnSocial-specific scripts

### 4. WANNA TALK stagnation
- 19 high-value leads (Kantar, Patreon, Spotter, inDrive, Jellysmack)
- All stuck in "Messaged" status with no follow-up plan
- These are enterprise targets (500-10,000+ employees)

### 5. SmartLead MCP limitations
- `fetch_inbox_replies` API returns 400 error — can't pull manual replies
- `list_campaign_leads` returns N/A for lead details
- Manual replies from Nastya are invisible in API — only outbound sequences visible
- Statistics endpoint returns max ~500 entries per call

## Funnel Issues

### 1. Low reply-to-meeting conversion
- 148 replies → 9 meetings booked = **6.08%**
- But many replies are OOO/auto (21+) — real conversion from genuine replies is higher
- Excluding OOO: ~55 genuine replies → 9 meetings = **16.4%** — actually decent

### 2. PR firms segment underperforming
- 1,000 contacted → 2 replies (0.20%) — lowest of all segments
- Possible issues: wrong ICP, wrong messaging angle, bad timing

### 3. LinkedIn: 0 meetings from 20 replies
- Accept rate good (18.8%), reply rate decent (3.5%)
- But no meetings booked — missing closing step?

### 4. Small companies diluting pipeline
- BrandNation (MVP only), Yagency (can't afford) — wasted meetings
- Need better pre-qualification before booking

## Sequence Issues

### 1. Deployed vs Planned sequences mismatch — AUTHORSHIP MATTERS
- Sally (agency) wrote the generic sequences (Sequences sheet, TEST A/B) — these are what's deployed in SmartLead
- Yarik + Sonya wrote 3 segment-specific sequences with A/B hypotheses (INFPLAT, IMAGENCY, AFFPERF) — NEVER deployed
- Google Sheet has detailed A/B hypotheses per segment (INFPLAT, IMAGENCY, AFFPERF)
- SmartLead has simplified versions actually deployed
- PR firms variant exists in SmartLead but NOT in the sheet
- Testing protocol (cohort sizes, timing) defined but unclear if followed

### 2. Personalization gaps
- Some leads received "Hi ," (empty first_name) — e.g., Pierre-Antoine Leroux, Anna Lukaszewicz, Gabrielle Backman
- Some leads have no company name in custom fields

### 3. No variant tracking
- SmartLead shows TEST B deployed in flagship campaign
- No clear A/B results visible — which variant wins?
- Hypothesis dashboard in sheet is mostly empty

## Operational Issues

### 1. No automation for reply logging
- Manual copy-paste from SmartLead inbox to Google Sheet
- Leads to 66+ unlogged replies

### 2. No systematic OOO follow-up
- 21 OOO responses — need calendar reminders to re-engage after return dates
- Currently no process for this

### 3. Cross-campaign lead overlap
- Luis Carrillo (Adsmurai) appears in BOTH campaign 2947684 AND 2990385
- No dedup protection across campaigns
