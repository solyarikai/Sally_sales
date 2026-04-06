# Get Recent Searches API Documentation

## Overview

Returns paginated recent searches for the authenticated user.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/recent-searches`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of recent searches to return |
| `offset` | string | No | 0 | Number of recent searches to skip for pagination |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/recent-searches?api_key=YOUR_API_KEY&limit=10&offset=0"
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": {
    "recentSearches": [
      {
        "id": 327106,
        "search_string": "Director in United States",
        "filter_details": {
          "title": ["director"],
          "country": ["United States"],
          "dontDisplayOwnedContact": false,
          "limit": 25,
          "titleExactMatch": false
        },
        "created_at": "2025-01-15T10:00:00.000Z",
        "updated_at": "2025-01-20T14:30:00.000Z"
      }
    ],
    "totalCount": 1
  }
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
