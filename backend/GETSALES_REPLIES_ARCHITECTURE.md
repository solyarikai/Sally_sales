# GetSales LinkedIn Replies — Architecture & Data Flow

## Overview

GetSales LinkedIn replies flow through two independent ingestion paths into the same processing pipeline, producing `ProcessedReply` records with AI classification, draft generation, Telegram notifications, and inbox links.

---

## 1. Ingestion Paths

### Path A: Webhook (`POST /api/webhook/getsales`)

```
GetSales automation event → HTTP POST → getsales_webhook() → process_getsales_reply()
```

**File:** `backend/app/api/crm_sync.py:923`

**Webhook body structure:**
```json
{
  "body": {
    "contact": { "uuid": "<lead_uuid>", "work_email": "...", ... },
    "automation": { "uuid": "<automation_uuid>", "name": "...", "sender_profile_uuid": "<sender_uuid>" },
    "linkedin_message": { "uuid": "<msg_uuid>", "text": "...", "type": "inbox" },
    "account": { "name": "..." },
    "contact_markers": { ... }
  }
}
```

**Key extraction:**
- `lead_uuid` = `body.contact.uuid`
- `sender_profile_uuid` = `body.automation.sender_profile_uuid`
- `raw_data` passed to `process_getsales_reply()` = entire `body` dict

### Path B: Polling (`sync_getsales_replies()`)

```
Cron (every 5 min) → GetSales API /flows/api/inbox-messages → sync_getsales_replies() → process_getsales_reply()
```

**File:** `backend/app/services/crm_sync_service.py:1600+`

**Polled message structure:**
```json
{
  "uuid": "<msg_uuid>",
  "lead_uuid": "<lead_uuid>",
  "sender_profile_uuid": "<sender_uuid>",
  "text": "...",
  "created_at": "2026-02-20T14:30:00Z",
  "automation": { "uuid": "...", "name": "..." }
}
```

**Key extraction:**
- `lead_uuid` = `msg.lead_uuid` or `msg.lead.uuid`
- `sender_profile_uuid` = `msg.sender_profile_uuid`
- `raw_data` passed to `process_getsales_reply()` = entire `msg` dict

### Deduplication Between Paths

Both paths converge in `process_getsales_reply()` which deduplicates by checking:
```sql
SELECT * FROM processed_replies
WHERE source = 'getsales' AND LOWER(lead_email) = :email AND campaign_name = :campaign
```
If a reply already exists for this email+campaign, it updates rather than creates a new one.

Additionally, polling uses a Redis cache (`getsales_replies:{message_id}`) to skip already-processed messages without hitting the database.

---

## 2. Sender Name Resolution

### Two separate mappings

**CRITICAL ARCHITECTURE DECISION:** Sender profiles and automations are separate concepts:
- A **sender profile** = a LinkedIn account (person), e.g., "Lera Yurkoits"
- An **automation** = a campaign/flow, e.g., "Mifort Partners Salesforce"
- The SAME sender profile can be used across MULTIPLE automations/projects

Two **strictly separate** mappings exist in `crm_sync_service.py`:

1. `GETSALES_FLOW_NAMES`: Maps **only automation UUIDs** → campaign names (used for campaign routing + project classification)
2. `GETSALES_SENDER_PROFILES`: Maps **only sender_profile UUIDs** → person names (display only, NEVER for routing)

**CRITICAL RULE:** Sender profile UUIDs must NEVER appear in `GETSALES_FLOW_NAMES`. A sender (e.g. Pavel Medvedev) can work across multiple projects (EasyStaff RU, Rizzult, etc.). Using sender UUID for campaign routing causes misclassification.

### Source of truth

GetSales API endpoint `/flows/api/sender-profiles` (paginated, 50 per page).

Each sender profile has:
```json
{
  "uuid": "4d1effeb-34fc-4999-bada-4a3651021adb",
  "first_name": "Ekaterina",
  "last_name": "Khoroshilova",
  "label": "EasyStaff"
}
```

### Where sender name is extracted

**Backend API** (`replies.py`, `_extract_sender_name()`):

- **LinkedIn replies**: looks up `sender_profile_uuid` in `GETSALES_SENDER_PROFILES` → person name (e.g., "Lera Yurkoits")
- **Email replies**: extracts `from_email` from `raw_webhook_data` → inbox email (e.g., "egor@paybissecure.com")

### Where displayed

| Channel  | Campaign name               | Sender name              |
|----------|-----------------------------|--------------------------|
| LinkedIn | "Mifort Partners Salesforce"| "via Lera Yurkoits"      |
| Email    | "Paybis_Baltics"            | "egor@paybissecure.com"  |

Both are shown in:
1. **Replies UI** — campaign name + sender (separated by " · ")
2. **Telegram notification** — "Campaign:" line + "Sender:" line
3. **Send button** — shows `via {campaign_name}`

### Adding new sender profiles

When a new LinkedIn account is added to GetSales:
1. Query the API: `GET /flows/api/sender-profiles?limit=100`
2. Add UUID → person name to `GETSALES_SENDER_PROFILES` **only**
3. Do NOT add to `GETSALES_FLOW_NAMES` — that map is for automations only

### Adding new automations

When a new automation/campaign is created in GetSales:
1. Get the automation UUID from GetSales (webhook payload or API)
2. Add UUID → campaign name to `GETSALES_FLOW_NAMES`
3. `_PROJECT_PREFIXES` auto-populates `GETSALES_UUID_TO_PROJECT` for Telegram routing

**If a sender UUID is missing from `GETSALES_SENDER_PROFILES`:**
- `sender_name` will be `None` → UI shows `campaign_name` only
- Telegram notification omits the "Sender:" line
- Inbox link still works
- No crash or data loss

**If an automation UUID is missing from `GETSALES_FLOW_NAMES`:**
- Webhook path still works (uses automation name from payload directly)
- Polling path: `automation: "synced"` always → reply gets empty campaign_name (unclassified)
- Unclassified replies appear in "All" view but not in any project
- Once webhook arrives with real automation data, campaign_name is corrected (FIXED 2026-02-27: timestamp guard bypassed for unclassified records)

**`_PROJECT_PREFIXES` mapping (project name prefix → project ID):**
- Used to auto-populate `GETSALES_UUID_TO_PROJECT` for Telegram notification routing
- Covers: easystaff(40), squarefi(40), inxy(40), rizzult(22), mifort(21), mft(21), tfp(13), archistruct(24), gwc(17), onsocial(42), palark(16)

---

## 3. Inbox Links (GetSales Conversation URLs)

### Correct format (as of 2026-02-27)

```
https://amazing.getsales.io/messenger/{lead_uuid}?senderProfileId="{sender_profile_uuid}"
```

The `senderProfileId` value is URL-encoded: `%22{uuid}%22` (double-quotes around UUID).

### How inbox links are built

**File:** `crm_sync_service.py:730-737`, `GetSalesClient.build_inbox_url()`

```python
base = f"https://amazing.getsales.io/messenger/{lead_uuid}"
if sender_profile_uuid:
    base += f'?senderProfileId={quote(chr(34) + sender_profile_uuid + chr(34))}'
```

### lead_uuid extraction in `process_getsales_reply()`

**File:** `reply_processor.py:1302-1303`

```python
lead_uuid = (
    raw_data.get("lead_uuid")           # polling format: top-level
    or raw_data.get("lead", {}).get("uuid")  # alternative polling format
    or raw_data.get("contact", {}).get("uuid")  # webhook format: nested under contact
)
```

All three paths are covered. The webhook body uses `contact.uuid`, polling uses `lead_uuid`.

### sender_profile_uuid extraction for inbox links

**File:** `reply_processor.py:1304-1308`

```python
sender_profile_uuid = (
    raw_data.get("sender_profile_uuid")  # polling: top-level
    or (raw_data.get("automation", {}) or {}).get("sender_profile_uuid")  # webhook: nested
    or ""
)
```

### Current DB state

| Metric | Count |
|--------|-------|
| GetSales replies with correct inbox_link (includes senderProfileId) | 156 |
| GetSales replies with incomplete inbox_link (no senderProfileId) | 0 |
| GetSales replies with old unibox format | 0 |
| GetSales replies with no inbox_link | 0 |

---

## 4. Telegram Notifications

### Email replies (SmartLead)

**Function:** `notify_reply_needs_attention()` in `notification_service.py:757`

```
📧 New Email Reply!
From: lead@example.com
Subject: Re: ...
Company: Acme Corp
Campaign: Campaign Name
Inbox: egor@paybissecure.com    ← inbox/mailbox email

Message: <preview>

📋 Open in Replies UI  ·  📬 Open in SmartLead
```

### LinkedIn replies (GetSales)

**Function:** `notify_linkedin_reply()` in `notification_service.py:800`

```
🔗 New LinkedIn Reply!
From: John Doe
Email: john@acme.com
Campaign: Mifort Partners Salesforce    ← automation/campaign name
Sender: Lera Yurkoits                   ← person name (LinkedIn account)

Message: <preview>

📋 Open in Replies UI
💼 Open in GetSales
```

Both notifications include:
- **"Open in Replies UI"** → `http://46.62.210.24/tasks/replies?lead={email}` (pre-fills search, shows all categories)
- **Source platform link** → SmartLead master inbox or GetSales messenger URL

### Routing

1. Admin chat always receives all notifications
2. Project subscribers receive notifications routed by campaign_name → project mapping
3. Fallback: `GETSALES_UUID_TO_PROJECT` maps sender_profile_uuid → project_id for routing when campaign lookup fails

---

## 5. Campaign Selection & Multi-Campaign Replies

### Architecture

A single contact may have replies across multiple campaigns (e.g., different SmartLead campaigns or GetSales automations).

### Frontend logic (`ReplyQueue.tsx`)

1. **Default selection**: When history loads, `campaigns[0]` is auto-selected — backend sorts by `latest_at DESC` (most recent first)
2. **CampaignDropdown**: Shown when `history.campaigns.length > 1`, displays campaign name, message count, and recency
3. **ConversationThread**: Filters displayed messages by the selected campaign
4. **Sticky header**: "Hide history" button + campaign dropdown stick to top of card while scrolling through long threads

### Cross-campaign send protection (`guardSend`)

```
User clicks Send → guardSend() checks:
  ├─ No campaign selected (history not loaded) → Send immediately (default campaign)
  ├─ Selected campaign == reply.campaign_name → Send immediately (default campaign)
  └─ Selected campaign != reply.campaign_name → Show confirmation modal:
      ├─ "Switch to {default} and send"  → switches + sends
      ├─ "Send in {viewed} anyway"       → sends as-is
      └─ "Cancel"                        → cancels
```

The reply is always sent via `reply.campaign_name` (the ProcessedReply's campaign). The confirmation modal warns the operator when they're viewing a different campaign's thread.

---

## 6. Channel Labels in UI

| Channel | Badge | Color |
|---------|-------|-------|
| LinkedIn | `LinkedIn` | Blue (#0a66c2 on #e7f0fe) |
| Email | `Email` | Orange (#b45309 on #fef3e2) |

Both badges appear next to the lead name in the reply card header.

---

## 7. Clipboard Copy (LinkedIn URL)

Uses `navigator.clipboard.writeText()` with fallback for non-HTTPS environments.

Since the app runs on `http://46.62.210.24` (plain HTTP), `navigator.clipboard` is unavailable. A `document.execCommand('copy')` fallback via hidden textarea is used.

---

## 8. Potential Issues & Mitigations

### Race condition: concurrent webhook + polling

**Risk:** Same reply arrives via webhook and polling simultaneously.
**Mitigation:** `process_getsales_reply()` uses two-tier dedup:
1. Exact match by `(source, lead_email, campaign_id)` — handles same-path duplicates (only when `flow_uuid` is non-empty)
2. Broader match by `(source, lead_email)` — catches all cases including polling-without-automation + webhook-with-automation

Redis cache in polling path provides additional fast-path dedup.

### Polling always returns `automation: "synced"` (KNOWN LIMITATION)

**Root cause:** The GetSales inbox API (`/flows/api/inbox-messages`) ALWAYS returns `"automation": "synced"` as a string, never the actual automation object. This is a GetSales API limitation, not a bug in our code.

**Impact:** Polling can never determine the automation/campaign for a reply. All polling-created records start with empty `campaign_name`.

**Mitigation:** Webhook-driven correction (see below).

### Cross-project sender profiles (FIXED 2026-02-25)

**Root cause:** `GETSALES_FLOW_NAMES` mixed sender_profile UUIDs with automation UUIDs. When polling returned `automation: "synced"`, it fell back to `sender_profile_uuid` as campaign ID → looked up "EasyStaff RU - Pavel Medvedev" → routed to EasyStaff RU even when the actual automation was Rizzult/Mifort.

**Architectural fix:**
1. **`GETSALES_FLOW_NAMES` contains ONLY automation UUIDs** — all ~35 sender profile entries removed
2. **Polling NEVER uses sender_profile_uuid for routing** — when `automation: "synced"` and no contact campaigns found, `flow_name` and `flow_uuid` stay empty
3. **Empty campaign = unclassified** (visible in "All" view, not in any project) — this is correct behavior, better than misclassified
4. **Webhook auto-corrects** — when the real webhook arrives with proper automation data, `campaign_name` and `campaign_id` get updated on the existing record
5. **Update logic protects existing data** — `campaign_name` is only overwritten when the new `flow_name` is non-empty

### Webhook not updating polling-created records (FIXED 2026-02-27)

**Root cause:** `process_getsales_reply()` dedup checked `activity_at <= existing_pr.received_at` and skipped the update if true. Polling sets `received_at = datetime.utcnow()`. Webhook's `activity_at` comes from `linkedin_message.sent_at` (actual message time, BEFORE polling picked it up). So `activity_at < received_at` → webhook skipped → campaign_name never updated.

**Fix:** When existing record has empty `campaign_name` and the incoming call has a non-empty `flow_name`, the timestamp guard is bypassed, allowing the webhook to fill in the correct automation/campaign data.

**Code:** `reply_processor.py:1240-1247` — `has_new_campaign_info` check.

### Missing sender_profile_uuid

**Risk:** GetSales webhook/polling response doesn't include sender_profile_uuid.
**Mitigation:** Extraction checks 3 locations: `raw_data.sender_profile_uuid`, `raw_data.automation.sender_profile_uuid`, and empty string fallback. Inbox link is still usable without senderProfileId.

### New sender profile added to GetSales

**Risk:** New LinkedIn account added, replies come in but sender name not shown.
**Mitigation:** Graceful degradation — UI shows `campaign_name` only, Telegram omits "Sender:" line. No crash. To fix: add UUID to `GETSALES_SENDER_PROFILES` only (NOT to `GETSALES_FLOW_NAMES`).

### New automation added to GetSales

**Risk:** New automation/campaign, replies come through polling but unclassified.
**Mitigation:** Add automation UUID → campaign name to `GETSALES_FLOW_NAMES`. Until added, replies still arrive (via polling or webhook) but campaign_name may be empty until webhook data fills it in.

### GetSales API changes message format

**Risk:** Polling API changes field names.
**Mitigation:** Multi-path extraction for all critical fields (`lead_uuid`, `sender_profile_uuid`). Three extraction paths per field ensure forward compatibility.

---

## 9. Key Files Reference

| File | Purpose |
|------|---------|
| `backend/app/api/crm_sync.py:923` | GetSales webhook handler |
| `backend/app/services/crm_sync_service.py:150` | `GETSALES_FLOW_NAMES` — automation UUIDs only (NEVER sender profiles) |
| `backend/app/services/crm_sync_service.py:183` | `GETSALES_SENDER_PROFILES` — sender profiles for display only |
| `backend/app/services/crm_sync_service.py:730` | `build_inbox_url()` |
| `backend/app/services/crm_sync_service.py:1600` | `sync_getsales_replies()` polling |
| `backend/app/services/reply_processor.py:1185` | `process_getsales_reply()` |
| `backend/app/services/notification_service.py:800` | `notify_linkedin_reply()` |
| `backend/app/api/replies.py:57` | `_extract_sender_name()` |
| `backend/scripts/backfill_getsales_inbox_links.py` | One-time migration: unibox→messenger format |
| `backend/scripts/check_gs_automations.py` | Debug: list all GetSales flows |
| `backend/scripts/check_gs_senders.py` | Debug: list all sender_profile_uuids in DB |
| `frontend/src/components/ReplyQueue.tsx` | Reply queue UI with campaign selection |
| `frontend/src/components/CampaignDropdown.tsx` | Multi-campaign selector |
