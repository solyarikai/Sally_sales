# Update Saved Search API Documentation

## Overview

Updates the search string (human-readable name) of an existing saved search by ID.

**HTTP Method:** PUT

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/save-search/{id}`

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | The ID of the saved search to update (positive integer) |

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

## Request Body (JSON)

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `search_string` | string | Yes | 1-255 chars | The new search string/name for the saved search |

---

## Request Example

```bash
curl -X PUT "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/save-search/327105?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "search_string": "Directors and VPs in United States"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Saved search updated successfully"
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

### Error Response (404)

```json
{
  "success": false,
  "message": "Saved search not found",
  "error": "Not found"
}
```
