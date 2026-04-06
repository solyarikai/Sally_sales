# Review Contacts API Documentation

## Overview

Reviews and updates contacts for a given filter, syncing metrics and verification status.

**HTTP Method:** PATCH

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/review-contacts/{filter_id}`

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `filter_id` | string | Yes | Filter identifier to review contacts for |

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

---

## Request Example

```bash
curl -X PATCH "https://prospect-api.smartlead.ai/api/v1/search-email-leads/review-contacts/327105?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Contacts reviewed successfully",
  "data": {
    "filter_id": 327105,
    "records_updated": 150,
    "fetch_details": {
      "metrics": {
        "totalContacts": 200,
        "totalEmails": 180,
        "noEmailFound": 20,
        "invalidEmails": 10,
        "catchAllEmails": 5,
        "verifiedEmails": 165,
        "completed": 180
      },
      "leads_found": 200,
      "email_fetched": 180,
      "catch_all_status_list": ["catch_all_verified", "catch_all_unknown"],
      "verification_status_list": ["valid", "invalid"]
    }
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

### Error Response (404)

```json
{
  "success": false,
  "message": "Filter not found",
  "error": "Not found"
}
```
