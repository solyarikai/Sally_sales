# Get Day-wise Positive Reply Stats by Sent Time

## Overview

Retrieves day-wise positive reply statistics grouped by sent time for a specified date range. The data is based on lead sentiment analysis and grouped by the original email send date.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/day-wise-positive-reply-stats-by-sent-time`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `timezone` | string | Yes | — | Timezone for calculations |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (max 100) |

---

## Request Example (cURL)

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/day-wise-positive-reply-stats-by-sent-time?api_key=YOUR_API_KEY&start_date=2024-06-18&end_date=2024-06-20&timezone=UTC"
```

---

## Response Format

### Success Response (200)

```json
{
  "success": true,
  "message": "Day-wise positive reply stats by sent time fetched successfully!",
  "data": {
    "day_wise_stats": [
      {
        "date": "18 Jun",
        "day_name": "Tuesday",
        "email_engagement_metrics": {
          "positive_replied": 8
        }
      },
      {
        "date": "19 Jun",
        "day_name": "Wednesday",
        "email_engagement_metrics": {
          "positive_replied": 12
        }
      },
      {
        "date": "20 Jun",
        "day_name": "Thursday",
        "email_engagement_metrics": {
          "positive_replied": 5
        }
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success status |
| `message` | string | Response message |
| `data.day_wise_stats` | array | Array of daily statistics |
| `data.day_wise_stats[].date` | string | Formatted date (e.g., "18 Jun") |
| `data.day_wise_stats[].day_name` | string | Day of the week |
| `data.day_wise_stats[].email_engagement_metrics.positive_replied` | integer | Count of positive replies |

### Error Responses

**400 Bad Request:**
```json
{
  "success": false,
  "message": "Invalid date format. Please use YYYY-MM-DD format."
}
```

**401 Unauthorized:**
```json
{
  "success": false,
  "message": "Unauthorized access. Please provide valid authentication token."
}
```
