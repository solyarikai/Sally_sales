# Create Campaign API Documentation

## Endpoint Overview

**Title:** Create Campaign

**Description:** This endpoint creates a campaign

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Endpoint Path:** `/create`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/create`

---

## Authentication

**Security Scheme:** API Key (Query Parameter)

- **Parameter Name:** `api_key`
- **Location:** Query string
- **Required:** Yes
- **Type:** String
- **Default Value:** `API_KEY`

---

## Request Parameters

### Query Parameters

| Parameter | Type | Required | Description | Default |
|-----------|------|----------|-------------|---------|
| `api_key` | String | Yes | Your API key | `API_KEY` |

### Request Body

The endpoint accepts a JSON payload with the following structure:

```json
{
  "name": "Test email campaign",
  "client_id": 22
}
```

**Body Parameters:**

| Parameter | Type | Required | Description | Notes |
|-----------|------|----------|-------------|-------|
| `name` | String | Yes | Name of the campaign | - |
| `client_id` | Integer | No | Client identifier | Leave null if no client association |

---

## Request Examples

### cURL Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/create?api_key=${API_KEY} \
  --data '{
    "name": "Test email campaign",
    "client_id": 22
  }'
```

---

## Response Examples

### Success Response (200)

**Status Code:** 200 OK

**Response Body:**

```json
{
  "ok": true,
  "id": 3023,
  "name": "Test email campaign",
  "created_at": "2022-11-07T16:23:24.025929+00:00"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ok` | Boolean | Indicates successful campaign creation |
| `id` | Integer | Unique identifier of created campaign |
| `name` | String | Campaign name |
| `created_at` | ISO 8601 Timestamp | Campaign creation timestamp |

### Error Response (400)

**Status Code:** 400 Bad Request

**Response Body:**

```json
{}
```

---

## Additional Notes

- The API returns a unique campaign ID upon successful creation
- The `client_id` parameter is optional; omit or set to null if campaign is not associated with a client
- Campaign creation timestamp is provided in ISO 8601 format with UTC timezone
