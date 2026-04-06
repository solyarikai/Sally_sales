# Get Departments API Documentation

## Overview

Returns paginated list of departments. Supports optional search filtering by department names.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/departments`

---

## Authentication

Bearer token or API key query parameter.

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of departments to return (1-100) |
| `offset` | string | No | 0 | Number of departments to skip for pagination |
| `search` | string | No | null | Search string to match department names starting with value (1-255 chars) |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/departments?api_key=YOUR_API_KEY&limit=10&offset=0&search=Eng" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
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
      "department_name": "Engineering"
    },
    {
      "id": 2,
      "department_name": "Sales"
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
