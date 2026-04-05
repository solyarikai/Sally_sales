# Fetch Campaign Statistics By Campaign ID

## Overview
This endpoint fetches campaign statistics using the campaign's ID, providing detailed engagement metrics for a specific campaign.

## Request Details

### HTTP Method & Endpoint
```
GET https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics
```

### Path Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The ID of the campaign for which to retrieve statistics |

### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

### Request Body
No request body required for this endpoint.

## Response Format

### Success Response (200)
The endpoint returns campaign statistics including engagement metrics such as sent count, open count, click count, reply count, and other performance indicators.

**Example Response Structure:**
```json
{
  "id": 1562695,
  "user_id": "[user_id]",
  "created_at": "2025-02-24T11:51:47.872Z",
  "status": "COMPLETED",
  "name": "Test campaign to check - copy",
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
Returns an empty object on validation failure.

## Example Request

### cURL
```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics?api_key={API_KEY}
```

### Shell
```bash
curl https://server.smartlead.ai/api/v1/campaigns/1562695/statistics?api_key=YOUR_API_KEY
```

## Response Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Campaign identifier |
| `user_id` | string | User who owns the campaign |
| `created_at` | string | Campaign creation timestamp |
| `status` | string | Current campaign status (COMPLETED, ACTIVE, PAUSED, etc.) |
| `name` | string | Campaign name |
| `sent_count` | string | Total emails sent |
| `unique_sent_count` | string | Number of unique recipients |
| `open_count` | string | Total email opens |
| `unique_open_count` | string | Unique opens count |
| `click_count` | string | Total link clicks |
| `unique_click_count` | string | Unique click count |
| `reply_count` | string | Total replies received |
| `block_count` | string | Blocked emails |
| `bounce_count` | string | Bounced emails |
| `unsubscribed_count` | string | Unsubscribed leads |
