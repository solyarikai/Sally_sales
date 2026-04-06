# Fetch Campaign Statistics By Campaign ID And Date Range

## Overview

Retrieves campaign-specific analytics for a specified date range using the campaign's ID.

## Endpoint Details

**HTTP Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/analytics-by-date`

---

## Parameters

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The unique identifier of the campaign |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |
| `start_date` | string (date) | Yes | — | Starting point for the date range (format: YYYY-MM-DD) |
| `end_date` | string (date) | Yes | — | Ending point for the date range (format: YYYY-MM-DD) |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/campaigns/1562695/analytics-by-date?api_key=YOUR_API_KEY&start_date=2025-01-29&end_date=2025-02-25" \
  -H "Content-Type: application/json"
```

---

## Response Examples

### Success Response (200)

```json
{
  "id": 1562695,
  "user_id": "[user_id]",
  "created_at": "2025-02-24T11:51:47.872Z",
  "status": "COMPLETED",
  "name": "Test campaign to check - copy",
  "start_date": "2025-01-29",
  "end_date": "2025-02-25",
  "sent_count": "30",
  "unique_sent_count": "10",
  "open_count": "5",
  "unique_open_count": "2",
  "click_count": "0",
  "unique_click_count": "0",
  "reply_count": "0",
  "block_count": "0",
  "total_count": "30",
  "drafted_count": "0",
  "bounce_count": "0",
  "unsubscribed_count": "0"
}
```

### Error Response (400)

```json
{}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Campaign identifier |
| `user_id` | string | User identifier |
| `created_at` | string (ISO 8601) | Campaign creation timestamp |
| `status` | string | Campaign status (e.g., COMPLETED) |
| `name` | string | Campaign name |
| `start_date` | string | Query start date |
| `end_date` | string | Query end date |
| `sent_count` | string | Total emails sent |
| `unique_sent_count` | string | Unique recipients reached |
| `open_count` | string | Total email opens |
| `unique_open_count` | string | Unique opens |
| `click_count` | string | Total link clicks |
| `unique_click_count` | string | Unique click events |
| `reply_count` | string | Total replies received |
| `block_count` | string | Blocked emails |
| `total_count` | string | Total leads processed |
| `drafted_count` | string | Drafted emails |
| `bounce_count` | string | Bounced emails |
| `unsubscribed_count` | string | Unsubscribe events |
