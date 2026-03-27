# Get Domain-wise Health Metrics

## Overview

Retrieve domain-wise health metrics for mailboxes across your SmartLead account.

## API Endpoint

```
GET https://server.smartlead.ai/api/v1/analytics/mailbox/domain-wise-health-metrics
```

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your API authentication key |
| `start_date` | string (date) | Yes | - | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | - | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (max 100) |
| `full_data` | string | No | - | Set to "true" for detailed metrics |
| `limit` | string | No | - | Number of domains to return |
| `offset` | string | No | - | Starting position for pagination |

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/mailbox/domain-wise-health-metrics?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Domain health metrics fetched successfully",
  "data": {
    "domain_health_metrics": [
      {
        "domain": "domain1.com",
        "sent": 1,
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

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API call |
| `message` | string | Descriptive response message |
| `data.domain_health_metrics` | array | List of domain performance objects |
| `data.domain_health_metrics[].domain` | string | Domain name |
| `data.domain_health_metrics[].sent` | integer | Total emails sent |
| `data.domain_health_metrics[].opened` | integer | Emails opened |
| `data.domain_health_metrics[].replied` | integer | Emails replied to |
| `data.domain_health_metrics[].positive_replied` | integer | Positive replies received |
| `data.domain_health_metrics[].bounced` | integer | Bounced emails |
| `data.domain_health_metrics[].unique_lead_count` | integer | Unique leads targeted |
| `data.domain_health_metrics[].unique_open_count` | integer | Unique opens |
| `data.domain_health_metrics[].open_rate` | string | Percentage of opens |
| `data.domain_health_metrics[].reply_rate` | string | Percentage of replies |
| `data.domain_health_metrics[].positive_reply_rate` | string | Percentage of positive replies |
| `data.domain_health_metrics[].bounce_rate` | string | Percentage of bounces |
