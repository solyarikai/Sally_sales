# Fetch Inbox Replies API Documentation

## Endpoint Overview

**Title:** Fetch Inbox Replies

**Description:** "Retrieve all leads that have replied to email campaigns"

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/master-inbox`

**Full Endpoint:** `https://server.smartlead.ai/api/v1/master-inbox/inbox-replies`

---

## Authentication

**Type:** API Key (Query Parameter)

| Parameter | Type | Required | Location | Default |
|-----------|------|----------|----------|---------|
| `api_key` | string | Yes | Query | API_KEY |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API authentication key |
| `fetch_message_history` | boolean | No | false | "Include complete email conversation history" |

---

## Request Body

**Content-Type:** `application/json`

### Body Schema

```json
{
  "offset": {
    "type": "integer",
    "description": "Number of records to skip (minimum 0)",
    "default": 0
  },
  "limit": {
    "type": "integer",
    "description": "Maximum number of records to return (1-20)",
    "default": 10
  },
  "filters": {
    "type": "object",
    "properties": {
      "search": {
        "type": "string",
        "description": "Search text for lead names or emails"
      },
      "leadCategories": {
        "type": "object",
        "properties": {
          "unassigned": {
            "type": "boolean",
            "description": "Include leads without any category assigned"
          },
          "isAssigned": {
            "type": "boolean",
            "description": "Include leads with categories assigned"
          },
          "categoryIdsNotIn": {
            "type": "array",
            "items": { "type": "integer" },
            "description": "Exclude leads with these category IDs"
          },
          "categoryIdsIn": {
            "type": "array",
            "items": { "type": "integer" },
            "description": "Include only leads with these category IDs"
          }
        }
      },
      "emailStatus": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["Opened", "Clicked", "Replied", "Unsubscribed", "Bounced", "Accepted", "Not Replied"]
        },
        "description": "Filter by email engagement status"
      },
      "campaignId": {
        "type": "array",
        "items": { "type": "integer" },
        "maxItems": 5,
        "description": "Filter by campaign ID (array of numbers, max 5)"
      },
      "emailAccountId": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "Filter by email account ID (array of numbers)"
      },
      "campaignTeamMemberId": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "Filter by team member ID (array of numbers)"
      },
      "campaignTagId": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "Filter by campaign tag ID (array of numbers)"
      },
      "campaignClientId": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "Filter by client ID (array of numbers)"
      },
      "replyTimeBetween": {
        "type": "array",
        "items": { "type": "string" },
        "minItems": 2,
        "maxItems": 2,
        "description": "Filter by reply time range [start_date, end_date]"
      }
    }
  },
  "sortBy": {
    "type": "string",
    "enum": ["REPLY_TIME_DESC", "SENT_TIME_DESC"],
    "description": "Sort order for results"
  }
}
```

---

## Request Example

### cURL

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/inbox-replies?api_key=YOUR_API_KEY&fetch_message_history=true" \
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
      "emailAccountId": [100, 200],
      "campaignTeamMemberId": [50],
      "campaignTagId": [10, 20],
      "campaignClientId": [300],
      "replyTimeBetween": ["2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"]
    },
    "sortBy": "REPLY_TIME_DESC"
  }'
```

---

## Response Schema

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
      "lead_email": "digitalgpoint.webmail@gmail.com",
      "email_lead_id": "2326941038",
      "email_lead_map_id": "1906151033",
      "lead_status": "COMPLETED",
      "current_sequence_number": 1,
      "sub_sequence_id": null,
      "old_replaced_lead_data": null,
      "lead_next_timestamp_to_send": null,
      "email_campaign_seq_id": null,
      "is_important": false,
      "is_archived": false,
      "is_snoozed": false,
      "team_member_id": null,
      "is_ooo_automated_push_lead": null,
      "email_campaign_id": 1456277,
      "email_campaign_name": "Visha_Backlink Outreach",
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
          "from": "vgarg@smartlead-backlinking.com",
          "to": "digitalgpoint.webmail@gmail.com",
          "type": "SENT",
          "message_id": "<6d6ef88a-d0c9-sl71-4b7c-9522-922c05b37a35@smartlead-backlinking.com>",
          "time": "2025-07-07T11:13:06.744Z",
          "email_body": "<div>Hey Team,</div><div><br></div><div>I hope you're doing well!</div>",
          "subject": "Linking Up for Mutual Benefit - smartlead.ai",
          "email_seq_number": "1",
          "open_count": 9,
          "click_count": 0,
          "click_details": {}
        },
        {
          "stats_id": "6d6ef88a-d0c9-4b7c-9522-922c05b37a35",
          "from": "digitalgpoint.webmail@gmail.com",
          "to": "vgarg@smartlead-backlinking.com",
          "type": "REPLY",
          "message_id": "<CALvt9-KpZo-aRSyEKqbcUkeB7P0FpJ5FY6aLEufiXTeEW_jLMA@mail.gmail.com>",
          "time": "2025-07-07T11:18:14.000Z",
          "email_body": "<div>Hi,</div><div>Thank you for reaching out.</div>",
          "email_seq_number": "1",
          "cc": []
        }
      ]
    }
  ],
  "offset": 0,
  "limit": 2
}
```

### Response Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Request success indicator |
| `data` | array | Array of lead records with reply data |
| `offset` | integer | Number of records skipped in pagination |
| `limit` | integer | Maximum records returned per request |

#### Lead Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `lead_category_id` | integer | Category classification ID for lead |
| `last_sent_time` | string (date-time) | Timestamp of the most recent email sent to this lead |
| `last_reply_time` | string (date-time) | Timestamp of the most recent reply received from this lead |
| `has_new_unread_email` | boolean | Unread message indicator |
| `email_account_id` | integer | Email account identifier |
| `revenue` | string | Deal value associated with lead |
| `is_pushed_to_sub_sequence` | boolean | Sub-sequence migration status |
| `lead_first_name` | string | Contact first name |
| `lead_last_name` | string | Contact last name |
| `lead_email` | string | Contact email address |
| `email_lead_id` | string | Lead record identifier |
| `email_lead_map_id` | string | Lead-campaign mapping identifier |
| `lead_status` | string | Current lead status (INPROGRESS, COMPLETED, etc.) |
| `current_sequence_number` | integer | Position in email sequence |
| `email_campaign_id` | integer | Campaign identifier |
| `email_campaign_name` | string | Campaign name |
| `campaign_sending_schedule` | object | Campaign timing configuration |

#### Email History Fields

| Field | Type | Description |
|-------|------|-------------|
| `stats_id` | string | Email statistics record identifier |
| `from` | string | Sender email address |
| `to` | string | Recipient email address |
| `type` | string | Email category (SENT or REPLY) |
| `message_id` | string | Unique message identifier |
| `time` | string (date-time) | Email timestamp |
| `email_body` | string | HTML email content |
| `subject` | string | Email subject line |
| `email_seq_number` | string | Sequence position number |
| `open_count` | integer | Email open count |
| `click_count` | integer | Click count within email |
| `click_details` | object | Click interaction details |
| `cc` | array | Carbon copy recipients |

---

## Error Responses

### 401 Unauthorized

```json
{
  "message": "API key is required."
}
```

### 400 Bad Request

```json
{}
```

---

## HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Success - Request completed |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing/invalid API key |
