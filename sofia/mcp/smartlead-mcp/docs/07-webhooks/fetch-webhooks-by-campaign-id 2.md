# Fetch Webhooks By Campaign ID

## Overview

This endpoint retrieves all webhooks associated with a specific campaign using the campaign ID.

## Request Details

**HTTP Method:** `GET`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign-id` | string | Yes | The ID of the campaign for which to fetch webhooks |

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |

### Request Body

No request body required for this endpoint.

## Examples

### cURL Request

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks?api_key=${API_KEY}
```

## Response

### Success Response (200)

```json
{
  "ok": true,
  "data": [
    {
      "id": 123,
      "campaign_id": "456",
      "webhook_url": "https://example.com/webhook",
      "events": ["email_sent", "email_opened"],
      "created_at": "2023-01-15T10:30:00Z"
    }
  ]
}
```

### Error Response (400/404)

```json
{
  "error": "Campaign not found - Invalid campaign_id."
}
```
