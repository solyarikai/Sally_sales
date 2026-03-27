# Fetch All Leads From Entire Account

## Overview

This endpoint retrieves all leads within your entire account with optional filtering and pagination capabilities.

**Description:** "This endpoint fetches all the leads in your account."

## Request Details

**HTTP Method:** `GET`

**Base URL:** `https://server.smartlead.ai/api/v1/leads`

**Full URL:** `https://server.smartlead.ai/api/v1/leads/global-leads`

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |
| `offset` | string | No | — | Pagination offset value |
| `limit` | string | No | `1` | Number of leads per request (maximum 100) |
| `created_at_gt` | string | No | `2022-12-23` | Filter by creation date in YYYY-MM-DD format |
| `email` | string | No | — | Filter results by specific email address |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/leads/global-leads?api_key={API_KEY}&limit=21&offset=1&created_at_gt=2024-03-01&email=email@email.com
```

## Response Examples

### Success Response (200)

```json
{
  "data": [
    {
      "id": "459608381",
      "email": "vijaykz@aol.com",
      "first_name": "Vijay",
      "last_name": "k",
      "company_name": "Smartlead",
      "website": "www.smartlead.ai",
      "company_url": null,
      "phone_number": "9042143923",
      "location": null,
      "custom_fields": {},
      "linkedin_profile": null,
      "created_at": "2024-03-07T09:25:00.759Z",
      "user_id": 288,
      "campaigns": [
        {
          "campaign_id": 261647,
          "lead_status": "COMPLETED",
          "campaign_name": "Test",
          "lead_added_at": "2024-03-07T09:25:00+00:00",
          "campaign_status": "COMPLETED",
          "email_lead_map_id": 373245373,
          "lead_last_seq_number": 1,
          "latest_sent_time": "2024-04-07T09:25:00.759Z"
        }
      ]
    }
  ],
  "skip": 1,
  "limit": 1,
  "hasMore": true
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `data` | array | Array of lead objects |
| `data[].id` | string | Unique lead identifier |
| `data[].email` | string | Lead email address |
| `data[].first_name` | string | Lead first name |
| `data[].last_name` | string | Lead last name |
| `data[].company_name` | string | Associated company name |
| `data[].website` | string | Company website URL |
| `data[].phone_number` | string | Lead phone number |
| `data[].created_at` | string | Lead creation timestamp |
| `data[].user_id` | integer | Account user identifier |
| `data[].campaigns` | array | Campaigns associated with lead |
| `data[].campaigns[].campaign_id` | integer | Campaign identifier |
| `data[].campaigns[].lead_status` | string | Status in campaign (e.g., COMPLETED) |
| `data[].campaigns[].campaign_name` | string | Name of the campaign |
| `skip` | integer | Offset value used in request |
| `limit` | integer | Limit value used in request |
| `hasMore` | boolean | Indicates if additional results exist |
