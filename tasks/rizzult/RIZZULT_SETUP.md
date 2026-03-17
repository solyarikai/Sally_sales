# Rizzult Project — Complete Reference

## Identity
- **Project ID**: 22
- **Sender**: Pavel Medvedev, Cofundador, Rizzult
- **Operator**: Aleksandra (Telegram chat: `6223732949`)
- **Reply Template ID**: 454 ("Rizzult - Auto-Reply")
- **Languages**: Spanish (primary), English, Portuguese

## Platforms

### GetSales (LinkedIn DMs)
Six LinkedIn sender accounts:

| Sender | UUID |
|--------|------|
| Pavel Medvedev | `29fd2e4e-d218-4ddc-b733-630e68a98124` |
| Elena Shamaeva | `91fb80ab-4430-4b07-bc19-330d3f4ac8fd` |
| Daniel Rew | `41b709f2-6d25-46cc-91a5-7f15ce84f5a7` |
| Elena Pugovishnikova | `2529a3dd-0dd1-4fc5-b4f3-7fdae203e454` |
| Lisa Woodard | `94aeceb5-12ca-4ed6-92ac-18ed4b3d937f` |
| Robert Hershberger | `4cbc70b5-4fb6-4a76-9088-f50a4ef096e7` |

### SmartLead (Email)
- Tag: `Aleksandra` — all Rizzult email campaigns carry this tag
- ~57 campaigns in `campaign_filters`

### Campaign Routing
```json
{
  "campaign_ownership_rules": {
    "prefixes": ["rizzult"],
    "contains": ["rizzult"],
    "smartlead_tags": ["Aleksandra"]
  }
}
```

## Google Sheet Sync

### Target Sheet
- **Sheet ID**: `1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s`
- **URL**: https://docs.google.com/spreadsheets/d/1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s/edit
- **Replies tab**: `Replies 09/03` (gid=384779363) — ALL synced replies go here
- **Reference tab**: `Replies 10.02` — read-only, original N8N-era data
- **NO "Leads" tab** — Rizzult does NOT use the leads push feature. Client has HubSpot.

### Sheet Config (DB `sheet_sync_config`)
```json
{
  "enabled": true,
  "sheet_id": "1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s",
  "row_format": "rizzult_28col",
  "week_epoch": "2025-11-24",
  "exclude_ooo": true,
  "replies_tab": "Replies 09/03",
  "reference_tab": "Replies 10.02"
}
```

**CRITICAL**: No `leads_tab` key. This is intentional — Rizzult does NOT use the system's Leads tab feature. The `push_leads_to_sheet()` and `poll_qualification_from_sheet()` functions skip when `leads_tab` is absent.

### Row Format: `rizzult_28col` (29 columns A-AC)
| Col | Field | Auto-filled | Notes |
|-----|-------|-------------|-------|
| A | Index | Yes | Sequential number |
| B | First Name | Yes | From contact |
| C | Last Name | Yes | From contact |
| D | Status (external) | Yes | Maps to client-facing status |
| E | Position | Yes | Job title |
| F-G | LinkedIn / Email | Yes | Contact info |
| H | Company | Yes | From contact |
| I-J | Website / Domain | Yes | |
| K | Company Location | Yes | |
| L | Employees | Yes | Company size |
| M | Reply Text | Yes | The actual reply content |
| N | Date/Time | Yes | `received_at` |
| O | Campaign | Yes | Campaign name |
| P | Campaign ID | Yes | |
| Q | Source | Yes | "Email" or "LinkedIn" |
| R | Category | Yes | Classification result |
| S | Week | Yes | Calculated from `week_epoch` |
| T | Sequence + Message | No | Operator fills |
| U | Comment | No | Operator fills |
| V-AC | Reserved | No | Operator/client columns |

### Operator Sheet Rules (from bugs/index)
- **Email field**: NOT auto-filled — operator fills manually
- **Current status**: filled by operator based on communication channel
- **Index column**: needed for chronological sort restoration after filtering

## Reply Processing

### 4 Paths
1. **SmartLead Webhook** — real-time email replies
2. **SmartLead Polling** — every 3 min, catches missed webhooks
3. **GetSales Webhook** — real-time LinkedIn DMs (savepoint-protected)
4. **GetSales Polling** — every 3 min, parallel with SmartLead

### Classification
- GPT-4o-mini for classification (fast, cheap)
- LinkedIn-specific prompt suffix added
- Project-specific classification prompt if configured

### Draft Generation
- Gemini 2.5 Pro (default) for draft replies
- LinkedIn drafts: SHORT (2-3 sentences), no signature, no em-dashes
- Calendly slots auto-injected for `meeting_request`/`interested`
- Reference examples loaded from `reference_examples` table

### LinkedIn Reaction Filter (added 2026-03-17)
- Single-emoji messages (👍, 👎, etc.) are LinkedIn reactions, NOT real replies
- Filtered out in `process_getsales_reply()` before classification
- Prevents noise in operator queue and sheet

## Telegram Notifications

### Format
```
💼 LinkedIn · 🟢 interested
👤 Sofia Fornera (ACME Corp)
📧 sofi@acme.com
💬 "Me interesa..."
🔗 [Open in GetSales] [Open in Replies UI]
```

### Operator Preferences (from tg_feedback)
- Wants BOLD headers to distinguish notifications
- Color badges: green=positive, yellow=OOO, red=negative
- Minimal fields: name, email, status, reply text
- "I need to spot 1 positive message among all the OOOs"

## Client Integration

### HubSpot Export
Statuses that trigger export:
- Interested
- Meeting Booked
- Positive
- Talks To Team
- Qualified Lead

For contacts without email: generate fake as `fake` + 2 chars from first name + 2 from last name.

### External Status Mapping
Internal statuses → client-facing statuses via `external_status_config` on project.

## Calendly (NOT YET IMPLEMENTED)
Two sales team members with Calendly:
- **Juan** — PAT token in `tasks/rizzult/index.md`
- **Pavel** — PAT token in `tasks/rizzult/index.md`

Planned: show scheduled calls in Godpanel (like easystaff ru).

## Incident History

### 2026-03-12: LinkedIn Reply Tracking Failure
5 cascading failures discovered and fixed in 11 waves:
1. `webhooks_enabled = false` on project 22
2. `AttributeError: 'Contact' object has no attribute 'touches'`
3. `AttributeError: 'Contact' object has no attribute 'campaigns'`
4. `NameError: 'pr' not defined`
5. No GetSales event recovery (only SmartLead events retried)

Result: savepoint isolation, per-reply commits, parallel sync, channel indicators, 7-day safety window.

### 2026-03-17: Sheet Missing Replies + Reaction Noise
**Root causes**:
1. No `leads_tab` in config → code defaulted to "Leads" → nonexistent tab → error every 5min cycle
2. LinkedIn 👍 reaction from Sofia Fornera classified as "interested" → noise row in sheet

**Fixes applied**:
1. Removed default "Leads" fallback — `push_leads_to_sheet()` and `poll_qualification_from_sheet()` now skip when `leads_tab` absent
2. Added emoji-only message filter in `process_getsales_reply()`
3. Fixed JSON null vs SQL NULL in `campaign_filters` for projects 6, 7, 49 (was breaking all GetSales processing)

## Key Files
- `tasks/rizzult/index.md` — operator workflow, sender accounts, Calendly tokens
- `tasks/rizzult/reply_tracking_architecture.md` — 4 reply paths, incident timeline, architecture hardening
- `tasks/rizzult/godpanel.md` — Calendly integration task (pending)
- `tasks/rizzult/bugs/index/index.md` — operator sheet format feedback
- `tasks/rizzult/tg_feedback/` — Telegram notification UI feedback
- `backend/app/services/reply_processor.py` — classification, drafts, GetSales/SmartLead processing
- `backend/app/services/sheet_sync_service.py` — Google Sheet bidirectional sync
- `backend/app/services/crm_scheduler.py` — scheduler loops (sheet sync every 5min)
- `backend/alembic/versions/202603090400_rizzult_sheet_sync.py` — initial sheet config migration
