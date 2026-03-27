# Fetch Campaign Top Level Analytics By Date Range

## Overview
This endpoint retrieves campaign statistics aggregated across a specified date range using the campaign's ID.

**Endpoint:** `GET https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/top-level-analytics-by-date`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | — | The unique identifier of the campaign |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your authentication API key |
| `start_date` | string (date) | Yes | — | Range start in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | Range end in YYYY-MM-DD format |

---

## Request Example

```bash
curl -X GET \
  "https://server.smartlead.ai/api/v1/campaigns/1562695/top-level-analytics-by-date?api_key=YOUR_API_KEY&start_date=2025-01-29&end_date=2025-02-25" \
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
| `user_id` | string | Owner user identifier |
| `created_at` | timestamp | Campaign creation date |
| `status` | string | Campaign status (COMPLETED, ACTIVE, PAUSED, etc.) |
| `name` | string | Campaign name |
| `start_date` | string | Analytics period start |
| `end_date` | string | Analytics period end |
| `sent_count` | string | Total email sends |
| `unique_sent_count` | string | Unique recipients sent to |
| `open_count` | string | Total opens |
| `unique_open_count` | string | Unique open count |
| `click_count` | string | Total link clicks |
| `unique_click_count` | string | Unique click count |
| `reply_count` | string | Total replies received |
| `block_count` | string | Blocked messages |
| `bounce_count` | string | Bounced emails |
| `unsubscribed_count` | string | Unsubscribe events |
