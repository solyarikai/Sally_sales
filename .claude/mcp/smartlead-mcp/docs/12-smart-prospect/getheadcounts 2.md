# Get Head Counts API Documentation

## Overview

Returns paginated list of head counts (company size ranges). Optional search filtering.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/head-counts`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of head counts to return (1-100) |
| `offset` | string | No | 0 | Number of head counts to skip for pagination |
| `search` | string | No | — | Search string for head count values (1-255 chars) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/head-counts?api_key=YOUR_API_KEY&limit=10&offset=0&search=1-10"
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
      "head_count": "1-10"
    },
    {
      "id": 2,
      "head_count": "11-50"
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
