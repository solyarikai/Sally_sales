# Get Sub-Industries API Documentation

## Overview

Returns paginated list of sub-industries. Optional search and industry_id filtering.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/sub-industries`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of sub-industries to return (1-100) |
| `offset` | string | No | 0 | Number of sub-industries to skip for pagination |
| `search` | string | No | — | Search string to match sub-industry names starting with value (1-255 chars) |
| `industry_id` | string | No | — | Filter by industry ID (positive integer) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/sub-industries?api_key=YOUR_API_KEY&limit=10&offset=0&industry_id=1"
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
      "sub_industry_name": "Software",
      "industry_id": 1
    },
    {
      "id": 2,
      "sub_industry_name": "Hardware",
      "industry_id": 1
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "page": 1,
    "count": 2
  },
  "search": null,
  "industry_id": null
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
