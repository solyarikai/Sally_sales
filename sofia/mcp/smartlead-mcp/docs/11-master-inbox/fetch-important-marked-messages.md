# Fetch Important Marked Messages

## Overview

**Description:** Use this endpoint to fetch all important messages in your master inbox

**HTTP Method:** POST

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/important`

---

## Authentication

**Type:** API Key (Query Parameter)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |
| `fetch_message_history` | boolean | No | `false` | Include complete email conversation history |

---

## Request Body

The request body uses the same schema as the "Fetch Inbox Replies" endpoint.

### Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `offset` | integer | No | 0 | Number of records to skip (minimum 0) |
| `limit` | integer | No | 10 | Maximum number of records to return (1-20) |
| `filters.search` | string | No | - | Search text for lead names or emails |
| `filters.leadCategories.unassigned` | boolean | No | - | Include leads without any category assigned |
| `filters.leadCategories.isAssigned` | boolean | No | - | Include leads with categories assigned |
| `filters.leadCategories.categoryIdsNotIn` | array(integer) | No | - | Exclude leads with these category IDs |
| `filters.leadCategories.categoryIdsIn` | array(integer) | No | - | Include only leads with these category IDs |
| `filters.emailStatus` | array(string) | No | - | Filter by status: "Opened", "Clicked", "Replied", "Unsubscribed", "Bounced", "Accepted", "Not Replied" |
| `filters.campaignId` | array(integer) | No | - | Filter by campaign ID (max 5) |
| `filters.emailAccountId` | array(integer) | No | - | Filter by email account ID |
| `filters.campaignTeamMemberId` | array(integer) | No | - | Filter by team member ID |
| `filters.campaignTagId` | array(integer) | No | - | Filter by campaign tag ID |
| `filters.campaignClientId` | array(integer) | No | - | Filter by client ID |
| `filters.replyTimeBetween` | array(string) | No | - | Filter by reply time range [start_date, end_date] |
| `sortBy` | string | No | - | Sort order: `REPLY_TIME_DESC` or `SENT_TIME_DESC` |

---

## cURL Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/important?api_key=YOUR_API_KEY&fetch_message_history=true" \
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
      "lead_email": "digitalgpoint.webmail@gmail.com",
      "email_lead_id": "2326941038",
      "email_lead_map_id": "1906151033",
      "lead_status": "COMPLETED",
      "current_sequence_number": 1,
      "sub_sequence_id": null,
      "lead_next_timestamp_to_send": null,
      "email_campaign_seq_id": null,
      "is_important": false,
      "is_archived": false,
      "is_snoozed": false,
      "team_member_id": null,
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
          "email_body": "<div>Hey Team,</div>",
          "subject": "Linking Up for Mutual Benefit - smartlead.ai",
          "email_seq_number": "1",
          "open_count": 9,
          "click_count": 0,
          "click_details": {}
        }
      ]
    }
  ],
  "offset": 0,
  "limit": 2
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

- This endpoint mirrors the "Fetch Inbox Replies" endpoint structure
- The `email_history` field is only included when `fetch_message_history=true`
- Maximum limit per request: 20 records
- Supports pagination via `offset` and `limit` parameters
