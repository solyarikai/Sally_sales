# Get Campaign Sequence Analytics

## Overview

Retrieves analytics data for a specific email campaign sequence, including sent count, open count, click count, and other engagement metrics.

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/sequence-analytics`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | integer (int32) | Yes | The ID of the campaign to fetch analytics for |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API Key for authentication |
| `start_date` | string (date) | Yes | Start date in YYYY-MM-DD HH:MM:SS format |
| `end_date` | string (date) | Yes | End date in YYYY-MM-DD HH:MM:SS format |

---

## Request Example (cURL)

```bash
curl --location 'https://server.smartlead.ai/api/v1/campaigns/1562551/sequence-analytics?api_key=<api_key>&start_date=2024-01-23%2000%3A00%3A00&end_date=2025-03-10%2000%3A00%3A00&time_zone=Europe%2FLondon' \
--header 'accept: application/json' \
--header 'content-type: application/json'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "data": [
    {
      "email_campaign_seq_id": 2868271,
      "sent_count": 6,
      "skipped_count": 0,
      "open_count": 2,
      "click_count": 0,
      "reply_count": 0,
      "bounce_count": 0,
      "unsubscribed_count": 0,
      "failed_count": 0,
      "stopped_count": 0,
      "ln_connection_req_pending_count": 0,
      "ln_connection_req_accepted_count": 0,
      "ln_connection_req_skipped_sent_msg_count": 0,
      "positive_reply_count": 0
    }
  ]
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Request success indicator |
| `data` | array | Array of sequence analytics objects |
| `data[].email_campaign_seq_id` | integer | Sequence ID |
| `data[].sent_count` | integer | Total emails sent |
| `data[].skipped_count` | integer | Skipped email count |
| `data[].open_count` | integer | Total opens |
| `data[].click_count` | integer | Total clicks |
| `data[].reply_count` | integer | Total replies |
| `data[].bounce_count` | integer | Bounced emails |
| `data[].unsubscribed_count` | integer | Unsubscribed leads |
| `data[].failed_count` | integer | Failed sends |
| `data[].stopped_count` | integer | Stopped leads |
| `data[].ln_connection_req_pending_count` | integer | LinkedIn requests pending |
| `data[].ln_connection_req_accepted_count` | integer | LinkedIn requests accepted |
| `data[].ln_connection_req_skipped_sent_msg_count` | integer | LinkedIn requests skipped |
| `data[].positive_reply_count` | integer | Positive reply count |

### Error Response (400)

```json
{}
```
