# Fetch Contacts API Documentation

## Overview

Retrieve contact emails for a search filter or by specific adapt IDs. Either provide adapt IDs with filter_id, or limit with filter_id to fetch up to limit contacts for that filter.

**HTTP Method:** POST

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/fetch-contacts`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

## Request Body Parameters

| Parameter | Type | Required | Min/Max | Description |
|-----------|------|----------|---------|-------------|
| `filter_id` | number | Yes | >= 1 | Filter ID (required) |
| `id` | array(string) | Conditional | Min 1 item | Adapt IDs to fetch (use with filter_id; no limit check) |
| `limit` | number | Conditional | 1-10000 | Number of contacts to fetch (required when not using id) |
| `visual_limit` | number | No | 1-1000 | Page size for visual pagination (default: 10) |
| `visual_offset` | number | No | >= 0 | Offset for visual pagination (default: 0) |

**Note:** Either provide `id` array with `filter_id`, OR `limit` with `filter_id`.

---

## Request Examples

### Fetch by Limit

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/fetch-contacts?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_id": 327105,
    "limit": 10,
    "visual_limit": 10,
    "visual_offset": 0
  }'
```

### Fetch by Adapt IDs

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/fetch-contacts?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_id": 327105,
    "id": ["5f22b0c8cff47e0001616f81", "5f22b1a0cff47e000161b01f"],
    "visual_limit": 10,
    "visual_offset": 0
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
        "company": {
          "name": "Example Corp",
          "website": "example.com"
        },
        "email": "orhan@example.com",
        "status": "completed"
      }
    ],
    "total_count": 1,
    "visual_limit": 10,
    "visual_offset": 0,
    "metrics": {
      "totalContacts": 1,
      "totalEmails": 1,
      "noEmailFound": 0,
      "invalidEmails": 0,
      "catchAllEmails": 0,
      "verifiedEmails": 1,
      "completed": 1
    }
  }
}
```

### Credits Limit Reached (200, success: false)

```json
{
  "success": false,
  "message": "Not enough credits left. Need 5 more credits to do this operation",
  "data": { "list": [], "total_count": 0 }
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

---

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `data.list` | array | Array of contact objects |
| `data.total_count` | number | Total number of contacts |
| `data.visual_limit` | number | Page size used |
| `data.visual_offset` | number | Offset used |
| `data.metrics.totalContacts` | number | Total contacts found |
| `data.metrics.totalEmails` | number | Emails found |
| `data.metrics.verifiedEmails` | number | Verified email count |
| `data.metrics.invalidEmails` | number | Invalid email count |
| `data.metrics.catchAllEmails` | number | Catch-all email count |
| `data.metrics.noEmailFound` | number | Contacts with no email |
