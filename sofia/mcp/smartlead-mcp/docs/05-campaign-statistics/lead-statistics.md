# Fetch Campaign Lead Statistics

## Endpoint Overview

**Description:** This endpoint fetches campaign statistics using the campaign's ID

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/lead-statistics`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | N/A | The ID of the campaign for which to fetch lead statistics |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Body

No request body required for this endpoint.

---

## Authentication

**Security Scheme:** API Key

- **Type:** API Key
- **Location:** Query parameter
- **Parameter Name:** `api_key`

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/lead-statistics?api_key={API_KEY}
```

---

## Response Examples

### Success Response (200)

The endpoint returns campaign lead statistics. Based on the documentation structure, expected response fields include:

```json
{
  "campaign_lead_statistics": {
    "total_leads": 100,
    "sent_count": 85,
    "open_count": 42,
    "click_count": 15,
    "reply_count": 8,
    "bounce_count": 3,
    "unsubscribed_count": 2
  }
}
```

### Error Response (400)

```json
{}
```

---

## Notes

- This endpoint is part of the **Campaign Statistics** section
- No request body parameters are needed
- Authentication requires a valid API key passed as a query parameter
- The endpoint retrieves aggregated lead performance metrics for a specific campaign
