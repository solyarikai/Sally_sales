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

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/app/api/smartlead.py` | Webhook receiver (`POST /api/smartlead/webhook`) |
| `backend/app/services/reply_processor.py` | Core pipeline: classify, draft, store |
| `backend/app/api/replies.py` | Replies CRUD + approve-and-send endpoint |
| `backend/app/models/reply.py` | ProcessedReply, ReplyAutomation, ReplyPromptTemplate models |
| `backend/app/models/contact.py` | Project model (sender fields, campaign_filters) |
| `backend/app/services/crm_sync_service.py` | Webhook registration + conversation sync |
| `backend/app/services/crm_scheduler.py` | Periodic background sync (every 30 min) |
| `frontend/src/pages/RepliesPage.tsx` | Replies UI (quick-reply queue) |
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
