# Fetch Leads From Global Block List

## Overview

Retrieves leads and domains from the global block list. This endpoint enables you to access blocked entries with optional filtering.

**Description:** "This endpoint gets a lead/domain from the global block list"

---

## API Endpoint

```
GET https://server.smartlead.ai/api/v1/leads/get-domain-block-list
```

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |
| `offset` | string | No | — | Pagination offset for results |
| `limit` | string | No | `1` | Number of results per request (max 100) |
| `filter_client_id` | string | No | `apple.com` | Filter by specific client ID |
| `filter_email_or_domain` | string | No | — | Fuzzy match filter for email or domain |
| `filter_email_with_domain` | string | No | — | Exact match filter for email address |

---

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/leads/get-domain-block-list?offset=0&limit=1&filter_email_with_domain=test1.com&api_key=API_KEY
```

---

## Response

### Success Response (200)

```json
[
  {
    "id": 17,
    "email_or_domain": "test2.com",
    "created_at": "2023-12-06T06:31:51.566Z",
    "source": "manual",
    "client_id": null
  },
  {
    "id": 16,
    "email_or_domain": "ramesh@test1.com",
    "created_at": "2023-12-06T06:31:43.457Z",
    "source": "manual",
    "client_id": 2
  }
]
```

### Response Schema

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `id` | integer | 17 | Block list entry ID |
| `email_or_domain` | string | "test2.com" | Blocked email address or domain |
| `created_at` | string (ISO 8601) | "2023-12-06T06:31:51.566Z" | Creation timestamp |
| `source` | string | "manual" | Source of the block |
| `client_id` | integer/null | 2 | Associated client ID (if applicable) |
