# Telegram DM Inbox — Full Plan & How It Works

## How does tdata import actually work?

**tdata** is Telegram Desktop's session storage folder. It contains **auth keys** — 256-byte cryptographic keys that prove identity to Telegram servers. Each account has one auth key + its DC (data center) address.

When you upload a tdata archive:
1. Backend extracts the archive (RAR/ZIP)
2. Reads `key_datas` (master key) and `Accounts.txt` (list of accounts)
3. For each account: extracts `auth_key` (256 bytes) + `dc_id` (1-5)
4. Builds a **Telethon StringSession** from these — a base64-encoded string containing `dc_id + server_ip + port + auth_key`
5. Stores the StringSession in DB (the `telegram_dm_accounts` table)
6. Connects to Telegram using this StringSession — **no phone code or 2FA needed**

The StringSession IS the account. Anyone with it can connect as that Telegram user. That's why we store it encrypted in DB and never expose it in API responses.

## Will new replies to these accounts be received?

**YES — but only after the integration (Phase 4 below) is built.** Here's the full picture:

### What works NOW (MVP):
- 15 accounts connected from tdata
- You can browse dialogs and messages manually on `/telegram-inbox`
- You can send replies from the UI
- **BUT** new incoming messages are NOT automatically detected — you have to click refresh or re-select the account

### What the integration adds:
- **Automatic polling every 3 minutes** — for each connected account, checks all DMs for new inbound messages
- **AI classification + draft generation** — same as SmartLead/GetSales (category: interested/meeting/question/etc.)
- **Telegram notification** — operator gets notified on Telegram with deep link to the reply
- **Appears in Tasks/Replies** — alongside email and LinkedIn replies, with "Telegram" badge
- **Approve and send** — operator reviews AI draft, clicks send, message goes out via Telegram

### How polling works:
```
Every 3 minutes:
  For each connected TelegramDMAccount with project_id set:
    → Telethon: get_dialogs() (list all DM conversations)
    → Filter to dialogs with new messages since last_processed_at
    → For each new inbound message:
      → process_telegram_reply() [classify + draft + store]
      → Commit to DB
      → Send Telegram notification to operator
    → Update last_processed_at
```

### What about real-time? (BACKLOG — after core is built)

**How Kotatogram/Telegram Desktop actually works:** They maintain a **persistent TCP socket** to Telegram servers. The server **pushes** new messages over this open socket — sub-second delivery, zero polling. This is how the MTProto protocol is designed.

**Telethon has the exact same capability:** `client.run_until_disconnected()` keeps a persistent TCP connection and fires `@client.on(events.NewMessage)` handlers instantly when messages arrive.

**Why we start with polling:** Faster to ship, consistent with existing architecture (GetSales polls too). Polling every 3 min means 90s average latency.

**BACKLOG: Upgrade to persistent connections (Phase 2)**

After core pipeline works with polling, upgrade to:
```python
# For each connected account, register event handler:
@client.on(events.NewMessage(incoming=True))
async def on_new_message(event):W
    if not event.is_private: return  # skip groups
    await process_telegram_reply(...)
    await send_notification(...)
```

Run all Telethon clients as long-lived daemon tasks inside the backend container (`restart: always`). Telethon handles reconnection and gap recovery automatically (tracks pts/seq, calls getDifference() on reconnect).

**Impact:** Latency drops from ~90s to <1s. Zero wasted API calls.

**Tradeoff:** Requires proper process supervision. If container restarts, all clients must reconnect (which they already do via `reconnect_all()` on startup). The polling loop serves as safety net — even with persistent connections, poll every 5 min to catch any missed messages.

**STATUS: IMPLEMENTED** (2026-03-25 02:46 UTC)
- All 15 accounts have persistent TCP connections to Telegram
- `@client.on(events.NewMessage(incoming=True))` fires instantly
- Polling still runs every 3 min as safety net
- Auto-reconnect on disconnect with 10s backoff

## Do I need anything besides tdata?

**No. tdata is all you need.** It contains everything:
- Auth keys (identity)
- Phone numbers (per account)
- Account info (first name, last name, username)

The only additional setup:
1. **Assign accounts to a project** — so the system knows which project's knowledge/templates/sender identity to use for drafts
2. **Project must have knowledge configured** — ICP, outreach templates, sender name (same as SmartLead/GetSales)

## What about contacts that have no email or LinkedIn?

Telegram contacts are identified by their **Telegram user ID** (`telegram_peer_id`). This is a unique integer assigned by Telegram. The system uses a 3-way identity chain:

```
COALESCE(lead_email, getsales_lead_uuid, telegram_peer_id)
```

- Email leads → identified by email
- LinkedIn leads → identified by GetSales UUID
- Telegram leads → identified by Telegram user ID
- A lead can have all three (if they're contacted on multiple channels)

**No fake emails, no placeholders.** If a Telegram contact has no email, `lead_email` is NULL. The `telegram_peer_id` is their identity.

## Edge cases

| Scenario | How it's handled |
|----------|-----------------|
| Same person on Telegram + LinkedIn + email | Three separate ProcessedReply records (one per channel). They appear as separate contacts unless email is discovered and matched. |
| Account disconnected (session revoked) | Polling skips disconnected accounts. UI shows red status dot. Operator re-uploads tdata. |
| FloodWait from Telegram | Polling staggered 2-3s between accounts. If FloodWait > 60s, account skipped this cycle. |
| Emoji-only reaction | Skipped (same filter as GetSales). |
| Duplicate message (polling race) | Content-based dedup via `MD5(body[:500].lower())` — same as SmartLead/GetSales. |
| Operator already replied | Auto-dismiss: if last thread message is outbound, reply gets `approval_status="dismissed"`. |
| Bot messages | Filtered out — `dialog.entity.bot == True` skips bots. |
| Group chats | Filtered out — only `dialog.is_user` (private DMs) are processed. |
| Media-only messages (photos, stickers) | Skipped — only text messages are processed. |

---

# Implementation Plan

## Phase 1: Migration — extend ProcessedReply for Telegram identity

**New file:** `backend/alembic/versions/k1_telegram_reply_integration.py`

- Add `telegram_peer_id` (String(50), indexed) to `processed_replies`
- Add `telegram_account_id` (Integer, FK→telegram_dm_accounts) to `processed_replies`
- Add `last_processed_at` (DateTime) to `telegram_dm_accounts` (polling cursor)
- Recreate dedup index: `COALESCE(lead_email, getsales_lead_uuid, telegram_peer_id)`

## Phase 2: Model updates

- `backend/app/models/reply.py` — add `telegram_peer_id`, `telegram_account_id` columns
- `backend/app/models/telegram_dm.py` — add `last_processed_at` column

## Phase 3: `process_telegram_reply()` — classification + draft

**Modify:** `backend/app/services/reply_processor.py`

New function following `process_getsales_reply()` exactly:
- Emoji skip → dedup → project lookup → classify → load knowledge → generate draft → create ProcessedReply → store thread → auto-dismiss
- Sets `source="telegram"`, `channel="telegram"`, `telegram_peer_id=str(peer_id)`
- Draft style: short/conversational (like LinkedIn DMs, not formal email)

## Phase 4: Polling loop — automatic message detection

**Modify:** `backend/app/services/telegram_dm_service.py` — `poll_new_messages()`
**Modify:** `backend/app/services/crm_scheduler.py` — `_run_telegram_dm_inbox_loop()` (3 min)

For each connected account with `project_id` set:
→ Fetch dialogs → find new inbound → `process_telegram_reply()` → notify

## Phase 5: COALESCE updates — 3-way identity

**Modify:** `backend/app/api/replies.py` (6 locations)
- Contact grouping, deep link resolution, follow-up check, campaign count
- All change from `COALESCE(email, getsales_uuid)` → `COALESCE(email, getsales_uuid, telegram_peer_id)`

**Modify:** `backend/app/services/follow_up_service.py` — extend newer_inbound check

## Phase 6: Project filter — include Telegram accounts

**Modify:** `backend/app/api/replies.py` — `_build_project_campaign_filter()`
- Add: `ProcessedReply.telegram_account_id.in_(select accounts where project_id = project.id)`

## Phase 7: Approve and send — Telegram branch

**Modify:** `backend/app/api/replies.py` — `approve_and_send_reply()`
- New branch: `if reply.channel == "telegram": await telegram_dm_service.send_message(...)`
- Plus: outbound ThreadMessage, ContactActivity, learning system

## Phase 8: Notification — `notify_telegram_dm_reply()`

**Modify:** `backend/app/services/notification_service.py`
- Same pattern as `notify_linkedin_reply()` but shows @username instead of email
- Deep link: `?reply_id={id}&project={slug}`

## Phase 9: Frontend — ReplyQueue integration

**Modify:** `frontend/src/components/ReplyQueue.tsx`
- Channel badge: blue "Telegram" tag
- Toast: "Sent via Telegram"
- Channel detection

**Modify:** `frontend/src/api/replies.ts` — add `telegram_peer_id`, `telegram_account_id` types

## Phase 10: Project Page — tdata management

**Modify:** `frontend/src/pages/ProjectPage.tsx`
- New "Telegram Accounts" section
- Show connected accounts, upload tdata, connect/disconnect

**Modify:** `backend/app/api/telegram_dm.py`
- `project_id` param on upload-tdata (auto-assign)

---

## Files

**New (1):** migration
**Modified (11):** reply.py model, telegram_dm.py model, reply_processor.py, telegram_dm_service.py, crm_scheduler.py, notification_service.py, follow_up_service.py, replies.py API, main.py, ReplyQueue.tsx, ProjectPage.tsx

## Verification

1. Send test DM to one of the 15 connected accounts
2. Wait ≤3 min → ProcessedReply appears with AI category + draft
3. Operator gets Telegram notification with deep link
4. Click link → lands on reply in Tasks/Replies with Telegram badge
5. Operator edits draft → clicks Send → message delivered via Telegram
6. Multiple messages from same peer grouped as one card
7. Only replies from project's assigned accounts visible in that project
