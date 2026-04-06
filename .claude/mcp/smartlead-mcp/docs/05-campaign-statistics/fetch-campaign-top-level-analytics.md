# Fetch Campaign Top Level Analytics

## Overview
This endpoint retrieves top-level analytics data for a specific email campaign, including metrics such as sent count, open count, click count, reply count, and other engagement statistics.

## Endpoint Details

**HTTP Method:** GET

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full Endpoint:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/analytics`

---

## Parameters

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The unique identifier for the campaign |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/analytics?api_key={API_KEY}
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
| `created_at` | string | Campaign creation timestamp |
| `status` | string | Campaign status |
| `name` | string | Campaign name |
| `sent_count` | string | Total emails sent |
| `unique_sent_count` | string | Number of unique recipients |
| `open_count` | string | Total email opens |
| `unique_open_count` | string | Number of unique opens |
| `click_count` | string | Total link clicks |
| `unique_click_count` | string | Number of unique clicks |
| `reply_count` | string | Total replies received |
| `block_count` | string | Blocked emails |
| `total_count` | string | Total leads processed |
| `drafted_count` | string | Drafted emails |
| `bounce_count` | string | Bounced emails |
| `unsubscribed_count` | string | Unsubscribed leads |
