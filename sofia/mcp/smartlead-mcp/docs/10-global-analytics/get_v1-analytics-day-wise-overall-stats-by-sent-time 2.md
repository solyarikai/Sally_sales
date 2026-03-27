# Get Day-wise Overall Stats by Sent Time

## Overview

This endpoint retrieves daily email engagement statistics organized by the date emails were sent.

**HTTP Method:** `GET`

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/day-wise-overall-stats-by-sent-time`

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |
| `start_date` | string (date) | Yes | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | End date in YYYY-MM-DD format |
| `timezone` | string | Yes | Timezone for calculations |
| `client_ids` | string | No | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | Comma-separated campaign IDs to filter (Max 100) |

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/day-wise-overall-stats-by-sent-time?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31&timezone=UTC&client_ids=123,456&campaign_ids=789,1011"
```

## Response Schema

### Success Response (200)

```json
{
  "success": true,
  "message": "Day-wise overall stats by sent time fetched successfully!",
  "data": {
    "day_wise_stats": [
      {
        "date": "18 Jun",
        "day_name": "Tuesday",
        "email_engagement_metrics": {
          "sent": 100,
          "opened": 50,
          "replied": 10,
          "bounced": 5,
          "unsubscribed": 2,
          "positive_replied": 8,
          "unique_lead_reached": 90
        }
      },
      {
        "date": "19 Jun",
        "day_name": "Wednesday",
        "email_engagement_metrics": {
          "sent": 120,
          "opened": 60,
          "replied": 12,
          "bounced": 6,
          "unsubscribed": 1,
          "positive_replied": 10,
          "unique_lead_reached": 115
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
| `message` | string | Descriptive response message |
| `data.day_wise_stats` | array | Array of daily statistics |
| `data.day_wise_stats[].date` | string | Formatted date (e.g., "18 Jun") |
| `data.day_wise_stats[].day_name` | string | Day of the week |
| `data.day_wise_stats[].email_engagement_metrics.sent` | integer | Number of emails sent |
| `data.day_wise_stats[].email_engagement_metrics.opened` | integer | Number of emails opened |
| `data.day_wise_stats[].email_engagement_metrics.replied` | integer | Number of emails that received replies |
| `data.day_wise_stats[].email_engagement_metrics.bounced` | integer | Number of emails that bounced |
| `data.day_wise_stats[].email_engagement_metrics.unsubscribed` | integer | Number of unsubscribes |
| `data.day_wise_stats[].email_engagement_metrics.positive_replied` | integer | Number of positive replies |
| `data.day_wise_stats[].email_engagement_metrics.unique_lead_reached` | integer | Count of unique leads reached |

## Error Responses

### Bad Request (400)

```json
{
  "success": false,
  "message": "Invalid date format. Please use YYYY-MM-DD format."
}
```

### Unauthorized (401)

```json
{
  "success": false,
  "message": "Unauthorized access. Please provide valid authentication token."
}
```
