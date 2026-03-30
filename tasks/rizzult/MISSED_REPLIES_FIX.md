# Missed LinkedIn Replies — Root Cause & Architecture Fix

## Problem
165 LinkedIn replies silently dropped. They exist in GetSales UI but never reach ProcessedReply → Telegram → Sheet.

## Root Cause
The entire reply pipeline assumes every contact has an email. LinkedIn contacts usually don't. The system was built email-first — `lead_email` is `NOT NULL` in the DB, used as the primary identifier for dedup, grouping, display, linking, and notifications.

When a LinkedIn contact replies and has no email, the reply is killed at the gate:
```python
if not lead_email:
    return None  # 165 real replies lost here
```

## Why placeholder emails are wrong
Generating `gs_{uuid}@linkedin.placeholder` is a hack that:
- Pretends LinkedIn contacts have email when they don't
- Creates fake data that confuses operators and client CRM (HubSpot)
- Breaks when we add Telegram outreach (Telegram contacts also have no email)
- Makes the identifier column meaningless — it's not an email, it's a UUID in disguise

## Correct Architecture: channel-agnostic contact identity

A contact can be reached via:
- **Email** → identifier = email address
- **LinkedIn** → identifier = LinkedIn profile URL or GetSales UUID
- **Telegram** (future) → identifier = Telegram user ID

The system needs ONE identifying field per reply that is:
1. Non-null (every reply comes from somewhere)
2. Unique per contact (for dedup and grouping)
3. Human-readable (operator sees it in Telegram notifications and sheet)
4. Channel-appropriate (email for email, LinkedIn URL for LinkedIn)

## What breaks today (full audit)

| Severity | What | Where | Fix needed |
|----------|------|-------|------------|
| BLOCKER | DB rejects NULL email | `ProcessedReply.lead_email` is `nullable=False` | Migration: make nullable |
| BLOCKER | Pydantic schema requires email | `ProcessedReplyBase.lead_email: str` | Change to `Optional[str]` |
| BLOCKER | Both reply paths skip no-email | `reply_processor.py:1221,1909` | Remove guards, use contact UUID as fallback |
| CRITICAL | Dedup unique index includes email | `UNIQUE(lead_email, campaign_id, message_hash)` | Add fallback: use `getsales_lead_uuid` or `linkedin_conversation_uuid` when no email |
| CRITICAL | `DISTINCT ON (lead_email)` collapses all email-less into 1 card | `replies.py:944` group-by-contact | Use `COALESCE(lead_email, getsales_lead_uuid, id::text)` |
| CRITICAL | `quote(None)` crashes Telegram link | `notification_service.py:944` | Guard with `or ""` |
| HIGH | Contact matching fails (15+ places) | `Contact.email == lead_email.lower()` | Add `getsales_lead_uuid` join path |
| HIGH | Follow-up guard fails (NULL != NULL) | `follow_up_service.py:71` | Use `id` or `COALESCE` |
| MEDIUM | Display shows "None" | Notifications, dashboard | Show LinkedIn URL or name instead |

## Implementation Plan

### Phase 1: Stop dropping replies (immediate, deploy today)

**Goal**: All LinkedIn replies get processed regardless of email.

1. **DB migration**: `ALTER TABLE processed_replies ALTER COLUMN lead_email DROP NOT NULL`
2. **Remove skip guards** in `reply_processor.py` — both SmartLead (line 1221) and GetSales (line 1909)
3. **For GetSales replies without email**: populate `lead_email` with the LinkedIn profile URL from the contact (human-readable, unique per person). If no LinkedIn URL, use `contact.first_name contact.last_name` as display + `getsales_lead_uuid` for dedup.
4. **Fix dedup index**: create new unique index `UNIQUE(COALESCE(lead_email, getsales_lead_uuid, id::text), campaign_id, message_hash)` — works whether email exists or not
5. **Fix Telegram notification**: `quote(reply.lead_email or reply.getsales_lead_uuid or "unknown")`
6. **Fix Pydantic schema**: `lead_email: Optional[str] = None`

### Phase 2: Recover dropped replies (same day)

For **Rizzult week 17** (the immediate ask): write missed LinkedIn replies directly to the Google Sheet — no drafts, no Telegram, no ProcessedReply pipeline. Just read from `contact_activities` and append rows to "Replies 09/03" in rizzult_28col format.

For **older replies (165 total across all projects)**: backfill `ProcessedReply` records from `contact_activities` + `webhook_events` data, but with `approval_status = 'auto_resolved'` and `telegram_sent_at = now()` so they DON'T trigger drafts or Telegram notifications. They just exist for the record and sheet sync picks them up normally.

### Phase 3: Contact identity refactor (next sprint)

Replace email-centric identity with channel-agnostic `lead_identifier`:
- Add `lead_identifier` computed column: `COALESCE(lead_email, linkedin_url, getsales_lead_uuid)`
- Migrate all `DISTINCT ON (lead_email)` → `DISTINCT ON (lead_identifier)`
- Migrate all `GROUP BY lead_email` → `GROUP BY lead_identifier`
- UI: show appropriate icon (email icon, LinkedIn icon, Telegram icon) based on identifier type
- Sheet: write LinkedIn URL in email column for LinkedIn-only contacts

### Phase 4: Telegram channel support (future)

When Telegram outreach is added:
- Contact identity already works (just add `telegram_id` to COALESCE chain)
- Reply processing already works (no email guard)
- Sheet sync already works (writes whatever identifier is available)
- Dedup already works (COALESCE-based index)

## Files to modify (Phase 1)

| File | Change |
|------|--------|
| `alembic/versions/NEW_migration.py` | `lead_email` nullable, new dedup index |
| `reply_processor.py:1221,1909` | Remove email skip guards |
| `reply_processor.py:1913` | Use LinkedIn URL as identifier when no email |
| `notification_service.py:944,998,1018` | Null-safe display |
| `schemas/reply.py:136` | `Optional[str]` |
| `replies.py:944` | `COALESCE` in DISTINCT ON |
| `follow_up_service.py:71` | `COALESCE` in correlation |

## Scale
- 65,059 GetSales contacts have no email
- 165 have inbound replies that were dropped
- Affects ALL projects using GetSales LinkedIn outreach
- Will grow as more LinkedIn campaigns run

---

## WHY FIXES DON'T STICK — Root Cause Analysis

### The Pattern: Every Safety Guard Becomes a Data Loss Point

The system has gone through **4 rounds of fixes** since Mar 12. Each fix removes a guard that drops data, then adds a NEW guard to prevent spam from the fix, which then drops NEW data:

| Round | Date | Guard Removed | New Guard Added | New Data Lost |
|-------|------|--------------|-----------------|---------------|
| 1 | Mar 12 | 5 cascading failures (webhooks_enabled, contact.touches, etc.) | None | — |
| 2 | Mar 18 | 1-hour notification cutoff (`403d40b`) | None | — |
| 3 | Mar 19 01:26 | **Death gate** (`if not lead_email: return None`) | **2-hour time guard** on notifications | Replies received >2h before fix was deployed |
| 4 | — | ??? | ??? | ??? |

**Round 3 is why Juan Camilo Millan's reply was missed:**

1. **Mar 18, 15:01 UTC+2** — Juan Camilo replies to Robert Hershberger (Rizzult sender `4cbc70b5`)
2. **Mar 18, 15:01 → Mar 19, 01:26** — Reply arrives via webhook AND polling every 3 min. Death gate drops it EVERY time (Juan Camilo has no email). Webhook event marked `processed=true` (bug A3, also unfixed at this point). Reply permanently lost on webhook path. Polling retries but always fails.
3. **Mar 19, 01:26** — Fix `cfa712d` deployed. Death gate removed.
4. **Mar 19, ~01:30** — Next polling cycle. Death gate gone → ProcessedReply CREATED successfully.
5. **Mar 19, ~01:30** — `send_getsales_notification()` called → checks `received_at` age → **10.5 hours old → 2h time guard BLOCKS the notification** (line 2298-2303 in `reply_processor.py`)
6. **Mar 19, 17:53** — Aleksandra reports "не пришло". Reply EXISTS in DB but she never got Telegram.

### The Deeper Architecture Problem

**There is NO distinction between "old reply just discovered" and "old reply already notified."**

The 2h time guard uses `received_at` (when the LEAD sent the message) instead of `created_at` (when WE first processed it). A reply we just processed for the first time is treated the same as a week-old backfill.

**There is NO monitoring for the gap between "processed" and "notified."**

- `ProcessedReply` exists in DB ✓
- `telegram_sent_at IS NULL` ✗
- Nobody checks this mismatch. The only detection mechanism is an operator manually saying "не пришло."

### All Silent Data Loss Points (Current State)

| Guard | Location | Status | Can Still Drop Data? |
|-------|----------|--------|---------------------|
| ~~Death gate (no email)~~ | reply_processor.py | **REMOVED** (cfa712d) | No |
| ~~1-hour notification cutoff~~ | crm_sync_service.py | **REMOVED** (403d40b) | No |
| ~~Total-count guard~~ | crm_sync_service.py | **REMOVED** (comment says so) | No |
| **2-hour time guard** | reply_processor.py:2298 | **ACTIVE** | **YES — blocks late-processed replies** |
| **Conversation dedup** | crm_sync_service.py:3071 | **ACTIVE** | Yes — caches older messages per conversation, skips forever |
| **Early stop (50 cached)** | crm_sync_service.py:3062 | **ACTIVE** | Yes — stops pagination before reaching new messages |
| **Redis cache** | crm_sync_service.py:3058 | **ACTIVE** | Yes — if message wrongly cached, permanently skipped |
| **no_contact skip** | crm_sync_service.py:3093 | **ACTIVE** | Yes — if contact not synced, reply skipped every cycle |
| **Sheet sync email filter** | sheet_sync_service.py:183 | **ACTIVE** (Phase 2) | Yes — NULL email replies excluded from sheet |

### What MUST Change

**1. The 2h time guard must use `created_at`, not `received_at`:**
```python
# WRONG (current) — blocks newly-processed old replies:
age = datetime.utcnow() - processed_reply.received_at

# RIGHT — only blocks if we already processed it long ago:
age = datetime.utcnow() - processed_reply.created_at
```
If we JUST created the ProcessedReply, `created_at` is NOW → age ≈ 0 → notification SENT regardless of when the lead originally replied.

**2. Add a notification watchdog** — every 5 min, find:
```sql
SELECT * FROM processed_replies
WHERE telegram_sent_at IS NULL
  AND created_at > NOW() - INTERVAL '30 minutes'
  AND notification_attempts < 3;
```
This catches any reply that slipped through ALL guards.

**3. Log every skip as a WARNING, not INFO** — every `return None`, `continue`, `skip` in the pipeline should produce a WARNING-level log with the lead name + message snippet, so failures are VISIBLE in monitoring.

---

## Incident Log

### 2026-03-19: Juan Camilo Millan reply missed (Rizzult)
- **Reported by**: Aleksandra (operator), 5:53 PM — "не пришло"
- **Lead**: Juan Camilo Millan
- **Sender (our SDR)**: Robert Hershberger (UUID `4cbc70b5`, Rizzult)
- **Reply date**: 18 Mar 2026, 15:01
- **Message** (Spanish): "Hola ya no trabajo ahí y segundo esa empresa es muy cerrada. Y tienen sus propios modelos de IA para que sepas. Y no te desgastes es una multinacional demasiado grande"
- **Translation**: "I don't work there anymore, and that company is very closed. They have their own AI models FYI. Don't waste your effort, it's a multinational that's too large."
- **Category**: Wrong Person / Not Interested
- **Root cause**: Reply received BEFORE fix `cfa712d` was deployed → death gate dropped it → fix deployed 10.5h later → polling processed it → **2h time guard blocked the notification** → ProcessedReply likely exists in DB but `telegram_sent_at IS NULL`
- **Note**: Juan Camilo was already one of the 8 backfilled replies (PR 40504) for an OLDER message. This is a NEW second reply from the same lead, also missed.
- **Fix needed**: Change time guard from `received_at` to `created_at` (see analysis above)
