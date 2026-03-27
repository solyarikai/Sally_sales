# Get Campaign Response Stats

## Overview

Retrieve detailed response statistics for campaigns.

**HTTP Method:** `GET`

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/response-stats`

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |
| `full_data` | string | No | — | Set to "true" for detailed metrics |

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/response-stats?api_key=YOUR_API_KEY&start_date=2025-01-01&end_date=2025-01-31&campaign_ids=123456,567890&full_data=true"
```

## Response

### Success Response (200)

```json
{
  "success": true,
  "message": "Campaign wise response stats",
  "data": {
    "campaign_wise_response_stats": [
      {
        "email_campaign_id": 123456,
        "email_campaign_name": "Campaign Name 1",
        "leads_contacted": 1482,
        "not_replied": 0,
        "total_response": 1482,
        "total_unique_response": 1476,
        "unrecognised_response": 1482,
        "total_positive_response": 0,
        "total_negative_response": 0,
        "total_neutral_response": 0
      },
      {
        "email_campaign_id": 567890,
        "email_campaign_name": "Campaign Name 2",
        "leads_contacted": 1287,
        "not_replied": 0,
        "total_response": 1287,
        "total_unique_response": 1279,
        "unrecognised_response": 7,
        "total_positive_response": 0,
        "total_negative_response": 0,
        "total_neutral_response": 1280
      }
    ]
  }
}
```

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API request |
| `message` | string | Response message |
| `data.campaign_wise_response_stats` | array | Array of campaign statistics |
| `data.campaign_wise_response_stats[].email_campaign_id` | integer | Unique campaign identifier |
| `data.campaign_wise_response_stats[].email_campaign_name` | string | Campaign display name |
| `data.campaign_wise_response_stats[].leads_contacted` | integer | Total leads contacted in campaign |
| `data.campaign_wise_response_stats[].not_replied` | integer | Leads that did not reply |
| `data.campaign_wise_response_stats[].total_response` | integer | All responses received |
| `data.campaign_wise_response_stats[].total_unique_response` | integer | Count of unique responses |
| `data.campaign_wise_response_stats[].unrecognised_response` | integer | Unrecognised/uncategorized responses |
| `data.campaign_wise_response_stats[].total_positive_response` | integer | Positive reply count |
| `data.campaign_wise_response_stats[].total_negative_response` | integer | Negative reply count |
| `data.campaign_wise_response_stats[].total_neutral_response` | integer | Neutral reply count |
