# Get Domains API Documentation

## Overview

Returns list of domains with optional pagination and search filtering.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/domain`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 100 | Number of domains to return |
| `offset` | string | No | 0 | Number of domains to skip for pagination |
| `search` | string | No | — | Search string to filter domains by name |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/domain?api_key=YOUR_API_KEY&limit=100&offset=0&search=acme"
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": [
    {
      "domain_name": "acme.com"
    },
    {
      "domain_name": "techinc.com"
    }
  ]
}
```

### Error Response (401)

```json
{
  "statusCode": 401,
  "success": false,
  "message": "Unauthorized",
  "error": "User not authenticated"
}
```

### Error Response (500)

```json
{
  "success": false,
  "message": "Internal server error",
  "error": "Error details"
}
```
