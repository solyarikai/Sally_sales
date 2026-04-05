# Get Campaign By ID - API Documentation

## Endpoint Overview

**Title:** Get Campaign By Id

**Description:** This endpoint fetches a campaign based on its ID

**HTTP Method:** GET

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | - | The ID of the campaign you want to fetch |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key |

---

## Request Body

No request body required for this endpoint.

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}?api_key={API_KEY}
```

---

## Response Examples

### Success Response (200)

```json
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
  "stop_lead_settings": "REPLY_TO_AN_EMAIL",
  "unsubscribe_text": "Don't Contact Me",
  "client_id": 23,
  "enable_ai_esp_matching": true,
  "send_as_plain_text": true,
  "follow_up_percentage": 40
}
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
| `stop_lead_settings` | string | Lead stopping criteria |
| `unsubscribe_text` | string | Custom unsubscribe text |
| `client_id` | integer | Associated client ID (null if unattached) |
| `enable_ai_esp_matching` | boolean | AI ESP matching enabled |
| `send_as_plain_text` | boolean | Plain text sending enabled |
| `follow_up_percentage` | integer | Follow-up percentage allocation |
