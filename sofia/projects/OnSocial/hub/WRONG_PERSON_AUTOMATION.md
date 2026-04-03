# Wrong Person - Automated Routing

**Date**: 2026-04-02
**Author**: Sofia
**Status**: ACTIVE

---

## What This Does

When someone replies "I'm not the right person" or "talk to my colleague X", the system automatically adds them to a dedicated SmartLead follow-up campaign that asks for a referral.

**Scope: OnSocial campaigns ONLY.** The script filters by `campaign_name ILIKE '%OnSocial%'` and will never touch leads from other projects (EasyStaff, SquareFi, TFP, etc.).

---

## SmartLead Campaign

- **Name**: `c-OnSocial_WRONG-PERSON-referral`
- **ID**: `3092917`
- **Status**: DRAFTED (activate manually in SmartLead UI)

---

## Sequence (copy-paste ready)

### Step 1 (Day 0)

**Subject**: `{{colleague_name}} pointed me your way`

```
Hey {{first_name}},

I reached out to {{colleague_name}} at {{company_name}} - they pointed me to you as the right person to speak with about influencer data.

We give agencies access to 450M+ creator profiles across Instagram, TikTok, YouTube and 7 other networks - one unified layer, no scraping.

Worth a 15-min call?

Kind regards,
Bhaskar Vishnu from OnSocial
```

### Step 2 (Day 3)

**Subject**: `Re: {{colleague_name}} pointed me your way`

```
Hey {{first_name}},

Quick follow-up - the main thing agencies tell us saves them the most time is pulling real audience data on any creator across all platforms without depending on a vendor.

Happy to show it live if relevant for {{company_name}}.

Kind regards,
Bhaskar Vishnu from OnSocial
```

### Step 3 (Day 8)

**Subject**: `Re: {{colleague_name}} pointed me your way`

```
Hey {{first_name}},

Last note - if this is not a priority right now, totally fine.

Feel free to reach out whenever the timing is right.

Kind regards,
Bhaskar Vishnu from OnSocial
```

---

## Variables

| Variable | What it is | Example |
|----------|-----------|---------|
| `{{first_name}}` | Name of the NEW contact (who we're emailing now) | Johan |
| `{{company_name}}` | Company name | impact.com |
| `{{colleague_name}}` | Name of the person who replied "wrong person" (the original contact) | Damon Fairchild |

**Important**: `{{colleague_name}}` must be filled when adding a lead. The script sets it automatically from the original responder's first name. If the reply mentions a specific person to contact, update `colleague_name` manually in SmartLead.

---

## How the Script Works

**File**: `sofia/scripts/sync_wrong_person.py`

### Data flow:

```
Leadgen DB (processed_replies table)
  -> filter: category = 'wrong_person' AND campaign_name ILIKE '%OnSocial%'
  -> filter: not already synced (checked via contact_activities)
  -> SmartLead API: POST /campaigns/3092917/leads
  -> mark synced in contact_activities
  -> Telegram notification
```

### Database details:

- **Source table**: `processed_replies` - contains all categorized email replies
- **Tracking table**: `contact_activities` - stores sync state (`extra_data->>'smartlead_synced' = 'true'`)
- **Connection**: PostgreSQL on Hetzner (`docker exec leadgen-postgres`)
- **Credentials**: from `.env` file (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)

### SmartLead API:

- Calls `https://server.smartlead.ai/api/v1/campaigns/3092917/leads` directly
- Uses `SMARTLEAD_API_KEY` from `.env`
- Sends: email, first_name, last_name, company_name, custom_fields.colleague_name

### Schedule:

- Cron: `0 9,17 * * *` (09:00 and 17:00 UTC)
- Wrapper: `/home/leadokol/run_sync_wrong_person.sh`
- Logs: `~/logs/wrong_person_sync.log`

---

## Manual Operations

### Run manually:
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/sync_wrong_person.py --project OnSocial --campaign-id 3092917 --chat-id 7380803777"
```

### Check logs:
```bash
ssh hetzner "tail -50 ~/logs/wrong_person_sync.log"
```

### Disable cron:
```bash
ssh hetzner "crontab -l | grep -v run_sync_wrong_person | crontab -"
```

### Re-enable cron:
```bash
ssh hetzner "(crontab -l; echo '0 9 * * * /home/leadokol/run_sync_wrong_person.sh'; echo '0 17 * * * /home/leadokol/run_sync_wrong_person.sh') | crontab -"
```

---

## Safety

- **Project isolation**: Only processes OnSocial campaigns (`ILIKE '%OnSocial%'`). Other projects are never touched.
- **Idempotent**: `smartlead_synced` flag prevents duplicate adds. Safe to re-run.
- **Read-only on source**: Only SELECTs from `processed_replies` (never modifies).
- **Append-only on SmartLead**: Only adds leads, never deletes or modifies existing ones.
- **Failure safe**: If the script crashes, leads just wait for the next run.
