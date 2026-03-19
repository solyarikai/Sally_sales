# Reply Processing Architecture — Full Incident Report & Fix Log

**Created**: 2026-03-18
**Last updated**: 2026-03-19 00:40 (Phase 1 deployed + backfill complete)
**Status**: Phase 1 DEPLOYED. 8 Rizzult week 17 replies recovered. Monitoring.

---

## TL;DR — What Happened and What Was Done

The reply pipeline had an `if not lead_email: return None` gate that silently dropped **149 LinkedIn replies** since March 1 across 10 projects. 65,059 GetSales contacts (33%) have no email. On top of that, notification routing depended on campaign name (often empty from polling), so even when replies WERE processed, Aleksandra's Telegram didn't get them.

**Fixed on 2026-03-18 23:30 UTC** (commit `cfa712d`):
- Death gate removed. Replies processed regardless of email.
- `lead_email` made nullable in DB (migration `g1_channel_agnostic`).
- Sender UUID promoted to PRIMARY routing signal (was last-resort fallback).
- 2-hour time guard added to prevent old reply notification spam.
- Webhook events no longer marked `processed=true` when reply creation fails.
- 8 Rizzult week 17 dropped replies recovered via backfill script.

---

## Part 1: Complete Issue Catalog

### Category A: REPLY DROPS — Data Silently Lost

#### A1. Death Gate in process_getsales_reply — FIXED
- **File**: `reply_processor.py:1909` (old line number, removed)
- **Code was**: `if not lead_email: return None`
- **Impact**: 149 replies lost since March 1. 7/day average. Both webhook AND polling paths used the same function.
- **Confirmed in production logs**: 7 drops on Mar 18 alone (Katya Anamaria, Ian D., Flavia Adriasola, Juan Camilo Millan, etc.)
- **Fix**: Removed the guard entirely. `lead_email` is now `None` for no-email contacts — system processes the reply regardless.
- **Commit**: `cfa712d`

#### A2. Death Gate in SmartLead webhook path — FIXED
- **File**: `reply_processor.py:1221` (old line number, removed)
- **Code was**: `if not lead_email: return None`
- **Fix**: Removed. Future-proofing for non-email channels.
- **Commit**: `cfa712d`

#### A3. Webhook event marked processed=true even when reply dropped — FIXED
- **File**: `crm_sync.py:1262`
- **Code was**: `webhook_event.processed = True` ran unconditionally
- **Impact**: Reply dropped by death gate, but webhook_event marked "done" — no retry possible, data permanently lost.
- **Fix**: `if not is_reply or pr:` — only mark processed if ProcessedReply was actually created. Non-reply events (connection requests) always marked processed.
- **Commit**: `cfa712d`

#### A4. Sheet sync silently drops NULL-email replies — REMAINING (Phase 2)
- **File**: `sheet_sync_service.py:183`
- **Code**: `emails = list({r.lead_email.lower() for r in replies if r.lead_email})`
- **Impact**: LinkedIn-only replies filtered out of sheet sync. Currently mitigated because backfill set `sheet_synced_at=NULL` for Rizzult week 17 specifically, so scheduler picks them up by received_at, not by email.
- **Status**: Works for now. Full fix in Phase 2.

---

### Category B: NOTIFICATION FAILURES — Reply Exists but Operator Not Notified

#### B1. Empty campaign → no project → no subscriber notification — FIXED
- **File**: `notification_service.py:1088-1094`
- **Impact**: Empty campaign_name → `_get_project_for_campaign("")` returns None → subscriber loop skipped → Aleksandra gets nothing
- **Fix**: Added sender UUID as third routing fallback in `notify_linkedin_reply()`. If campaign routing fails AND project_id lookup fails, sender UUID resolves project.
- **Commit**: `cfa712d`

#### B2. Polling path doesn't propagate sender_profile_uuid — FIXED
- **File**: `crm_sync_service.py:3156`
- **Impact**: Polling `raw_data` didn't have sender UUID → notification sender fallback couldn't work
- **Fix**: Normalize `msg["sender_profile"]["uuid"]` into `msg["sender_profile_uuid"]` before passing to process_getsales_reply.
- **Commit**: `cfa712d`

#### B3. Notification exception swallowed in polling path — FIXED
- **File**: `crm_sync_service.py:3275`
- **Code was**: `except Exception: pass`
- **Fix**: `except Exception as _notif_err: logger.warning(f"[GETSALES] Polling notification failed for reply {_pr.id}: {_notif_err}")`
- **Commit**: `cfa712d`

#### B4. Sender UUID was last-resort fallback — FIXED
- **File**: `reply_processor.py:2295-2330` (send_getsales_notification)
- **Code was**: sender UUID checked only if `not resolved_project_id and not _valid_campaign`
- **Fix**: Sender UUID is now the FIRST check. Campaign-based and contact.project_id are fallbacks.
- **Why**: Every GetSales sender maps to exactly one project. Sender UUID is the strongest signal — always available, never empty.
- **Commit**: `cfa712d`

#### B5. No time guard on GetSales notification — FIXED
- **File**: `reply_processor.py:2287` (send_getsales_notification)
- **Impact**: SmartLead path had 2-hour time guard. GetSales had none. Removing death gate without this would spam 149 old notifications.
- **Fix**: Added `if age > timedelta(hours=2): return False` at top of `send_getsales_notification()`.
- **Commit**: `cfa712d`

#### B6. Stale project cache (5-min TTL) — REMAINING (Phase 2)
- **File**: `notification_service.py:704-719`
- **Impact**: After adding new campaigns/projects, routing is wrong for up to 5 minutes.

#### B7. telegram_sent_at tracks admin only, not subscribers — REMAINING (Phase 2)
- **Impact**: If admin send succeeds but subscriber send fails, telegram_sent_at is set and retry won't happen.

---

### Category C: DATABASE SCHEMA — FIXED

#### C1. ProcessedReply.lead_email was NOT NULL — FIXED
- **File**: `models/reply.py:95`
- **Migration**: `g1_channel_agnostic_identity.py` → `ALTER TABLE processed_replies ALTER COLUMN lead_email DROP NOT NULL`
- **Verified**: `SELECT is_nullable FROM information_schema.columns WHERE table_name='processed_replies' AND column_name='lead_email'` → `YES`

#### C2. Dedup index was email-based — FIXED
- **Old**: `UNIQUE(lead_email, campaign_id, message_hash)` — NULL emails bypass dedup
- **New**: `UNIQUE(COALESCE(lead_email, getsales_lead_uuid), COALESCE(campaign_id, ''), message_hash) WHERE message_hash IS NOT NULL`
- **Verified**: `SELECT indexname FROM pg_indexes WHERE tablename='processed_replies' AND indexname LIKE 'uq_%'` → `uq_reply_dedup`

#### C3. Dedup query used lead_email == lead_email (NULL != NULL) — FIXED
- **File**: `reply_processor.py:2185`
- **Fix**: When lead_email is None, dedup query uses `ProcessedReply.getsales_lead_uuid == contact.getsales_id` instead.

#### C4. DISTINCT ON lead_email collapses all NULL into one row — REMAINING (Phase 2)
- **File**: `api/replies.py:944`
- **Impact**: `group_by_contact=true` shows one card for ALL no-email contacts.

---

### Category D: DISPLAY & UX — PARTIALLY FIXED

#### D1. Telegram deep link crashes with None email — FIXED
- **Files**: `notification_service.py:944, 1111`
- **Was**: `f"?lead={quote(reply.lead_email)}"` — renders `?lead=None` string literal
- **Fix**: Check `is_real_email` before using lead_email in URL. Fall back to project-only link.
- **Commit**: `cfa712d`

#### D2. client_dashboard.py crashes on missing email — REMAINING (Phase 2)
- **File**: `client_dashboard.py:316` — `contact.email.split("@")[0]`

#### D3. Contacts page won't show NULL-email contacts — REMAINING (Phase 2)
- **File**: `api/contacts.py:439, 455`

#### D4. Frontend TypeScript types assume email is always string — REMAINING (Phase 2)
- **File**: `frontend/src/api/replies.ts:130`

---

### Category E: DUPLICATE CONTACTS — REMAINING (Phase 3)

#### E1. SmartLead + GetSales create separate contacts for same person
- **Example**: Katya Anamaria — Contact 140381 (SmartLead, email=katyaanamaria@fluvip.com) vs Contact 518645 (GetSales, email="", getsales_id=b20b15d6)
- **Impact**: Webhook matches GetSales contact (no email) instead of SmartLead contact (has email).

---

### Category F: PLATFORM ASSUMPTIONS — REMAINING (Phase 2)

#### F1. Source checks hardcoded for smartlead/getsales — `api/replies.py:190-202`
#### F2. Domain extraction assumes @ — `crm_sync_service.py:1376`
#### F3. Follow-up name extraction assumes @ — `follow_up_service.py:243`
#### F4. Conversation sync groups by lead_email — `crm_sync_service.py:3475-3500`

---

## Part 2: What Was Deployed (Phase 1)

### Commit `cfa712d` — "fix: channel-agnostic identity"

**Files changed** (6 files, +138/-45 lines):

| File | What Changed |
|------|-------------|
| `alembic/versions/g1_channel_agnostic_identity.py` | New migration: lead_email nullable, new dedup index |
| `models/reply.py` | `nullable=True` on lead_email, removed old index from `__table_args__` |
| `reply_processor.py` | Removed both death gates, fixed dedup query for NULL email, added 2h time guard, sender-first routing, pass sender_profile_uuid to notify |
| `crm_sync.py` | webhook_event.processed conditional on pr creation |
| `notification_service.py` | Added sender_profile_uuid param, sender routing fallback, fixed deep links |
| `crm_sync_service.py` | Propagate sender_profile_uuid in polling, log notification failures |

### Commit `f3388d8` — "add: backfill script for dropped replies"

| File | What |
|------|------|
| `app/scripts/backfill_dropped_replies.py` | Recovers ProcessedReply from webhook_events for dropped replies |

### Migration `g1_channel_agnostic`

```sql
-- 1. Make nullable
ALTER TABLE processed_replies ALTER COLUMN lead_email DROP NOT NULL;

-- 2. Replace index
DROP INDEX uq_processed_reply_content;
CREATE UNIQUE INDEX uq_reply_dedup ON processed_replies (
    COALESCE(lead_email, getsales_lead_uuid),
    COALESCE(campaign_id, ''),
    message_hash
) WHERE message_hash IS NOT NULL;
```

---

## Part 3: Deployment Verification (Checksums)

### Pre-deploy checks (all passed)

| Check | Command | Expected | Result |
|-------|---------|----------|--------|
| Syntax | `ast.parse()` on all 6 files | No SyntaxError | **PASS** |
| Imports | `from app.models.reply import ProcessedReply` etc | All imports OK | **PASS** |
| Schema | `ProcessedReply.lead_email.property.columns[0].nullable` | `True` | **PASS** |

### Post-deploy checks (all passed)

| Check | Query/Command | Expected | Result |
|-------|--------------|----------|--------|
| lead_email nullable | `SELECT is_nullable FROM information_schema.columns WHERE table_name='processed_replies' AND column_name='lead_email'` | YES | **YES** |
| New dedup index | `SELECT indexname FROM pg_indexes WHERE tablename='processed_replies' AND indexname LIKE 'uq_%'` | uq_reply_dedup | **uq_reply_dedup** |
| No notification spam | `SELECT COUNT(*) FROM processed_replies WHERE telegram_sent_at > deploy_time AND received_at < deploy_time - 2h` | 0 | **0** |
| No "Skipping reply — no email" in logs | `docker logs --since 5m \| grep 'no email'` | 0 lines | **0 lines** |
| Backend healthy | `docker logs --since 5m \| grep ERROR` | No crashes | **No crashes** |
| Death gate gone | `grep -n 'Skipping reply.*no email' reply_processor.py` | 0 matches | **0 matches** |

### Backfill verification (all passed)

| Check | Query | Expected | Result |
|-------|-------|----------|--------|
| Rizzult week 17 total | `SELECT COUNT(*) FROM processed_replies WHERE campaign_name ILIKE '%rizzult%' AND received_at >= '2026-03-17' AND received_at < '2026-03-24' AND category != 'ooo'` | 46+ (was 38) | **47** |
| Recovered replies exist | `SELECT COUNT(*) FROM processed_replies WHERE id IN (40500..40508)` | 8 | **8** |
| No spam (all pre-marked) | `SELECT COUNT(*) FROM processed_replies WHERE id >= 40500 AND telegram_sent_at IS NULL` | 0 | **0** |
| Sheet sync enabled for week 17 | `SELECT COUNT(*) FROM processed_replies WHERE id >= 40500 AND sheet_synced_at IS NULL` | 6-8 | **6** (2 already picked up by scheduler) |
| Both sources caught | GetSales count for week 17 | Was 19, should be ~28 | **28** |
| SmartLead unaffected | SmartLead count for week 17 | 19 | **19** |

### Rizzult week 17 — all 8 recovered replies

| ProcessedReply ID | Contact | Campaign | Source | Status |
|---|---|---|---|---|
| 40500 | Victor Rodarte Candiani | RIzzult Streaming 14 02 26 | Backfill | In DB, sheet pending |
| 40501 | Daryl Pace | RIzzult global QSR 08 03 | Backfill | In DB, sheet pending |
| 40502 | Juan Corredor Martinez | RIzzult Streaming 14 02 26 | Backfill | In DB, sheet pending |
| 40503 | Flavia Adriasola | RIzzult Streaming 14 02 26 | Backfill | In DB, sheet pending |
| 40504 | Juan Camilo Millan | RIzzult big 5 agencies 27 02 26 | Backfill | In DB, sheet pending |
| 40506 | Katya Anamaria | RIzzult partner agencies 15 02 26 | Backfill | In DB, sheet pending |
| 40507 | Ian D. | RIzzult global QSR 08 03 | Backfill | In DB, sheet pending |
| 40508 | Tove Vinz | RIzzult global QSR 08 03 | Backfill | In DB, sheet pending |

---

## Part 4: Cross-Project Impact

### Affected projects (149 total dropped replies)

| Project | Dropped | Sheet Sync | Subscribers | Backfill Status |
|---------|---------|-----------|-------------|----------------|
| **Rizzult (22)** | 50 | YES (week-based) | Aleksandra | Week 17: **DONE** (8 recovered). Older: not backfilled. |
| **easystaff ru (40)** | 42 | YES | Sergey, Petr | NOT BACKFILLED. Run `--all` to recover. |
| **tfp (13)** | 12 | NO | 2 chats | NOT BACKFILLED |
| **mifort (21)** | 10 | YES | 3 chats | NOT BACKFILLED |
| **OnSocial (42)** | 8 | NO | 1 chat | NOT BACKFILLED |
| **palark (16)** | 6 | ? | ? | NOT BACKFILLED |
| **easystaff global (9)** | 4 | NO | 1 chat | NOT BACKFILLED |
| **archistruct (24)** | 4 | ? | ? | NOT BACKFILLED |
| **Unknown** | 13 | - | - | NOT BACKFILLED |

**To backfill ALL projects** (with sheet sync blocked, no notification spam):
```bash
docker exec leadgen-backend python -m app.scripts.backfill_dropped_replies --all
```

### Safety guarantees for other projects

| Guarantee | How |
|-----------|-----|
| No notification spam | 2-hour time guard in `send_getsales_notification()` — old replies silently processed |
| No sheet pollution | Backfill script sets `sheet_synced_at = NOW()` for non-Rizzult-week-17 replies |
| No broken SmartLead | SmartLead contacts always have email. Death gate removal is a no-op for them. |
| No frontend crash | `lead_email` was already optional in most frontend code (ternary guards exist) |
| No dedup bypass | New index uses `COALESCE(lead_email, getsales_lead_uuid)` — at least one is always present |

---

## Part 5: Invariants (Rules That Must Never Be Violated)

### INV-1: Every inbound message creates a ProcessedReply
No guard, no early return, no silent skip. If a message arrives, it MUST be stored. The only valid skip is exact content dedup (same message_hash from same contact).

### INV-2: Every ProcessedReply triggers a notification attempt
Admin always. Subscriber if project is resolved. If project resolution fails, log ERROR. Never swallow notification exceptions with `pass`.

### INV-3: Contact identity is contact_id / getsales_lead_uuid, not email
Dedup, grouping, linking, display — all must work with whatever identifier the contact HAS. Email is optional metadata.

### INV-4: Project routing has 3 independent signals
1. Sender UUID → project (strongest for GetSales)
2. Campaign name → project (ownership rules)
3. Contact.project_id (assigned at contact creation)

If ANY of the 3 resolves, notification is routed. All 3 failing = ERROR.

### INV-5: Webhook event processed = true only after ProcessedReply committed
If processing fails, the event stays retryable. No data loss from marking "done" before it's actually done.

### INV-6: No .split("@") without guard
Every email string operation must handle: None, empty string, non-email identifiers.

---

## Part 6: Remaining Work

### Phase 2: Fix all email assumptions (28 locations)

| File | Line | Issue | Severity |
|------|------|-------|----------|
| `api/replies.py` | 944 | DISTINCT ON lead_email collapses NULL | HIGH |
| `api/replies.py` | 3867, 3962 | .split("@") crash in referrals | BLOCKER |
| `api/client_dashboard.py` | 316 | .split("@") crash | BLOCKER |
| `services/follow_up_service.py` | 243 | .split("@") name extraction | MEDIUM |
| `services/sheet_sync_service.py` | 183 | Filters out NULL-email | HIGH |
| `services/crm_sync_service.py` | 1376 | Domain extraction .split("@") | MEDIUM |
| `services/crm_sync_service.py` | 3475 | Conversation sync groups by email | CRITICAL |
| `api/contacts.py` | 439, 455 | NULL-email contacts invisible | HIGH |
| `frontend/src/api/replies.ts` | 130 | TypeScript type not optional | LOW |
| `frontend/src/components/ReplyQueue.tsx` | 841 | Null guard on lead_email | MEDIUM |

### Phase 3: Contact merge (SmartLead + GetSales)

Merge duplicate contacts by name + company when webhook provides getsales_id for a contact that has an email twin from SmartLead.

### Phase 4: Monitoring

- Unrouted reply alert (logger.error when no project found)
- Daily digest of `telegram_sent_at IS NULL` by project
- Separate tracking for admin vs subscriber notification success

---

## Part 7: Historical Incident Timeline

| Date | Incident | Root Cause | Fixes | Status |
|------|----------|-----------|-------|--------|
| Mar 12 | Zero LinkedIn replies (5 cascading failures) | webhooks_enabled=false, Contact.touches crash, Contact.campaigns crash, pr undefined, recovery email-only | 11 hardening patches: savepoints, parallel sync, per-reply commit, Redis dedup, event recovery | **FIXED** |
| Mar 17 | Sheet missing 473 replies (6 self-inflicted recovery errors) | No leads_tab default, emoji=reply, JSON null campaign_filters, sheet_synced_at before write | emoji filter, jsonb guard, write-first | **FIXED** |
| Mar 18 | Missing Telegram notifications + 149 replies silently lost | Email death gate, campaign-based routing, no sender UUID routing, webhook processed=true on failure | Phase 1 deploy: death gate removed, sender-first routing, time guard, migration, backfill | **FIXED** (Phase 1) |
| Ongoing | Duplicate contacts | No merge between SmartLead (email) and GetSales (UUID) twins | Phase 3 | **PLANNED** |
| Ongoing | 28 .split("@") crash points | Email-first assumptions in display/utility code | Phase 2 | **PLANNED** |

---

## Part 8: Monitoring Queries (Run After Deploy)

```sql
-- 1. Verify no death gate skips (should stay 0 forever)
SELECT COUNT(*) FROM webhook_events
WHERE event_type = 'linkedin_inbox'
  AND processed = true
  AND error LIKE '%returned None%'
  AND created_at > '2026-03-18 23:30:00';

-- 2. Verify new no-email replies ARE being created
SELECT id, lead_email, lead_first_name, lead_last_name, campaign_name, received_at
FROM processed_replies
WHERE lead_email IS NULL AND created_at > '2026-03-18 23:30:00'
ORDER BY created_at DESC;

-- 3. Verify no notification spam for old replies
SELECT COUNT(*) FROM processed_replies
WHERE telegram_sent_at > '2026-03-18 23:30:00'
  AND received_at < '2026-03-18 21:00:00';

-- 4. Check Rizzult sheet sync completeness (week 17)
SELECT COUNT(*) as total,
       COUNT(CASE WHEN sheet_synced_at IS NOT NULL THEN 1 END) as synced,
       COUNT(CASE WHEN sheet_synced_at IS NULL THEN 1 END) as pending
FROM processed_replies
WHERE campaign_name ILIKE '%rizzult%'
  AND received_at >= '2026-03-17' AND received_at < '2026-03-24'
  AND category != 'ooo';

-- 5. Count remaining unbackfilled drops (other projects)
SELECT COUNT(*) FROM webhook_events
WHERE event_type = 'linkedin_inbox'
  AND processed = true
  AND lead_email NOT LIKE '%@%'
  AND created_at > '2026-03-01'
  AND id NOT IN (SELECT we_id FROM ... ); -- approximate
```

---

## Part 9: Classification Outage — Mar 18-19

### Incident: OpenAI quota exceeded → all replies classified "other"

**When**: Mar 18 16:29 → Mar 19 ~09:15 (~17 hours)
**Root cause**: OpenAI API key `sk-p...RNQA` hit billing quota. All calls return `429 insufficient_quota`.
**Impact**: 41 replies across all projects classified as `category=other, confidence=low` with `classification_reasoning` = the 429 error message.
**Symptom reported by Agnia (EasyStaff RU operator)**: "все приходят без зеленых красных желтых" — all Telegram notifications show 📧 (no color) instead of 🟢/🔴/🟡.

**Fallback behavior**: When classification fails 3 times, `classify_reply()` returns `{category: "other", confidence: "low", reasoning: <error_message>}`. This is by design — the reply is still processed and notified, just without proper category coloring.

**Fix applied**: Mar 19 09:15
1. OpenAI billing topped up (user action)
2. Reclassification script ran on all 41 broken replies
3. All 41 now have correct categories with high confidence

**Reclassification results**:
- out_of_office: 12, not_interested: 15, wrong_person: 3, interested: 2, question: 2, other: 5, unsubscribe: 2

**Prevention**: See `CLASSIFICATION_MODEL_COMPARISON.md` for model cost analysis and fallback strategy.

### INV-7: Classification failure must not produce silent "other"
When classification API fails, the fallback category should be clearly marked (e.g., `category=unclassified` or `category=other_api_error`) so operators and monitoring can distinguish real "other" from API failures. Add OpenAI balance monitoring alert.

---

## Part 10: Missed Telegram Notifications — Analysis & Fix Plan

### Incident: Sachin Singh (OnSocial) — Reply Never Received

**Report claims**: Reply from sachin.singh@fabulate.com.au was processed (classified as Meeting Request, draft generated) but Telegram notification never sent.

**Reality (verified against DB)**:
- **NO ProcessedReply exists** for sachin.singh@fabulate.com.au
- **NO EMAIL_REPLY webhook** in webhook_events — only `LEAD_CATEGORY_UPDATED` (SmartLead AI category update, not a reply webhook)
- The reply was **never received by our system**, not just "missing notification"

**Root cause**: SmartLead webhook delivery failure OR server restart killed the async task before the webhook_event was committed. The report's analysis is partially wrong — it assumes the reply was processed.

### Full Scope: telegram_sent_at IS NULL Analysis

Queried all ProcessedReplies from last 7 days where `telegram_sent_at IS NULL`:

| Category | Count | Should we re-notify? |
|----------|-------|---------------------|
| Old replies polled late (`received_at` > 1h before `created_at`) | 193 | **NO** — time guard correctly blocked these. They're old messages discovered during historical polling. Sending notifications for week-old replies is confusing. |
| Genuinely missed (received ≈ created, should have been notified) | 14 | **MAYBE** — but they're 1-7 days old. Re-sending now would confuse operators. |
| OpenAI quota failure | 1 | **NO** — already reclassified, but notification window passed. |

**The 14 genuinely missed**, by project:
| Project | Missed | Categories | Oldest |
|---------|--------|-----------|--------|
| easystaff ru | 7 | interested, question, wrong_person | Mar 12 |
| mifort | 4 | interested | Mar 18 |
| Inxy | 3 | meeting_request | Mar 13 |
| Rizzult | 1 | not_interested | Mar 16 |

### Why Notifications Were Missed (3 bugs from the report, verified)

**Bug 1 (CONFIRMED): No retry for failed Telegram sends**
- `reply_processor.py:1720`: `if sent: processed_reply.telegram_sent_at = datetime.utcnow()`
- If `send_telegram_notification()` returns False (rate limit, timeout, network error), `telegram_sent_at` stays NULL
- No background process ever checks for `telegram_sent_at IS NULL` to retry
- Notification permanently lost

**Bug 2 (CONFIRMED): Event Recovery passes raw event_type**
- `crm_scheduler.py:689`: Recovery passes raw SmartLead payload where `event_type` may be "reply" or "lead.replied"
- `reply_processor.py:1674`: `should_notify = event_type == "EMAIL_REPLY"` — only matches the normalized type
- Recovery-processed replies → no notification

**Bug 3 (CONFIRMED): 2-hour time guard blocks legitimate retries**
- OUR FIX from tonight added `send_getsales_notification` time guard
- SmartLead path already had it at `reply_processor.py:1686`
- If a reply is processed normally but notification fails, then retry happens > 2h later → time guard blocks it

### CRITICAL SAFETY ANALYSIS: Why a Naive Retry Loop Would Spam

If we add `SELECT * FROM processed_replies WHERE telegram_sent_at IS NULL AND created_at > NOW() - 24h`:

1. **193 old-polled replies** would be re-notified → operators get 193 old notifications
2. **The 8 Rizzult backfill replies** have `telegram_sent_at` set (safe), but future backfills might not
3. **Every project affected** — Rizzult, EasyStaff RU, Mifort, Inxy, TFP, OnSocial, Paybis operators ALL get spammed
4. **No per-project scoping** — the retry loop doesn't know which notifications are intentionally skipped vs genuinely missed

### Safe Retry Design (Proposed)

**Principle**: Never re-notify replies older than 30 minutes. If notification fails, retry 3 times within 30 minutes. After that, accept the loss — operator will see it in Replies UI.

**Implementation**:

Add two columns to `processed_replies`:
```sql
ALTER TABLE processed_replies ADD COLUMN notification_attempts INTEGER DEFAULT 0;
ALTER TABLE processed_replies ADD COLUMN last_notification_attempt_at TIMESTAMP;
```

Retry loop in `crm_scheduler.py` (every 5 minutes):
```python
# Find replies that need notification retry
candidates = SELECT * FROM processed_replies
WHERE telegram_sent_at IS NULL
  AND notification_attempts < 3
  AND created_at > NOW() - INTERVAL '30 minutes'
  AND (last_notification_attempt_at IS NULL
       OR last_notification_attempt_at < NOW() - INTERVAL '5 minutes')
```

**Safety guarantees**:
- `created_at > NOW() - 30 minutes` → NEVER touches old replies (not 193, not backfills)
- `notification_attempts < 3` → max 3 retries, then stops
- `5-minute cooldown` → no rapid-fire retries
- Time guard in `send_getsales_notification` stays (blocks old GetSales replies)
- Each retry still goes through full project routing → correct operator only

**What this does NOT fix**:
- The 14 historical missed notifications → too old, don't re-notify
- Sachin Singh → reply never received (webhook delivery issue, not notification issue)
- Old-polled replies → correctly blocked by time guard

### Fix for Bug 2 (Event Recovery payload normalization)

In `crm_scheduler.py:689`, after loading the payload:
```python
payload = json.loads(event.payload)
# Normalize event_type for recovery processing
if event.event_type in ("EMAIL_REPLY", "lead.replied", "reply"):
    payload["event_type"] = "EMAIL_REPLY"
```

### Historical Missed Notifications — DO NOT RE-SEND

The 14 genuinely missed notifications from March 12-18 are too old. Re-sending them would:
- Confuse operators ("why am I getting a notification for a 7-day-old reply?")
- Potentially trigger re-processing of already-handled replies
- Create duplicate notifications if the operator already saw it in the UI

**Decision**: Accept the loss. The retry mechanism only protects FUTURE notifications.

### Files to Change

| File | Change | Risk |
|------|--------|------|
| Alembic migration | Add `notification_attempts`, `last_notification_attempt_at` columns | None — additive |
| `crm_scheduler.py` | Add notification retry loop (every 5 min) | LOW — scoped to 30-min window |
| `crm_scheduler.py:689` | Normalize event_type in recovery | LOW — only affects recovery path |
| `reply_processor.py:1720` | Increment `notification_attempts` on every attempt | LOW — field update only |
