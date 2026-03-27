# Get Levels API Documentation

## Overview

Returns paginated list of job/seniority levels with optional search filtering.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/levels`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Results per page (1-100) |
| `offset` | string | No | 0 | Number of records to skip for pagination |
| `search` | string | No | — | Filter by level names starting with value (1-255 chars) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/levels?api_key=YOUR_API_KEY&limit=10&offset=0&search=Senior"
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
      "level_name": "Entry"
    },
    {
      "id": 2,
      "level_name": "Senior"
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
