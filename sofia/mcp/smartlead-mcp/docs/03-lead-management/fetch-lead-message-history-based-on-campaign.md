# Fetch Lead Message History Based on Campaign

## Overview
Retrieves the complete message history of a lead within a specific campaign, including all sent emails, replies, and engagement metrics (same data available in the master inbox).

## API Endpoint

```
GET https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history
```

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | - | The ID of the campaign to fetch message history from |
| `lead_id` | string | Yes | - | The ID of the lead whose message history to retrieve |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API key for authentication |
| `event_time_gt` | string | No | - | Filters messages based on time greater than specified date (format: 2024-01-01T10:33:02.871Z) |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history?api_key={API_KEY}
```

With date filtering:
```bash
curl "https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history?api_key={API_KEY}&event_time_gt=2024-01-01T10:33:02.871Z"
```

## Response Format

### Success Response (200)

```json
{
  "history": [
    {
      "type": "SENT",
      "message_id": "<sw-uibo3i2hoi-ced32-23iuboufde-23oub@outlook.com>",
      "stats_id": "iuh2o3iuh3o2ih2-iuho3-edwhi92-oiho3-3223oihoi9uf",
      "time": "2023-03-13T07:44:12.978Z",
      "email_body": "<div>Hi Christiano, lets do the SIIUUUU</div>",
      "subject": "Quick question for you, Ronaldo",
      "email_seq_number": "1",
      "open_count": 9,
      "click_count": 1,
      "click_details": {
        "https://google.com": true
      }
    },
    {
      "type": "REPLY",
      "message_id": "<sw-uibo3i2hoi-ced32-23iuboufde-23oub@outlook.com>",
      "stats_id": "iuh2o3iuh3o2ih2-iuho3-edwhi92-oiho3-3223oihoi9uf",
      "time": "2023-03-15T09:13:29.000Z",
      "email_body": "<p>Yes, I was upset but I am fine</p>"
    }
  ],
  "from": "j_s@smartlead-outbound.com",
  "to": "ronaldo.christiano@siu.io"
}
```

### Error Response (400)

```json
{}
```

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `history` | array | Array of message objects in chronological order |
| `type` | string | Message type: SENT or REPLY |
| `message_id` | string | Unique message identifier |
| `stats_id` | string | Unique statistics tracking ID per lead/sequence/campaign |
| `time` | string | ISO 8601 timestamp of message |
| `email_body` | string | HTML formatted email body content |
| `subject` | string | Email subject line |
| `email_seq_number` | string | Sequence number (campaign emails only) |
| `open_count` | integer | Email open count (campaign emails only) |
| `click_count` | integer | Link click count (campaign emails only) |
| `click_details` | object | URL tracking data showing clicked links |
| `from` | string | Sender email address |
| `to` | string | Recipient email address |
