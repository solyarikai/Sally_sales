# Unsubscribe/Pause Lead From Campaign API

## Overview
Endpoint to unsubscribe or pause a lead from a specific campaign.

## HTTP Method & Endpoint
```
POST https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/unsubscribe
```

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | Campaign ID to unsubscribe lead from |
| `lead_id` | string | Yes | `lead_id` | The lead ID to unsubscribe |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body
No request body parameters required for this endpoint.

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/unsubscribe?api_key={API_KEY}
```

## Response Examples

### Success Response (200)
```json
{}
```
