# Get Month-wise Client Count API

## Overview
Retrieve month-wise client count statistics from the SmartLead analytics system.

## Endpoint Details

**HTTP Method:** `GET`

**Full URL:** `https://server.smartlead.ai/api/v1/analytics/client/month-wise-count`

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your API authentication key |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |

---

## Request Examples

### cURL
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/client/month-wise-count?api_key=YOUR_API_KEY"
```

### cURL with Client Filtering
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/client/month-wise-count?api_key=YOUR_API_KEY&client_ids=id1,id2,id3"
```

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Monthly stats for clients fetched successfully",
  "data": {
    "monthly_stats": [
      {
        "month": "June",
        "count": "2"
      },
      {
        "month": "May",
        "count": "1"
      },
      {
        "month": "April",
        "count": "1"
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API call |
| `message` | string | Confirmation message |
| `data.monthly_stats` | array | Array of monthly client count records |
| `data.monthly_stats[].month` | string | Month name |
| `data.monthly_stats[].count` | integer | Client count for that month |

---

## Notes

- Maximum 50 client IDs can be filtered in a single request
- Requires valid API authentication key
- Returns data sorted by most recent month first
