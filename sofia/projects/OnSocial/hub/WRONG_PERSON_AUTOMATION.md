# Wrong Person - Automated Routing

**Date**: 2026-04-03
**Author**: Sofia
**Status**: ACTIVE

---

## What This Does

When someone replies "I'm not the right person" or "talk to my colleague X", the system automatically adds them to a dedicated SmartLead follow-up campaign that asks for a referral.

**Works for any project.** The script takes `--project` (e.g. OnSocial, EasyStaff) and:
1. Discovers all SmartLead campaigns with the project name in their title
2. Collects Wrong Person replies from those campaigns
3. Syncs them to the project's WRONG-PERSON referral campaign

**No hardcoded IDs.** New campaigns are picked up automatically by name.

---

## Setup for a New Project

1. Create a SmartLead campaign named `c-{Project}_WRONG-PERSON-referral`
2. Add sequences (see below) and email accounts
3. Add a cron entry:

```bash
# In ~/run_sync_wrong_person_{project}.sh
cd ~/magnum-opus-project/repo
set -a && source .env && set +a
python3 sofia/scripts/sync_wrong_person.py --project {Project} --chat-id {YOUR_TG_CHAT_ID} >> ~/logs/wrong_person_sync.log 2>&1
```

```bash
# Cron: 2x daily
0 9,17 * * * /home/leadokol/run_sync_wrong_person_{project}.sh
```

That's it. The script will auto-discover:
- **Destination**: campaign matching `{Project}` + `WRONG` + `PERSON` in name
- **Source**: all campaigns containing `{Project}` in name (excluding the WRONG-PERSON one)

---

## How Discovery Works

```
SmartLead API: GET /campaigns
  -> filter by name containing project (e.g. "OnSocial")
  -> split into:
     SOURCE campaigns (all OnSocial campaigns)
     DESTINATION campaign (the one with WRONG + PERSON in name)

Leadgen DB: SELECT from processed_replies
  -> WHERE category = 'wrong_person'
  -> AND campaign_name = ANY(source campaign names)
  -> AND not already synced (contact_activities check)

SmartLead API: POST /campaigns/{destination_id}/leads
  -> upload new Wrong Person leads
  -> mark as synced in contact_activities
  -> send Telegram report
```

---

## Sequence (copy-paste ready for new projects)

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

**Important**: `{{colleague_name}}` is set automatically from the original responder's first name.

---

## Usage

### Run manually:
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/sync_wrong_person.py --project OnSocial --chat-id 7380803777"
```

### Dry run (preview without syncing):
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/sync_wrong_person.py --project OnSocial --chat-id 7380803777 --dry-run"
```

### Override campaign ID (if auto-discovery fails):
```bash
python3 sofia/scripts/sync_wrong_person.py --project OnSocial --campaign-id 3092917 --chat-id 7380803777
```

### Check logs:
```bash
ssh hetzner "tail -50 ~/logs/wrong_person_sync.log"
```

---

## Safety

- **Project isolation**: `--project` scopes everything. OnSocial run never touches EasyStaff campaigns.
- **Idempotent**: `smartlead_synced` flag prevents duplicate adds. Safe to re-run.
- **Read-only on source**: Only SELECTs from `processed_replies` (never modifies).
- **Append-only on SmartLead**: Only adds leads, never deletes or modifies existing ones.
- **Failure safe**: If the script crashes, leads just wait for the next run.
