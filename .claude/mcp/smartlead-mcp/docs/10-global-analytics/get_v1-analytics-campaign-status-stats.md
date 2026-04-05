# Get Campaign Status Stats

## Overview

Retrieve campaign status statistics.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/status-stats`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |
| `client_ids` | string | No | Comma-separated client IDs to filter (Max 50) |

---

## Request Examples

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/status-stats?api_key=YOUR_API_KEY"
```

### With Optional Parameters

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/status-stats?api_key=YOUR_API_KEY&client_ids=id1,id2,id3"
```

---

## Response

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Campaign status stats",
  "data": {
    "campaign_status_stats": [
      {
        "status": "Active",
        "total_count": "30"
      },
      {
        "status": "Paused",
        "total_count": "32"
      },
      {
        "status": "Drafted",
        "total_count": "21"
      },
      {
        "status": "Completed",
        "total_count": "30"
      },
      {
        "status": "Stopped",
        "total_count": 0
      },
      {
        "status": "Campaigns with Smart Servers",
        "total_count": 2
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request completion status |
| `message` | string | Response message |
| `data.campaign_status_stats` | array | Array of status statistics objects |
| `data.campaign_status_stats[].status` | string | Campaign status label |
| `data.campaign_status_stats[].total_count` | integer/string | Count of campaigns with this status |

---

## Notes

- No date range required for this endpoint (unlike most analytics endpoints)
- Maximum 50 client IDs can be filtered in a single request
