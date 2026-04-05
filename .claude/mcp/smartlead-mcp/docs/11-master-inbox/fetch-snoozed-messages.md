# Fetch Snoozed Messages API Documentation

## Overview
Retrieve all snoozed messages from your master inbox using this endpoint.

## Endpoint Details

**HTTP Method:** `POST`

**Base URL:** `https://server.smartlead.ai/api/v1/master-inbox`

**Path:** `/snoozed`

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/snoozed`

---

## Authentication

**Type:** API Key (Query Parameter)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fetch_message_history` | boolean | No | Include complete email conversation history |

---

## Request Body

### Body Schema Structure:

```json
{
  "offset": 0,
  "limit": 10,
  "filters": {
    "search": "string",
    "leadCategories": {
      "unassigned": false,
      "isAssigned": true,
      "categoryIdsNotIn": [1, 2],
      "categoryIdsIn": [3, 4, 5]
    },
    "emailStatus": ["Opened", "Clicked", "Replied"],
    "campaignId": [12345],
    "emailAccountId": [100],
    "campaignTeamMemberId": [50],
    "campaignTagId": [10],
    "campaignClientId": [300],
    "replyTimeBetween": ["2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"]
  },
  "sortBy": "REPLY_TIME_DESC"
}
```

### Body Parameters:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `offset` | integer | No | 0 | Number of records to skip (minimum 0) |
| `limit` | integer | No | 10 | Maximum records to return (1-20) |
| `filters` | object | No | — | Filtering options for snoozed messages |
| `sortBy` | string | No | — | Sort order: `REPLY_TIME_DESC` or `SENT_TIME_DESC` |

---

## Request Example

```bash
curl -X POST \
  "https://server.smartlead.ai/api/v1/master-inbox/snoozed?api_key=YOUR_API_KEY&fetch_message_history=true" \
  -H "Content-Type: application/json" \
  -d '{
    "offset": 0,
    "limit": 5,
    "filters": {
      "search": "john",
      "emailStatus": ["Replied", "Opened"],
      "campaignId": [12345]
    },
    "sortBy": "REPLY_TIME_DESC"
  }'
```

---

## Response Schema

### Success Response (200 OK)

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
      "is_important": false,
      "is_archived": false,
      "is_snoozed": true,
      "email_campaign_id": 1456277,
      "email_campaign_name": "Sample Campaign",
      "campaign_sending_schedule": {
        "tz": "Asia/Kolkata",
        "days": [1, 2, 3, 4, 5],
        "endHour": "18:00",
        "startHour": "09:00"
      }
    }
  ],
  "offset": 0,
  "limit": 10
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Operation success indicator |
| `data` | array | Array of snoozed message records |
| `offset` | integer | Number of records skipped |
| `limit` | integer | Maximum records returned |

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

---

## HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Success - Request completed |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing/invalid API key |
