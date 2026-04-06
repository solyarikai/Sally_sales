# Add Leads to a Campaign by ID

## Overview
This endpoint adds leads to a campaign using the campaign's ID. Maximum 100 leads can be added per request.

## API Details

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The campaign ID to add leads to |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Body

**Content-Type:** `application/json`

### Main Parameters

| Field | Type | Description |
|-------|------|-------------|
| `lead_list` | array | Array of JSON objects (max 100 leads). Each object represents a lead's details |
| `settings` | object | Optional configuration settings for lead import behavior |

### Lead Object Structure

```json
{
  "first_name": "string",
  "last_name": "string",
  "email": "string (required)",
  "phone_number": "integer",
  "company_name": "string",
  "website": "string",
  "location": "string",
  "linkedin_profile": "string",
  "company_url": "string",
  "custom_fields": "object (max 20 fields)"
}
```

### Settings Object (Optional)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ignore_global_block_list` | boolean | false | Bypass global block list check |
| `ignore_unsubscribe_list` | boolean | false | Skip unsubscribe list comparison |
| `ignore_community_bounce_list` | boolean | false | Bypass community bounce list check |
| `ignore_duplicate_leads_in_other_campaign` | boolean | false | Skip duplicate check across campaigns |
| `return_lead_ids` | boolean | false | Include email-to-lead ID mapping in response |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads?api_key={API_KEY} \
  --data '{
    "lead_list": [
      {
        "first_name": "Cristiano",
        "last_name": "Ronaldo",
        "email": "cristiano@mufc.com",
        "phone_number": 239392029,
        "company_name": "Manchester United",
        "website": "mufc.com",
        "location": "London",
        "linkedin_profile": "http://www.linkedin.com/in/cristianoronaldo",
        "company_url": "mufc.com",
        "custom_fields": {
          "Title": "Regional Manager",
          "First_Line": "Loved your recent post about remote work on Linkedin"
        }
      }
    ],
    "settings": {
      "ignore_global_block_list": true,
      "return_lead_ids": true
    }
  }'
```

---

## Response Examples

### Success Response (200 OK)

```json
{
  "ok": true,
  "upload_count": 240,
  "total_leads": 400,
  "already_added_to_campaign": 200,
  "duplicate_count": 150,
  "invalid_email_count": 40,
  "unsubscribed_leads": 10,
  "is_lead_limit_exhausted": false,
  "lead_import_stopped_count": 0,
  "emailToLeadIdMap": {
    "newlyAddedLeads": {
      "john.doe@example.com": "2340838746"
    },
    "existingLeads": {
      "jane.smith@example.com": "2340432189"
    },
    "existingLeadsInOtherCampaigns": {
      "abc@something.com": "12312312"
    }
  }
}
```

### Error Response - Lead Limit Exhausted

```json
{
  "ok": false,
  "is_lead_limit_exhausted": true,
  "lead_import_stopped_count": 1,
  "error": "The lead credit limit has been reached, preventing any further lead imports."
}
```

---

## Response Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Request success indicator |
| `upload_count` | integer | Number of leads successfully uploaded |
| `total_leads` | integer | Total leads in the request |
| `already_added_to_campaign` | integer | Leads already existing in campaign |
| `duplicate_count` | integer | Duplicate email addresses detected |
| `invalid_email_count` | integer | Invalid email format count |
| `unsubscribed_leads` | integer | Leads on unsubscribe list |
| `is_lead_limit_exhausted` | boolean | Account lead limit reached |
| `lead_import_stopped_count` | integer | Count of stopped imports |
| `error` | string | Error message if applicable |
| `emailToLeadIdMap` | object | Mapping of emails to lead IDs (if `return_lead_ids` enabled) |
