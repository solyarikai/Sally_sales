# Provider Wise Report

## Overview
Displays spam test results organized by email provider, showing how emails performed across specific providers with detailed delivery metrics.

## Endpoint Details

**HTTP Method:** POST

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/providerwise`

---

## Path Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spamTestId` | Integer (int32) | Yes | The ID of the spam test |

## Query Parameters
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | String | Yes | `API_KEY` | Authentication key for API access |

---

## Request Example

```bash
curl --location -g --request POST \
  'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/providerwise?api_key=${API_KEY}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "overallTotalCount": 5,
  "status": "COMPLETED",
  "result": [
    {
      "provider_id": 21,
      "provider_name": "Office365",
      "group_id": 2,
      "region_id": 1,
      "inbox_count": 1,
      "tab_count": 0,
      "spam_count": 0,
      "adjusted_total_email_count": 1
    },
    {
      "provider_id": 27,
      "provider_name": "Outlook (Dev)",
      "group_id": 14,
      "region_id": 4,
      "inbox_count": 4,
      "tab_count": 0,
      "spam_count": 0,
      "adjusted_total_email_count": 4
    }
  ]
}
```

### Error Response (400)

```json
{
  "message": "string"
}
```

---

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `overallTotalCount` | Integer | Total number of providers tested |
| `status` | String | Test completion status (COMPLETED, ACTIVE, etc.) |
| `provider_id` | Integer | Unique identifier for the email provider |
| `provider_name` | String | Display name of the email provider |
| `group_id` | Integer | Classification group within the region |
| `region_id` | Integer | Geographical region or country identifier |
| `inbox_count` | Integer | Number of test emails delivered to inbox |
| `tab_count` | Integer | Emails placed in alternate tabs (Promotions, Updates, etc.) |
| `spam_count` | Integer | Emails marked as spam or junk |
| `adjusted_total_email_count` | Integer | Total adjusted email count for this provider |
