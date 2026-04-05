# Geo Wise Report

## Overview

Displays test results sorted by location/region. Shows email performance breakdown across particular regions or countries, useful for geographically-targeted campaigns.

## HTTP Method & URL

```
POST https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/groupwise
```

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spamTestId` | integer (int32) | Yes | The ID of the Spam Test |

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |

---

## Request Example

```bash
curl --location -g --request POST 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/groupwise?api_key=${API_KEY}'
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
      "group_id": 5,
      "group_name": "Italy",
      "region_id": 2,
      "inbox_count": 3,
      "tab_count": 0,
      "spam_count": 0,
      "adjusted_total_email_count": 3
    },
    {
      "group_id": 14,
      "group_name": "France",
      "region_id": 4,
      "inbox_count": 4,
      "tab_count": 0,
      "spam_count": 0,
      "adjusted_total_email_count": 4
    },
    {
      "group_id": 2,
      "group_name": "US Professional",
      "region_id": 1,
      "inbox_count": 3,
      "tab_count": 0,
      "spam_count": 0,
      "adjusted_total_email_count": 3
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
| `overallTotalCount` | integer | Total count of emails across all regions |
| `status` | string | Test status (e.g., COMPLETED) |
| `group_id` | integer | Unique identifier for geographic group |
| `group_name` | string | Name of region or country group |
| `region_id` | integer | Identifier for geographic region |
| `inbox_count` | integer | Emails delivered to inbox |
| `tab_count` | integer | Emails in alternate tabs (e.g., Promotions) |
| `spam_count` | integer | Emails flagged as spam |
| `adjusted_total_email_count` | integer | Total adjusted email count for group |
