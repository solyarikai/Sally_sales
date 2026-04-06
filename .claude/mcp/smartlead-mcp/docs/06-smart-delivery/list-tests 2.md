# List all Tests

## Overview

This will provide the list of all the tests. The list will either be all manual tests or all automated tests, based on query param.

## Request Details

**HTTP Method:** POST

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |
| `testType` | string | Yes | `auto` | Filter type: `manual` or `auto` |

## Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | Yes | `10` | Number of tests to retrieve |
| `offset` | integer | Yes | `0` | Pagination offset value |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report?api_key={API_KEY}&testType=auto' \
--data-raw '{
  "limit": 1,
  "offset": 0
}'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "spam_test_id": 7558,
    "test_end_date": "2024-12-15T00:00:00.000Z",
    "every_days": 1,
    "current_test_run_no": 0,
    "schedule_start_time": "2024-12-10T09:30:00.000Z",
    "test_name": "Email Deliverability Test AT 221",
    "test_type": "auto",
    "status": "ACTIVE",
    "created_at": "2024-12-10T09:18:47.424Z",
    "inbox_count": 0,
    "tab_count": 0,
    "spam_count": 0,
    "adjusted_total_email_count": 0
  }
]
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `spam_test_id` | integer | Unique test identifier |
| `test_name` | string | Name of the spam/deliverability test |
| `test_type` | string | Type: `auto` or `manual` |
| `status` | string | Current test status |
| `created_at` | string | Test creation timestamp (ISO 8601) |
| `schedule_start_time` | string | When automated test begins |
| `test_end_date` | string | When automated test concludes |
| `every_days` | integer | Frequency for automated tests |
| `current_test_run_no` | integer | Current run count |
| `inbox_count` | integer | Emails landing in inbox |
| `tab_count` | integer | Emails in secondary tabs |
| `spam_count` | integer | Emails marked as spam |
| `adjusted_total_email_count` | integer | Total adjusted email count |

### Error Response (400)

```json
{}
```

---

**Note:** The `testType` parameter determines which test category displays -- use `manual` for manually created tests or `auto` for scheduled automated tests.
