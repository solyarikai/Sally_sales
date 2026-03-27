# Get Client List API Documentation

## Overview
**Title:** Get Client List
**Description:** Retrieve a list of all clients for analytics purposes.

**API Version:** v1.0
**Base URL:** `https://server.smartlead.ai/api`

---

## HTTP Method & Endpoint
```
GET /v1/analytics/client/list
```

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |

**Note:** No path parameters or request body required.

---

## Request Example

### cURL
```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/client/list?api_key=YOUR_API_KEY&client_ids=12345,67890"
```

---

## Response

### Success Response (200 OK)

**Schema:**
```json
{
  "success": boolean,
  "message": string,
  "data": {
    "client_list": [
      {
        "id": integer,
        "name": string,
        "email": string,
        "uuid": string,
        "created_at": string (date-time),
        "user_id": integer,
        "logo": string,
        "logo_url": string
      }
    ]
  }
}
```

**Example Response:**
```json
{
  "success": true,
  "message": "Clients fetched successfully",
  "data": {
    "client_list": [
      {
        "id": 12345,
        "name": "Campaign Name",
        "email": "myuser@email.com",
        "uuid": "87f8171e-b44b-45a2-954a-15ac16fa0ab6",
        "created_at": "2025-06-23T16:37:48.539Z",
        "user_id": 12345,
        "logo": "Queen One",
        "logo_url": "https://myurl.com"
      }
    ]
  }
}
```

---

## Notes
- Maximum 50 client IDs can be filtered in a single request
- The `client_ids` parameter is optional; omit to retrieve all clients
- Authentication via `api_key` query parameter is mandatory
