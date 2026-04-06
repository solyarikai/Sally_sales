# Get Day-wise Positive Reply Stats

## Overview

Get day-wise positive reply statistics for the specified date range.

## API Endpoint

**HTTP Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/analytics/day-wise-positive-reply-stats`

## Query Parameters

| Parameter | Type | Required | Description | Default |
|-----------|------|----------|-------------|---------|
| `api_key` | string | Yes | API authentication key | — |
| `start_date` | string (date) | Yes | Start date in YYYY-MM-DD format | — |
| `end_date` | string (date) | Yes | End date in YYYY-MM-DD format | — |
| `client_ids` | string | No | Comma-separated client IDs (Max 50) | "" |
| `campaign_ids` | string | No | Comma-separated campaign IDs (Max 100) | "" |

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/day-wise-positive-reply-stats?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

## Response Schema

### Success Response (200)

```json
{
  "success": true,
  "message": "Email engagement stats fetched successfully!",
  "data": {
    "day_wise_stats": [
      {
        "date": "1 Jan",
        "day_name": "Wednesday",
        "email_engagement_metrics": {
          "positive_replied": 1
        }
      },
      {
        "date": "2 Jan",
        "day_name": "Thursday",
        "email_engagement_metrics": {
          "positive_replied": 0
        }
      }
    ]
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success status |
| `message` | string | Response message |
| `data.day_wise_stats` | array | Daily statistics array |
| `data.day_wise_stats[].date` | string | Date representation |
| `data.day_wise_stats[].day_name` | string | Day of week |
| `data.day_wise_stats[].email_engagement_metrics.positive_replied` | integer | Count of positive replies |
