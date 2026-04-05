# Fetch Campaign Mailbox Statistics

## Overview

This endpoint retrieves mailbox statistics specific to a campaign. It provides insights into email account performance metrics for a particular campaign.

## Request Details

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/mailbox-statistics`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | N/A | The ID of the campaign for which to fetch mailbox statistics |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/mailbox-statistics?api_key={API_KEY}
```

---

## Response

### Success Response (200)

The endpoint returns mailbox statistics data specific to the campaign.

**Example Response Structure:**
```json
{
  "status": 200,
  "data": {
    "campaign_id": "string",
    "mailbox_statistics": []
  }
}
```

### Error Response (400)

```json
{}
```

---

## Authentication

This endpoint requires API key authentication passed as a query parameter.

**Security Scheme:** API Key (Query Parameter)
- **Name:** `api_key`
- **Location:** Query string
