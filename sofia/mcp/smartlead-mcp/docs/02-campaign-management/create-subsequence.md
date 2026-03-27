# Create Subsequence API Documentation

## Endpoint Overview

**Title:** Create Subsequence

**Description:** Use this endpoint to create subsequences

**HTTP Method:** POST

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/create-subsequence`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body

The endpoint accepts a JSON payload with campaign configuration details including:

- Campaign identification and settings
- Sequence configuration
- Email account assignments
- Schedule parameters
- General settings (tracking, unsubscribe text, etc.)

---

## Request Example (cURL)

```bash
curl https://server.smartlead.ai/api/v1/campaigns/create-subsequence?api_key=${API_KEY} \
  --request POST \
  --header "Content-Type: application/json" \
  --data '{
    "name": "Test subsequence",
    "client_id": 22
  }'
```

---

## Response Examples

### Success Response (200 OK)

```json
{
  "ok": true,
  "id": 3023,
  "name": "Test email campaign",
  "created_at": "2022-11-07T16:23:24.025929+00:00"
}
```

### Error Response (400 Bad Request)

```json
{}
```
