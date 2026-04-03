# Contact Sync Architecture

How SmartLead and GetSales contacts are synced with the CRM database.

## SmartLead Contact Sync

### API Endpoints

- **CSV Export** (primary sync method):
  `GET https://server.smartlead.ai/api/v1/campaigns/{id}/leads-export?api_key={KEY}`
  Returns all contacts for a campaign in a single API call.

- **Analytics** (checksum verification):
  `GET https://server.smartlead.ai/api/v1/campaigns/{id}/analytics?api_key={KEY}`
  Returns `campaign_lead_stats.total` — used to verify export completeness.

### Authentication

- API key: `SMARTLEAD_API_KEY` env var on production
- SmartLead UI login: `services@getsally.io` / `SallySarrh7231` (requires OTP/2FA for web UI)

### Sync Schedule

- Runs every 30 minutes via CRM scheduler
- Per-contact `added_at` dates stored in `platform_state.smartlead.campaigns[].added_at`
- `leads_count` on campaigns table refreshed during CSV export (actual row count)

### SmartLead CSV Columns

```
id, campaign_lead_map_id, status, category, is_interested, created_at, first_name,
last_name, email, phone_number, company_name, website, location, custom_fields,
linkedin_profile, company_url, is_unsubscribed, last_email_sequence_sent,
open_count, click_count, reply_count
```

### Bulk Enrichment

The `smartlead_raw` JSONB column stores all CSV fields per contact. Enrichment script:
```bash
ssh hetzner "docker exec -e PYTHONPATH=/app leadgen-backend python3 /tmp/sync_smartlead_raw.py"
```
- Downloads CSV per campaign via API
- Uses psycopg2 staging tables for bulk UPDATE
- Only updates contacts where `smartlead_raw = '{}'::jsonb`
- Sets `created_at` from SmartLead's `created_at` if DB value is NULL

### Verification

- CSV export count must match analytics count
- Phantom gaps = bounced/deleted leads counted in analytics but not present in CSV
- Current state: 61,801 contacts across 116 campaigns — 100% verified

---

## GetSales Contact Sync

### API Approach (automated)

- **Auth**: `GETSALES_API_KEY` env var (JWT, valid until ~2029)

- **List flows**:
  `GET https://amazing.getsales.io/flows/api/flows?offset=0&limit=100`
  Paginate using `has_more` flag.

- **Flow contacts**:
  `GET https://amazing.getsales.io/flows/api/flows-leads?filter[flow_uuid]={uuid}&limit=20&offset=N`
  Max 20 per page. Returns `lead_uuids` only.

- **Lead details**:
  `GET https://amazing.getsales.io/leads/api/leads/{lead_uuid}`
  Returns `work_email`, `first_name`, `last_name`, `company_name`.

- **Limitation**: Slow (~0.12s per lead), max 20 per page. Not practical for full sync of 15k+ contacts.

### Browser Approach (bulk export — PREFERRED for full sync)

**Scripts**:
- `~/getsales_export_v2.js` on Hetzner (login-based)
- `scripts/getsales_export.js` in repo (JWT cookie-based)

**Credentials**: `serge@inxydigital.com` / `hX0NRECCixee` (READONLY)

**Process**:
1. Puppeteer launches Chrome
2. Navigates to login page, fills email/password, submits
3. Navigates to `/crm/contacts`
4. Clicks "Action Queue"
5. Clicks "View N more files" to expand download list
6. Clicks all download buttons for `contacts_export*.csv`
7. Waits for downloads to complete

**Output**: ~110 CSV files in `~/getsales_exports/` on Hetzner

**Import (full procedure)**:
```bash
# 1. Copy CSVs into the backend container
ssh hetzner "docker cp ~/getsales_exports leadgen-backend:/tmp/getsales_exports"

# 2. Run the bulk sync script inside the container
ssh hetzner "docker exec -e PYTHONPATH=/app leadgen-backend python3 /tmp/sync_getsales_fast.py"
```

The sync script (`sync_getsales_fast.py`):
- Uses psycopg2 staging tables for bulk speed (processes 109K rows in ~30 seconds)
- Deduplicates by email (lowercase) and LinkedIn URL
- Project assignment based on "Active Flows" and "Tags" CSV columns
- Stores ALL raw CSV fields in `getsales_raw` JSONB column
- Sets `created_at` from CSV's "Created At" field (when added to campaign in GetSales)
- Email contacts: UPDATE existing (enrich getsales_id, linkedin_url, getsales_raw), INSERT new
- LinkedIn-only contacts: matched by linkedin_url or getsales_id, INSERT if truly new
- Strips null bytes (`\x00`) from all field values
- Cleans up any placeholder emails (`email LIKE '%placeholder%'` → SET NULL)

**Important notes**:
- CSV contains ALL GetSales contacts (all projects, not just EasyStaff) — must filter by flow/campaign name for project assignment
- API JWT (`token_type: "api"`) does NOT work as a browser session cookie. Must use username/password login.

### Prerequisites on Hetzner

```bash
# Install Puppeteer dependencies (one-time, in home dir)
cd ~ && npm install puppeteer puppeteer-extra puppeteer-extra-plugin-stealth

# Chrome is already installed at /usr/bin/google-chrome
```

### Running the Export

```bash
# Run the export script
ssh hetzner "cd ~ && node getsales_export_v2.js"
# Downloads ~110 CSVs to ~/getsales_exports/

# Copy to container and import
ssh hetzner "docker cp ~/getsales_exports/. leadgen-backend:/tmp/getsales_csvs/"
```

### GetSales CSV Columns

```
System UUID, Pipeline Stage, Full Name, First Name, Last Name, Position, Headline, About,
LinkedIn ID, Sales Navigator ID, LinkedIn Nickname, LinkedIn URL, Facebook Nickname,
Twitter Nickname, Work Email, Personal Email, Work Phone Number, Personal Phone Number,
Connections Number, Followers Number, Primary Language, Has Open Profile, Has Verified Profile,
Has Premium, Location Country, Location State, Location City, Active Flows, List, Tags,
Company Name, Company Industry, Company LinkedIn ID, Company Domain, Company LinkedIn URL,
Company Employees Range, Company Headquarter, ..., Created At
```

### Verification

- 109,624 total rows across 110 CSVs
- 71,202 with email, 38,421 LinkedIn-only (after filtering 38,422 placeholder emails)
- Project distribution: P9=88,181 (EasyStaff Global), P40=10,216 (EasyStaff RU), P10=5,795 (inxy), P21=3,635 (mifort), P13=78 (tfp)
- Checksum: compare source count (CSV) vs DB count per campaign

---

## Project Assignment

Campaigns are assigned to projects using `campaign_ownership_rules` (JSON column on `projects` table):

```json
{
  "prefixes": [],
  "contains": [],
  "smartlead_tags": []
}
```

### Match Logic (evaluation order)

1. **Tags** (most explicit): SmartLead campaign tags matched against `smartlead_tags`
2. **Longest prefix**: campaign name starts with a project prefix — longest match wins
3. **Contains** (loosest): campaign name contains a substring

Implementation: `match_campaign_to_project(name, tags)` in `crm_sync_service.py`

### Key Project Rules

| Project | ID | Rule |
|---|---|---|
| EasyStaff Global | 9 | Campaigns with "EasyStaff" but NOT "Russian DM" |
| EasyStaff RU | 40 | "Russian DM" campaigns |

### GetSales Sender-to-Project Mapping

GetSales replies are routed to projects via `getsales_senders` UUID list on each project. See sender mappings in `MEMORY.md`.

---

## Placeholder Email Handling

GetSales creates placeholder emails like `gs_{uuid}@linkedin.placeholder` for LinkedIn-only contacts.

Rules:
- **NEVER** insert placeholder emails into CRM
- LinkedIn-only contacts: store with `linkedin_url` but `NULL` email
- Filter in views: `WHERE email NOT LIKE '%placeholder%'` or `WHERE email IS NOT NULL`
- Periodic cleanup: `UPDATE contacts SET email = NULL WHERE email LIKE '%placeholder%'`

---

## Full Sync Procedure (Reusable)

Run these steps to fully sync all contacts from both sources:

### 1. SmartLead Sync (automated)
```bash
# Already runs every 30 min via CRM scheduler
# Manual trigger for full re-sync:
ssh hetzner "docker exec leadgen-backend python3 -c \"
from app.services.crm_sync_service import sync_smartlead_contacts
import asyncio; asyncio.run(sync_smartlead_contacts())
\""

# Enrich smartlead_raw JSONB:
ssh hetzner "docker exec -e PYTHONPATH=/app leadgen-backend python3 /tmp/sync_smartlead_raw.py"
```

### 2. GetSales Sync (browser-based)
```bash
# Step 1: Export CSVs via Puppeteer
ssh hetzner "cd ~ && node getsales_export_v2.js"

# Step 2: Copy to container
ssh hetzner "docker cp ~/getsales_exports leadgen-backend:/tmp/getsales_exports"

# Step 3: Import
ssh hetzner "docker exec -e PYTHONPATH=/app leadgen-backend python3 /tmp/sync_getsales_fast.py"
```

### 3. Cleanup
```bash
# Remove placeholder emails
ssh hetzner 'docker exec leadgen-postgres psql -U leadgen -d leadgen -c "UPDATE contacts SET email = NULL WHERE email LIKE '"'"'%placeholder%'"'"'"'

# Verify
ssh hetzner 'docker exec leadgen-postgres psql -U leadgen -d leadgen -c "SELECT source, count(*) FROM contacts GROUP BY source ORDER BY count(*) DESC"'
```

### 4. Blacklisting (Google Sheet)
```bash
# Run inside container — creates "New Only" tabs in master sheet
ssh hetzner "docker exec -e PYTHONPATH=/app leadgen-backend python3 /tmp/blacklist_sheet.py"
```
- Filter in views: `WHERE email NOT LIKE '%placeholder%'`

---

## Reply Sync Architecture

### SmartLead Replies
- **Webhook** (real-time): `POST /api/smartlead/webhook` — events: `EMAIL_REPLY`, `LEAD_CATEGORY_UPDATED`
- **Polling** (fallback): `GET /campaigns/{id}/statistics` — paginated, checks `sl_reply_count` guard
- **Message history**: `GET /campaigns/{id}/leads/{id}/message-history` — fetches email thread
- **Dedup**: `UNIQUE(lead_email, campaign_id, message_hash)` where hash = MD5(body[:500].lower())

### GetSales Replies
- **Webhook** (real-time): `POST /api/getsales/webhook` — event: `contact_replied_linkedin_message`
- **Polling** (fallback): `GET /flows/api/linkedin-messages` with inbox filter, early-stop after 50 cached hits
- **Campaign resolution** (3-tier): webhook automation → contact's cached campaigns → webhook history DB
- **Upsert**: same (lead_email, message_hash) with empty campaign → enrich instead of duplicate

### Rate Limiting
- **SmartLead**: semaphore max 10 concurrent, 150 req/min target, 429 retry [2s, 8s, 30s]
- **GetSales**: 200ms minimum between requests

---

## Scheduler Frequencies

| Task | Interval | Notes |
|------|----------|-------|
| SmartLead reply polling | 3-10 min (adaptive) | Fast on startup, slow steady state |
| GetSales reply polling | 3-10 min (adaptive) | Same adaptive pattern |
| Contact sync (incremental) | 10 min | Only campaigns with count changes |
| Contact sync (full) | 24 hours | Full reconciliation |
| Webhook registration | 60 min | SmartLead + GetSales |
| Conversation sync | 3 min | Thread history for draft generation |
| Follow-up generation | 3 min | AI draft generation for stale leads |
| Deep cleanup | 6 hours | Check ALL pending replies (no date limit) |
| Campaign auto-discovery | 3 min | Register + assign new campaigns |
| Task watchdog | 60 sec | Resurrects dead scheduler tasks |

Implementation: `crm_scheduler.py` — all tasks self-healing via watchdog.

---

## Clay Contact Import (Mar 15, 2026)

### Source
Master Google Sheet: `1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU`

### Import Results
| Corridor | Tab | Imported | Dedup |
|----------|-----|----------|-------|
| UAE-Pakistan | Original | 15,830 | 37 |
| AU-Philippines | Original | 6,515 | 4 |
| Arabic-SouthAfrica | Original | 5,348 | 3,242 |
| All "New Only" tabs | — | 0 | 30,154 (overlap with parent) |
| **Total** | | **27,693** | 33,437 |

### How it works
- Script: `/tmp/import_clay_contacts.py` (run inside leadgen-backend container)
- Dedup by LinkedIn URL against existing CRM contacts
- No placeholder emails — email field NULL if not available
- Source = "clay", project_id = 9 (easystaff global)
- Clay enrichment stored in `provenance` JSON: origin_score, name_match_reason, schools, corridor
- CRM total after import: **114,855** contacts for easystaff global
