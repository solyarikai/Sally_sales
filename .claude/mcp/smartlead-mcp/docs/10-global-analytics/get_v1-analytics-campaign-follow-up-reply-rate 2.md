# Get Follow-up Reply Rate API Documentation

## Overview

Get follow-up reply rate statistics for campaigns.

**HTTP Method:** GET

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/follow-up-reply-rate`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/follow-up-reply-rate?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Follow-up reply rate stats fetched successfully!",
  "data": {
    "followup_reply_rate": "0.00%",
    "followup_stats": {
      "total_followups": 100,
      "followup_replies": 5,
      "followup_reply_rate": "5.00%",
      "avg_followups_per_campaign": 2.5
    }
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates if the request succeeded |
| `message` | string | Human-readable status message |
| `data.followup_reply_rate` | string | Overall follow-up reply rate |
| `data.followup_stats.total_followups` | integer | Total follow-up emails sent |
| `data.followup_stats.followup_replies` | integer | Number of replies received |
| `data.followup_stats.followup_reply_rate` | string | Reply rate as percentage |
| `data.followup_stats.avg_followups_per_campaign` | number | Average follow-ups per campaign |
