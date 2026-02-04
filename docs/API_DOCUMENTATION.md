# CRM API Documentation & Data Flow

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
                    │    - has_replied ✅                  │
                    │    - reply_channel (email/linkedin)  │
                    │    - last_reply_at                   │
                    │    - campaigns (JSON) ✅ enriched    │
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
```
POST /campaigns/{campaign_id}/webhooks?api_key={key}
{
  "name": "Reply Webhook",
  "webhook_url": "http://46.62.210.24:8000/api/crm-sync/webhook/smartlead",
  "event_types": ["EMAIL_REPLY"]
}
```

### Webhook Payload (EMAIL_REPLY)
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
    "reply_message": { "text": "Thanks for reaching out..." },
    "last_reply": { "email_body": "...", "time": "2026-02-01T14:30:00.000Z" },
    "history": [...]
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
| Smartlead | Webhook | ✅ Primary | Real-time, includes full reply message content |
| Smartlead | API Poll (category=9) | ✅ Fallback | Marks contacts as replied, NO message content |
| GetSales | Webhook | ✅ Primary | Real-time, includes full LinkedIn message |
| GetSales | API Poll (inbox) | ✅ Fallback | Fetches LinkedIn inbox messages with content |

**Note on Smartlead API limitations:**
- The Smartlead API does NOT provide reply message content
- API polling uses `lead_category_id=9` to find replied leads
- Reply content is ONLY available via webhooks
- API polling serves as a fallback to catch missed webhooks

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

### Recent Fixes (2026-02-03)

| Issue | Fix Applied | Result |
|-------|-------------|--------|
| **Duplicate contacts** | Redis sync lock + unique email index | Prevented future duplicates |
| **Low merge count (819)** | Case-insensitive email matching | Merged: 819 → 3,679 (4.5x) |
| **Missing smartlead_id** | Backfill script queried Smartlead API | 2,808 contacts fixed |
| **Concurrent sync race** | Disabled cron, use in-app scheduler only | No more duplicate creation |

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

### Running the Fast Enrichment Script

```bash
# SSH to Hetzner and run:
docker exec -e DATABASE_URL="postgresql://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen" \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e TELEGRAM_CHAT_ID="your-chat-id" \
  leadgen-backend python3 /app/scripts/enrich_getsales_flows_fast.py
```

The script sends Telegram notifications at 10%, 20%, ... 100% progress.

