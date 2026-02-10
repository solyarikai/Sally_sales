# Smartlead & GetSales Reply Tracking System

## Overview

The system tracks lead replies from two sources:
- **Smartlead** (email campaigns) - via webhooks + API polling every 30 minutes
- **GetSales** (LinkedIn outreach) - via webhooks + API polling every 30 minutes

Both feed into `ProcessedReply` (classification, draft, notifications) and `ContactActivity` (conversation history) tables.

### Architecture: Dual Approach (Webhooks + Polling)

| Layer | Smartlead (Email) | GetSales (LinkedIn) |
|-------|-------------------|---------------------|
| **Real-time** | Webhook: `POST /api/smartlead/webhook` | Webhook: `POST /api/crm-sync/webhook/getsales` |
| **Backup polling** | Every 30 min via Statistics API | Every 30 min via Inbox API |
| **Deduplication** | Redis cache + ProcessedReply DB | Redis cache + ContactActivity DB |
| **Processing** | Classify -> Draft -> Slack/Telegram -> Google Sheets | Classify -> Draft -> Telegram |

---

## Smartlead Integration (Email)

### Webhooks (Real-time)

**Endpoint:** `POST /api/smartlead/webhook`
**Handler:** `reply_processor.process_reply_webhook()`

**Events received:**
| Event | Description |
|-------|-------------|
| `EMAIL_REPLY` | Lead replied to a campaign email |
| `EMAIL_SENT` | Outbound email sent to lead |
| `LEAD_CATEGORY_UPDATED` | Lead's category changed (e.g., "Interested") |

**Webhook payload fields:**
- `event_type` - one of the events above
- `lead_email` - lead's email address
- `lead_name` - lead's full name
- `campaign_id` - Smartlead campaign ID
- `campaign_name` - campaign name
- `email_body` - HTML email body
- `email_subject` - subject line

**Processing pipeline (for EMAIL_REPLY):**
1. Strip HTML from email body
2. Check Redis + DB for duplicates
3. Classify reply via GPT-4o-mini (interested, not_interested, out_of_office, meeting_request, question, wrong_person, other)
4. Generate draft reply via AI
5. Create `ProcessedReply` record
6. Send Slack notification
7. Send Telegram notification
8. Log to Google Sheets

### API Polling (every 30 minutes)

**Scheduler:** `crm_scheduler._check_replies()` -> `crm_sync_service.sync_smartlead_replies()`

**Purpose:** Catches replies that webhooks might miss (downtime, network issues, delayed processing).

### Smartlead API Endpoints Used

| Endpoint | Purpose | Key Parameters |
|----------|---------|----------------|
| `GET /api/v1/campaigns` | List all campaigns | `api_key` |
| `GET /api/v1/campaigns/{id}/statistics` | **Primary:** Find all replied leads | `api_key`, `limit=500`, `offset` |
| `GET /api/v1/leads/?email={email}` | Global lead enrichment | `api_key`, `email` |
| `GET /api/v1/campaigns/{id}/leads/{lead_id}/message-history` | Get reply content | `api_key` |
| `GET /api/v1/campaigns/{id}/leads` | Get leads by category | `api_key`, `lead_category_id`, `offset`, `limit` |

### Statistics Endpoint (Primary Polling Method)

`GET /api/v1/campaigns/{campaign_id}/statistics?api_key=...&limit=500&offset=0`

Returns entries for each email sent in a campaign. Key fields:
- `lead_email` - the lead's email address
- `lead_name` - lead name
- `reply_time` - timestamp when lead replied (null if no reply)
- `is_bounced` - true if the email bounced
- `lead_category` - text category name (e.g., "Out Of Office")
- `email_subject` - subject line of the sent email

**Why this is the best approach:** It catches ALL replies regardless of lead category assignment. Some leads reply but are never categorized - the statistics endpoint still shows their `reply_time`. The previous category-based approach (`lead_category_id=9`) was broken because category 9 means "Sender Originated Bounce", not actual replies.

### Global Lead Search (Enrichment)

`GET /api/v1/leads/?email={email}&api_key=...`

Returns full lead data including:
- `id` (numeric lead ID, needed for message-history)
- `company_name`, `website`, `linkedin_profile`, `location`
- `custom_fields` (segment, title, #_Employees, etc.)
- `lead_campaign_data` array with `campaign_lead_map_id` per campaign

### Message History

`GET /api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history?api_key=...`

**Important:** The `lead_id` must be NUMERIC (from global lead search), NOT an email address. Passing an email returns a 400 error.

Returns `{ "history": [...] }` with messages:
- `type: "SENT"` - outbound emails
- `type: "REPLY"` - inbound replies (the data we want)
- `email_body` - HTML content of the message
- `time` - timestamp
- `subject` - email subject

### Lead Category IDs (Account-Specific)

These are custom per Smartlead account:

| Category ID | Meaning | Count (Rizzult) |
|-------------|---------|-----------------|
| 1 | Interested | ~27 |
| 2 | Meeting Booked | ~8 |
| 3 | Not Interested | ~10 |
| 5 | Do Not Contact | ~1 |
| 6 | Replied (general) | ~154 |
| 9 | Sender Originated Bounce | ~141 (EXCLUDED) |
| 77593 | Custom reply category | ~25 |
| 77594 | Custom reply category | ~1 |
| 77596 | Custom reply category | ~1 |
| 77598 | Hot Lead / Meeting Scheduled | ~19 |

**Category 9 is bounces and is excluded from reply tracking.**

### Smartlead Polling Flow

```
crm_scheduler._check_replies() (every 30 min)
  -> crm_sync_service.sync_smartlead_replies()
    -> For each campaign (ACTIVE/PAUSED/COMPLETED):
      -> smartlead_service.get_all_campaign_replied_leads()
        -> GET /campaigns/{id}/statistics (paginated, 500/page)
        -> Filter: reply_time != null AND is_bounced == false
        -> Dedup by email
      -> For each new replied lead:
        -> Check Redis cache (key: "smartlead_replies", field: "{email}_{campaignId}")
        -> Check ProcessedReply DB (email+campaign)
        -> smartlead_service.get_lead_by_email_global(email)
          -> GET /leads/?email={email} (enrichment: company, linkedin, etc.)
          -> Extract numeric lead_id for message history
        -> smartlead_service.get_email_thread(campaign_id, lead_id)
          -> GET /campaigns/{id}/leads/{lead_id}/message-history
          -> Find latest REPLY message, strip HTML
        -> reply_processor.process_reply_webhook(payload)
          -> Classify via OpenAI GPT-4o-mini
          -> Generate draft reply
          -> Create ProcessedReply record
          -> Send Slack notification
          -> Send Telegram notification
          -> Log to Google Sheets
```

---

## GetSales Integration (LinkedIn)

### Base URL & Authentication

- **Base URL:** `https://amazing.getsales.io`
- **Auth:** Bearer token in `Authorization` header
- All requests include `Content-Type: application/json`

### Webhooks (Real-time)

**Endpoint:** `POST /api/crm-sync/webhook/getsales`
**Handler:** `backend/app/api/crm_sync.py` (lines 748-1126)

**Webhook events:**
| Event | Description |
|-------|-------------|
| `contact_replied_linkedin_message` | Lead replied on LinkedIn |
| `contact_replied_email` | Lead replied via email |
| `contact_enriched` | Contact data enriched |
| `contact_linkedin_connection_accepted` | Connection request accepted |
| `contact_linkedin_connection_requested` | Connection request sent |

**Webhook payload structure:**
```json
{
  "body": {
    "contact": {
      "uuid": "lead-uuid",
      "first_name": "John",
      "last_name": "Doe",
      "work_email": "john@company.com",
      "linkedin_url": "https://linkedin.com/in/johndoe",
      "position": "CEO",
      "company_name": "Company Inc",
      "pipeline_stage_name": "Replied"
    },
    "account": {
      "name": "Company Inc",
      "website": "https://company.com"
    },
    "automation": {
      "uuid": "flow-uuid",
      "name": "Rizzult_shopping_apps"
    },
    "linkedin_message": {
      "type": "inbox",
      "text": "Hi, I'm interested...",
      "sent_at": "2026-02-10T12:00:00Z",
      "linkedin_type": "MEMBER_TO_MEMBER"
    },
    "contact_markers": {
      "linkedin_messages_sent_count": 3,
      "linkedin_messages_inbox_count": 1
    }
  }
}
```

**Webhook processing flow:**
1. Extract `contact`, `account`, `automation`, `linkedin_message` from payload
2. Determine if reply (`type == "inbox"`) or sent message
3. Find or create Contact (by `getsales_id`, email, or LinkedIn URL)
4. Dedup check (same source + activity type + time window + snippet)
5. Create `ContactActivity` record
6. If reply: classify via AI, generate draft, create `ProcessedReply`, send Telegram notification
7. Update contact status (`has_replied`, `reply_channel`, `last_reply_at`)
8. Add flow to contact's campaign list

**Webhook auto-setup:** `crm_scheduler` calls `getsales.setup_crm_webhooks()` every 6 hours, pointing to `http://46.62.210.24:8000/api/crm-sync/webhook/getsales`. Checks existing webhooks before creating to avoid duplicates.

### GetSales API Endpoints Used

| Endpoint | Purpose | Key Parameters |
|----------|---------|----------------|
| `GET /flows/api/linkedin-messages` | Fetch inbox/outbox messages | `filter[type]`, `limit`, `offset`, `order_field`, `order_type` |
| `GET /flows/api/linkedin-messages` | Get conversation thread | `filter[linkedin_conversation_uuid]` |
| `GET /leads/api/lists` | List all lead lists | - |
| `GET /flows/api/flows` | List automations/flows | - |
| `POST /leads/api/leads/search` | Search leads with filters | `list_uuid`, `search` |
| `GET /integrations/api/webhooks` | List configured webhooks | - |
| `POST /integrations/api/webhooks` | Create webhook | `name`, `event`, `target_url` |
| `DELETE /integrations/api/webhooks/{uuid}` | Delete webhook | - |

### Inbox Messages (Polling)

`GET /flows/api/linkedin-messages`

**Parameters for inbox:**
- `filter[type]: "inbox"` - Only received messages
- `limit: 100` - Per page
- `offset: 0` - Pagination
- `order_field: "created_at"` - Sort by date
- `order_type: "desc"` - Newest first

**Response:**
```json
{
  "data": [
    {
      "uuid": "msg-uuid",
      "id": 12345,
      "text": "Thanks for reaching out...",
      "sender_profile_uuid": "lead-uuid",
      "linkedin_conversation_uuid": "conv-uuid",
      "linkedin_type": "MEMBER_TO_MEMBER",
      "created_at": "2026-02-10T12:00:00Z",
      "automation": { "uuid": "flow-uuid", "name": "Flow Name" }
    }
  ],
  "has_more": true,
  "total": 250
}
```

### GetSales Polling Flow

```
crm_scheduler._check_replies() (every 30 min)
  -> crm_sync_service.sync_getsales_replies()
    -> Pagination loop (max 10 pages x 100 messages):
      -> GET /flows/api/linkedin-messages (type=inbox, newest first)
      -> For each message:
        -> Check Redis cache (key: "getsales", field: msg uuid/id)
        -> If cached: increment cached counter, check early stop
        -> If msg older than 48h: stop pagination
        -> If 20 consecutive cached hits: early stop
      -> For each NEW message:
        -> Find Contact by getsales_id (lead_uuid)
        -> If no contact found: skip, increment no_contact counter
        -> Check DB for existing ContactActivity (source=getsales, source_id=msg_id)
        -> Create ContactActivity:
          -> activity_type: "linkedin_replied"
          -> channel: "linkedin"
          -> direction: "inbound"
          -> source: "getsales"
          -> source_id: message uuid
          -> body: message text
          -> extra_data: sender_profile_uuid, conversation_uuid, linkedin_type, automation
        -> Update Contact:
          -> has_replied = True
          -> reply_channel = "linkedin"
          -> last_reply_at = message time
          -> status = "replied"
      -> Bulk add all new message IDs to Redis cache
    -> Return stats: {new_replies, existing, cached, no_contact, pages}
```

### GetSales Flow Name Resolution

Known flow UUIDs are mapped to human-readable names:

| Flow UUID | Name |
|-----------|------|
| `b4188b80-...` | EasyStaff - Russian DM [>500 connects] |
| `f62647b1-...` | Inxy - Russian DM's |
| `4bbd26d3-...` | RIzzult_Wellness apps 10 01 26 |
| `6bfeca8c-...` | Rizzult_shopping_apps |

Resolution priority: `automation_name` from webhook -> `flow_name` -> UUID lookup -> contact campaigns -> "Unknown Flow"

---

## Scheduling & Polling Configuration

**File:** `backend/app/services/crm_scheduler.py`

| Task | Interval | Method |
|------|----------|--------|
| Full Contact Sync | 30 min | `_sync_contacts()` |
| **Reply Check (Smartlead + GetSales)** | **30 min** | `_check_replies()` |
| Webhook Setup | 6 hours | `_setup_webhooks()` |
| Reports | 4 hours | `_send_reports()` |
| Prompt Refresh | Weekly (168h) | `_refresh_prompts()` |

The `_check_replies()` method calls both `sync_smartlead_replies()` and `sync_getsales_replies()` in sequence.

---

## Deduplication Strategy

### Multi-Layer Approach

| Layer | Smartlead | GetSales |
|-------|-----------|----------|
| **Redis (fast)** | Key: `smartlead_replies`, Field: `{email}_{campaignId}` | Key: `getsales`, Field: `{msg_uuid}` |
| **DB (reliable)** | Query `ProcessedReply` by email+campaign | Query `ContactActivity` by source+source_id |
| **Webhook-level** | - | Time-window (same minute) + snippet match |

### Redis Operations
```python
# Check if already processed
cached = await bulk_check_replies("smartlead_replies", reply_keys)
cached = await bulk_check_replies("getsales", message_ids)

# Mark as processed
await bulk_add_replies("smartlead_replies", new_reply_keys)
await bulk_add_replies("getsales", new_message_ids)
```

---

## Comparison with Reference Sheet

### Endpoint
`GET /replies/rizzult-comparison`

Reads the n8n reference Google Sheet and compares with local `ProcessedReply` records.

### Reference Sheet
- Sheet ID: `1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s`
- Tab: "Replies" (gid: 1599376288)
- Key columns: `target_lead_email`, `campaign`, `campaign_id`, `Source`, `text`

### Current Coverage (as of 2026-02-10)
- **Smartlead API polling:** 310 unique emails found
- **Reference sheet (Email):** 137 unique emails -> 92 matched (67.2%)
- **Reference sheet (LinkedIn):** 120 unique emails (via GetSales)
- Missing emails are from: deleted leads, legacy campaigns, or webhook-only captures

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/smartlead_service.py` | Smartlead API client (statistics, global lead search, message history) |
| `backend/app/services/crm_sync_service.py` | Reply sync logic (polling) + GetSalesClient class |
| `backend/app/services/crm_scheduler.py` | Scheduler (30-min polling, 6h webhook setup) |
| `backend/app/services/reply_processor.py` | Reply classification + processing pipeline |
| `backend/app/api/replies.py` | API endpoints including `/rizzult-comparison` |
| `backend/app/api/crm_sync.py` | Webhook endpoints for Smartlead + GetSales |
| `backend/app/services/notification_service.py` | Slack + Telegram notifications |
| `backend/app/services/google_sheets_service.py` | Google Sheets read/write |

---

## HTML Stripping

Reply bodies from Smartlead come as HTML. The `_strip_html()` method in `crm_sync_service.py`:
- Removes `<style>` and `<script>` blocks
- Removes inline CSS (`* { font-family:... }`)
- Converts `<br>`, `<div>`, `<p>` to newlines
- Strips all remaining HTML tags
- Decodes HTML entities
- Removes quoted content (previous emails in thread)

---

## Improvements Made (2026-02-10)

### Critical Bug Fixes
1. **Smartlead polling was completely broken:** The old code passed `lead_category_id=9` to `get_campaign_leads()`, but category 9 = "Sender Originated Bounce" (bounces, NOT replies). All 141 "replies" found were actually bounces.
2. **`get_email_thread()` used email as lead_id:** The message-history endpoint requires a NUMERIC lead_id (from global search), not an email address. Passing email returned 400 errors.
3. **No reply content fetched:** Old polling only created ContactActivity records without fetching actual reply text, classifying, or notifying.

### New Approach
1. **Statistics endpoint** replaces category-based filtering — catches ALL replies regardless of category assignment
2. **Global lead search** enriches each replied lead with company/LinkedIn/website data and provides the numeric lead_id needed for message-history
3. **Full reply pipeline** now runs for polled replies (same as webhooks): classify -> draft -> notify -> log
4. **Proper HTML stripping** handles CSS blocks, script tags, inline styles, and quoted content
