# Update Lead Using the Lead ID

## Overview
This endpoint allows you to modify lead information using the lead ID and campaign ID.

**Description:** "This endpoint lets you update a lead using the lead ID"

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | Campaign ID that lead belongs to |
| `lead_id` | string | Yes | The lead ID to update |

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

---

## Request Body Parameters

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `first_name` | string | No | Lead's first name | "Cristiano" |
| `last_name` | string | No | Lead's last name | "Ronaldo" |
| `email` | string | No | Lead's email address | "cristiano@mufc.com" |
| `phone_number` | integer | No | Lead's phone number | 239392029 |
| `company_name` | string | No | Company name | "Manchester United" |
| `website` | string | No | Lead's website | "mufc.com" |
| `location` | string | No | Lead's location | "London" |
| `custom_fields` | object | No | Custom fields (max 20 fields) | `{"Title": "Regional Manager"}` |
| `linkedin_profile` | string | No | LinkedIn profile URL | "http://www.linkedin.com/in/cristianoronaldo" |
| `company_url` | string | No | Company URL | "mufc.com" |

---

## Request Example (cURL)

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}?api_key={API_KEY} \
  --data '{
    "first_name": "Cristiano",
    "last_name": "Ronaldo",
    "email": "cristiano@mufc.com",
    "phone_number": 239392029,
    "company_name": "Manchester United",
    "website": "mufc.com",
    "location": "London",
    "custom_fields": {
      "Title": "Regional Manager",
      "First_Line": "Loved your recent post about remote work on Linkedin"
    },
    "linkedin_profile": "http://www.linkedin.com/in/cristianoronaldo",
    "company_url": "mufc.com"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true
}
```

### Error Response (400)

```json
{}
```
