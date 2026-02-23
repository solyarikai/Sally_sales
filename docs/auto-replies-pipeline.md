# Auto-Replies Pipeline — Architecture & Setup Guide

## Overview

The auto-replies pipeline classifies incoming email replies from Smartlead campaigns using GPT-4o-mini, generates AI draft replies, and presents them to an operator for one-click approval via the Replies UI. This document explains the full flow using the **Rizzult project** as a working reference, and provides a step-by-step guide for enabling auto-replies on any new project.

---

## Architecture Diagram

```
Smartlead Campaign
       │
       ▼ (webhook: EMAIL_REPLY)
POST /api/smartlead/webhook          ← backend/app/api/smartlead.py
       │
       ▼
process_reply_webhook()              ← backend/app/services/reply_processor.py
  ├─ classify_reply()   → GPT-4o-mini classification
  ├─ lookup Project     → sender_name, sender_company, prompt template
  ├─ generate_draft_reply() → GPT-4o-mini draft with sender identity
  └─ store ProcessedReply   → approval_status=NULL (pending)
       │
       ▼
Replies UI (/replies)                ← frontend/src/pages/RepliesPage.tsx
  ├─ Operator reviews draft
  ├─ Can edit draft before sending
  └─ Click "Send" or "Skip"
       │
       ▼ (Send clicked)
POST /api/replies/{id}/approve-and-send  ← backend/app/api/replies.py
       │
       ▼
SmartLead API: send reply to lead
```

---

## Data Models

### ProcessedReply (`processed_replies` table)
Stores each incoming reply with its classification and draft. Key fields:
- `campaign_id`, `campaign_name` — Smartlead campaign
- `lead_email`, `lead_first_name`, `lead_last_name`, `lead_company`
- `email_subject`, `email_body`, `reply_text` — the incoming message
- `category` — GPT classification (see categories below)
- `category_confidence`, `classification_reasoning`
- `draft_reply`, `draft_subject` — AI-generated draft
- `approval_status` — NULL (pending), "approved", "dismissed", "replied_externally"
- `raw_webhook_data` — full Smartlead webhook payload (for debugging)

### ReplyCategory (enum)
```
interested, meeting_request, not_interested, out_of_office,
wrong_person, unsubscribe, question, other
```

### Project (`projects` table) — Sender Identity
Each project can have:
- `sender_name` — e.g. "Pavel Medvedev"
- `sender_position` — e.g. "Cofundador"
- `sender_company` — e.g. "Rizzult"
- `sender_signature` — optional full signature block
- `reply_prompt_template_id` — FK to `reply_prompt_templates` for custom prompt
- `campaign_filters` — JSON array of campaign names linked to this project

### ReplyPromptTemplateModel (`reply_prompt_templates` table)
Custom prompt templates for specific projects:
- `name` — display name
- `prompt_type` — "reply" or "classification"
- `prompt_text` — the full prompt with `{subject}`, `{body}`, `{category}`, `{first_name}`, `{last_name}`, `{company}`, `{sender_name}`, `{sender_position_line}`, `{sender_company_line}` placeholders

### ReplyAutomation (`reply_automations` table)
Optional per-campaign automation config (Slack notifications, Google Sheets logging). Not required for the core pipeline to work.

---

## How the Pipeline Works (Step by Step)

### 1. Webhook Registration
Smartlead webhooks are registered via:
```
POST /api/crm-sync/setup-webhooks
Body: {"webhook_base_url": "http://<server-ip>:8000/api"}
```
This calls `setup_crm_webhooks()` in `crm_sync_service.py` which iterates all active Smartlead campaigns and creates a webhook for each, pointing to `POST /api/smartlead/webhook`. Events: `EMAIL_REPLY`, `LEAD_CATEGORY_UPDATED`, `EMAIL_SENT`.

### 2. Webhook Received
When a lead replies, Smartlead sends a POST to `/api/smartlead/webhook` (`backend/app/api/smartlead.py`). The handler:
1. Stores the raw event in `webhook_events` table
2. Creates a `ContactActivity` record (direction=inbound)
3. For `EMAIL_REPLY` events only: spawns `process_reply_webhook()` in background

### 3. Reply Processing (`process_reply_webhook`)
Located in `backend/app/services/reply_processor.py`. Steps:

**a) Extract data** from webhook payload: campaign_id, lead_email, subject, body, lead name

**b) Find ReplyAutomation** (optional): matches by `campaign_ids` JSON containment

**c) Classify reply** via `classify_reply()`: calls GPT-4o-mini with a classification prompt. Returns `{category, confidence, reasoning}`.

**d) Lookup Project**: finds the Project whose `campaign_filters` contains the campaign name. Extracts:
- `sender_name`, `sender_position`, `sender_company` — for draft identity
- `reply_prompt_template_id` → loads custom prompt from `reply_prompt_templates`

**e) Generate draft** via `generate_draft_reply()`: calls GPT-4o-mini with:
- The custom project template (if exists) OR the base `DRAFT_REPLY_PROMPT`
- Sender identity injected: "You are replying as: {sender_name}, {position} at {company}"
- Explicit instruction: "Sign off as the sender name — NEVER use placeholder brackets"

**f) Store ProcessedReply**: creates/updates a record with all classification + draft data, `approval_status=NULL` (pending for operator review).

### 4. Operator Review (Replies UI)
The frontend at `/replies` fetches pending replies via `GET /api/replies?project_id=X&approval_status=pending`. The UI shows:
- Lead message with conversation thread
- AI classification + reasoning (sidebar)
- Draft reply (editable)
- "Send" and "Skip" buttons

### 5. Approve & Send
When operator clicks "Send":
```
POST /api/replies/{reply_id}/approve-and-send
Body: {"draft_reply": "edited text...", "draft_subject": "Re: ..."}
```
The endpoint:
1. Resolves `Contact.smartlead_id` (the Smartlead lead ID)
2. Fetches message thread from Smartlead to get the latest `message_id`
3. Sends the reply via Smartlead API (`POST /campaigns/{id}/leads/{id}/reply`)
4. Updates `approval_status = "approved"`

**Test mode**: pass `?test_mode=true` to redirect the email to `TEST_RECIPIENT_EMAIL` (pn@getsally.io) instead of the real lead.

---

## Rizzult Project — Working Reference

### Project Config (id=22)
```sql
-- Project record
name: Rizzult
sender_name: Pavel Medvedev
sender_position: Cofundador
sender_company: Rizzult
reply_prompt_template_id: 89  -- "Rizzult CPA Influencer Marketing"
campaign_filters: [
  "Rizzult Performance Agencies 22.11.25 Aleks",
  "Rizzult Fintech 22.11.25 Aleks",
  "Rizzult Foodtech 22.11.25 Aleks",
  "Rizzult QSR 22.11.25 Aleks",
  ... (16 campaigns total)
]
```

### Custom Prompt Template
The Rizzult template includes:
- Product context: "CPA influencer marketing platform, fixed cost per conversion"
- Tone: "Spanish, warm Latin American business style"
- Instructions: "Sign off as Pavel Medvedev, NEVER use placeholder brackets"
- Category-specific behavior (meeting_request → confirm eagerly, interested → explain CPA model)

---

## Setting Up Auto-Replies for a New Project

### Step 1: Create the Project (if not exists)
Ensure the project exists in `projects` table with `campaign_filters` listing all relevant campaign names.

### Step 2: Set Sender Identity
```sql
UPDATE projects
SET sender_name = 'John Smith',
    sender_position = 'Account Executive',
    sender_company = 'YourCompany'
WHERE id = <project_id>;
```
This ensures AI drafts sign off correctly instead of using `[Your Name]` placeholders.

### Step 3: Create a Custom Prompt Template (recommended)
Insert into `reply_prompt_templates`:
```sql
INSERT INTO reply_prompt_templates (name, prompt_type, prompt_text, is_default, created_at, updated_at)
VALUES (
  'YourProject Reply Template',
  'reply',
  '<prompt text with {subject}, {body}, {category}, {first_name}, {last_name}, {company}, {sender_name}, {sender_position_line}, {sender_company_line} placeholders>',
  false, NOW(), NOW()
) RETURNING id;
```

Required placeholders in the prompt template:
- `{subject}` — lead's email subject
- `{body}` — lead's reply text
- `{category}` — classified category
- `{first_name}`, `{last_name}` — lead's name
- `{company}` — lead's company
- `{sender_name}` — from Project.sender_name
- `{sender_position_line}` — renders as ", Position" or "" if empty
- `{sender_company_line}` — renders as " at Company" or "" if empty

The prompt must end with:
```
Respond with ONLY a JSON object:
{{"subject": "Re: <subject>", "body": "<reply text>", "tone": "<professional|friendly|formal>"}}
```

### Step 4: Assign Template to Project
```sql
UPDATE projects SET reply_prompt_template_id = <template_id> WHERE id = <project_id>;
```

### Step 5: Register Webhooks
If the project's campaigns don't already have webhooks:
```bash
curl -X POST http://<server>:8000/api/crm-sync/setup-webhooks \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: 1" \
  -d '{"webhook_base_url": "http://<server>:8000/api"}'
```

### Step 6: Verify
1. Check the Replies page in the UI — filter by your project
2. Wait for a reply to come in, or test with the prompt debug endpoint:
   ```bash
   curl -X POST "http://<server>:8000/api/replies/test-prompt" \
     -d "subject=Test&body=I'm interested&first_name=John&company=TestCo&sender_name=Jane&sender_company=YourCo"
   ```

---

## Approval Status States

`ProcessedReply.approval_status` tracks the lifecycle of each reply. Possible values:

| Status | Set by | Meaning |
|--------|--------|---------|
| `NULL` / `"pending"` | Default on creation | Needs operator attention. Both values are treated identically by all queries (`needs_reply=true` filter). |
| `"approved"` | `approve-and-send` (production) | Draft was sent to the real lead via Smartlead API. |
| `"approved_test"` | `approve-and-send` with `?test_mode=true` (send succeeded) | Draft was sent but redirected to `TEST_RECIPIENT_EMAIL` (pn@getsally.io) instead of the real lead. |
| `"approved_dry_run"` | `approve-and-send` with `?test_mode=true` (no lead_id or API error) | Approved for tracking, but no email was actually sent. Graceful fallback — no 502 raised. |
| `"dismissed"` | `PATCH /{id}/status` with `status=dismissed` | Operator explicitly skipped the reply. |
| `"replied_externally"` | `_fetch_and_cache_thread()` auto-detection or `sync_conversation_histories` | The last message in the Smartlead thread is outbound, meaning someone already replied directly in Smartlead's inbox. |

**Lifecycle flow:**
```
NULL/pending  ──┬──→  approved          (production send)
                ├──→  approved_test     (test send succeeded)
                ├──→  approved_dry_run  (test send, no lead_id or API error)
                ├──→  dismissed         (operator skipped)
                └──→  replied_externally (auto-detected outbound reply in thread)
```

---

## Inbox Links

Each `ProcessedReply` can have an `inbox_link` pointing to the Smartlead master inbox for that specific lead conversation.

### How links are constructed

**Primary source — webhook payload:**
```python
inbox_link = (
    payload.get("ui_master_inbox_link")
    or (payload.get("body") or {}).get("ui_master_inbox_link")
)
```
Smartlead sends `ui_master_inbox_link` directly in the webhook payload.

**Fallback — constructed from `sl_email_lead_map_id`:**
```python
if not inbox_link:
    lead_map_id = payload.get("sl_email_lead_map_id") or ...
    if lead_map_id:
        inbox_link = f"https://app.smartlead.ai/app/master-inbox?action=INBOX&leadMap={lead_map_id}"
```

### Where inbox links appear
- **Replies UI**: clickable icon next to each reply opens the Smartlead inbox view
- **Slack notifications**: lead name is a hyperlink to the inbox, plus a "📬 Inbox" action button
- **Telegram notifications**: "Open in Smartlead" link appended to the message

---

## Conversation Thread & ThreadMessage

### ThreadMessage model (`thread_messages` table)
Pre-fetched conversation messages from Smartlead, cached in DB so the UI reads instantly without hitting the Smartlead API on every thread click.

Key fields:
- `reply_id` — FK to `processed_replies` (CASCADE delete)
- `direction` — `"inbound"` / `"outbound"`
- `subject`, `body` — message content
- `activity_at` — original message timestamp
- `activity_type` — `"email_sent"` (outbound) or `"email_replied"` (inbound)
- `position` — ordering index preserving chronological order

### `_fetch_and_cache_thread()` function
Located in `reply_processor.py`. Called:
1. Immediately after saving a new `ProcessedReply` (webhook processing)
2. On `GET /{reply_id}/conversation` — on cache miss or stale cache (>5 min)
3. On `GET /{reply_id}/full-history` — for any reply from the same lead never fetched

**Flow:**
1. Resolves `smartlead_lead_id` (three-tier fallback: reply field → Contact table → raw webhook data)
2. Calls `GET /campaigns/{id}/leads/{id}/message-history` on Smartlead API
3. Replaces all existing `ThreadMessage` rows (idempotent cache refresh)
4. Sets `reply.thread_fetched_at = utcnow()` to prevent re-fetch
5. **Auto-detects `replied_externally`**: if the last message is outbound and status is pending, auto-marks the reply

---

## Notification Channels

### Slack
- **Auth**: `SLACK_BOT_TOKEN` env var (xoxb- token). Falls back to incoming webhook URL if token is not set.
- **Message format**: Block Kit with header (emoji + category + clickable lead name), message preview (≤100 chars), draft preview, and action buttons: **OK** (approve), **Edit**, **Skip**, **📬 Inbox** (URL button).
- **Routing**: `ReplyAutomation` per campaign specifies the Slack channel. If no automation exists, falls back to default channel.
- **Interactive actions**: handled by `backend/app/api/slack_interactions.py` — operators can approve/dismiss directly from Slack.

### Telegram
- **Auth**: `TELEGRAM_BOT_TOKEN` env var (hardcoded default for dev).
- **Routing**: dual-routing — always sends to admin `TELEGRAM_CHAT_ID` ("57344339"), then looks up the project's `telegram_chat_id` for per-project operator routing.
- **Bot commands**: `/start project_<id>` (auto-link chat to project), `/start` (register username), `/status` (list linked projects).
- **Rate limiting**: respects Telegram 429 `retry_after`, exponential backoff (2s→4s→8s) for other errors.
- **Periodic reports**: every 4 hours, summarizes warm leads (interested/meeting_request/question) and negative replies per campaign. Admin gets all-projects view, operators get filtered.

---

## Scheduler & Background Jobs

`CRMScheduler` in `crm_scheduler.py` manages 9 supervised asyncio tasks with a watchdog:

| Task | Interval | Purpose |
|------|----------|---------|
| **CRM sync** | 30 min | Full sync — Smartlead + GetSales contacts & replies |
| **Reply polling** | 3 min (startup/unhealthy) → 10 min (steady) | Backup reply fetching + auto-assign new campaigns to projects by name prefix |
| **Webhook registration** | 5 min (1 min retry on failure) | Ensures all campaigns have webhooks pointing to `/api/smartlead/webhook` |
| **Event recovery** | 5 min (2 min initial delay) | Reprocesses failed `webhook_events` (up to 5 retries, exponential backoff: 5m→15m→45m→2h→6h) |
| **Conversation sync** | 3 min (1 min initial delay) | Fetches Smartlead thread history for pending replies, auto-marks `replied_externally` |
| **Telegram polling** | Continuous (30s long-poll) | Bot commands: `/start`, `/status`, project deep links |
| **Reports** | 4 hours | Telegram digest — warm leads + negative replies per campaign/project |
| **Prompt refresh** | Weekly (1h initial delay) | Regenerates AI reply prompt templates for all configured projects |
| **Sheet sync** | 5 min (90s initial delay) | Google Sheet bidirectional sync — push replies/leads, pull qualification changes every 15 min |
| **Watchdog** | 60 sec | Restarts dead tasks, monitors webhook health (>15 min since last webhook → fast polling) |

---

## Test Mode & Localhost Behavior

### Auto-enabled on localhost
The frontend automatically sets `test_mode=true` when running on `localhost` (see `frontend/src/api/replies.ts`). This ensures local development never sends emails to real leads.

### What happens in test mode
```
POST /api/replies/{id}/approve-and-send?test_mode=true

  ├─ No SmartLead lead_id
  │   → approval_status = "approved_dry_run"
  │   → No email sent, reply tracked for UI testing
  │
  ├─ Has lead_id → send via Smartlead API
  │   ├─ API call SUCCEEDS
  │   │   → Email sent to TEST_RECIPIENT_EMAIL (pn@getsally.io)
  │   │   → Subject prefixed with "[TEST — original: <real_email>]"
  │   │   → approval_status = "approved_test"
  │   │
  │   └─ API call FAILS
  │       → approval_status = "approved_dry_run"
  │       → Graceful fallback (no 502 error)
```

- `TEST_RECIPIENT_EMAIL` defaults to `pn@getsally.io` (configurable via env var)
- The email body is prefixed with `[TEST — original recipient: <real_email>]` + `<hr>` separator

### Production mode comparison
- Requires `Contact.smartlead_id` — raises HTTP 400 if missing
- Raises HTTP 502 on Smartlead API error (no graceful fallback)
- Sets `approval_status = "approved"`
- Creates `ContactActivity` record for the outbound message
- Syncs approval to Google Sheet if configured

---

## Testing with Real Smartlead Campaigns

### TEST_LORD_TEST Project (id=43)
A dedicated test project used for E2E testing of the full reply pipeline. Located at:
```
http://localhost:5179/replies → select "TEST_LORD_TEST" from project dropdown
```

### Scripts

#### `backend/create_real_campaigns.py`
Creates 3 real Smartlead campaigns, each with a different sender account:

| Sender | Domain |
|--------|--------|
| danila@flowsally.com | flowsally.com |
| danila@cloudsallyai.com | cloudsallyai.com |
| danila@team-sallyai.com | team-sallyai.com |

Each campaign:
- Has a unique timestamp-based name (e.g., `E2E_Test_GetSally_0223_1627`)
- Contains a 1-step email sequence
- Adds `pn@getsally.io` as the sole lead
- Is set to START immediately (24/7 schedule)

```bash
cd backend && python3 create_real_campaigns.py
```

#### `backend/seed_test_replies.py`
Seeds the database with 6 test replies (2 per campaign) across various categories:
- `meeting_request`, `interested`, `question`, `not_interested`, `out_of_office`

Each reply includes thread messages (outbound + inbound) for realistic conversation views. The script:
1. Updates `TEST_LORD_TEST.campaign_filters` to include the new campaign names
2. Deletes any existing test replies (cascade deletes thread messages)
3. Creates fresh replies with `approval_status=NULL` (pending)
4. Constructs `inbox_link` from `lead_map_id` for each campaign

```bash
cd backend && python seed_test_replies.py
```

### Test-Flow API Endpoints

Built-in API endpoints for testing the pipeline without needing external scripts:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/replies/test-flow/create-real-campaign` | Create a real Smartlead campaign (leaves in DRAFT for review) |
| `POST` | `/api/replies/test-flow/create-campaign` | Create a mock in-memory test campaign (no Smartlead call) |
| `POST` | `/api/replies/test-flow/simulate-reply` | Simulate a webhook reply — runs through full `process_reply_webhook()` pipeline |
| `GET` | `/api/replies/test-flow/email-accounts` | List Smartlead email accounts with remaining daily send capacity |
| `GET` | `/api/replies/test-flow/campaigns` | List campaigns matching "test" in name |
| `GET` | `/api/replies/test-flow/check-setup/{campaign_id}` | Check if a `ReplyAutomation` exists for a campaign |

### E2E Test Walkthrough

1. **Create campaigns** (one-time):
   ```bash
   cd backend && python3 create_real_campaigns.py
   ```
   Note the campaign IDs and Smartlead dashboard links from the output.

2. **Update seed script** with new campaign IDs and `lead_map_id` values:
   - Look up `lead_map_id` via: `GET /campaigns/{id}/leads?api_key=<key>`
   - Edit `TEST_CAMPAIGNS` in `seed_test_replies.py`

3. **Seed test replies**:
   ```bash
   cd backend && python seed_test_replies.py
   ```

4. **Verify in UI**: Open `http://localhost:5179/replies`, select TEST_LORD_TEST project. Should see 6 test replies with various categories.

5. **Test inbox link**: Click the inbox icon on any reply → should open Smartlead master inbox for that lead.

6. **Test send flow**: Click "Send" on a reply → `test_mode=true` (auto on localhost) redirects to `pn@getsally.io` → check inbox for the received test email.

7. **Verify via API**:
   ```bash
   # Check reply status after send
   curl -s http://localhost:8001/api/replies/?project_id=43 \
     -H "X-Company-ID: 1" | python3 -m json.tool | head -20
   ```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/app/api/smartlead.py` | Webhook receiver (`POST /api/smartlead/webhook`) |
| `backend/app/services/reply_processor.py` | Core pipeline: classify, draft, store, thread cache |
| `backend/app/api/replies.py` | Replies CRUD + approve-and-send + test-flow endpoints |
| `backend/app/models/reply.py` | ProcessedReply, ThreadMessage, ReplyAutomation, ReplyPromptTemplate models |
| `backend/app/models/contact.py` | Project model (sender fields, campaign_filters) |
| `backend/app/services/crm_sync_service.py` | Webhook registration + conversation sync |
| `backend/app/services/crm_scheduler.py` | 9 background tasks: CRM sync, reply polling, webhooks, recovery, threads, Telegram, reports, prompts, sheets |
| `backend/app/services/notification_service.py` | Slack + Telegram notifications, dual-routing, periodic reports |
| `backend/app/api/slack_interactions.py` | Slack interactive actions (approve/edit/dismiss from Slack) |
| `backend/create_real_campaigns.py` | Script: create 3 real Smartlead test campaigns |
| `backend/seed_test_replies.py` | Script: seed 6 test replies + threads for TEST_LORD_TEST project |
| `frontend/src/pages/RepliesPage.tsx` | Replies UI (quick-reply queue) |
| `frontend/src/api/replies.ts` | API client — test_mode auto-detection on localhost |
| `frontend/src/hooks/useTheme.ts` | Dark/light theme toggle |

## Troubleshooting

### Drafts show `[Tu Nombre]` or `[Your Name]` placeholders
→ Project is missing `sender_name`. Run: `UPDATE projects SET sender_name='...' WHERE id=X`

### Replies not appearing in UI
→ Check webhook is registered: `GET /api/smartlead/campaigns/{id}/webhooks`
→ Check `processed_replies` table for recent records
→ Check backend logs for webhook processing errors

### "No SmartLead lead_id" when sending
→ The Contact record is missing `smartlead_id`. The system tries to resolve it from `raw_webhook_data.sl_email_lead_id`. Trigger a sync or manually update.

### Draft language doesn't match lead's language
→ Add explicit language instruction in the custom prompt template (e.g., "Write in the SAME LANGUAGE as the prospect's message")
