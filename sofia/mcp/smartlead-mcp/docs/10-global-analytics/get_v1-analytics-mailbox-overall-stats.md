# Get Mailbox Overall Stats

## Description

Get overall mailbox statistics. Retrieves comprehensive mailbox performance data including connection status, health metrics, and warmup information.

## API Endpoint
```
GET https://server.smartlead.ai/api/v1/analytics/mailbox/overall-stats
```

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |
| `client_ids` | string | No | Comma-separated client IDs to filter (Max 50) |

## Request Examples

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/mailbox/overall-stats?api_key=YOUR_API_KEY"
```

### With Client Filter
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/mailbox/overall-stats?api_key=YOUR_API_KEY&client_ids=id1,id2"
```

## Response

### Success Response (200)

```json
{
  "success": true,
  "message": "Overall mailbox stats fetched successfully!",
  "data": {
    "overall_mailbox_stats": {
      "total_connected": 13870,
      "in_use": 10297,
      "disconnected": 2,
      "enabled_without_warmup": 3282
    }
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success indicator |
| `message` | string | Response status message |
| `data.overall_mailbox_stats.total_connected` | integer | Total number of connected mailboxes |
| `data.overall_mailbox_stats.in_use` | integer | Mailboxes currently in active use |
| `data.overall_mailbox_stats.disconnected` | integer | Number of disconnected mailboxes |
| `data.overall_mailbox_stats.enabled_without_warmup` | integer | Enabled mailboxes not using warmup |
