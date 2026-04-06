# Get Day-wise Overall Stats API Documentation

## Endpoint Overview

**Title:** Get Day-wise Overall Stats

**Description:** Retrieve day-wise overall statistics for a specified date range, including email engagement metrics.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/day-wise-overall-stats`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |

---

## Request Examples

### cURL

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/day-wise-overall-stats?api_key=YOUR_API_KEY&start_date=2024-04-20&end_date=2024-04-21"
```

### With Filters

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/day-wise-overall-stats?api_key=YOUR_API_KEY&start_date=2024-04-20&end_date=2024-04-21&client_ids=123,456&campaign_ids=789,101112"
```

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Email engagement stats fetched successfully!",
  "data": {
    "day_wise_stats": [
      {
        "date": "20 Apr",
        "day_name": "Sunday",
        "email_engagement_metrics": {
          "sent": 2316,
          "opened": 0,
          "replied": 25,
          "bounced": 125,
          "unsubscribed": 0
        }
      },
      {
        "date": "21 Apr",
        "day_name": "Monday",
        "email_engagement_metrics": {
          "sent": 92881,
          "opened": 0,
          "replied": 338,
          "bounced": 12049,
          "unsubscribed": 0
        }
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API request |
| `message` | string | Descriptive message about the response |
| `data.day_wise_stats` | array | Array of daily statistics |
| `data.day_wise_stats[].date` | string | Date in "DD MMM" format |
| `data.day_wise_stats[].day_name` | string | Day of week (e.g., "Monday") |
| `data.day_wise_stats[].email_engagement_metrics.sent` | integer | Total emails sent |
| `data.day_wise_stats[].email_engagement_metrics.opened` | integer | Total emails opened |
| `data.day_wise_stats[].email_engagement_metrics.replied` | integer | Total email replies received |
| `data.day_wise_stats[].email_engagement_metrics.bounced` | integer | Total emails bounced |
| `data.day_wise_stats[].email_engagement_metrics.unsubscribed` | integer | Total unsubscribe requests |

---

## Notes

- Requires valid API authentication key
- Date range is inclusive for both start and end dates
- Optional filtering supports up to 50 client IDs and 100 campaign IDs
- Response includes aggregated metrics across specified filters
