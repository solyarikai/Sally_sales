# List all leads by Campaign ID - API Documentation

## Endpoint Overview

**Title:** List all leads by Campaign ID

**Description:** This endpoint fetches all the leads in a campaign using the campaign's ID

**HTTP Method:** GET

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full Endpoint:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads`

---

## Parameters

### Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The campaign ID to retrieve leads for |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |
| `offset` | integer | No | null | List offset number for pagination |
| `limit` | integer | No | null | Maximum number of leads to return |
| `created_at_gt` | string | No | — | Filter by creation date (format: 2023-10-16 10:33:02.000Z) |
| `last_sent_time_gt` | string | No | — | Filter by last send date (format: 2023-10-16 10:33:02.000Z) |
| `event_time_gt` | string | No | `2022-12-23` | Filter by event date (YYYY-MM-DD format) |
| `status` | string | No | null | Lead status filter: STARTED, INPROGRESS, COMPLETED, PAUSED, STOPPED |
| `lead_category_id` | integer | No | null | Associated lead category ID |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads?api_key={API_KEY}&offset={number}&limit={number}
```

---

## Response Examples

### Success Response (200)

```json
{
  "total_leads": 823,
  "offset": 10,
  "limit": 100,
  "data": [
    {
      "campaign_lead_map_id": 23,
      "status": "SENT",
      "created_at": "2022-05-26T03:47:31.448094+00:00",
      "lead": {
        "id": 423,
        "first_name": "Cristiano",
        "last_name": "Ronaldo",
        "email": "cristiano@mufc.com",
        "phone_number": 0239392029,
        "company_name": "Manchester United",
        "website": "mufc.com",
        "location": "London",
        "custom_fields": {
          "Title": "Regional Manager",
          "First_Line": "Loved your recent post about remote work on Linkedin"
        },
        "linkedin_profile": "http://www.linkedin.com/in/cristianoronaldo",
        "company_url": "mufc.com",
        "is_unsubscribed": false
      }
    }
  ]
}
```

### Error Response (400)

```json
{}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_leads` | integer | Total number of leads in campaign |
| `offset` | integer | Current pagination offset |
| `limit` | integer | Current result limit |
| `data` | array | Array of lead objects |
| `campaign_lead_map_id` | integer | Unique mapping ID for lead in campaign |
| `status` | string | Lead status in campaign |
| `created_at` | timestamp | When lead was added to campaign |
| `lead.id` | integer | Lead's unique identifier |
| `lead.first_name` | string | Lead's first name |
| `lead.last_name` | string | Lead's last name |
| `lead.email` | string | Lead's email address |
| `lead.phone_number` | integer | Lead's phone number |
| `lead.company_name` | string | Company name |
| `lead.website` | string | Website URL |
| `lead.location` | string | Geographic location |
| `lead.custom_fields` | object | Additional custom data fields |
| `lead.linkedin_profile` | string | LinkedIn profile URL |
| `lead.company_url` | string | Company URL |
| `lead.is_unsubscribed` | boolean | Unsubscription status |
