# Export Data from a Campaign

## Overview

**Description:** This endpoint returns a CSV file containing all leads from a campaign using the campaign's ID.

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads-export`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The ID of the campaign you want to fetch data from |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads-export?api_key={API_KEY}
```

---

## Response

### Success Response (200)

**Content-Type:** `text/plain`

The endpoint returns CSV data with the following columns:

```
id - integer
campaign_lead_map_id - integer
status - text
created_at - timestamp with time zone
first_name - text
last_name - text
email - text
phone_number - text
company_name - text
website - text
location - text
custom_fields - jsonb
linkedin_profile - text
company_url - text
is_unsubscribed - boolean
last_email_sequence_sent - integer
is_interested - boolean
open_count - integer
click_count - integer
reply_count - integer
```

### Error Response (400)

```json
{}
```

---

## Notes

- Data is returned in CSV format for easy import/export functionality
- Ensure the `campaign_id` parameter is valid; invalid IDs will result in errors
