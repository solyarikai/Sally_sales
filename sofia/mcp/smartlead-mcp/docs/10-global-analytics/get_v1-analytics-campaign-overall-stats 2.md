# Get Campaign Overall Stats

## Overview

Retrieve comprehensive performance metrics for campaigns within a specified date range.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/overall-stats`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |
| `start_date` | string (date) | Yes | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | End date in YYYY-MM-DD format |
| `full_data` | string | No | Set to "true" for detailed metrics |
| `limit` | string | No | Number of campaigns to return |
| `offset` | string | No | Starting position for pagination |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/overall-stats?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

---

## Response Schema

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Campaign wise performance fetched successfully!",
  "data": {
    "campaign_wise_performance": [
      {
        "id": 123456,
        "campaign_name": "My Campaign Name 1",
        "sent": 153,
        "opened": 0,
        "replied": 8,
        "bounced": 0,
        "open_rate": "0.00%",
        "reply_rate": "26.67%",
        "bounce_rate": "0.00%",
        "positive_reply_rate": "12.50%",
        "positive_replied": 1,
        "unique_lead_count": 30,
        "unique_open_count": 0
      }
    ]
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API call |
| `message` | string | Descriptive status message |
| `data.campaign_wise_performance` | array | Array of campaign metrics |
| `data.campaign_wise_performance[].id` | integer | Campaign identifier |
| `data.campaign_wise_performance[].campaign_name` | string | Name of the campaign |
| `data.campaign_wise_performance[].sent` | integer | Total emails sent |
| `data.campaign_wise_performance[].opened` | integer | Emails opened |
| `data.campaign_wise_performance[].replied` | integer | Emails replied to |
| `data.campaign_wise_performance[].bounced` | integer | Bounced emails |
| `data.campaign_wise_performance[].open_rate` | string | Percentage of opens |
| `data.campaign_wise_performance[].reply_rate` | string | Percentage of replies |
| `data.campaign_wise_performance[].bounce_rate` | string | Percentage of bounces |
| `data.campaign_wise_performance[].positive_reply_rate` | string | Percentage of positive responses |
| `data.campaign_wise_performance[].positive_replied` | integer | Count of positive replies |
| `data.campaign_wise_performance[].unique_lead_count` | integer | Distinct leads targeted |
| `data.campaign_wise_performance[].unique_open_count` | integer | Distinct leads who opened |

---

## Notes

- All date parameters must use YYYY-MM-DD format
- Authentication via API key is required
- Pagination supported through `limit` and `offset` parameters
- Optional detailed metrics available with `full_data=true`
