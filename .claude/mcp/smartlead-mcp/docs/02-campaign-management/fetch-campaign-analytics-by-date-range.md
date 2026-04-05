# Fetch Campaign Analytics by Date Range

## Overview

**Status:** DEPRECATED

**Description:** This endpoint fetches campaign-specific analytics for a specified date range

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaignId}/analytics-by-date`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaignId` | string | Yes | The campaign identifier |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Authentication API key |
| `start_date` | string (date) | No | Starting point for the date range |
| `end_date` | string (date) | No | Ending point for the date range |

## Request Body

No request body required for this GET endpoint.

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

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Campaign identifier |
| `user_id` | string | User identifier |
| `created_at` | string | Timestamp when campaign was created |
| `status` | string | Campaign status |
| `name` | string | Campaign name |
| `start_date` | string | Analytics start date |
| `end_date` | string | Analytics end date |
| `sent_count` | string | Total emails sent |
| `unique_sent_count` | string | Unique recipients |
| `open_count` | string | Total email opens |
| `unique_open_count` | string | Unique opens |
| `click_count` | string | Total link clicks |
| `unique_click_count` | string | Unique clicks |
| `reply_count` | string | Total replies |
| `block_count` | string | Blocked messages |
| `total_count` | string | Total count |
| `drafted_count` | string | Drafted emails |
| `bounce_count` | string | Bounced emails |
| `unsubscribed_count` | string | Unsubscribed leads |

---

## Notes

This endpoint is marked as deprecated. Consider using alternative analytics endpoints for new implementations.
