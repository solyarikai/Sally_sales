# Telegram DM Integration — Error Log & Lessons

## Critical Errors Found & Fixed (2026-03-25)

### 1. Entity resolution: "Could not find input entity for PeerUser"
**When:** Calling `client.iter_messages(peer_id)` or `client.get_messages(peer_id)`
**Why:** StringSession has NO entity cache. After container restart, Telethon doesn't know any peer entities.
**Fix:** Call `get_input_entity(peer_id)` first. If that fails, call `get_dialogs(limit=100)` to populate cache, then retry. Last resort: `InputPeerUser(peer_id, 0)` with access_hash=0.
**File:** `telegram_dm_service.py:get_messages()`

### 2. Timezone naive vs aware: "can't subtract offset-naive and offset-aware datetimes"
**When:** Storing Telethon message dates into DB columns (DateTime without timezone)
**Why:** Telethon returns `datetime.datetime(tz=timezone.utc)`. DB columns are timezone-naive.
**Fix:** Always `.replace(tzinfo=None)` before storing. Also use `datetime.utcnow()` not `datetime.now(timezone.utc)`.
**Files:** `telegram_dm_service.py`, `telegram_dm.py` API, `replies.py` full-history

### 3. ThreadMessage creation: invalid column names
**When:** Creating ThreadMessage rows for Telegram conversations
**Why:** Used `sender_email` and `sender_name` which don't exist on ThreadMessage model.
**Fix:** Only use actual columns: `reply_id, direction, channel, subject, body, activity_at, position, source, activity_type`.
**File:** `replies.py:get_reply_full_history()` Telegram branch

### 4. full-history returns empty for Telegram replies
**When:** Clicking "History" on a Telegram reply card
**Why:** Early return on line 2291 checked `if not lead_email and not getsales_lead_uuid` — Telegram has neither.
**Fix:** Added `and not telegram_peer_id` to the check. Also added `telegram_peer_id` branch for finding all replies from same lead.
**File:** `replies.py:get_reply_full_history()`

### 5. session.rollback() kills entire endpoint after thread fetch failure
**When:** Telethon disconnected, thread fetch fails, then remaining endpoint code fails with 500
**Why:** `await session.rollback()` after failed thread fetch detaches all ORM objects in the session.
**Fix:** Use `session.begin_nested()` (savepoint) for thread fetch. If it fails, savepoint rolls back but main session survives. Endpoint returns reply data without thread.
**File:** `replies.py:get_reply_full_history()` Telegram thread fetch block

### 6. opentele infinite recursion with multi-account tdata
**When:** Loading tdata with 15 accounts
**Why:** `TDesktop.api.setter` and `Account.api.setter` call each other infinitely.
**Fix:** Monkey-patch both setters with recursion guard.
**File:** `telegram_dm_service.py:_parse_tdata_all_accounts()`

### 7. opentele kMaxAccounts=3 limit
**When:** Loading tdata with >3 accounts
**Why:** Hardcoded `TDesktop.kMaxAccounts = 3` in opentele. Kotatogram supports 100.
**Fix:** Patch `td_mod.TDesktop.kMaxAccounts = 100` before loading.
**File:** `telegram_dm_service.py:_parse_tdata_all_accounts()`

### 8. opentele ToTelethon() broken
**When:** Converting TDesktop account to Telethon session
**Why:** `auth_session` local variable not associated with value.
**Fix:** Build StringSession manually: `struct.pack(">B4sH", dc_id, ip_bytes, 443) + auth_key` → base64.
**File:** `telegram_dm_service.py:_parse_tdata_all_accounts()`

### 9. Polling only checked unread messages (not unanswered)
**When:** First poll cycle produced 0 replies despite 50+ conversations
**Why:** `if not dialog.unread_count: continue` — all messages were "read" from browsing /telegram-inbox.
**Fix:** Check if last message is INBOUND (lead needs reply), regardless of unread status.
**File:** `telegram_dm_service.py:_poll_account()`

### 10. Project filter didn't include Telegram accounts
**When:** Telegram replies existed in DB but invisible in project-filtered Replies page
**Why:** `_build_project_campaign_filter()` only matched `campaign_name` and `getsales_senders`. Telegram replies have `campaign_name="Telegram @username"` which isn't in campaign_filters.
**Fix:** Added Tier 3 filter: `ProcessedReply.telegram_account_id.in_(select TelegramDMAccount.id where project_id = project.id)`.
**File:** `replies.py:_build_project_campaign_filter()`

### 11. Infinite scroll broken (IntersectionObserver root mismatch)
**When:** Reply list stops loading more pages after first 30 replies
**Why:** Observer used `root: scrollRef.current` but nested overflow containers confused the intersection calculation.
**Fix:** Changed to `rootMargin: '400px'` with no explicit root (uses viewport). More reliable.
**File:** `ReplyQueue.tsx` IntersectionObserver setup

### 12. Telegram peer @username not shown in Contact section
**When:** Telegram reply card shows empty CONTACT section
**Why:** `telegram_peer_username` not in API response schema. `raw_webhook_data` not exposed to frontend.
**Fix:** Extract `peer_username` from `raw_webhook_data` server-side, return as `telegram_peer_username` field.
**Files:** `replies.py` response builder, `reply.py` schema, `ReplyQueue.tsx` Contact section

---

## Patterns to Follow for Telegram

1. **Always strip timezone** from Telethon dates before DB insert: `.replace(tzinfo=None)`
2. **Always resolve entities** before accessing peer messages — call `get_dialogs()` to populate cache
3. **Use savepoints** (`session.begin_nested()`) for Telegram API calls in request handlers — don't let failures kill the session
4. **ThreadMessage columns** are: `reply_id, direction, channel, subject, body, activity_at, position, source, activity_type` — nothing else
5. **3-way COALESCE** everywhere: `COALESCE(lead_email, getsales_lead_uuid, telegram_peer_id)`
6. **Account connectivity** can drop at any time. Always handle `ValueError("Account X lost connection")` gracefully.
