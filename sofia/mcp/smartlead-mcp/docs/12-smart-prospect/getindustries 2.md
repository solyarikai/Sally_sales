# Get Industries API Documentation

## Overview

Returns a paginated list of industries. Optional search and sub-industry filtering available.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/industries`

---

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of industries to return (1-100) |
| `offset` | string | No | 0 | Number of industries to skip for pagination |
| `search` | string | No | — | Search string to match industry names starting with value (1-255 chars) |
| `withSubIndustry` | string | No | — | Include sub-industries for each industry. Values: "true" or "false" |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/industries?api_key=YOUR_API_KEY&limit=10&offset=0&withSubIndustry=true"
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
      "industry_name": "Technology",
      "sub_industry_list": [
        {
          "sub_industry_name": "Software"
        },
        {
          "sub_industry_name": "Hardware"
        }
      ]
    },
    {
      "id": 2,
      "industry_name": "Healthcare",
      "sub_industry_list": []
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
