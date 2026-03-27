# Get Client Overall Stats

## Description

Retrieve comprehensive performance metrics for clients within a specified date range.

**Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/analytics/client/overall-stats`

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your API authentication key |
| `start_date` | string (date) | Yes | - | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | - | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `filter` | string | No | - | Additional filter criteria |
| `full_data` | string | No | - | Set to "true" for detailed metrics |
| `limit` | string | No | - | Number of clients to return |
| `offset` | string | No | - | Starting position for pagination |

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/client/overall-stats?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-12-31"
```

## Response

### Success Response (200)

```json
{
  "success": true,
  "message": "Client wise performance fetched successfully!",
  "data": {
    "client_wise_performance": [
      {
        "client_id": 12345,
        "client_name": "Client 1",
        "total_campaigns_count": "47",
        "campaign_stats": {
          "sent": 809456,
          "opened": 0,
          "replied": 1880,
          "positive_replied": 40,
          "client_health": "0.11%",
          "open_rate": "0.00%",
          "reply_rate": "5.03%",
          "positive_reply_rate": "2.13%",
          "unique_open_count": 0,
          "unique_lead_count": 37364
        }
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request status |
| `message` | string | Response message |
| `data.client_wise_performance` | array | Array of client performance objects |
| `data.client_wise_performance[].client_id` | integer | Client ID |
| `data.client_wise_performance[].client_name` | string | Client name |
| `data.client_wise_performance[].total_campaigns_count` | string | Total campaigns for client |
| `data.client_wise_performance[].campaign_stats.sent` | integer | Total emails sent |
| `data.client_wise_performance[].campaign_stats.opened` | integer | Total opens |
| `data.client_wise_performance[].campaign_stats.replied` | integer | Total replies |
| `data.client_wise_performance[].campaign_stats.positive_replied` | integer | Total positive replies |
| `data.client_wise_performance[].campaign_stats.client_health` | string | Client health percentage |
| `data.client_wise_performance[].campaign_stats.open_rate` | string | Open rate percentage |
| `data.client_wise_performance[].campaign_stats.reply_rate` | string | Reply rate percentage |
| `data.client_wise_performance[].campaign_stats.positive_reply_rate` | string | Positive reply rate percentage |
| `data.client_wise_performance[].campaign_stats.unique_open_count` | integer | Unique opens |
| `data.client_wise_performance[].campaign_stats.unique_lead_count` | integer | Unique leads |
