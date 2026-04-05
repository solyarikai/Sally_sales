# Get Contacts API Documentation

## Overview

Retrieve saved contacts either by `filter_id` (with optional limit/offset/search/verification filters) or by `id` (array of adapt_ids, max 200). Provide either id or filter_id -- not both (XOR).

**HTTP Method:** POST

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/get-contacts`

---

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

## Request Body Parameters

| Name | Type | Required | Default | Constraints | Description |
|------|------|----------|---------|-------------|-------------|
| `id` | array[string] | Conditional | — | Max 200 items | Array of adapt_ids for specific contacts |
| `filter_id` | number | Conditional | — | — | Filter ID to retrieve data |
| `limit` | number | No | — | 1-1000 | Number of records to return (with filter_id) |
| `offset` | number | No | 0 | >= 0 | Pagination offset |
| `search` | string | No | — | — | Search by first_name, last_name, or full_name |
| `verification_status` | string | No | — | valid, catch_all, invalid | Filter by email verification status |
| `catch_all_status` | string | No | — | catch_all_verified, catch_all_soft_bounced, catch_all_hard_bounced, catch_all_unknown, catch_all_bounced | Filter by catch-all status |

---

## Request Examples

### Fetch by Filter ID

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/get-contacts?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_id": 327105,
    "limit": 50,
    "offset": 0
  }'
```

### Fetch by Contact IDs

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/get-contacts?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": ["5f22b0c8cff47e0001616f81", "5f22b1a0cff47e000161b01f"]
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": {
    "list": [
      {
        "id": "5f22b0c8cff47e0001616f81",
        "firstName": "Orhan",
        "lastName": "Demiri",
        "fullName": "Orhan Demiri",
        "title": "Director",
        "company": { "name": "Example Corp", "website": "example.com" },
        "department": ["Sales"],
        "level": "C-Level",
        "industry": "Technology",
        "email": "orhan@example.com",
        "verificationStatus": "valid",
        "catchAllStatus": null
      }
    ],
    "metrics": {
      "totalContacts": 100,
      "totalEmails": 95,
      "noEmailFound": 2,
      "invalidEmails": 1,
      "catchAllEmails": 2,
      "verifiedEmails": 90,
      "completed": 95
    },
    "pagination": {
      "filterId": 327105,
      "limit": 50,
      "offset": 0,
      "total": 100,
      "hasMore": true
    },
    "totalCount": 100,
    "last_fetched_at": "2024-01-15T10:30:00Z"
  }
}
```

### Error Response (400)

```json
{
  "success": false,
  "message": "Either id or filter_id is required",
  "error": "Missing required parameter"
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
