# Fetch Scheduled Messages - API Documentation

## Endpoint Overview

**Title:** Fetch Scheduled Messages

**Description:** Use this endpoint to fetch all scheduled messages in your master inbox

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/scheduled`

---

## Authentication

**Type:** API Key (Query Parameter)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Authentication credential for your request |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Authentication credential for your request |
| `fetch_message_history` | boolean | No | `false` | Include complete email conversation history |

---

## Request Body

### Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `offset` | integer | No | 0 | Number of records to skip (minimum 0) |
| `limit` | integer | No | 10 | Maximum number of records to return (1-20) |
| `filters` | object | No | — | Filtering options for scheduled messages |
| `sortBy` | string | No | — | Sort order: `SCHEDULED_TIME_DESC` or `SCHEDULED_TIME_ASC` |

### Filter Object Properties

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Search text for lead names or emails |
| `leadCategories.unassigned` | boolean | Include leads without category |
| `leadCategories.isAssigned` | boolean | Include leads with categories |
| `leadCategories.categoryIdsNotIn` | array(integer) | Exclude leads with these category IDs |
| `leadCategories.categoryIdsIn` | array(integer) | Include only leads with these category IDs |
| `emailStatus` | array(string) | Filter by status: Opened, Clicked, Replied, Unsubscribed, Bounced, Accepted, Not Replied |
| `campaignId` | array(integer) | Filter by campaign ID (max 5) |
| `emailAccountId` | array(integer) | Filter by email account ID |
| `campaignTeamMemberId` | array(integer) | Filter by team member ID |
| `campaignTagId` | array(integer) | Filter by campaign tag ID |
| `campaignClientId` | array(integer) | Filter by client ID |
| `replyTimeBetween` | array(string) | Two-element array [start_date, end_date] |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/scheduled?api_key=YOUR_API_KEY&fetch_message_history=true" \
  -H "Content-Type: application/json" \
  -d '{
    "offset": 0,
    "limit": 5,
    "filters": {
      "search": "john",
      "leadCategories": {
        "unassigned": false,
        "isAssigned": true,
        "categoryIdsIn": [3, 4, 5]
      },
      "emailStatus": ["Replied", "Opened"],
      "campaignId": [12345, 67890]
    },
    "sortBy": "SCHEDULED_TIME_DESC"
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
      "revenue": "0.00",
      "is_pushed_to_sub_sequence": false,
      "lead_first_name": "Team",
      "lead_last_name": null,
      "lead_email": "example@gmail.com",
      "email_lead_id": "2326941038",
      "email_lead_map_id": "1906151033",
      "lead_status": "INPROGRESS",
      "current_sequence_number": 1,
      "email_campaign_id": 1456277,
      "email_campaign_name": "Example Campaign",
      "campaign_sending_schedule": {
        "tz": "Asia/Kolkata",
        "days": [1, 2, 3, 4, 5],
        "endHour": "18:00",
        "startHour": "09:00"
      },
      "email_history": []
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

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Request success indicator |
| `data` | array | Array of scheduled message records |
| `offset` | integer | Number of records skipped |
| `limit` | integer | Maximum records returned |

---

## Notes

The sorting parameter specifically supports scheduled message ordering with values: `SCHEDULED_TIME_DESC` or `SCHEDULED_TIME_ASC`. All other parameters match the Inbox Replies endpoint structure.
