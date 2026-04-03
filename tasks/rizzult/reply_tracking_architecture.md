# Rizzult Reply Tracking — Architecture & Incident History

## Project Setup (DB: project_id=22)

- **Platform**: GetSales (LinkedIn DMs) + SmartLead (email campaigns)
- **Telegram operator**: chat_id `6223732949` (compact format with channel indicator)
- **Google Sheet**: `1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s` (replies tab)
- **Campaign matching**: `campaign_ownership_rules.prefixes` includes "rizzult", SmartLead tag "Aleksandra"
- **webhooks_enabled**: `true` (was `false` — root cause of Mar 12 incident)

### GetSales LinkedIn Senders
| Name | Sender UUID | Messenger URL |
|------|-------------|---------------|
| Pavel Medvedev | `29fd2e4e-d218-4ddc-b733-630e68a98124` | [link](https://amazing.getsales.io/messenger/c96f1be4-32e8-4636-a853-8677fde9d656?senderProfileId=%2229fd2e4e-d218-4ddc-b733-630e68a98124%22) |
| Elena Shamaeva | `91fb80ab-4430-4b07-bc19-330d3f4ac8fd` | [link](https://amazing.getsales.io/messenger/c96f1be4-32e8-4636-a853-8677fde9d656?senderProfileId=%2291fb80ab-4430-4b07-bc19-330d3f4ac8fd%22) |
| Daniel Rew | `41b709f2-6d25-46cc-91a5-7f15ce84f5a7` | [link](https://amazing.getsales.io/messenger/c96f1be4-32e8-4636-a853-8677fde9d656?senderProfileId=%2241b709f2-6d25-46cc-91a5-7f15ce84f5a7%22) |
| Elena Pugovishnikova | `2529a3dd-0dd1-4fc5-b4f3-7fdae203e454` | [link](https://amazing.getsales.io/messenger/c96f1be4-32e8-4636-a853-8677fde9d656?senderProfileId=%222529a3dd-0dd1-4fc5-b4f3-7fdae203e454%22) |
| Lisa Woodard | `94aeceb5-12ca-4ed6-92ac-18ed4b3d937f` | [link](https://amazing.getsales.io/messenger/c96f1be4-32e8-4636-a853-8677fde9d656?senderProfileId=%2294aeceb5-12ca-4ed6-92ac-18ed4b3d937f%22) |
| Robert Hershberger | `4cbc70b5-4fb6-4a76-9088-f50a4ef096e7` | [link](https://amazing.getsales.io/messenger/c96f1be4-32e8-4636-a853-8677fde9d656?senderProfileId=%224cbc70b5-4fb6-4a76-9088-f50a4ef096e7%22) |

---

## How Reply Tracking Works (4 Paths)

### Path 1: SmartLead Webhook (real-time email)
```
SmartLead → POST /api/crm-sync/webhook/smartlead
  → WebhookEventModel stored (event_type="EMAIL_REPLY")
  → process_reply_webhook() creates ProcessedReply + Gemini draft
  → session.commit()
  → Telegram notification sent (after commit)
  → Sheet sync picks up on next cycle
```
- Self-contained: manages its own session/commit/rollback
- Recovery: event_recovery loop retries unprocessed events (5min backoff)

### Path 2: SmartLead Polling (every 3 min, catches missed webhooks)
```
CRM Scheduler → _sl_sync() with own session
  → sync_smartlead_replies() iterates all enabled campaigns
  → For each campaign: fetch replies from SmartLead API
  → Dedup: checks (lead_email, message_hash) in processed_replies
  → process_reply_webhook() for new replies
  → Telegram notification + sheet sync after commit
```
- Runs in parallel with GetSales sync (separate sessions via asyncio.gather)
- 369+ campaigns checked per cycle

### Path 3: GetSales Webhook (real-time LinkedIn)
```
GetSales → POST /api/crm-sync/webhook/getsales
  → WebhookEventModel stored (event_type="linkedin_inbox")
  → Contact lookup by UUID/email/LinkedIn URL
  → ContactActivity created
  → begin_nested() savepoint:
    → process_getsales_reply() creates ProcessedReply + Gemini draft
  → session.commit() (webhook_event + contact + activity always survive)
  → Telegram notification sent (after commit)
```
- Savepoint isolates process_getsales_reply failures from the rest
- Recovery: event_recovery loop now includes "linkedin_inbox" events

### Path 4: GetSales Polling (every 3 min, catches missed webhooks)
```
CRM Scheduler → _gs_sync() with own session
  → sync_getsales_replies() polls GetSales inbox API
  → For each message: resolve contact, check dedup
  → begin_nested() savepoint:
    → process_getsales_reply() creates ProcessedReply + Gemini draft
  → Post-commit: batch Telegram notifications
```
- Runs in parallel with SmartLead sync
- Uses webhook_events table as fallback for campaign name resolution

---

## Telegram Notification Format (Rizzult-specific)

Rizzult project 22 has `telegram_notification_config.compact = true`.

Compact format includes channel indicator:
- LinkedIn replies: `💼 LinkedIn · 🔵 <b>{category}</b>`
- Email replies: `📧 Email · 🔵 <b>{category}</b>`

Operator requested this (Mar 12): "формат супер, добавь плиз в начале Линкедин или Емейл чтобы знать куда бежать"

Each notification includes "Open in Replies UI" deep link with `?project=rizzult` param.

---

## Google Sheet Sync

- Runs after each reply sync cycle
- Filters: `ProcessedReply.campaign_name IN project.campaign_filters`, `received_at > last_replies_sync_at`, excludes OOO
- Dedup: reads ALL existing emails from sheet, checks both exact email AND username (local part before @)
- Only NEW replies since last sync timestamp are appended — no historical backfill

---

## Mar 12, 2026 — LinkedIn Tracking Incident

### Timeline

**~1:00 AM** — Operator reports: Rizzult LinkedIn replies are not being tracked. Zero Telegram notifications received.

**Root cause investigation** revealed 5 cascading failures:

#### Failure 1: `webhooks_enabled = false`
- Rizzult project (id=22) had `webhooks_enabled` flag set to `false` in DB
- All GetSales webhook events were silently skipped: "webhooks disabled for project"
- The `_disabled_cache` has 60s TTL, so even after DB fix, had to wait for cache expiry
- **Fix**: `UPDATE projects SET webhooks_enabled = true WHERE id = 22`

#### Failure 2: `AttributeError: 'Contact' object has no attribute 'touches'`
- GetSales webhook handler at line 1245 tried to access `contact.touches`
- This attribute doesn't exist on the Contact model (tracked via ContactActivity instead)
- Crashed AFTER ProcessedReply INSERT but BEFORE `session.commit()`
- **Result**: INSERT rolled back, reply lost, no Telegram notification
- **Fix**: Removed 20 lines of dead code referencing contact.touches

#### Failure 3: `AttributeError: 'Contact' object has no attribute 'campaigns'`
- Same handler at line 1267 tried `parse_campaigns(contact.campaigns)`
- `campaigns` is a Project relationship, not a Contact attribute
- Same crash pattern: PR created then lost on rollback
- **Fix**: Removed 14 lines of broken campaigns enrichment code

#### Failure 4: `NameError: 'pr' not defined`
- If `process_getsales_reply` threw an exception, `pr` was never assigned
- Line 1301 `if is_reply and pr:` would crash with NameError
- **Fix**: Added `pr = None` initialization before the try block

#### Failure 5: No recovery mechanism for GetSales events
- The event recovery loop only filtered for SmartLead event types: `["EMAIL_REPLY", "lead.replied", "email.replied", "reply"]`
- GetSales events stored as `linkedin_inbox` were never retried
- **Fix**: Added `"linkedin_inbox"` to recovery loop filter + `_reprocess_getsales_event()` method

### Verification
- Replayed webhook event 97862 (Taras Malyshev, RIzzult global QSR 08 03)
- ProcessedReply 38513 created successfully
- Telegram sent to both admin (57344339) and Rizzult operator (6223732949)
- 59 missed webhook events existed in webhook_events table

---

## Architecture Hardening (Mar 12, 2026)

### Fix 1: Savepoint isolation in GetSales webhook handler
**File**: `backend/app/api/crm_sync.py`

Previously, if `process_getsales_reply()` failed (AI timeout, DB error, etc.), the session entered an error state. The subsequent `session.commit()` at line 1262 would hit `PendingRollbackError`, losing EVERYTHING: the webhook_event record, contact updates, activity — not just the ProcessedReply.

Now: `process_getsales_reply()` runs inside `session.begin_nested()` savepoint. If it fails, only the savepoint rolls back. The webhook_event gets marked `processed=True`, contact activity is preserved, and the commit succeeds.

### Fix 2: GetSales event recovery
**File**: `backend/app/services/crm_scheduler.py`

Added `"linkedin_inbox"` to the event_type filter in `_recover_events()`. Created `_reprocess_getsales_event()` method that:
1. Parses the stored webhook payload
2. Finds the contact by UUID or email
3. Calls `process_getsales_reply()` inside a savepoint
4. Sends Telegram notification after commit

Recovery uses exponential backoff: 5min → 15min → 45min → 2h → 6h (max 5 retries per event).

### Fix 3: GetSales duplicate handling
**File**: `backend/app/services/reply_processor.py`

In `process_getsales_reply()`, when a duplicate is detected (unique constraint violation on `(lead_email, campaign_id, message_hash)`), the code previously called `await session.rollback()`. Inside a `begin_nested()` savepoint (polling path), this corrupted the ENTIRE outer session, killing the whole batch.

Now: re-raises the exception instead of calling rollback. The caller's `begin_nested()` context manager handles the savepoint rollback automatically.

### Fix 4: Parallel SmartLead + GetSales sync
**File**: `backend/app/services/crm_scheduler.py`

Previously, SmartLead and GetSales reply syncs ran sequentially in the same session. SmartLead checked 369+ campaigns (~30+ min), completely blocking GetSales sync.

Now: `asyncio.gather(_sl_sync(), _gs_sync())` runs both in parallel with separate sessions. GetSales replies arrive within seconds of the polling cycle, not after SmartLead finishes.

### Fix 5: Channel indicator in Telegram
**File**: `backend/app/services/notification_service.py`

Added `💼 LinkedIn` / `📧 Email` prefix to compact Telegram notifications. Only affects projects with `telegram_notification_config.compact = true` (currently only Rizzult project 22).

---

## Current State (post-fix)

| Component | Status | Notes |
|-----------|--------|-------|
| GetSales webhooks | Working | Savepoint-protected, recovery-enabled |
| GetSales polling | Working | Parallel with SmartLead, separate session |
| SmartLead webhooks | Working | Was always working for Rizzult |
| SmartLead polling | Working | Parallel with GetSales |
| Telegram notifications | Working | Compact format with channel indicator |
| Google Sheet sync | Working | New replies only, dedup by email+hash |
| Event recovery | Working | Covers both SmartLead AND GetSales events |
| Gemini AI drafts | Working | Generated at detection time for new replies |

### Data flow guarantee
```
New reply arrives (webhook or poll)
  → ProcessedReply created with AI draft
  → Telegram notification (after commit, no ghost notifications)
  → Google Sheet append (next sync cycle, dedup prevents duplicates)
  → No historical backfill, no old data spam
```

### What can still fail (acknowledged risks)
- **Gemini AI timeout** (3+ min): savepoint catches it, webhook_event still commits, recovery retries later
- **GetSales API downtime**: polling skips cycle, webhooks still work independently
- **SmartLead "Plan expired!" intermittent errors**: usually self-recovers, polling retries next cycle

---

## Mar 12, 2026 — Architecture Hardening (Wave 2)

### Fix 6: SmartLead polling savepoint isolation
**File**: `backend/app/services/crm_sync_service.py` (sync_smartlead_replies)

Previously, `process_reply_webhook()` called `session.rollback()` on duplicate detection.
In the polling path (shared session across all campaigns), this rolled back the ENTIRE
transaction — silently deleting ALL previously-processed replies from the same cycle.

Now:
- `process_reply_webhook()` re-raises on duplicate (same pattern as `process_getsales_reply()`)
- Polling path wraps each call in `session.begin_nested()` (savepoint)
- Duplicates caught by savepoint — other replies survive
- Webhook path catches the re-raise and marks event as processed (no infinite retry)
- Recovery loop catches duplicates and marks events as processed

### Fix 7: SmartLead analytics guard counter timing
**File**: `backend/app/services/crm_sync_service.py` (sync_smartlead_replies)

Previously, `sl_reply_count` was updated BEFORE processing individual leads.
If any lead processing failed, the count already matched SmartLead's total,
so next cycle skipped the campaign entirely. That reply was permanently lost.

Now: `sl_reply_count` is updated AFTER processing all leads, and ONLY if zero
errors occurred for that campaign. Failed processing keeps the old count,
ensuring the next cycle re-checks the campaign.

### Fix 8: GetSales polling safety margins
**File**: `backend/app/services/crm_sync_service.py` (sync_getsales_replies)

- `max_age_hours`: 48h → 168h (7 days). Wider fallback window for recovery.
- `early_stop_threshold`: 20 → 50. Prevents premature stops during reply bursts.

### Timing estimates (steady state)

| Path | Interval | Latency | Notes |
|------|----------|---------|-------|
| SmartLead webhook | Real-time | ~5s | Fires async, own session |
| GetSales webhook | Real-time | ~5s | Savepoint-protected |
| SmartLead polling | 3-10 min | ~30min/cycle | 369+ campaigns × 0.2s + per-lead API |
| GetSales polling | 3-10 min | ~2s/cycle | 1 inbox API call, paginated |
| Event recovery | 5 min | immediate | Exponential backoff per event |
| Watchdog | 60s | immediate | Resurrects dead tasks |

### Bottleneck analysis

1. **SmartLead polling is the slowest path** (~30min per cycle for 369 campaigns).
   Mitigated by: analytics guard (skip unchanged campaigns), webhooks as primary path.
2. **Gemini AI draft generation** (~3-5s per reply). Non-blocking — runs inside savepoint.
3. **SmartLead `get_lead_by_email_global`** API call per NEW lead in polling (0.3s rate limit).
   Only called for leads not already in DB. Most leads are cached after first sync.

### Worst-case scenarios

| Scenario | Max latency to detect reply | Recovery mechanism |
|----------|---------------------------|-------------------|
| Both webhook + polling working | Real-time (webhook) | N/A |
| Webhook fails, polling works | 3-10 min (next poll) | Polling catches it |
| Both fail, event stored | 5 min (recovery loop) | Event recovery retries |
| Event recovery fails 5x | 24h (event cutoff) | GetSales: 7-day polling window |
| All paths fail | Manual replay | `webhook_events` table stores raw payload |

---

## Mar 12, 2026 — Transaction Durability (Wave 3)

### Fix 9: Per-reply commit in GetSales polling
**File**: `backend/app/services/crm_sync_service.py` (sync_getsales_replies)

Previously, the entire GetSales inbox scan (23,329 messages, up to 10 pages of 100) ran in ONE transaction,
only committing at the very end. Each new reply takes ~30s for Gemini AI draft generation. With 30+ new
replies per page, the transaction was open 15-20 minutes. Frequent container restarts (other deploys) killed
every cycle before the commit, losing ALL work. ProcessedReply IDs 38640-38671 were consumed across
multiple aborted cycles but never persisted — sequence gaps from rolled-back transactions.

Now: each ProcessedReply is committed IMMEDIATELY after creation + AI draft:
1. `session.begin_nested()` savepoint wraps `process_getsales_reply()`
2. On success: `await session.commit()` + `bulk_add_replies("getsales", [message_id])` to Redis cache
3. On failure: savepoint rolls back, message_id cached to skip next cycle
4. Result: each reply durable within seconds, container restarts lose at most 1 in-flight reply

### Fix 10: GetSales notification time guard
**File**: `backend/app/services/crm_sync_service.py` (sync_getsales_replies)

The 7-day polling window (`max_age_hours=168`) means the catch-up phase processes old replies.
Previously, each would trigger a Telegram notification to the operator — spamming 30+ old replies.

Now: `_notif_cutoff = datetime.utcnow() - timedelta(hours=1)`. Replies with `received_at` older
than 1 hour are silently processed (PR created, cached) but no Telegram notification sent.
Stats track `skipped_old_notif` count.

SmartLead polling already had this guard (lines 1616-1630 in reply_processor.py: skip > 2 hours).
GetSales was the missing path.

### Fix 11: Redis cache backfill on startup
**File**: `backend/app/services/crm_scheduler.py`

On container restart, Redis loses all cached message IDs. The cache service backfills from recent
ProcessedReplies on startup (`getsales: 13` entries recovered after latest restart). This prevents
re-processing already-committed replies after a restart.

### Catch-up verification (post-deploy)

Container restarted 5+ times during catch-up. Zero data lost:
- 9 GetSales ProcessedReplies committed (PRs 38701-38709+)
- 2 are Rizzult-specific: PR 38702 (`rizzult big 5 media 08 03 part 2 - sr`), PR 38703 (`RIzzult Farmacies 14 02 26`)
- Redis cache grew from 9 → 13 entries across restarts
- Per-reply SAVEPOINT/RELEASE/COMMIT cycles visible in logs every few seconds
- No old Telegram notifications sent (time guard working)

### Transaction durability comparison

| Pattern | Commit frequency | Max data loss on restart | Catch-up time |
|---------|-----------------|------------------------|---------------|
| End-of-cycle (old) | Every 15-20 min | ALL replies in cycle | Never completes |
| Per-page (intermediate) | Every 5+ min | All replies on current page | ~10 cycles |
| **Per-reply (current)** | **Every ~30s** | **1 in-flight reply** | **Steady progress** |
