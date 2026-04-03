# Wrong Person Sync — Team Guide

Script: `sofia/scripts/sync_wrong_person.py`

Syncs "wrong person" replies from the DB to a SmartLead referral campaign — 2x/day via cron.

---

## What it does

When a lead replies "I'm not the right person", the system:
1. Picks them up from `processed_replies` (category = `wrong_person`)
2. Adds them to your referral SmartLead campaign
3. Sets `colleague_name` = original contact's first name (used in email sequence)
4. Marks them as synced so they never get sent twice

---

## Setup

### 1. Create a SmartLead referral campaign

Name convention: `c-<PROJECT>_WRONG-PERSON-referral`

**Sequence (3 steps):**

**Step 1 (Day 0)**
Subject: `{{colleague_name}} pointed me your way`

```
Hey {{first_name}},

I reached out to {{colleague_name}} at {{company_name}} - they pointed me to you as the right person to speak with about <YOUR PITCH>.

<YOUR VALUE PROP — 1-2 sentences>

Worth a 15-min call?

Kind regards,
<YOUR NAME>
```

**Step 2 (Day 3)**
Subject: `Re: {{colleague_name}} pointed me your way`

```
Hey {{first_name}},

Quick follow-up - <KEY BENEFIT for {{company_name}}>.

Happy to show it live if relevant.

Kind regards,
<YOUR NAME>
```

**Step 3 (Day 8)**
Subject: `Re: {{colleague_name}} pointed me your way`

```
Hey {{first_name}},

Last note - if this is not a priority right now, totally fine.

Feel free to reach out whenever the timing is right.

Kind regards,
<YOUR NAME>
```

### Variables

| Variable | What it is |
|----------|-----------|
| `{{first_name}}` | Name of the NEW contact you're reaching |
| `{{company_name}}` | Their company |
| `{{colleague_name}}` | The original contact who replied "wrong person" |

### 2. Set up cron wrapper on Hetzner

Create `/home/leadokol/run_sync_wrong_person_<PROJECT>.sh`:

```bash
#!/bin/bash
cd ~/magnum-opus-project/repo
set -a && source .env && set +a
python3 sofia/scripts/sync_wrong_person.py \
  --project <PROJECT_NAME> \
  --campaign-id <SMARTLEAD_CAMPAIGN_ID> \
  --chat-id <TELEGRAM_CHAT_ID> \
  >> ~/logs/wrong_person_sync_<PROJECT>.log 2>&1
```

```bash
chmod +x /home/leadokol/run_sync_wrong_person_<PROJECT>.sh
```

Add to cron (`crontab -e` on Hetzner):
```
0 9,17 * * * /home/leadokol/run_sync_wrong_person_<PROJECT>.sh
```

---

## Manual operations

### Dry-run (see what would be synced, no changes):
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && \
python3 sofia/scripts/sync_wrong_person.py \
  --project <PROJECT_NAME> \
  --campaign-id <SMARTLEAD_CAMPAIGN_ID> \
  --chat-id <TELEGRAM_CHAT_ID> \
  --dry-run"
```

### Full run:
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && \
python3 sofia/scripts/sync_wrong_person.py \
  --project <PROJECT_NAME> \
  --campaign-id <SMARTLEAD_CAMPAIGN_ID> \
  --chat-id <TELEGRAM_CHAT_ID>"
```

### Check logs:
```bash
ssh hetzner "tail -50 ~/logs/wrong_person_sync_<PROJECT>.log"
```

### Disable cron:
```bash
ssh hetzner "crontab -l | grep -v run_sync_wrong_person_<PROJECT> | crontab -"
```

---

## Telegram chat IDs

| Project | Chat ID |
|---------|---------|
| OnSocial | `7380803777` |
| EasyStaff RU | `345617905` |
| EasyStaff Global | `7563044134` |
| SquareFi | `5857488453` |
| TFP | `496864195` |
| Palark | `406189309` |
| Rizzult | `6223732949` |
| Flintera | `400716548` |
| Admin (all projects) | `57344339` |

---

## Safety

- **Project isolation**: only processes replies where `campaign_name ILIKE '%<PROJECT_NAME>%'`. Other projects are never touched.
- **Idempotent**: `smartlead_synced` flag prevents duplicate sends. Safe to re-run.
- **Read-only on source**: only SELECTs from `processed_replies`, never modifies it.
- **Failure safe**: if the script crashes, leads wait for the next run.
