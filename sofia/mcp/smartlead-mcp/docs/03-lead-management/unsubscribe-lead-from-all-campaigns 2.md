# Unsubscribe Lead From All Campaigns

## Description

"This endpoint unsubscribe a lead from all campaigns the lead belongs to and prevents it from being added to any future campaigns"

## HTTP Method & URL

```
POST https://server.smartlead.ai/api/v1/leads/{lead_id}/unsubscribe
```

## Path Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `lead_id` | string | Yes | `lead_id` | The lead ID to unsubscribe from all campaigns |

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body

No request body required for this endpoint.

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/leads/{lead_id}/unsubscribe?api_key={API_KEY}
```

## Response Examples

### Success Response (200 OK)

```json
{
  "ok": true
}
```

### Error Response (404 Not Found)

```json
{
  "error": "Lead not found - Invalid lead_id."
}
```
