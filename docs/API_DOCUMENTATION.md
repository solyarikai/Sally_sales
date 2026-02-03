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
                    │  contacts (46K+)                     │
                    │    - email (unique key for merge)    │
                    │    - has_replied ✅                  │
                    │    - reply_channel (email/linkedin)  │
                    │    - last_reply_at                   │
                    │    - campaigns (JSON) ✅ enriched    │
                    │    - smartlead_id / getsales_id      │
                    │                                      │
                    │  contact_activities (351+)           │
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

| Scenario | Smartlead | GetSales |
|----------|-----------|----------|
| **New contact via webhook** | ✅ Creates contact with campaign info | ✅ Creates contact with flow info |
| **Reply from unknown contact** | ✅ Creates contact, marks as replied | ✅ Creates contact, marks as replied |
| **Existing contact, new flow** | N/A | ✅ Enriches with flow on reply |
| **Missing email** | ⚠️ Ignored | ✅ Uses `linkedin_{uuid}@getsales.local` |
| **Duplicate activity** | ✅ Checked by source_id | ✅ Checked by source_id |

---

## Smartlead API

**Base URL:** `https://server.smartlead.ai/api/v1`  
**Authentication:** Query parameter `?api_key={SMARTLEAD_API_KEY}`

### Reply Tracking Methods

| Method | Type | Frequency | Description |
|--------|------|-----------|-------------|
| Webhook | Real-time | Instant | Configure per-campaign, receives EMAIL_REPLY events |
| API Poll | `/campaigns/{id}/statistics` | Daily (2 AM) | Fetch all leads with `reply_time` field |

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
  "status": "COMPLETED",  // ACTIVE, PAUSED, COMPLETED
  "max_leads_per_day": 100
}
```

#### 2. Get Campaign Statistics (Leads + Replies) ⭐
```
GET /campaigns/{campaign_id}/statistics?api_key={key}&limit=500&offset=0
```
**Response:**
```json
{
  "data": [
    {
      "lead_email": "john@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "lead_status": "REPLIED",
      "reply_time": "2026-02-01T14:30:00.000Z",  // ⭐ Key field for reply detection
      "open_count": 3,
      "click_count": 1
    }
  ]
}
```

#### 3. Get Email Thread History
```
GET /campaigns/{campaign_id}/leads/{email}/message-history?api_key={key}
```

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
**Authentication:** Header `Authorization: Bearer {GETSALES_API_KEY}`

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
**Note:** No filtering by lead_uuid - must paginate through all

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

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | int | Auto | Primary key |
| `email` | string | Both | Email (unique key for merge) |
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

| Platform | Method | Status | Cron |
|----------|--------|--------|------|
| Smartlead | Webhook | ✅ Active | Real-time |
| Smartlead | API Poll | ✅ Active | Daily 2 AM |
| GetSales | Webhook | ✅ Active | Real-time |
| GetSales | API Poll | ✅ Active | Daily 2 AM |

### Cron Jobs (Hetzner)

```bash
# Daily Smartlead reply refetch at 2 AM
0 2 * * * /home/leadokol/magnum-opus-project/repo/scripts/daily_reply_refetch.sh

# Auto-sync every 5 minutes
*/5 * * * * /home/leadokol/magnum-opus-project/repo/scripts/auto_sync_cron.sh
```

---

## Webhook URLs (Hetzner Server)

| Purpose | URL | Status |
|---------|-----|--------|
| GetSales Bulk Export | `http://46.62.210.24:8000/api/crm-sync/webhook/getsales/bulk-import` | ✅ |
| GetSales Reply | `http://46.62.210.24:8000/api/crm-sync/webhook/getsales` | ✅ |
| Smartlead Reply | `http://46.62.210.24:8000/api/crm-sync/webhook/smartlead` | ✅ |

---

## Current Stats (as of 2026-02-03)

| Metric | Count |
|--------|-------|
| **Total Contacts** | **46,492** |
| Smartlead Contacts | 41,061 |
| GetSales Contacts | 6,247 |
| Merged (Both) | 819 |
| **Replied Contacts** | **343** |

### Campaign Enrichment Status

| Source | Total Contacts | With Campaigns | Coverage |
|--------|----------------|----------------|----------|
| **Smartlead** | 41,061 | 40,954 | **99.7%** |
| **GetSales** | 6,247 | 3,645 | **58.3%** |

**Note:** Smartlead contacts get campaign info during initial sync (from `/campaigns/{id}/statistics`). GetSales contacts require enrichment via `/flows/api/flows-leads` (510K records to paginate through).

### Platform Stats

| Platform | Metric | Count |
|----------|--------|-------|
| Smartlead | Campaigns | 1,676 |
| GetSales | Flows | 20 |
| GetSales | Flow-Leads (API) | 510,697 |
| GetSales | Inbox Messages | 19,527 |

---

## Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| `fetch_getsales_replies.py` | ✅ Fetch LinkedIn inbox messages & mark contacts as replied | `~/magnum-opus-project/repo/scripts/` |
| `enrich_getsales_flows.py` | Enrich GetSales contacts with flow names | `~/magnum-opus-project/repo/scripts/` |
| `enrich_smartlead_campaigns.py` | Enrich Smartlead contacts with campaign names (rarely needed) | `~/magnum-opus-project/repo/scripts/` |
| `daily_reply_refetch.sh` | Daily reply fetch from both platforms | `~/magnum-opus-project/repo/scripts/` |
| `run_enrichment.sh` | Run all enrichment scripts | `~/magnum-opus-project/repo/scripts/` |

