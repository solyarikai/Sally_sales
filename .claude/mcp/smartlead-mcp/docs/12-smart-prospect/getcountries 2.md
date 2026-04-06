# Get Countries API Documentation

## Overview

Returns a paginated list of countries with optional search filtering.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/countries`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Authentication API key |
| `limit` | string | No | 10 | Number of countries to return (1-100) |
| `offset` | string | No | 0 | Countries to skip for pagination |
| `search` | string | No | — | Search string matching country names starting with value (1-255 chars) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/countries?api_key=YOUR_API_KEY&limit=10&offset=0&search=united"
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
      "country_name": "United States"
    },
    {
      "id": 2,
      "country_name": "United Kingdom"
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
