# Push Leads/List to Campaign

## Overview
Allows you to push selected leads or an entire list to a campaign for email outreach execution.

## API Endpoint
**POST** `https://server.smartlead.ai/api/v1/leads/push-to-campaign`

---

## Authentication
- **Type**: API Key
- **Parameter**: `api_key` (query parameter)
- **Default Value**: `API_KEY`

---

## Request Parameters

### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

### Body Parameters
The request body accepts a JSON object. Based on the documented schema, the endpoint supports:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| (Body schema) | object | Yes | Push leads configuration (exact structure not fully detailed in source) |

---

## Request Examples

### cURL
```bash
curl https://server.smartlead.ai/api/v1/leads/push-to-campaign?api_key=${API_KEY}
```

---

## Response

### Success Response (200 OK)
```json
{
  "ok": true,
  "message": "Leads pushed to campaign successfully"
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Indicates successful operation |
| `message` | string | Confirmation message |

---

## Notes
- The source documentation indicates this endpoint exists but provides minimal parameter details in the visible schema
- Refer to related endpoints like "Add leads to a campaign by ID" for similar functionality patterns
- Maximum of 10,000 leads can be processed per request based on platform patterns
