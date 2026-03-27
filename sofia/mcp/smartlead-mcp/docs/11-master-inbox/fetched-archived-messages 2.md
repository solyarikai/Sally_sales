# Fetched Archived Messages API Documentation

## Overview
Use this endpoint to fetch all archived messages in your master inbox

## Endpoint Details
- **HTTP Method:** POST
- **URL:** `https://server.smartlead.ai/api/v1/master-inbox/archived`

## Authentication
- **Type:** API Key (Query Parameter)
- **Parameter Name:** `api_key`
- **Required:** Yes

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API authentication key |
| `fetch_message_history` | boolean | No | false | Include complete email conversation history |

## Request Body

The request body accepts the same parameters as the Inbox Replies endpoint:

### Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `offset` | integer | No | 0 | Records to skip (minimum 0) |
| `limit` | integer | No | 10 | Max records returned (1-20) |
| `filters` | object | No | — | Filtering options |
| `sortBy` | string | No | — | Sort order: REPLY_TIME_DESC or SENT_TIME_DESC |

### Filter Options

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Search text for lead names/emails |
| `leadCategories` | object | Filter by category assignments |
| `emailStatus` | array(string) | Filter by engagement status |
| `campaignId` | array(integer) | Filter by campaign (max 5) |
| `emailAccountId` | array(integer) | Filter by email account |
| `campaignTeamMemberId` | array(integer) | Filter by team member |
| `campaignTagId` | array(integer) | Filter by campaign tag |
| `campaignClientId` | array(integer) | Filter by client |
| `replyTimeBetween` | array(string) | Filter by date range [start, end] |

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/archived?api_key=YOUR_API_KEY&fetch_message_history=true" \
  -H "Content-Type: application/json" \
  -d '{
    "offset": 0,
    "limit": 5,
    "filters": {
      "search": "john",
      "leadCategories": {
        "unassigned": false,
        "isAssigned": true,
        "categoryIdsNotIn": [1, 2],
        "categoryIdsIn": [3, 4, 5]
      },
      "emailStatus": ["Replied", "Opened"],
      "campaignId": [12345, 67890],
      "emailAccountId": [100, 200]
    },
    "sortBy": "REPLY_TIME_DESC"
  }'
```

## Response Format

### Success Response (200)

```json
{
  "ok": true,
  "data": [
    {
      "lead_category_id": 1454,
      "last_sent_time": "2025-07-08T13:01:33.131Z",
      "last_reply_time": "2025-07-31T16:48:44.000Z",
      "has_new_unread_email": true,
      "email_account_id": 5352520,
      "revenue": "0.00",
      "is_pushed_to_sub_sequence": false,
      "lead_first_name": "Team",
      "lead_last_name": null,
      "lead_email": "example@gmail.com",
      "email_lead_id": "2326941038",
      "email_lead_map_id": "1906151033",
      "lead_status": "COMPLETED",
      "current_sequence_number": 1,
      "sub_sequence_id": null,
      "email_campaign_id": 1456277,
      "email_campaign_name": "Backlink Outreach",
      "client_id": null,
      "belongs_to_sub_sequence": false,
      "campaign_sending_schedule": {
        "tz": "Asia/Kolkata",
        "days": [1, 2, 3, 4, 5],
        "endHour": "18:00",
        "startHour": "09:00"
      },
      "email_history": [
        {
          "stats_id": "6d6ef88a-d0c9-4b7c-9522-922c05b37a35",
          "from": "sender@domain.com",
          "to": "recipient@gmail.com",
          "type": "SENT",
          "message_id": "<message-id@domain.com>",
          "time": "2025-07-07T11:13:06.744Z",
          "email_body": "<div>Email content here</div>",
          "subject": "Subject line",
          "email_seq_number": "1",
          "open_count": 9,
          "click_count": 0
        }
      ]
    }
  ],
  "offset": 0,
  "limit": 5
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

## Notes

All params, queries, and body objects are exactly the same as the Inbox Replies endpoint.
