# Get Overall Stats API Documentation

## Endpoint Overview

**Title:** Get Overall Stats

**Description:** Get comprehensive overall statistics with enhanced features.

**HTTP Method:** `GET`

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/overall-stats-v2`

---

## Request Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your API authentication key |
| `start_date` | string (date) | Yes | - | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | - | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |
| `is_agency` | string | No | - | Filter by agency status |
| `full_data` | string | No | - | Set to "true" for detailed metrics |

---

## Request Examples

### cURL

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/overall-stats-v2?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

### cURL with Optional Parameters

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/overall-stats-v2?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31&client_ids=123,456&campaign_ids=789,101&full_data=true"
```

---

## Response Examples

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Overall Stats fetched successfully!",
  "data": {
    "overall_stats": {
      "sent": 12,
      "opened": 10,
      "replied": 3,
      "bounced": 1,
      "unique_lead_count": 8,
      "unique_open_count": 5,
      "positive_replied": 2,
      "open_rate": "0.00%",
      "reply_rate": "0.00%",
      "positive_reply_rate": "0.00%",
      "bounce_rate": "0.00%"
    }
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful request completion |
| `message` | string | Descriptive message about the response |
| `data.overall_stats.sent` | integer | Total emails sent |
| `data.overall_stats.opened` | integer | Total emails opened |
| `data.overall_stats.replied` | integer | Total emails replied to |
| `data.overall_stats.bounced` | integer | Total emails bounced |
| `data.overall_stats.unique_lead_count` | integer | Count of unique leads |
| `data.overall_stats.unique_open_count` | integer | Count of unique opens |
| `data.overall_stats.positive_replied` | integer | Count of positive replies |
| `data.overall_stats.open_rate` | string | Percentage of opened emails |
| `data.overall_stats.reply_rate` | string | Percentage of replied emails |
| `data.overall_stats.positive_reply_rate` | string | Percentage of positive replies |
| `data.overall_stats.bounce_rate` | string | Percentage of bounced emails |

---

## Notes

- Maximum of 50 client IDs allowed in single request
- Maximum of 100 campaign IDs allowed in single request
- Date format must be YYYY-MM-DD
- Set `full_data=true` to retrieve enhanced metrics
