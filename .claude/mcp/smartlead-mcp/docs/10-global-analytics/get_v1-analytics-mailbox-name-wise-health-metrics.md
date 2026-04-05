# Get Email-Id-wise Health Metrics

## Overview

Retrieves name-wise health metrics for mailboxes within a specified date range.

## Endpoint

```
GET https://server.smartlead.ai/api/v1/analytics/mailbox/name-wise-health-metrics
```

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |
| `full_data` | string | No | — | Set to "true" for detailed metrics |
| `limit` | string | No | — | Number of mailboxes to return |
| `offset` | string | No | — | Starting position for pagination |

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/mailbox/name-wise-health-metrics?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

## Response Format

### Success Response (200)

```json
{
  "success": true,
  "message": "Email health metrics fetched successfully",
  "data": {
    "email_health_metrics": [
      {
        "from_email": "user1@email.com",
        "sent": 2,
        "opened": 0,
        "replied": 1,
        "positive_replied": 0,
        "bounced": 0,
        "unique_lead_count": 1,
        "unique_open_count": 0,
        "open_rate": "0.00%",
        "reply_rate": "100.00%",
        "positive_reply_rate": "0.00%",
        "bounce_rate": "0.00%"
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation success status |
| `message` | string | Response message |
| `data.email_health_metrics` | array | Array of mailbox metrics |
| `data.email_health_metrics[].from_email` | string | Sender email address |
| `data.email_health_metrics[].sent` | integer | Number of emails sent |
| `data.email_health_metrics[].opened` | integer | Number of emails opened |
| `data.email_health_metrics[].replied` | integer | Total replies received |
| `data.email_health_metrics[].positive_replied` | integer | Positive replies count |
| `data.email_health_metrics[].bounced` | integer | Number of bounced emails |
| `data.email_health_metrics[].unique_lead_count` | integer | Unique leads contacted |
| `data.email_health_metrics[].unique_open_count` | integer | Unique opens count |
| `data.email_health_metrics[].open_rate` | string | Percentage of opens |
| `data.email_health_metrics[].reply_rate` | string | Percentage of replies |
| `data.email_health_metrics[].positive_reply_rate` | string | Percentage of positive replies |
| `data.email_health_metrics[].bounce_rate` | string | Percentage of bounces |
