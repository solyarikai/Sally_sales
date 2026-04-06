# Get Cities API Documentation

## Overview

Returns paginated list of cities. Supports optional search filtering and filters by state/country.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/cities`

---

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of cities to return (1-100) |
| `offset` | string | No | 0 | Number of cities to skip for pagination |
| `search` | string | No | — | Search string to match city names starting with value (1-255 chars) |
| `state` | string | No | — | Filter by state name(s), comma-separated (1-255 chars) |
| `country` | string | No | — | Filter by country name(s), comma-separated; requires state (1-255 chars) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/cities?api_key=YOUR_API_KEY&limit=10&offset=0&search=austin&state=california&country=usa"
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
      "city_name": "Austin"
    },
    {
      "id": 2,
      "city_name": "Houston"
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
