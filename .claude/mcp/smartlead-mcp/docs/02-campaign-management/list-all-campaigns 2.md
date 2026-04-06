# List All Campaigns API Documentation

## Endpoint Overview

**Title:** List all Campaigns

**Description:** This endpoint fetches all the campaigns in your account

**HTTP Method:** GET

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full Endpoint:** `GET https://server.smartlead.ai/api/v1/campaigns`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key |
| `client_id` | integer | No | - | Filter by client_id |
| `include_tags` | boolean | No | - | If true returns the tags associated to the campaign |

---

## Request Body

No request body required for this endpoint.

---

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/campaigns?api_key={API_KEY}
```

### With Optional Parameters

```bash
curl https://server.smartlead.ai/api/v1/campaigns?api_key={API_KEY}&client_id=22&include_tags=true
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "id": 372,
    "user_id": 124,
    "created_at": "2022-05-26T03:47:31.448094+00:00",
    "updated_at": "2022-05-26T03:47:31.448094+00:00",
    "status": "ACTIVE",
    "name": "My Epic Campaign",
    "track_settings": "DONT_REPLY_TO_AN_EMAIL",
    "scheduler_cron_value": "{ tz: 'Australia/Sydney', days: [ 1, 2, 3, 4, 5 ], endHour: '23:00', startHour: '10:00' }",
    "min_time_btwn_emails": 10,
    "max_leads_per_day": 10,
    "parent_campaign_id": 13423,
    "stop_lead_settings": "REPLY_TO_AN_EMAIL",
    "unsubscribe_text": "Don't Contact Me",
    "client_id": 22
  }
]
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Campaign identifier |
| `user_id` | integer | Associated user ID |
| `created_at` | string | Creation timestamp |
| `updated_at` | string | Last update timestamp |
| `status` | string | Campaign status (DRAFTED/ACTIVE/COMPLETED/STOPPED/PAUSED) |
| `name` | string | Campaign name |
| `track_settings` | string | Tracking configuration |
| `scheduler_cron_value` | string | Scheduling details |
| `min_time_btwn_emails` | integer | Minimum time between emails (minutes) |
| `max_leads_per_day` | integer | Maximum leads per day |
| `parent_campaign_id` | integer | Parent campaign ID (null if parent campaign) |
| `stop_lead_settings` | string | Lead stopping criteria |
| `unsubscribe_text` | string | Custom unsubscribe text |
| `client_id` | integer | Associated client ID (null if unattached) |

---

## Notes

- Returns array of campaign objects for authenticated user
- Null `parent_campaign_id` indicates parent campaign; non-null indicates subsequence
- Null `client_id` means campaign not attached to client
- Status values: DRAFTED, ACTIVE, COMPLETED, STOPPED, PAUSED
