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

### 2026-03-17: Sheet Missing Replies + Reaction Noise + Recovery Mess

**Symptom**: Aleksandra reported Google Sheet "Replies 09/03" missing week 17 replies. Sheet had 583 rows but DB had 1,056 non-OOO replies.

**Root causes found**:

1. **No `leads_tab` in config → "Leads" default → nonexistent tab → error every 5min**
   - `sheet_sync_service.py` had `config.get("leads_tab", "Leads")` — hardcoded default
   - Rizzult sheet has no "Leads" tab (uses HubSpot instead)
   - `push_leads_to_sheet()` and `poll_qualification_from_sheet()` threw `Unable to parse range: 'Leads'` every 5min cycle
   - This did NOT block reply sync (separate function) but generated error noise and poisoned session in some edge cases

2. **LinkedIn 👍 reaction treated as real reply**
   - Sofia Fornera's 👍 reaction → classified as "interested" → synced to sheet row 583 → noise for operator
   - GetSales API sends LinkedIn reactions as regular messages with no type distinction

3. **JSON `null` vs SQL `NULL` in `campaign_filters`**
   - Projects 6, 7, 49 had `campaign_filters = 'null'::jsonb` (JSON null, not SQL NULL)
   - `jsonb_array_elements_text(null)` → "cannot extract elements from a scalar"
   - This broke ALL GetSales reply processing (project lookup query scans all projects)
   - Error cascaded: poisoned transaction → webhook processing failures → retry exhaustion

4. **473 replies marked as synced but never written to sheet**
   - The DB had `sheet_synced_at` set for ALL 1,056 non-OOO replies, but only 583 were actually in the sheet
   - Root cause unclear — likely a past bug where `sheet_synced_at` was set before confirming the Google Sheets API write succeeded, or a batch write partially failed

**Fixes applied**:

| Fix | What | Where |
|-----|------|-------|
| Code | Removed default "Leads" fallback — skip when `leads_tab` absent | `sheet_sync_service.py:661,855`, `contacts.py:2302,2356` |
| Code | Added emoji-only message filter for LinkedIn reactions | `reply_processor.py:1910` |
| DB | `UPDATE projects SET campaign_filters = NULL WHERE id IN (6,7,49)` | One-time fix |
| DB | Auto-resolved noisy reply 40088 (👍 reaction) | One-time fix |

**Recovery errors (self-inflicted during fix)**:

| Mistake | Impact | Lesson |
|---------|--------|--------|
| Mass-reset ALL `sheet_synced_at` (1,057 rows) without stopping scheduler first | Scheduler ran mid-reset, pushed ~480 duplicate rows to sheet | **ALWAYS stop the scheduler before bulk-resetting sync flags** |
| Used `received_at < '2026-03-10'` as cutoff instead of calculating week 17 dates first | Re-marked wrong rows, left gaps | **Calculate the week epoch dates BEFORE writing SQL** |
| Triggered manual sync without checking what the scheduler had already pushed | Created 13 more rows on top of scheduler's duplicates | **Check current sheet state before triggering sync** |
| First dedup used WRONG column indices: col 6=last_name (not email), col 19=category (not campaign) | Removed 101 rows using (last_name, datetime, category) as key — deleted legitimate week 17 replies | **ALWAYS verify column indices against `_build_rizzult_rows()` before any sheet manipulation** |
| Second dedup correct but left 382 dateless legacy rows sorting AFTER dated rows | Week 17 rows buried in the middle (row 544), legacy at bottom (row 559+) — operator scrolls to bottom and sees only week 16 | **Legacy dateless rows must come FIRST, dated rows AFTER, so newest weeks are always at the bottom** |
| Typo in Python variable name (`legacy_count` instead of `len(legacy)`) wasted another round | Simple bug in one-off script caused crash | **Test scripts locally before running on production** |

**Correct column mapping for rizzult_28col** (from `_build_rizzult_rows`):

| Index | Column | Field | Notes |
|-------|--------|-------|-------|
| 0 | A | index | Sequential, auto-generated |
| 1 | B | updated email | Operator fills manually |
| 2 | C | status | Legacy, unused |
| 3 | D | current status | Operator fills manually |
| 4 | E | (blank) | |
| 5 | F | first name | Auto |
| 6 | G | last name | Auto |
| 7 | H | Position | Auto |
| 8 | I | Linkedin | Auto |
| **9** | **J** | **target_lead_email** | **DEDUP KEY 1** |
| 10 | K | segment | Auto |
| 11 | L | Company | Auto |
| 12 | M | Website | Auto |
| 13 | N | Company Location | Auto |
| 14 | O | Employees | Auto |
| 15 | P | text | Reply text, auto |
| 16 | Q | time | `dd.mm.yyyy HH:MM` format |
| **17** | **R** | **campaign** | **DEDUP KEY 3** |
| 18 | S | campaign_id | Auto |
| 19 | T | category | Auto (classification result) |
| 20 | U | from_email | Auto |
| 21 | V | to_email | Auto |
| **22** | **W** | **created time (ISO)** | **DEDUP KEY 2, sort key, week calc source** |
| 23 | X | Source | "Email" or "LinkedIn" |
| 24 | Y | Status | Operator fills manually |
| 25 | Z | Week | Calculated: `(received_at - epoch).days // 7 + 1` |
| 26 | AA | Sequence + message | Operator fills |
| 27 | AB | Comment | Operator fills |
| 28 | AC | auto_updated_at | ISO timestamp of last sync |

**Sheet row ordering rule**: Legacy dateless rows (382 from N8N era, no col W) come FIRST. Dated rows sorted chronologically AFTER. This ensures the newest week is always at the bottom where the operator looks.

**Recovery actions**:

1. First dedup (WRONG cols 6,19,22): 1,076 → removed 101 → 974. Killed week 17 rows.
2. Second dedup (CORRECT cols 9,22,17): 975 → removed 34 → 941. Week 17 present but buried at row 544 behind 382 dateless legacy rows.
3. Reordered: legacy (382) first, then dated (560) chronologically. Week 17 now at rows 926-940, right after week 16.
4. Updated DB config to match.

**Final state**: Sheet has 942 rows. 382 legacy (dateless) + 560 dated. Week 17 (Mar 16-22) = **15 replies at rows 926-940**, directly after week 16 at the bottom of the sheet.

**Prevention rules for future**:
- **NEVER mass-reset `sheet_synced_at` while scheduler is running** — stop scheduler first or use a maintenance window
- **NEVER use hardcoded default tab names** — every project must explicitly configure tabs it uses, absent = skip
- **ALWAYS calculate dates from week_epoch before operating on week-based data**
- **The `_chronological_merge_write` function does NOT dedup** — it combines and sorts, duplicates pass through
- **`sheet_synced_at` is the ONLY dedup mechanism** — if it lies, the system has no backup protection

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
