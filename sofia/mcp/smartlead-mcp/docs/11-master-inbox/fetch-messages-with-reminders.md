# Fetch Messages with Reminders

## Overview

Use this endpoint to fetch all messages with reminders in your master inbox

**HTTP Method:** `POST`

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/reminders`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Authentication credentials for request verification |
| `fetch_message_history` | boolean | No | `false` | Include complete email conversation history |

---

## Request Body

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `offset` | integer | No | 0 | Records to skip (minimum 0) |
| `limit` | integer | No | 10 | Max records returned (1-20) |
| `filters` | object | No | — | Filtering configuration |
| `sortBy` | string | No | — | Sort order: `REMINDER_TIME_DESC` or `REMINDER_TIME_ASC` |

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

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/reminders?api_key=YOUR_API_KEY&fetch_message_history=true" \
  -H "Content-Type: application/json" \
  -d '{
    "offset": 0,
    "limit": 5,
    "filters": {
      "search": "john",
      "emailStatus": ["Replied", "Opened"],
      "campaignId": [12345],
      "replyTimeBetween": ["2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"]
    },
    "sortBy": "REMINDER_TIME_DESC"
  }'
```

---

## Response Examples

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
      "revenue": "500.50",
      "lead_first_name": "Team",
      "lead_email": "example@domain.com",
      "email_lead_id": "2326941038",
      "email_lead_map_id": "1906151033",
      "lead_status": "COMPLETED",
      "is_important": false,
      "is_archived": false,
      "is_snoozed": false,
      "email_campaign_id": 1456277,
      "email_campaign_name": "Backlink Outreach",
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
          "to": "recipient@domain.com",
          "type": "SENT",
          "time": "2025-07-07T11:13:06.744Z",
          "subject": "Subject Line",
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

---

## Notes

This endpoint functions identically to the "Fetch Inbox Replies" endpoint with the single modification of using reminder-specific sort parameters (`REMINDER_TIME_DESC` / `REMINDER_TIME_ASC`).
