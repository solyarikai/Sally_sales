# EasyStaff Global Corridors — Gathering, Scoring, Campaign Setup

## Quick Start

### Check gathering progress
```bash
ssh hetzner 'curl -s http://localhost:8000/api/diaspora/status'
```

### Launch gathering for a corridor
```bash
ssh hetzner 'curl -s -X POST http://localhost:8000/api/diaspora/gather \
  -H "Content-Type: application/json" \
  -d "{\"corridor\": \"CORRIDOR_KEY\", \"mode\": \"university\", \"target_count\": 20000, \"existing_sheet_id\": \"SHEET_ID\"}"'
```
Corridor keys: `uae-pakistan`, `australia-philippines`, `arabic-south-africa`

### Score a corridor algorithmically
```bash
docker exec leadgen-backend python3 /app/scripts/score_corridors_algo.py
```

### FindyMail + upload to SmartLead
```bash
docker exec leadgen-backend python3 /app/scripts/findymail_enrich_uae_pk.py
docker exec leadgen-backend python3 /app/scripts/upload_leads_to_campaign.py
```

---

## Full Pipeline

### 1. Gather contacts (Clay browser + Apollo)
- Pipeline: `POST /api/diaspora/gather` with `mode="university"`
- University = definitive origin signal (no pre-filter needed)
- Language search is unreliable but adds volume
- Raw data persisted to `/scripts/data/raw_contacts/` on Hetzner
- Pipeline state persisted to `/scripts/data/pipeline_state/` (survives restarts)

### 2. Score with algorithmic blacklist
- Script: `score_corridors_algo.py` or `score_uae_pk_god.py`
- Blacklist: `enterprise_blacklist.json` (1004 domains, 150+ name patterns, 73 credential patterns)
- Filters: location (must be in buyer country), domain required, enterprise domains, name patterns, anti-titles, credential surnames, Arabic-only names, single-word names, company-as-name junk
- Output: Google Sheet with scored contacts

### 3. Opus review (iterate until <1%)
- Split contacts into 5 batches
- Launch 5 parallel Opus agents
- Each agent reads every contact, flags enterprise >500, junk, non-business
- Aggregate removals → update blacklist → re-run algo → repeat
- Stop when removal rate drops below 1%

### 4. FindyMail enrichment
- Script: `findymail_enrich_uae_pk.py`
- Finds emails by LinkedIn URL (not domain)
- ~70% hit rate
- Saves progress to `/tmp/findymail_*_progress.json` (resumable)
- API key: `FINDYMAIL_API_KEY` env var, needs `set_api_key()` call

### 5. SmartLead campaign
- Create: `create_campaign_and_project.py`
- Add email accounts: `add_accounts_to_campaign.py`
- Set sequence: `set_sequence_uae_pk.py`
- Upload leads: `upload_leads_to_campaign.py`
- Campaign created in DRAFT — launch from UI only

---

## Key Files

| File | Purpose |
|---|---|
| `enterprise_blacklist.json` | 1004 enterprise domains, 150+ name patterns, 73 credential patterns |
| `score_corridors_algo.py` | Algorithmic scorer for AU-PH and Arabic-SA corridors |
| `score_uae_pk_god.py` | UAE-PK scorer with relaxed filters |
| `findymail_enrich_uae_pk.py` | FindyMail email enrichment by LinkedIn URL |
| `upload_leads_to_campaign.py` | Upload to SmartLead campaign |
| `create_campaign_and_project.py` | Create SmartLead campaign + system project |
| `add_accounts_to_campaign.py` | Add Petr email accounts from infra sheet |
| `set_sequence_uae_pk.py` | Set 5-email sequence on campaign |
| `EASYSTAFF_GLOBAL_SEQUENCE.md` | ICP, sequence templates, objection handling, verification process |
| `EASYSTAFF_GLOBAL_CONVERSATIONS.md` | Real conversation analysis, patterns |
| `EASYSTAFF_OUTREACH_PLAN.md` | Corridor strategy, prioritization |

## Corridors

| Corridor | Key | Buyer country | Talent country | Status |
|---|---|---|---|---|
| UAE→Pakistan | `uae-pakistan` | UAE | Pakistan | Campaign live (3043938) |
| AU→Philippines | `australia-philippines` | Australia | Philippines | Scored, needs Opus review |
| Arabic→South Africa | `arabic-south-africa` | Gulf states | South Africa | Scored, needs Opus review |

## Master Sheet
`1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU`

## SmartLead Campaigns
- UAE-Pakistan: `3043938` (Petr accounts, 5-email sequence, LIVE)
- Infra sheet: `1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg` (Accounts infra tab)
