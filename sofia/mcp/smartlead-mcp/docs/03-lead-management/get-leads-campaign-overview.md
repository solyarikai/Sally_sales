# Get leads- Campaign Overview

## Description
"Get overview of a lead across all the associated campaigns"

## Endpoint
```
GET https://server.smartlead.ai/api/v1/leads/{lead_id}/campaign-overview
```

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| lead_id | string | Yes | - | The target lead identifier |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| api_key | string | Yes | API_KEY | Your API key for authentication |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/leads/{lead_id}/campaign-overview?api_key={API_KEY}
```

## Success Response (200)

```json
{
  "ok": true,
  "message": "Campaign lead overview fetched successfully",
  "data": {
    "id": "1889475",
    "email": "jimmy.conroy@bankwithunited.com",
    "last_name": "Conroy",
    "first_name": "Jimmy",
    "phone_number": null,
    "company_name": null,
    "website": null,
    "company_url": null,
    "location": null,
    "custom_fields": {},
    "linkedin_profile": null,
    "esp_domain_type": 0,
    "email_campaign_leads_mappings": [
      {
        "id": 1773547,
        "status": "COMPLETED",
        "lead_category_id": null,
        "revenue": 17361.51,
        "current_seq_num": 1,
        "next_timestamp_to_reach": null,
        "email_campaign_id": 11004,
        "email_campaign": {
          "id": 11004,
          "name": "ooo",
          "status": "COMPLETED"
        }
      }
    ]
  }
}
```

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| ok | boolean | Success indicator |
| message | string | Descriptive response message |
| data | object | Lead overview data |
| data.id | string | Lead identifier |
| data.email | string | Lead email address |
| data.first_name | string | Lead first name |
| data.last_name | string | Lead last name |
| data.email_campaign_leads_mappings | array | Array of campaign associations |
| data.email_campaign_leads_mappings[].status | string | Lead status in campaign |
| data.email_campaign_leads_mappings[].revenue | number | Associated revenue value |
| data.email_campaign_leads_mappings[].current_seq_num | integer | Current sequence number |
| data.email_campaign_leads_mappings[].email_campaign | object | Campaign details |
