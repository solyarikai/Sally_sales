# Get Lead Overall Stats API Documentation

## Overview

Get overall lead statistics.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/lead/overall-stats`

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

## Request Examples

### cURL
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/lead/overall-stats?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

### With Filters
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/lead/overall-stats?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31&client_ids=123,456&campaign_ids=789,101"
```

---

## Response

### Success Response (200)
```json
{
  "success": true,
  "message": "Lead stats fetched successfully",
  "data": {
    "lead_stats": {
      "count": {
        "total": 4507,
        "new": 1593,
        "follow_up": 2914
      },
      "percentage": {
        "new": "35%",
        "follow_up": "65%"
      }
    }
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success status |
| `message` | string | Response message |
| `data.lead_stats.count.total` | integer | Total leads |
| `data.lead_stats.count.new` | integer | New leads count |
| `data.lead_stats.count.follow_up` | integer | Follow-up leads count |
| `data.lead_stats.percentage.new` | string | New leads percentage |
| `data.lead_stats.percentage.follow_up` | string | Follow-up leads percentage |

---

## Notes
- No request body required (GET request)
- API key authentication required
- Date range filters are mandatory
- Optional client and campaign filters support comma-separated values with specified limits
