# Get Lead to Reply Time API Documentation

## Overview

The median and average time between contacting leads after getting their first reply.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/lead-to-reply-time`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your API authentication key |
| `start_date` | string (date) | Yes | - | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | - | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/lead-to-reply-time?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

---

## Response

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Lead to reply time stats fetched successfully!",
  "data": {
    "lead_to_reply_time": {
      "average_time_diff": "13d 20h 28m 46s",
      "median_time_diff": "2d 0h 50m 41s"
    }
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API call |
| `message` | string | Status message |
| `data.lead_to_reply_time.average_time_diff` | string | Average time between contact and first reply |
| `data.lead_to_reply_time.median_time_diff` | string | Median time between contact and first reply |

---

## Notes

- Response times are formatted as human-readable duration strings (e.g., "13d 20h 28m 46s")
- Maximum 50 client IDs and 100 campaign IDs per request
