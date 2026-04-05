# Get Campaign List API Documentation

## Overview
Retrieve a list of all campaigns for analytics purposes.

## Request Details

**HTTP Method:** GET
**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/list`

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your API authentication key |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter campaigns (Max 50) |

## Request Examples

### cURL
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/list?api_key=YOUR_API_KEY"
```

### cURL with Client Filtering
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/list?api_key=YOUR_API_KEY&client_ids=56789,12345"
```

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Campaign list fetched successfully!",
  "data": {
    "campaign_list": [
      {
        "id": 12345678,
        "name": "My Campaign Title",
        "status": "ACTIVE",
        "user_id": 12345,
        "client_id": 56789,
        "created_at": "2025-05-14T20:55:34.620Z"
      }
    ]
  }
}
```

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API execution |
| `message` | string | Status message |
| `data.campaign_list` | array | Array of campaign objects |
| `data.campaign_list[].id` | integer | Campaign ID |
| `data.campaign_list[].name` | string | Campaign name |
| `data.campaign_list[].status` | string | Campaign status (e.g., ACTIVE) |
| `data.campaign_list[].user_id` | integer | Associated user ID |
| `data.campaign_list[].client_id` | integer | Associated client ID |
| `data.campaign_list[].created_at` | string (ISO 8601) | Campaign creation timestamp |
