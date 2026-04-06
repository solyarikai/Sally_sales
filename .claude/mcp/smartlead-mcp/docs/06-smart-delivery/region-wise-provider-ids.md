# Region wise Provider IDs

## Overview
Retrieves a list of all Email Providers available for spam testing, organized by region/country. Provider IDs are required for creating manual or automated tests.

## Endpoint

**Method:** GET
**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/seed/providers`

## Authentication

**Type:** API Key (Query Parameter)
**Parameter Name:** `api_key`
**Required:** Yes

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | Your API Key for authentication |

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/seed/providers?api_key=$(API_KEY)'
```

## Response Examples

### Success Response (200)

```json
[
  {
    "region_id": "4",
    "region_name": "Asia/Pacific",
    "groups": [
      {
        "group_id": "14",
        "group_name": "Dev Env",
        "providers": [
          {
            "provider_id": "27",
            "provider_name": "Outlook (Dev)"
          },
          {
            "provider_id": "28",
            "provider_name": "New Outlook"
          }
        ]
      }
    ]
  },
  {
    "region_id": "2",
    "region_name": "Europe",
    "groups": [
      {
        "group_id": "5",
        "group_name": "Italy",
        "providers": [
          {
            "provider_id": "15",
            "provider_name": "Libero.it"
          }
        ]
      }
    ]
  },
  {
    "region_id": "1",
    "region_name": "North America",
    "groups": [
      {
        "group_id": "2",
        "group_name": "US Professional",
        "providers": [
          {
            "provider_id": "21",
            "provider_name": "Office365"
          },
          {
            "provider_id": "20",
            "provider_name": "G Suite"
          }
        ]
      }
    ]
  }
]
```

### Error Response (400)

```json
{
  "message": "\"api_key\" is required"
}
```

## Response Schema

**Type:** Array of Objects

| Field | Type | Description |
|-------|------|-------------|
| `region_id` | string | Unique identifier for the geographical region |
| `region_name` | string | Name of the region/country |
| `groups` | array | Array of provider groups within the region |
| `groups[].group_id` | string | Identifier for the provider group |
| `groups[].group_name` | string | Name of the group (e.g., country, environment) |
| `groups[].providers` | array | Array of email providers in this group |
| `groups[].providers[].provider_id` | string | Unique provider identifier (used in test creation) |
| `groups[].providers[].provider_name` | string | Display name of the email provider |

## Usage Notes

- Provider IDs returned are required for the "Create a Manual Placement Test" and "Create an Automated Placement Test" endpoints
- Results are organized hierarchically by region -> group -> providers for easy navigation
- This endpoint is read-only and requires no request body
