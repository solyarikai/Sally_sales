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
- **Script**: `findymail_host.py` — runs on HOST, NOT inside Docker
- **Why host**: `docker exec` processes die on container rebuild/restart. Host process with `nohup` survives everything.
- **Persistent cache**: `/scripts/findymail_email_cache.json` (host-mounted volume) — maps LinkedIn URL → email (or empty string for no-result). Survives container restarts, deploys, crashes.
- **Contacts file**: `/scripts/findymail_contacts.json` — pre-filtered from Google Sheet + FINAL_keep IDs, also persistent
- **Results**: `/scripts/findymail_results.json` — contacts that got emails, ready for SmartLead upload
- **Hit rate**: ~50% (niche Pakistani-origin contacts in UAE)
- **Auto-upload**: script uploads to SmartLead campaign automatically after enrichment

**How to run:**
```bash
# Launch on host (NOT docker exec!)
ssh hetzner 'nohup python3 ~/findymail_host.py </dev/null >~/findymail_nohup.log 2>&1 &'

# Check progress
ssh hetzner 'tail -5 ~/findymail_log.txt'
ssh hetzner 'python3 -c "import json; d=json.load(open(\"/home/leadokol/magnum-opus-project/repo/scripts/findymail_email_cache.json\")); e=sum(1 for v in d.values() if v); print(f\"Cache: {len(d)}/4411, {e} emails, {e*100//max(1,len(d))}% hit\")"'

# Check if alive
ssh hetzner 'ps aux | grep findymail_host | grep -v grep'
```

**Critical rules:**
1. NEVER run FindyMail inside Docker container — it WILL die on rebuild
2. NEVER store cache/progress in `/tmp/` inside container — it vanishes on restart
3. Always use `/scripts/` for persistent data (host-mounted volume)
4. Cache key = LinkedIn URL, value = email or empty string. Empty = "checked, no email found" (don't re-check)
5. Cache saved after EVERY batch of 50 — crash-safe, max 50 wasted credits on any failure
6. FindyMail API returns email in `response['contact']['email']`, NOT `response['email']`

### 5. SmartLead campaign
- Create: `create_campaign_and_project.py`
- Add email accounts: `add_accounts_to_campaign.py`
- Set sequence: `set_sequence_v2.py` (multi-country payments angle)
- Upload leads: auto-done by `findymail_host.py`, or manual with `upload_leads_to_campaign.py`
- Campaign created in DRAFT — launch from UI only

---

## Key Files

| File | Purpose |
|---|---|
| `enterprise_blacklist.json` | 1004 enterprise domains, 150+ name patterns, 73 credential patterns |
| `score_corridors_algo.py` | Algorithmic scorer for AU-PH and Arabic-SA corridors |
| `score_uae_pk_god.py` | UAE-PK scorer with relaxed filters |
| `findymail_host.py` | FindyMail enrichment — runs on HOST with persistent cache + auto-upload |
| `findymail_persistent.py` | FindyMail enrichment — runs in Docker (backup, less reliable) |
| `upload_leads_to_campaign.py` | Upload to SmartLead campaign (standalone) |
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
- UAE-Pakistan v1: `3043938` (Petr accounts, 5-email sequence, LIVE)
- UAE-Pakistan v2: `3048388` (multi-country payments angle, 4411 validated contacts)
- Infra sheet: `1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg` (Accounts infra tab)
