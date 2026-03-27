# Get States API Documentation

## Overview

Returns paginated list of states. Supports optional search filtering and filter by country.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/states`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of states to return (1-100) |
| `offset` | string | No | 0 | Number of states to skip for pagination |
| `search` | string | No | — | Search string to match state names starting with value (1-255 chars) |
| `country` | string | No | — | Filter by country name(s), comma-separated (e.g. india,usa,canada) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/states?api_key=YOUR_API_KEY&limit=10&offset=0&search=tex&country=usa"
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
      "id": 1,
      "state_name": "Texas"
    },
    {
      "id": 2,
      "state_name": "California"
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "page": 1,
    "count": 2
  },
  "search": null
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
