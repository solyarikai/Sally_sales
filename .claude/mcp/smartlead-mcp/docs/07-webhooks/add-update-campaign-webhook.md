# Add / Update Campaign Webhook

## Overview

This endpoint allows you to add a new webhook to a campaign or update an existing webhook configuration.

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign-id` | string | Yes | N/A | The unique identifier of the campaign |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Body

The request body accepts a JSON object with webhook configuration details.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | The webhook endpoint URL where events will be sent |
| `event_types` | array | Yes | Array of events to subscribe to (e.g., "email_opened", "email_replied", "email_sent") |
| `headers` | object | No | Custom HTTP headers to include in webhook requests |
| `active` | boolean | No | Whether the webhook is active (defaults to true) |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks?api_key=${API_KEY} \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/webhook",
    "event_types": ["email_sent", "email_opened", "email_replied"],
    "headers": {
      "Authorization": "Bearer token123"
    },
    "active": true
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "data": {
    "id": 12345,
    "campaign_id": 3070,
    "url": "https://example.com/webhook",
    "event_types": ["email_sent", "email_opened", "email_replied"],
    "active": true,
    "created_at": "2024-01-15T10:30:00.000Z",
    "updated_at": "2024-01-15T10:30:00.000Z"
  }
}
```

### Error Response (400)

```json
{
  "error": "Invalid webhook URL format"
}
```

```json
{
  "error": "Campaign not found - Invalid campaign_id"
}
```

---

## Notes

- Maximum of one webhook per event type per campaign
- Webhook will retry failed deliveries up to 5 times
- See "Capturing Email Replies" section for reply-specific webhook handling
