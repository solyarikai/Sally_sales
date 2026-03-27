# Get Revenue Options API Documentation

## Overview

Returns all active revenue options (company revenue ranges).

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/revenue`

---

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/revenue?api_key=YOUR_API_KEY"
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
      "revenue": "$1M-$10M"
    },
    {
      "id": 2,
      "revenue": "$10M-$50M"
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
