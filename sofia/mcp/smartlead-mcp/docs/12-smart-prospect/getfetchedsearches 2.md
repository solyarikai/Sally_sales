# Get Fetched Searches API Documentation

## Overview

Returns paginated fetched leads (search filters with fetch metrics) for the authenticated user.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/fetched-searches`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API key for authentication |
| `limit` | string | No | 10 | Number of fetched searches to return |
| `offset` | string | No | 0 | Number of fetched searches to skip for pagination |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/fetched-searches?api_key=YOUR_API_KEY&limit=10&offset=0"
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": {
    "fetchedLeads": [
      {
        "id": 327107,
        "user_id": 2568,
        "search_string": "Director in United States",
        "filter_details": {
          "title": ["Director"],
          "country": ["United States"],
          "limit": 100
        },
        "type": "saved",
        "include_owned": false,
        "is_saved": true,
        "is_fetched": true,
        "fetch_details": {
          "metrics": {
            "totalContacts": 500,
            "totalEmails": 480,
            "noEmailFound": 20,
            "invalidEmails": 10,
            "catchAllEmails": 5,
            "verifiedEmails": 465,
            "completed": 500
          },
          "leads_found": 500,
          "email_fetched": 480
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
