---
name: Conversation History Architecture
overview: "Phase 1: Fix needs-reply detection by syncing Smartlead message histories to catch operator replies. Phase 2: Add per-project Telegram notifications so operators see new replies in real time via @impecablebot."
todos:
  - id: sync-service
    content: "Phase 1a: Add sync_conversation_histories() to crm_sync_service.py — fetches Smartlead message histories for pending replies, creates missing outbound ContactActivity records, marks ProcessedReply as replied_externally"
    status: completed
  - id: scheduler-loop
    content: "Phase 1b: Add _run_conversation_sync_loop() to crm_scheduler.py — runs sync every 10 min, only checks pending replies without outbound activity"
    status: completed
  - id: initial-backfill
    content: "Phase 1c: Run initial sync for Rizzult (project_id=22) via sync-outbound-status endpoint to fix the 740 stale pending replies"
    status: completed
  - id: verify-counts
    content: "Phase 1d: Verify needs_reply count dropped to a realistic number (likely 20-50 for Rizzult)"
    status: completed
  - id: tg-model
    content: "Phase 2a: Add TelegramRegistration model + telegram_username field to Project model + Alembic migration"
    status: completed
  - id: tg-webhook
    content: "Phase 2b: Add /telegram/webhook endpoint to handle /start and register username->chat_id mapping"
    status: completed
  - id: tg-resolve
    content: "Phase 2c: Update project PATCH endpoint to resolve telegram_username -> chat_id from registrations table"
    status: completed
  - id: tg-frontend
    content: "Phase 2d: Add Telegram notification section to ProjectsPage with @username input, bot link, and status indicator"
    status: completed
  - id: tg-setup
    content: "Phase 2e: Register bot webhook URL with Telegram API (one-time setup on Hetzner)"
    status: completed
isProject: false
---

# Auto-Replies Production Architecture

Two phases: first make "needs reply" accurate 24/7, then let operators get notified in Telegram per-project.

---

## Phase 1: Fix Conversation History (Needs Reply Detection)

### The Problem

932 Rizzult replies show as "needs reply" when the real number is far lower. Root cause: **manual operator replies sent from Smartlead's master inbox UI do not trigger `EMAIL_SENT` webhooks**. Our system only learns about outbound messages via webhooks, so it never sees these replies.

### Current State

```mermaid
flowchart LR
  subgraph smartlead [Smartlead]
    AutoSeq[Automated Sequence]
    ManualReply[Operator Reply via UI]
    LeadReply[Lead Replies]
  end

  subgraph backend [Our Backend]
    WebhookEP[Webhook Endpoint]
    Poller[Reply Poller]
    CA[ContactActivity]
    PR[ProcessedReply]
  end

  AutoSeq -->|"EMAIL_SENT webhook"| WebhookEP
  LeadReply -->|"EMAIL_REPLY webhook"| WebhookEP
  LeadReply -->|"Statistics API poll"| Poller
  WebhookEP --> CA
  Poller --> PR

  ManualReply -.->|"NO webhook sent"| WebhookEP
```



**What's tracked today:**

- Inbound replies: via `EMAIL_REPLY` webhook + polling fallback (robust)
- Automated outbound emails: via `EMAIL_SENT` webhook (when delivered)
- Operator manual replies: **NOT tracked** (the gap)

### Solution: Bulk Statistics + Message History Sync

Three-layer architecture for reply tracking:

```mermaid
flowchart TD
  subgraph layer1 [Layer 1: Real-time Webhooks]
    WH[POST /api/smartlead/webhook]
    WH -->|"EMAIL_REPLY"| Pipeline[Classify + Draft + Notify]
    Pipeline --> PR[ProcessedReply]
    Pipeline --> CA[ContactActivity]
  end

  subgraph layer2 [Layer 2: Reply Poller - every 3-10 min]
    Poller[sync_smartlead_replies]
    Poller -->|"GET /statistics bulk"| StatsAPI[Statistics API 500/page]
    StatsAPI -->|"new replied leads"| Poller
    Poller -->|"message-history per new lead"| MsgAPI[Message History API]
    Poller --> Pipeline
  end

  subgraph layer3 [Layer 3: Conversation Sync - every 10 min]
    ConvSync[sync_conversation_histories]
    ConvSync -->|"GET /statistics bulk"| StatsAPI2[Statistics API 500/page]
    StatsAPI2 -->|"email to lead_id map"| ConvSync
    ConvSync -->|"message-history for ~20 pending"| MsgAPI2[Message History API]
    ConvSync -->|"last msg outbound?"| MarkExt[Mark replied_externally]
    ConvSync -->|"create missing"| CA2[ContactActivity]
  end

  subgraph layer3b [Optional: GPT Auto-Dismiss]
    GPT[GPT-4o-mini Classify]
    ConvSync -->|"last msg inbound?"| GPT
    GPT -->|"ooo/bounce/unsub"| AutoDismiss[Auto-dismiss]
    GPT -->|"needs_reply"| KeepPending[Keep pending]
  end
```



### Implementation (Updated Feb 12 2026)

**Key change:** Both `sync_conversation_histories()` and `sync_outbound_status()`
now use **bulk statistics endpoint** (GET /campaigns/{id}/statistics, 500/page) to
resolve email→lead_id, instead of per-lead API calls. This eliminates 429 errors.

**File: [backend/app/services/crm_sync_service.py**](backend/app/services/crm_sync_service.py) — `sync_conversation_histories()`:

1. Query `ProcessedReply` where pending + no outbound `ContactActivity` after `received_at`
2. Deduplicate by `(campaign_id, lead_email)`
3. **Bulk-fetch statistics** per campaign → build email→lead_id map (~5 calls per campaign)
4. Fallback: webhook data → Contact.smartlead_id (if not in statistics)
5. Fetch message-history with **adaptive delay** (1.5s start, 2x on 429, 0.9x on success)
6. If last message is outbound → mark `replied_externally` + create `ContactActivity`
7. If last message is inbound + `auto_dismiss=true` → GPT-4o-mini classify

**File: [backend/app/api/replies.py**](backend/app/api/replies.py) — `sync_outbound_status()` (manual trigger):

- Same bulk statistics approach as above
- Supports `project_id`, `auto_dismiss`, `dry_run` parameters
- Returns detailed breakdown with `already_replied`, `still_pending`, `auto_dismissed`
- New: `_classify_reply_needs_action()` GPT helper
- New: `GET /campaign/{id}/analytics-summary` returns Smartlead-matching stats

**File: [backend/app/services/crm_scheduler.py**](backend/app/services/crm_scheduler.py) — `_run_conversation_sync_loop()` every 10 min.

**API cost:** ~5 statistics calls + ~20 message-history calls per sync = ~25 total. Adaptive delay prevents 429s.

---

## Phase 2: Per-Project Telegram Notifications

### The Flow

```mermaid
sequenceDiagram
  participant Op as Operator
  participant Bot as impecablebot
  participant UI as Project Page
  participant BE as Backend
  participant DB as Database

  Op->>Bot: /start
  Bot->>DB: Store username to chat_id mapping
  Bot->>Op: Registered! Your @username will receive notifications.
  Op->>UI: Enter @username in project settings
  UI->>BE: PATCH /projects/22 telegram_username=alex
  BE->>DB: Lookup chat_id for alex
  BE->>DB: Save telegram_chat_id on project
  BE->>UI: OK notifications enabled
  Note over BE,Op: Later when a reply comes in...
  BE->>Bot: Send notification to operator chat_id
  Bot->>Op: New reply from lead at company.com
```



### Implementation

**1. New model** in [backend/app/models/reply.py](backend/app/models/reply.py):

```python
class TelegramRegistration(Base, TimestampMixin):
    __tablename__ = "telegram_registrations"
    id = Column(Integer, primary_key=True)
    telegram_username = Column(String(100), unique=True, index=True)  # lowercase, no @
    telegram_chat_id = Column(String(100), nullable=False)
    telegram_first_name = Column(String(100), nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
```

**2. Bot webhook endpoint** — new route handling `/start` command:

- Extracts `username` and `chat_id` from Telegram update
- Upserts into `telegram_registrations`
- Replies with confirmation message

**3. Project update** in [backend/app/api/contacts.py](backend/app/api/contacts.py):

- Accept `telegram_username` field
- Lookup `telegram_registrations` to resolve to `chat_id`
- If not found, return error: "User hasn't registered with the bot yet"

**4. Add `telegram_username` to Project model** in [backend/app/models/contact.py](backend/app/models/contact.py):

- Persists the @username so UI can display it
- `telegram_chat_id` (already exists) stores the resolved numeric ID

**5. Frontend** in [frontend/src/pages/ProjectsPage.tsx](frontend/src/pages/ProjectsPage.tsx):

- Add "Telegram Notifications" section to project edit form
- Text input for `@username`
- Helper text: "Open @impecablebot and send /start first"
- Green checkmark when active, amber warning when username not yet registered

**6. Frontend types** in [frontend/src/api/contacts.ts](frontend/src/api/contacts.ts):

- Add `telegram_username` to Project interfaces and `updateProject()` params

**Already done:**

- `telegram_chat_id` field exists on `Project` model
- [backend/app/services/notification_service.py](backend/app/services/notification_service.py) already routes notifications to project operators via `telegram_chat_id` (line 769-780)
- All `EMAIL_REPLY` events trigger `notify_reply_needs_attention()` which checks for project routing
- No changes needed to notification_service.py — once `telegram_chat_id` is set, notifications flow automatically

**One-time setup:** Register bot webhook URL with Telegram:

```
POST https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://46.62.210.24:8000/api/replies/telegram/webhook
```

