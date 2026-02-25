wjh# CRM API Documentation & Data Flow

## Overview

This document describes all known APIs for Smartlead (email outreach) and GetSales (LinkedIn outreach) integrations, including reply tracking mechanisms.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     CRM SYNC & REPLY TRACKING SYSTEM                            │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────────┐
                    │         EXTERNAL PLATFORMS           │
                    └──────────────────────────────────────┘
                              │                │
            ┌─────────────────┴────┐      ┌────┴─────────────────┐
            │      SMARTLEAD       │      │      GETSALES        │
            │   (Email Outreach)   │      │  (LinkedIn Outreach) │
            │   1,676 campaigns    │      │   20 flows/510K leads│
            └──────────────────────┘      └──────────────────────┘
                    │                              │
        ┌───────────┼───────────┐      ┌───────────┼───────────┐
        ▼           ▼           ▼      ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ Webhook │ │  API    │ │  API    │ │ Webhook │ │ Webhook │ │  API    │
   │ (Reply) │ │(Stats)  │ │(Camps)  │ │ (Reply) │ │ (Bulk)  │ │(Inbox)  │
   │ ✅ Live │ │ ✅ Daily│ │ ✅ Sync │ │ ✅ Live │ │ ✅ Live │ │ ✅ Daily│
   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │           │           │           │
        │     ┌─────┴─────┐     │           │           │     ┌─────┴─────┐
        │     │Daily Cron │     │           │           │     │Daily Cron │
        │     │ 2:00 AM   │     │           │           │     │ 2:00 AM   │
        │     └─────┬─────┘     │           │           │     └─────┬─────┘
        │           │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┴───────────┘
                                        │
                                        ▼
                    ┌──────────────────────────────────────┐
                    │         HETZNER SERVER               │
                    │      (46.62.210.24:8000)             │
                    └──────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
        ▼                               ▼                               ▼
┌───────────────┐           ┌───────────────────┐           ┌───────────────┐
│   Webhook     │           │     Sync API      │           │   Background  │
│   Handlers    │           │   /crm-sync/*     │           │   Scripts     │
├───────────────┤           ├───────────────────┤           ├───────────────┤
│/webhook/      │           │/trigger           │           │fetch_getsales_│
│  smartlead    │───┐       │/sync-now          │           │  replies.py   │
│  ✅ Creates   │   │       │/setup-webhooks    │           │               │
│  new contacts │   │       │/fetch-replies     │           │enrich_getsales│
│               │   │       │                   │           │  _flows.py    │
│/webhook/      │   │       │                   │           │               │
│  getsales     │───┼──────▶│ Creates contact   │           │daily_reply_   │
│  ✅ Creates   │   │       │ + Activity        │           │  refetch.sh   │
│  + Enriches   │   │       │ + Enriches flows  │           │               │
│               │   │       │                   │           │               │
│/webhook/      │   │       │                   │           │               │
│  getsales/    │───┘       │                   │           │               │
│  bulk-import  │           │                   │           │               │
│  ✅ Creates   │           │                   │           │               │
└───────┬───────┘           └─────────┬─────────┘           └───────┬───────┘
        │                             │                             │
        └─────────────────────────────┴─────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │           PostgreSQL DB              │
                    │     (46.62.210.24:5432)              │
                    ├──────────────────────────────────────┤
                    │  contacts (51K+)                     │
                    │    - email (unique, case-insensitive)│
                    │    - last_reply_at (→ has_replied)   │
                    │    - platform_state (JSONB)          │
                    │      └ smartlead: {campaigns, status}│
                    │      └ getsales: {campaigns, status} │
                    │    - provenance (JSONB, origin data) │
                    │    - smartlead_id / getsales_id      │
                    │                                      │
                    │  contact_activities (500+)           │
                    │    - email_replied                   │
                    │    - linkedin_replied                │
                    │    - email_sent / linkedin_sent      │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │           Frontend UI                │
                    │       (React + AG Grid)              │
                    ├──────────────────────────────────────┤
                    │  - Filter by "Replied" ✅            │
                    │  - Filter by Channel (Email/LI) ✅   │
                    │  - Filter by Campaign ✅             │
                    │  - View Activity History ✅          │
                    └──────────────────────────────────────┘
```

### Edge Cases Handled

| Scenario | Smartlead | GetSales | Handler Location |
|----------|-----------|----------|------------------|
| **New contact via webhook** | ✅ Creates contact with campaign info | ✅ Creates contact with flow info | `crm_sync.py:760+` |
| **Reply from unknown contact** | ✅ Creates contact, marks as replied | ✅ Creates contact, marks as replied | Webhook handlers |
| **Existing contact, new flow** | ✅ Appends campaign to JSON | ✅ Appends new flow to campaigns JSON | `crm_sync.py:827+` |
| **Missing email** | ⚠️ Requires email | ✅ Uses `linkedin_{uuid}@getsales.local` | `crm_sync.py:756` |
| **Duplicate activity** | ✅ Checked by source_id | ✅ Checked by source_id | Activity creation |
| **Invalid JSON in webhook** | ✅ Returns 400 | ✅ Returns 400 | Try/except wrapper |
| **linkedin_message missing** | ✅ N/A | ✅ Handles gracefully, is_reply=false | `crm_sync.py:700` |
| **automation field missing** | ✅ N/A | ✅ Contact created without campaign | Null check |
| **conversation_thread is list** | ✅ N/A | ✅ Fixed - handles list type | `crm_sync.py` |
| **Duplicate flow in campaigns** | ✅ Checks by campaign_id | ✅ Checks existing_flow_ids before append | `crm_sync.py:847` |
| **campaigns field is null/string/list** | ✅ Robust parsing | ✅ Robust parsing | JSON loads/dumps |

### Cross-Source Contact Merging ⭐ NEW

When a contact from one source matches an existing contact from another source:

| Scenario | Matching Logic | Result |
|----------|----------------|--------|
| **GetSales → existing Smartlead** | Match by email OR LinkedIn URL | Merges: adds `getsales_id`, appends flow to campaigns |
| **Smartlead → existing GetSales** | Match by email OR LinkedIn URL | Merges: adds `smartlead_id`, appends campaign to campaigns |
| **LinkedIn URL matching** | Extracts handle, case-insensitive | `linkedin.com/in/JohnDoe` matches `linkedin.com/in/johndoe` |

**Example merge result:**
```json
{
  "email": "john@example.com",
  "smartlead_id": "12345",
  "getsales_id": "uuid-abc-123",
  "campaigns": [
    {"name": "Email Campaign", "id": "12345", "source": "smartlead"},
    {"name": "LinkedIn Flow", "id": "uuid-flow", "source": "getsales"}
  ]
}

### Webhook Testing Commands

Test GetSales webhook with new contact + reply:
```bash
curl -X POST "http://46.62.210.24:8000/api/crm-sync/webhook/getsales" \
  -H "Content-Type: application/json" \
  -d '{"body":{"contact":{"uuid":"test-uuid","first_name":"Test","last_name":"User","work_email":"test@example.com"},"automation":{"uuid":"flow-123","name":"Test Flow"},"linkedin_message":{"type":"inbox","text":"Hello!"}}}'
```

Expected response:
```json
{"status":"processed","activity_id":123,"contact_id":456,"is_reply":true}
```

Test Smartlead webhook:
```bash
curl -X POST "http://46.62.210.24:8000/api/crm-sync/webhook/smartlead" \
  -H "Content-Type: application/json" \
  -d '{"body":{"event_type":"EMAIL_REPLY","lead_email":"test@example.com","campaign_id":123,"lead_data":{"first_name":"Test"}}}'
```

---

## API Credentials (for Local Agents)

All credentials needed to connect to external services:

```bash
# PostgreSQL Database
DATABASE_URL="postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen"

# Smartlead API
SMARTLEAD_API_KEY="eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"

# GetSales API
GETSALES_API_KEY="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc"

# Telegram Bot (for notifications)
TELEGRAM_BOT_TOKEN="8543996153:AAHnqBM52tK2zUUMUEM4fLUA4tozufXoOss"
TELEGRAM_CHAT_ID="57344339"

# Redis (internal to Docker network, use for local testing only if tunneled)
REDIS_URL="redis://redis:6379"
```

### Quick API Test Commands

**Test Smartlead API:**
```bash
curl "https://server.smartlead.ai/api/v1/campaigns?api_key=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5" | jq '.[:2]'
```

**Test GetSales API:**
```bash
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc" \
  "https://amazing.getsales.io/flows/api/flows?per_page=5" | jq '.data[:2]'
```

---

## Smartlead API

**Base URL:** `https://server.smartlead.ai/api/v1`  
**Authentication:** Query parameter `?api_key=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5`

### Reply Tracking Methods

| Method | Type | Frequency | Description |
|--------|------|-----------|-------------|
| Webhook | Real-time | Instant | Configure per-campaign, receives EMAIL_REPLY events with full message content |
| API Poll | `/campaigns/{id}/leads?lead_category_id=9` | Daily (2 AM) | Fetch leads marked as replied (no message content) |

**Important:** The Smartlead API does NOT provide reply message content via polling. Only webhooks receive the actual reply text.

### Lead Categories

| Category ID | Meaning |
|-------------|---------|
| 1-8 | Various custom categories |
| 9 | **Replied** - leads who have responded |

### Endpoints

#### 1. Get Campaigns
```
GET /campaigns?api_key={key}
```
**Response:** Array of campaigns (1676 total)
```json
{
  "id": 2896114,
  "name": "Auto-Reply Test 4cfd2e19",
  "status": "COMPLETED",  // ACTIVE, PAUSED, COMPLETED, SCHEDULED
  "max_leads_per_day": 100
}
```

#### 2. Get Campaign Leads (with Category Filter)
```
GET /campaigns/{campaign_id}/leads?api_key={key}&limit=100&lead_category_id=9
```
**Parameters:**
- `limit` - max leads to return (default 100)
- `offset` - pagination offset
- `lead_category_id` - filter by category (9 = replied)

**Response:**
```json
{
  "data": [
    {
      "campaign_lead_map_id": 2576933244,
      "lead_category_id": 9,
      "status": "COMPLETED",  // NOT "REPLIED" - status is about email sequence
      "created_at": "2026-01-12T13:24:46.000Z",
      "lead": {
        "id": 2528678434,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "linkedin_profile": "https://linkedin.com/in/johndoe"
      }
    }
  ],
  "total_leads": "232"
}
```

**Note:** `reply_time` and `lead_status=REPLIED` do NOT exist in this API. Use `lead_category_id=9` to find replied leads.

#### 3. Get Campaign Analytics
```
GET /campaigns/{campaign_id}/analytics?api_key={key}
```
**Response:** Contains `reply_count` for the campaign.

#### 4. Configure Webhooks

⚠️ **CRITICAL: Must include `categories` field for reply body!**

```
POST /campaigns/{campaign_id}/webhooks?api_key={key}
{
  "name": "Reply Webhook",
  "webhook_url": "http://46.62.210.24:8000/api/crm-sync/webhook/smartlead",
  "event_types": ["EMAIL_REPLY", "LEAD_CATEGORY_UPDATED", "EMAIL_SENT"],
  "categories": [
    "Interested", "Meeting Request", "Not Interested", "Do Not Contact",
    "Information Request", "Out Of Office", "Wrong Person",
    "Uncategorizable by Ai", "Sender Originated Bounce", "Sample Sent",
    "Positive Reply", "Negative Reply", "Sample Reviewed", "Qualified",
    "Meeting Booked", "Not Now", "Not Qualified"
  ]
}
```

**Without `categories`, Smartlead only sends metadata - NO reply body, preview_text, or reply_message!**

#### Webhook Management Notes

| Operation | Supported | Notes |
|-----------|-----------|-------|
| Create | ✅ POST | Returns webhook ID |
| List | ✅ GET `/campaigns/{id}/webhooks` | Returns all webhooks for campaign |
| Update | ❌ PATCH/PUT | Not supported - must delete and recreate |
| Delete | ❌ DELETE | Not supported via API - use Smartlead UI |

**Workaround for broken webhooks:** Create a NEW webhook with correct config. Old webhooks remain but new ones receive full data.

### Webhook Payload (EMAIL_REPLY)

**With `categories` field configured (correct):**
```json
{
  "body": {
    "event_type": "EMAIL_REPLY",
    "campaign_id": 123456,
    "lead_email": "john@example.com",
    "lead_id": 789,
    "lead_data": {
      "first_name": "John",
      "category": { "name": "Positive Reply", "sentiment_type": "positive" }
    },
    "reply_body": "Thanks for reaching out...",
    "preview_text": "Thanks for reaching...",
    "reply_message": { "text": "Thanks for reaching out...", "html": "<p>Thanks...</p>" },
    "last_reply": { "email_body": "...", "time": "2026-02-01T14:30:00.000Z" },
    "history": [...]
  }
}
```

**Without `categories` field (broken - only metadata):**
```json
{
  "body": {
    "event_type": "EMAIL_REPLY",
    "campaign_id": 123456,
    "lead_email": "john@example.com",
    "lead_id": 789,
    "lead_data": { "first_name": "John" }
    // NO reply_body, preview_text, or reply_message!
  }
}
```

---

## GetSales API

**Base URL:** `https://amazing.getsales.io`  
**Authentication:** Header `Authorization: Bearer <GETSALES_API_KEY from credentials above>`

### Reply Tracking Methods

| Method | Type | Frequency | Description |
|--------|------|-----------|-------------|
| Webhook | Real-time | Instant | Receives linkedin_message with type="inbox" |
| API Poll | `/flows/api/linkedin-messages` | Daily (planned) | Fetch all inbox messages (19,527 total) |

### Endpoints

#### 1. Get Flows (Automations)
```
GET /flows/api/flows?per_page=200
```

#### 2. Get Flows-Leads Mapping
```
GET /flows/api/flows-leads?per_page=1000&offset=0
```
**Total:** 510,697 records

**Filtering by lead_uuid (FAST enrichment):**
```
GET /flows/api/flows-leads?filter[lead_uuid]={uuid}&per_page=100
```
This returns only flows for a specific lead - much faster than paginating all 510K records!

#### 3. Get LinkedIn Inbox Messages (Replies) ⭐ NEW
```
GET /flows/api/linkedin-messages?limit=100&offset=0&filter[type]=inbox
```
**Total inbox messages:** 19,527

**Response:**
```json
{
  "data": [
    {
      "uuid": "352ce93b-5a17-4ef4-8b44-f046611a1920",
      "lead_uuid": "2d191f73-4643-4490-9fcc-263b483eeff8",  // ⭐ Match to contact
      "sender_profile_uuid": "774af09b-8158-4150-835d-6cf1ee00819a",
      "text": "Thanks for connecting, but not interested",
      "type": "inbox",  // ⭐ "inbox" = received reply
      "status": "done",
      "sent_at": "2026-02-03T15:55:04.000000Z",
      "created_at": "2026-02-03T15:55:06.000000Z"
    }
  ],
  "total": 19527,
  "has_more": true
}
```

**Filter Options:**
- `filter[type]=inbox` - Only received messages (replies)
- `filter[type]=outbox` - Only sent messages
- `filter[lead_uuid]=xxx` - Messages for specific lead
- `filter[sender_profile_uuid]=xxx` - Messages from specific sender

#### 4. Bulk Export Webhook
Configure in GetSales UI → Settings → Webhooks

**Webhook URL:** `http://46.62.210.24:8000/api/crm-sync/webhook/getsales/bulk-import`

#### 5. Reply Activity Webhook
**Webhook URL:** `http://46.62.210.24:8000/api/crm-sync/webhook/getsales`

**Webhook Payload (LinkedIn Reply):**
```json
{
  "body": {
    "contact": {
      "uuid": "2d191f73-4643-4490-9fcc-263b483eeff8",
      "first_name": "John",
      "linkedin_url": "linkedin.com/in/john-doe"
    },
    "automation": {
      "uuid": "b7a31e91-9166-41f8-9d16-4c2f8823ba5b",
      "name": "Inxy - Crypto Payments"
    },
    "linkedin_message": {
      "text": "Thanks for connecting...",
      "type": "inbox",  // ⭐ "inbox" = reply from contact
      "sent_at": "2026-02-03T15:55:04.000000Z"
    }
  }
}
```

---

## CRM Database Schema

### Connection Details

```
Host:     46.62.210.24
Port:     5432
Database: leadgen
User:     leadgen
Password: leadgen123
```

**Connection string:**
```
postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen
```

### Connection Test Commands

Before working with the database, verify connectivity:

**Quick test with psql:**
```bash
psql "postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen" -c "SELECT COUNT(*) as total_contacts FROM contacts;"
```

**Python test (asyncpg):**
```python
import asyncio
import asyncpg

async def test_connection():
    conn = await asyncpg.connect("postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen")
    result = await conn.fetchrow("SELECT COUNT(*) as total FROM contacts")
    print(f"Connected! Total contacts: {result['total']}")
    await conn.close()

asyncio.run(test_connection())
```

**Python test (psycopg2 sync):**
```python
import psycopg2
conn = psycopg2.connect("postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM contacts")
print(f"Connected! Total contacts: {cur.fetchone()[0]}")
conn.close()
```

**Expected output:** `Connected! Total contacts: 52352` (or similar)

### Quick Stats Verification Query

Run this to verify all key metrics at once:

```sql
SELECT 
  (SELECT COUNT(*) FROM contacts) as total_contacts,
  (SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL) as smartlead_contacts,
  (SELECT COUNT(*) FROM contacts WHERE getsales_id IS NOT NULL) as getsales_contacts,
  (SELECT COUNT(*) FROM contacts WHERE smartlead_id IS NOT NULL AND getsales_id IS NOT NULL) as merged,
  (SELECT COUNT(*) FROM contacts WHERE has_replied = true) as replied,
  (SELECT COUNT(*) FROM contact_activities) as activities,
  (SELECT COUNT(*) FROM processed_replies) as webhook_replies;
```

**Expected result (as of 2026-02-04):**
```
total_contacts | smartlead_contacts | getsales_contacts | merged | replied | activities | webhook_replies
---------------+--------------------+-------------------+--------+---------+------------+----------------
         52352 |              49971 |              6250 |   3871 |     879 |       9029 |             84
```

**If connection fails:**
1. Check if your IP is allowed (contact server admin)
2. Verify port 5432 is open: `nc -zv 46.62.210.24 5432`
3. Try from Hetzner server itself: `ssh hetzner 'docker exec leadgen-postgres psql -U leadgen -d leadgen -c "SELECT 1"'`

**psql command:**
```bash
psql "postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen"
```

**Python (asyncpg):**
```python
import asyncpg
conn = await asyncpg.connect("postgresql://leadgen:leadgen123@46.62.210.24:5432/leadgen")
```

**SQLAlchemy:**
```python
DATABASE_URL = "postgresql+asyncpg://leadgen:leadgen123@46.62.210.24:5432/leadgen"
```

---

### contacts table

**Unique Constraint:** `idx_contacts_email_unique` on `LOWER(email)` - prevents duplicate contacts

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | int | Auto | Primary key |
| `email` | string | Both | Email (unique, case-insensitive) |
| `first_name` | string | Both | |
| `last_name` | string | Both | |
| `company_name` | string | Both | |
| `linkedin_url` | string | Both | Normalized URL |
| `phone` | string | Both | |
| `status` | string | Computed | "new", "contacted", "replied" |
| `has_replied` | bool | Computed | ⭐ True if any reply received |
| `reply_channel` | string | Computed | "email" or "linkedin" |
| `last_reply_at` | datetime | Computed | When last reply was received |
| `smartlead_id` | string | Smartlead | Lead ID in Smartlead |
| `getsales_id` | string | GetSales | UUID in GetSales |
| `smartlead_status` | string | Smartlead | Category name |
| `getsales_status` | string | GetSales | Pipeline stage |
| `campaigns` | JSON | Enriched | Array of campaign associations |

### contact_activities table

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `contact_id` | int | FK to contacts |
| `activity_type` | string | "email_replied", "linkedin_replied", "email_sent", etc. |
| `channel` | string | "email" or "linkedin" |
| `direction` | string | "inbound" (reply) or "outbound" (sent) |
| `source` | string | "smartlead" or "getsales" |
| `body` | text | Message content |
| `activity_at` | datetime | When activity occurred |
| `extra_data` | JSON | Campaign info, automation info, etc. |

---

## Reply Tracking Configuration

### Currently Active

| Platform | Method | Status | Description |
|----------|--------|--------|-------------|
| Smartlead | Webhook | ✅ Primary | Real-time, includes full reply message content (requires `categories` field!) |
| Smartlead | API Poll (category=9) | ✅ Fallback | Marks contacts as replied, NO message content |
| GetSales | Webhook | ✅ Primary | Real-time, includes full LinkedIn message |
| GetSales | API Poll (inbox) | ✅ Fallback | Fetches LinkedIn inbox messages with content |

**Critical Notes on Smartlead:**

1. **Webhook `categories` field is MANDATORY for reply body:**
   - Without `categories`, webhook only sends metadata (email, campaign_id, category)
   - With `categories`, webhook includes `reply_body`, `preview_text`, `reply_message`
   - Our code now includes all 17 categories automatically

2. **API limitations:**
   - The Smartlead API does NOT provide reply message content
   - API polling uses `lead_category_id=9` to find replied leads
   - `reply_time` and `lead_status=REPLIED` do NOT exist - these were incorrectly assumed
   - Reply content is ONLY available via webhooks

3. **Webhook management:**
   - No DELETE or UPDATE endpoints exist
   - To fix a broken webhook, create a NEW one with correct config
   - Multiple webhooks per campaign are allowed

### Cron Jobs (Hetzner)

```bash
# Daily Smartlead reply refetch at 2 AM
0 2 * * * /home/leadokol/magnum-opus-project/repo/scripts/daily_reply_refetch.sh

# Autocoding loop (every 5 min)
*/5 * * * * /home/leadokol/magnum-opus-project/repo/scripts/autocoding_loop.sh
```

**Note:** `auto_sync_cron.sh` was disabled (2026-02-03) - sync now uses only the in-app `CRMScheduler` with Redis lock to prevent concurrent syncs.

### Sync Lock (Concurrency Protection)

The CRM sync uses a Redis-based lock to prevent duplicate contact creation:

```python
# In crm_sync_service.py
from app.services.cache_service import acquire_sync_lock, release_sync_lock

async def full_sync(...):
    if not await acquire_sync_lock():
        return {"error": "Sync already in progress", "skipped": True}
    try:
        # ... sync logic
    finally:
        await release_sync_lock()
```

**Lock settings:** Key: `leadgen:sync_lock`, TTL: 600 seconds (10 min)

---

## Webhook URLs (Hetzner Server)

| Purpose | URL | Status |
|---------|-----|--------|
| GetSales Bulk Export | `http://46.62.210.24:8000/api/crm-sync/webhook/getsales/bulk-import` | ✅ |
| GetSales Reply | `http://46.62.210.24:8000/api/crm-sync/webhook/getsales` | ✅ |
| Smartlead Reply | `http://46.62.210.24:8000/api/crm-sync/webhook/smartlead` | ✅ |

---

## Current Stats (as of 2026-02-04 01:40 UTC)

### Contacts

| Metric | Count |
|--------|-------|
| **Total Contacts** | **52,352** |
| Has Smartlead ID | 49,971 |
| Has GetSales ID | 6,250 |
| **Merged (Both IDs)** | **3,871** |
| **Replied Contacts** | **879** |

### Activities

| Metric | Count |
|--------|-------|
| **Total Activities** | **9,029** |
| Smartlead Activities | 657 |
| GetSales Activities | 8,372 |
| Processed Replies (webhook) | 84 |

### Historical Messages Available

| Platform | In Database | Available in API | Notes |
|----------|-------------|------------------|-------|
| Smartlead (Email) | 84 | N/A | API has no reply content endpoint |
| GetSales Inbox | ~1,300 | 19,551 | Run `sync_historical_messages.py` |
| GetSales Outbox | ~7,000 | 168,679 | Run `sync_historical_messages.py` |

### Recent Fixes

| Date | Issue | Fix Applied | Result |
|------|-------|-------------|--------|
| **2026-02-25** | `mark_replied()` never updates | Compare timestamps, keep latest | `last_reply_at` always reflects most recent reply |
| **2026-02-25** | Sheet sync `'int' object has no attribute 'id'` | Handle legacy int campaign IDs in `platform_state` | Sheet sync no longer crashes on old data |
| **2026-02-25** | `has_replied`, `reply_channel` columns redundant | Removed columns, `has_replied` derived from `last_reply_at` | Clean datamodel with no duplication |
| **2026-02-25** | Prompt refresh runs for disabled projects | Filter by `webhooks_enabled=True` | Disabled projects fully silent |
| 2026-02-03 | Duplicate contacts | Redis sync lock + unique email index | Prevented future duplicates |
| 2026-02-03 | Low merge count (819) | Case-insensitive email matching | Merged: 819 → 3,679 (4.5x) |
| 2026-02-03 | Missing smartlead_id | Backfill script queried Smartlead API | 2,808 contacts fixed |
| 2026-02-03 | Concurrent sync race | Disabled cron, use in-app scheduler only | No more duplicate creation |
| 2026-02-04 | Smartlead webhook "No body" | Added `categories` field to webhook creation | Now receives full reply content |

### Known Issues & Limitations

| Issue | Cause | Workaround |
|-------|-------|------------|
| **Smartlead: Can't delete webhooks** | API returns 404 on DELETE for campaign-level webhooks | Delete manually via SmartLead Settings UI; our system ignores events from disabled projects |
| **Smartlead: Can't update webhooks** | API doesn't support PATCH/PUT | Same as above - create new webhook |
| **Smartlead: No reply content via API** | API `get_campaign_leads` has no message fields | Use Statistics API + message-history endpoint; webhooks provide content directly |
| **"Company: Unknown" in notifications** | Contact lacks `company_name` in DB | Data enrichment issue - not all contacts have company data |
| **GetSales "Unknown Flow"** | API messages lack `automation_name` | Use `get_getsales_flow_name()` helper with UUID-to-name mapping |

### Campaign Enrichment Status

| Source | Total Contacts | With Campaigns | Coverage |
|--------|----------------|----------------|----------|
| **Smartlead** | 48,426 | ~48,300 | **99.7%** |
| **GetSales** | 6,227 | 6,226 | **99.99%** ✅ |

**Note:** 
- Smartlead contacts get campaign info during initial sync (from `/campaigns/{id}/statistics`)
- GetSales contacts are enriched via `filter[lead_uuid]` on `/flows/api/flows-leads` - processes 10K contacts in ~2.5 minutes
- GetSales enrichment found **39,978 flow entries** (many contacts are in multiple flows)

### Platform Stats

| Platform | Metric | Count |
|----------|--------|-------|
| Smartlead | Campaigns | 1,678 |
| Smartlead | Active Campaigns | 483 |
| GetSales | Flows (Automations) | 20 |
| GetSales | Active Flows | 13 |
| GetSales | Flow-Leads (API) | 510,697 |
| GetSales | Inbox Messages | 19,551 |
| GetSales | Outbox Messages | 168,679 |

---

## Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| `sync_historical_messages.py` | ✅ Fetch ALL historical GetSales messages (188K total) | `backend/scripts/` |
| `fetch_getsales_replies.py` | ✅ Fetch LinkedIn inbox messages & mark contacts as replied | `~/magnum-opus-project/repo/scripts/` |
| `enrich_getsales_flows_fast.py` | ✅ FAST enrichment using `filter[lead_uuid]` (~2.5 min for 10K contacts) | `~/magnum-opus-project/repo/scripts/` |
| `enrich_getsales_flows.py` | OLD: Slow enrichment scanning all 510K records (~30 min) | `~/magnum-opus-project/repo/scripts/` |
| `enrich_smartlead_campaigns.py` | Enrich Smartlead contacts with campaign names (rarely needed) | `~/magnum-opus-project/repo/scripts/` |
| `fix_missing_smartlead_ids.py` | ✅ Backfill smartlead_id for contacts with campaign data but no ID | `~/magnum-opus-project/repo/scripts/` |
| `deduplicate_contacts.sql` | ✅ SQL script to remove duplicate contacts | `~/magnum-opus-project/repo/scripts/` |
| `daily_reply_refetch.sh` | Daily reply fetch from both platforms | `~/magnum-opus-project/repo/scripts/` |
| `run_enrichment.sh` | Run all enrichment scripts | `~/magnum-opus-project/repo/scripts/` |

### Running Historical Messages Sync

```bash
# SSH to Hetzner and run in background:
docker exec leadgen-backend python3 -m app.scripts.sync_historical_messages &

# Or run interactively to see progress:
docker exec -it leadgen-backend python3 -m app.scripts.sync_historical_messages
```

This fetches all 188,230 GetSales messages (inbox + outbox) and stores them in `contact_activities`.
Sends Telegram progress updates every 1,000 inbox / 5,000 outbox messages.

---

## Raw JSON Debugging Columns

For local debugging and analytics, contacts have raw JSON columns that store all data from source platforms:

### `smartlead_raw` (JSONB)
Stores all Smartlead webhook payloads and API responses for a contact:
```json
{
  "webhooks": [
    {
      "received_at": "2026-02-04T10:30:00Z",
      "type": "reply",
      "category": "interested",
      "payload": { /* full webhook JSON */ }
    }
  ],
  "api_data": { /* data from API calls */ }
}
```

### `getsales_raw` (JSONB)
Stores all GetSales webhook payloads and API responses:
```json
{
  "webhooks": [
    {
      "received_at": "2026-02-04T10:30:00Z",
      "type": "reply",
      "category": "meeting_request",
      "payload": { /* full webhook JSON */ }
    }
  ],
  "api_data": { /* data from API calls */ }
}
```

### `touches` (JSONB)
Detailed history of all outreach touches:
```json
[
  {
    "at": "2026-02-04T10:30:00Z",
    "campaign": "Easystaff - Russian DM",
    "campaign_id": "2831338",
    "source": "smartlead",
    "channel": "email",
    "type": "sent",
    "category": null,
    "message": "Hi, I noticed..."
  },
  {
    "at": "2026-02-05T15:20:00Z",
    "campaign": "Easystaff - Russian DM",
    "source": "smartlead",
    "channel": "email",
    "type": "reply",
    "category": "interested",
    "message": "Yes, tell me more..."
  }
]
```

### Local Debugging Queries

**Check raw webhook data for a contact:**
```sql
SELECT email, smartlead_raw->'webhooks' as webhooks
FROM contacts WHERE email = 'example@company.com';
```

**Find contacts with specific webhook type:**
```sql
SELECT email, getsales_raw->'webhooks'->0->>'category' as category
FROM contacts 
WHERE getsales_raw->'webhooks' IS NOT NULL
LIMIT 10;
```

**Analyze touches for a contact:**
```sql
SELECT email, jsonb_array_length(touches::jsonb) as touch_count,
       touches->0->>'campaign' as first_campaign
FROM contacts WHERE touches IS NOT NULL AND touches::text != '[]'
ORDER BY jsonb_array_length(touches::jsonb) DESC LIMIT 10;
```

**Get contacts with N+ touches:**
```sql
SELECT id, email, jsonb_array_length(touches::jsonb) as touches
FROM contacts WHERE jsonb_array_length(touches::jsonb) >= 5
ORDER BY jsonb_array_length(touches::jsonb) DESC;
```

---

## Outbound Funnel Status Values

### Status Logic & Checksum

The `status` column represents the current funnel stage. **Key rule:** Every contact with `has_replied=true` MUST have a reply status (not `touched`).

**Checksum verification:**
```sql
-- These two numbers must match:
SELECT COUNT(*) FROM contacts WHERE has_replied = true;  -- replied contacts
SELECT COUNT(*) FROM contacts WHERE status IN ('warm', 'not_interested', 'out_of_office', 'wrong_person', 'other');  -- reply statuses
```

### Status Values

| Status | Description | Source |
|--------|-------------|--------|
| `touched` | Contacted via email/LinkedIn, **no reply yet** | `has_replied = false` |
| `warm` | Replied with interest, meeting request, question | AI classified as: interested, meeting_request, question |
| `not_interested` | Replied with explicit rejection | AI classified as: not_interested, unsubscribe |
| `out_of_office` | Auto-reply, vacation, away | AI classified as: out_of_office |
| `wrong_person` | Left company, wrong contact | AI classified as: wrong_person |
| `other` | Replied but content unknown/unclassified | Reply detected but no message body to classify |
| `scheduled` | Meeting scheduled | Has `scheduled_at` date |
| `qualified` | Meeting held, qualified | Has `qualified_at` date |
| `not_qualified` | Meeting held, not qualified | Has `disqualified_at` date |

### Status by Source Breakdown

| Status | Smartlead | GetSales | Both | Total |
|--------|-----------|----------|------|-------|
| touched | 45,929 | 2,259 | 3,464 | 51,652 |
| warm | 0 | 25 | 53 | 78 |
| not_interested | 0 | 52 | 264 | 316 |
| out_of_office | 2 | 0 | 3 | 5 |
| wrong_person | 207 | 10 | 21 | 238 |
| other | 515 | 30 | 98 | 643 |

**Total: 52,932 contacts**
- Smartlead only: 46,653
- GetSales only: 2,376  
- Both (merged): 3,903

### Why "other" exists

The `other` status (643 contacts) represents contacts that:
1. Were marked as "replied" by Smartlead API (lead_category_id=9)
2. But we don't have the actual reply message content
3. Without content, we cannot classify into warm/not_interested/etc

This happens because Smartlead API polling detects replies but doesn't provide message body. Only webhooks capture full reply content.

**Run stats script to see current funnel:**
```bash
ssh hetzner "docker exec leadgen-backend python3 /app/scripts/check_stats.py"
```

**Verify checksum:**
```bash
ssh hetzner "docker exec leadgen-postgres psql -U leadgen -d leadgen -c \"
SELECT 
  (SELECT COUNT(*) FROM contacts WHERE last_reply_at IS NOT NULL) as replied,
  (SELECT COUNT(*) FROM contacts WHERE status IN ('warm','not_interested','out_of_office','wrong_person','other')) as reply_statuses
\""
```

---

## Troubleshooting Guide

### Smartlead Webhook Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| **"No body" in Telegram notifications** | Webhook missing `categories` field | Create new webhook with categories (see "Configure Webhooks" section) |
| **Webhook not receiving events** | Webhook URL unreachable | Check server is running, port 8000 is open |
| **404 when deleting webhook** | Smartlead API doesn't support DELETE | Cannot delete via API - use Smartlead UI or create replacement webhook |
| **Reply not detected by API polling** | Wrong field check (`reply_time` doesn't exist) | Use `lead_category_id=9` filter |

### GetSales Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| **"Unknown Flow" in reports** | API messages lack automation_name | `get_getsales_flow_name()` helper uses UUID mapping + contact campaigns |
| **Messages duplicated** | Same message processed multiple times | Redis cache for reply IDs prevents duplicates |
| **Historical sync stopped** | Container restarted and killed background process | Restart: `docker exec -d leadgen-backend python3 -m app.scripts.sync_historical_messages` |

### Database Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Duplicate contacts** | Race condition during sync | Redis sync lock + unique email index |
| **Connection refused** | IP not whitelisted | Contact admin to add IP to pg_hba.conf |
| **"Company: Unknown"** | Contact missing company_name | Data quality issue - not all leads have company |

### Debugging Commands

**Check last webhook payload received:**
```bash
ssh hetzner "cat /tmp/last_webhook.json | jq ."
```

**Check backend logs for webhook processing:**
```bash
ssh hetzner "docker logs leadgen-backend --tail 100 | grep -i webhook"
```

**Verify webhook is configured correctly for a campaign:**
```bash
ssh hetzner "docker exec leadgen-backend python3 -c \"
import asyncio, httpx, os
async def check():
    api_key = os.getenv('SMARTLEAD_API_KEY')
    campaign_id = 2687353  # Replace with your campaign
    async with httpx.AsyncClient() as c:
        r = await c.get(f'https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/webhooks?api_key={api_key}')
        for w in r.json():
            print(f'Webhook {w[\"id\"]}: categories={len(w.get(\"categories\", []))} items')
asyncio.run(check())
\""
```

---

### Running the Fast Enrichment Script

```bash
# SSH to Hetzner and run:
docker exec -e DATABASE_URL="postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen" \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e TELEGRAM_CHAT_ID="your-chat-id" \
  leadgen-backend python3 /app/scripts/enrich_getsales_flows_fast.py
```

The script sends Telegram notifications at 10%, 20%, ... 100% progress.

---

## Status Sync Endpoint

### PATCH /api/contacts/{id}/status

Update contact status and sync to Smartlead.

**Request:**
```json
{
  "status": "scheduled",
  "scheduled_at": "2024-02-15T10:00:00Z",
  "sync_to_smartlead": true,
  "notes": "Meeting booked via calendar"
}
```

**Response:**
```json
{
  "id": 12345,
  "email": "john@company.com",
  "old_status": "warm",
  "new_status": "scheduled",
  "scheduled_at": "2024-02-15T10:00:00Z",
  "smartlead_synced": true,
  "getsales_synced": false
}
```

**Status Mapping (CRM → Smartlead Category):**

| CRM Status | Smartlead Category ID | Auto-Pause |
|------------|----------------------|------------|
| warm | 1 (Interested) | No |
| scheduled | 77598 (Meeting Booked) | Yes |
| qualified | 77597 (Qualified) | Yes |
| not_qualified | 78987 (Not Qualified) | Yes |
| not_interested | 3 (Not Interested) | Yes |
| wrong_person | 7 (Wrong Person) | Yes |
| out_of_office | 6 (Out Of Office) | No |

---

## Raw Data Gathering

### Purpose

Contacts from Smartlead/GetSales only have basic fields synchronized. The `smartlead_raw` and `getsales_raw` columns store complete webhook payloads and API data for future enrichment.

### Progress Check

```bash
ssh hetzner "docker exec leadgen-backend python3 /app/app/scripts/check_raw_data_progress.py"
```

### Start Enrichment

```bash
# Run in background (will send Telegram updates)
ssh hetzner "docker exec -d leadgen-backend python3 /app/app/scripts/enrich_raw_data.py"
```

### Data Structure

**contacts.smartlead_raw:**
```json
{
  "fetched_at": "2024-02-01T12:00:00Z",
  "campaigns": [...],
  "conversations": {"123": [...messages...]},
  "webhooks": [{"received_at": "...", "type": "email_reply", "payload": {...}}]
}
```

**contacts.getsales_raw:**
```json
{
  "fetched_at": "2024-02-01T12:00:00Z",
  "profile": {...full contact data...},
  "messages": [...LinkedIn message history...],
  "webhooks": [{"received_at": "...", "type": "linkedin_reply", "payload": {...}}]
}
```

### Webhook Enrichment

Webhooks automatically append to the raw columns when received:
- Smartlead reply webhook → appends to `smartlead_raw.webhooks`
- GetSales LinkedIn reply → appends to `getsales_raw.webhooks`

---

## Local Development Setup

### Database Tables (37 tables in production)

Required tables for ContactsPage:
- `contacts` - Main contacts table
- `conversations` - For needs_reply_count stats
- `campaigns` - Campaign metadata
- `contact_campaigns` - Contact-campaign associations
- `projects` - For filter options

All tables exist in production database.

### SSH Tunnel Setup

```bash
# Terminal 1: Start SSH tunnel to remote PostgreSQL
ssh -L 5433:localhost:5432 hetzner -N

# Optional: Redis tunnel
ssh -L 6380:localhost:6379 hetzner -N
```

### Environment Configuration

Create `.env.local` in backend directory:

```bash
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@localhost:5433/leadgen
REDIS_URL=redis://localhost:6380
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZWFtX2lkIjo4MjgsInVzZXJfaWQiOjEwNTgsInNjb3BlcyI6WyJhZG1pbiJdLCJpYXQiOjE3MzY1MDExNzR9.R_skxWr52Bl8tcNR5hSLey84_BMntjiLLjoH31FxV-M
TELEGRAM_BOT_TOKEN=7819187032:AAEgLFfbKblxXpNq7CZwAQK-SG67cEF9Q8E
TELEGRAM_CHAT_ID=312546298
DEBUG=true
```

### Run Backend Locally

```bash
cd backend
export $(cat .env.local | xargs)
uvicorn app.main:app --reload --port 8001
```

### Verify Connection

```bash
# Test database connection
psql postgresql://leadgen:leadgen_secret@localhost:5433/leadgen -c "SELECT COUNT(*) FROM contacts"
# Expected: ~56,000 rows

# Test API health
curl http://localhost:8001/api/health
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" on port 5433 | SSH tunnel not running - start it first |
| "Server error" on ContactsPage | Check DATABASE_URL is exported before uvicorn |
| "Unable to connect" in browser | Backend not running or wrong port (use 8001) |
| CORS errors | Add localhost:3000 to allowed origins if running frontend |

---

## Scripts Reference

### Stats & Monitoring Scripts

#### check_stats.py - Outbound Funnel Report

Comprehensive CRM statistics including contacts, campaigns, replies, and enrichment progress.

```bash
ssh hetzner "docker exec leadgen-backend python3 /app/scripts/check_stats.py"
```

**Output includes:**
- Contacts: Total, Smartlead, GetSales, Merged
- Campaigns: Total (509), Smartlead (402), GetSales (107)
- Campaign Status: COMPLETED, INPROGRESS, PAUSED, etc.
- Funnel Stages: touched, warm, not_interested, etc.
- Reply Sentiment: warm, neutral, cold
- Reply Categories: interested, meeting_request, not_interested, etc.
- Touches Distribution: 1, 2-5, 6-10, 10+
- Raw Data Enrichment Progress

#### check_raw_data_progress.py - Enrichment Progress

Quick visual progress for raw data gathering.

```bash
ssh hetzner "docker exec leadgen-backend python3 /app/app/scripts/check_raw_data_progress.py"
```

**Sample Output:**
```
============================================================
        RAW DATA GATHERING PROGRESS
============================================================
  Smartlead:   7,274 / 50,556 ( 14.4%)
  GetSales:        0 /  6,279 (  0.0%)
  Touches:    5,026 contacts
  Activities: 14,131 (SL: 961, GS: 13170)
  Replies:     2,365 (2365 with raw data)

  SL [##__________________] 14.4%
  GS [____________________] 0.0%
============================================================
```

### Data Enrichment Scripts

#### enrich_raw_data.py - Full Raw Data Gathering

Fetches complete Smartlead/GetSales data and stores in raw columns. Runs in background with Telegram notifications.

```bash
# Start in background
ssh hetzner "docker exec -d leadgen-backend python3 /app/app/scripts/enrich_raw_data.py"
```

**What it fetches:**
- Smartlead: Campaign list, conversation history with full email bodies
- GetSales: Full profile, LinkedIn message history

**Runtime:** ~10-12 hours for 50k Smartlead contacts, ~30min for 6k GetSales contacts

**Telegram updates:** Every 500 contacts processed

**Resumable:** Yes - queries for records where `raw = '{}'`, skips already-processed

#### enrich_getsales_flows_fast.py - GetSales Flow Names

Enriches GetSales contacts with flow/automation names.

```bash
ssh hetzner "docker exec -d leadgen-backend python3 /app/scripts/enrich_getsales_flows_fast.py"
```

#### sync_historical_messages.py - Historical LinkedIn Messages

Syncs historical GetSales LinkedIn messages to contact_activities.

```bash
ssh hetzner "docker exec -d leadgen-backend python3 -m app.scripts.sync_historical_messages"
```

### Utility Scripts

#### fix_missing_smartlead_ids.py - Fix Missing IDs

Attempts to match contacts without smartlead_id by email.

```bash
ssh hetzner "docker exec leadgen-backend python3 /app/scripts/fix_missing_smartlead_ids.py"
```

### Script Locations

| Script | Container Path | Purpose |
|--------|---------------|---------|
| check_stats.py | /app/scripts/ | Funnel report |
| check_raw_data_progress.py | /app/app/scripts/ | Enrichment progress |
| enrich_raw_data.py | /app/app/scripts/ | Raw data gathering |
| enrich_getsales_flows_fast.py | /app/scripts/ | GetSales flow names |
| sync_historical_messages.py | /app/app/scripts/ | LinkedIn history |

### Current Data Status (as of 2026-02-04)

| Metric | Count |
|--------|-------|
| Total Contacts | 52,932 |
| Smartlead Contacts | 50,556 |
| GetSales Contacts | 6,279 |
| Merged (both IDs) | 3,903 |
| Total Campaigns | 509 |
| Smartlead Campaigns | 402 |
| GetSales Campaigns | 107 |
| Contact-Campaign Links | 139,376 |
| Smartlead Replies | 2,365 |
| GetSales Replies | 1,397 |

