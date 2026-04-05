# Fetch Master Inbox Lead by ID

## Overview

Retrieve a specific lead from the master inbox using its ID.

## HTTP Method & URL

```
GET https://server.smartlead.ai/api/v1/master-inbox/{id}
```

## Parameters

### Path Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `id` | integer | Yes | — | The ID of the lead to retrieve |

### Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API key for authentication |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/master-inbox/1982614021?api_key={API_KEY}
```

## Response Schema

### Success Response (200)

```json
{
  "ok": true,
  "data": [
    {
      "lead_category_id": 1454,
      "last_sent_time": "2025-07-31T04:01:22.422Z",
      "last_reply_time": null,
      "has_new_unread_email": true,
      "email_account_id": 5352520,
      "revenue": "500.50",
      "is_pushed_to_sub_sequence": false,
      "lead_first_name": "Team",
      "lead_last_name": null,
      "lead_email": "hello@gurusoftware.com",
      "email_lead_id": "2428117568",
      "email_lead_map_id": "1982614021",
      "lead_status": "INPROGRESS",
      "current_sequence_number": 2,
      "sub_sequence_id": null,
      "old_replaced_lead_data": null,
      "lead_next_timestamp_to_send": "2025-08-02T04:01:22.422Z",
      "email_campaign_seq_id": 2738054,
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
      }
    }
  ]
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

## Response Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `lead_category_id` | integer | Category ID assigned to the lead |
| `last_sent_time` | string (date-time) | Timestamp of the last email sent |
| `last_reply_time` | string (date-time) | Timestamp of the last reply received |
| `has_new_unread_email` | boolean | Whether unread emails exist from this lead |
| `email_account_id` | integer | ID of the email account used |
| `revenue` | string | Revenue amount associated with lead |
| `is_pushed_to_sub_sequence` | boolean | Whether lead moved to sub-sequence |
| `lead_first_name` | string | Lead's first name |
| `lead_last_name` | string | Lead's last name |
| `lead_email` | string | Lead's email address |
| `email_lead_id` | string | Lead record identifier |
| `email_lead_map_id` | string | Lead-campaign mapping identifier |
| `lead_status` | string | Current status (INPROGRESS, COMPLETED, etc.) |
| `current_sequence_number` | integer | Position in email sequence |
| `email_campaign_id` | integer | ID of the email campaign |
| `email_campaign_name` | string | Name of the campaign |
| `campaign_sending_schedule` | object | Schedule configuration object |
