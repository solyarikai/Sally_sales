# Find Emails API Documentation

## Overview

Find email addresses for up to 10 contacts using first name, last name, and company domain.

**HTTP Method:** POST

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-contacts/find-emails`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | No | API key for authentication (alternative to Bearer token) |

## Request Body (JSON)

| Parameter | Type | Required | Max Items | Description |
|-----------|------|----------|-----------|-------------|
| `contacts` | array | Yes | 10 | Array of contact objects |
| `contacts[].firstName` | string | Yes | — | First name of the contact |
| `contacts[].lastName` | string | Yes | — | Last name of the contact |
| `contacts[].companyDomain` | string | Yes | — | Company domain (e.g., example.com) |

---

## Request Example

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-contacts/find-emails?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contacts": [
      {
        "firstName": "John",
        "lastName": "Doe",
        "companyDomain": "example.com"
      },
      {
        "firstName": "Jane",
        "lastName": "Smith",
        "companyDomain": "acme.io"
      }
    ]
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Find emails completed",
  "data": [
    {
      "firstName": "John",
      "lastName": "Doe",
      "companyDomain": "example.com",
      "email_id": "john.doe@example.com",
      "status": "Found",
      "verification_status": "Valid"
    },
    {
      "firstName": "Jane",
      "lastName": "Smith",
      "companyDomain": "acme.io",
      "email_id": "",
      "status": "Not Found",
      "verification_status": null
    }
  ]
}
```

### Error Response (400)

```json
{
  "success": false,
  "message": "contacts array is required and must have at least one item",
  "data": null
}
```

### Error Response (401)

```json
{
  "success": false,
  "message": "User not authenticated",
  "data": null
}
```

### Error Response (402)

```json
{
  "success": false,
  "message": "Insufficient credits",
  "data": null
}
```

---

## Response Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `firstName` | string | No | Contact first name (echo) |
| `lastName` | string | No | Contact last name (echo) |
| `companyDomain` | string | No | Company domain (echo) |
| `email_id` | string | No | Found email or empty string |
| `status` | string | No | "Found", "Not Found", or "Invalid" |
| `verification_status` | string | Yes | "Valid", "Catch_All", "Unknown", "Blacklisted", or null |

---

## Notes

- Credits are deducted for contacts that are new or were last fetched more than 30 days ago
- Maximum 10 contacts per request
- Each contact must include firstName, lastName, and companyDomain
