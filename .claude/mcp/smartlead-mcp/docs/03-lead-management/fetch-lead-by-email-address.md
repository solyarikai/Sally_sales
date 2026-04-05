# Fetch Lead by Email Address - API Documentation

## Overview
**Title:** Fetch Lead by email address

**Description:** This endpoint retrieves lead data using an email address as the lookup parameter.

**HTTP Method:** `GET`

**Base URL:** `https://server.smartlead.ai/api/v1/leads/`

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |
| `email` | string | No | `yourmail@email.com` | The email address to search for |

### Path Parameters
None

### Request Body
Not applicable (GET request)

---

## Request Examples

### cURL
```bash
curl https://server.smartlead.ai/api/v1/leads/?api_key=${API_KEY}&email=${email}
```

---

## Response Examples

### Success Response (200)

```json
{
  "id": "91094832",
  "first_name": "David",
  "last_name": "Carroll",
  "email": "davidbeckham@gmail.com",
  "created_at": "2023-08-04T01:09:11.785Z",
  "phone_number": "--",
  "company_name": "--",
  "website": "https://google.com",
  "location": "--",
  "custom_fields": {
    "lastname": "Carroll",
    "firstname": "David",
    "lead_guid": "6b425112-ee7e-4536-aa28-b2ec3ead7dba",
    "first_line": "I loved your recent interview in Forbes magazine",
    "lastmodifieddate": "1694271352931"
  },
  "linkedin_profile": "--",
  "company_url": null,
  "is_unsubscribed": false,
  "unsubscribed_client_id_map": {},
  "lead_campaign_data": [
    {
      "client_id": null,
      "campaign_id": 64961,
      "client_email": null,
      "campaign_name": "",
      "lead_category_id": null,
      "campaign_lead_map_id": 80266596
    }
  ]
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique lead identifier |
| `first_name` | string | Lead's first name |
| `last_name` | string | Lead's last name |
| `email` | string | Lead's email address |
| `created_at` | string | ISO 8601 timestamp of creation |
| `phone_number` | string | Contact phone number |
| `company_name` | string | Associated company |
| `website` | string | Company website URL |
| `location` | string | Geographic location |
| `custom_fields` | object | Additional custom data fields |
| `linkedin_profile` | string | LinkedIn profile URL |
| `company_url` | null/string | Company domain URL |
| `is_unsubscribed` | boolean | Subscription status |
| `unsubscribed_client_id_map` | object | Unsubscription mapping data |
| `lead_campaign_data` | array | Campaign associations |
