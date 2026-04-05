# Get Webhooks Publish Summary

## Overview

This endpoint provides a summary of webhook publish statuses for a specific Smartlead campaign. You can view the number of events sent, broken down by event type, as well as the counts for successful, failed, scheduled for retry, and retroactively failed events.

## API Endpoint

**HTTP Method:** `GET`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks/summary`

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign-id` | string | Yes | N/A | The ID of the campaign to fetch webhook summary for |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API key for authentication |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks/summary?api_key=${API_KEY}
```

## Response

### Success Response (200)

```json
{
  "ok": true,
  "data": {
    "sent_count": 150,
    "successful_count": 145,
    "failed_count": 3,
    "scheduled_for_retry_count": 2,
    "retroactively_failed_count": 0,
    "event_types": {
      "email_sent": 100,
      "email_opened": 45,
      "link_clicked": 15,
      "email_replied": 8
    }
  }
}
```

### Error Response (400)

```json
{
  "error": "Invalid campaign ID"
}
```
