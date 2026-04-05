# Spam Test Details

## Overview
Retrieve all configuration data for a spam test that has been created and run. This endpoint provides reference information about test parameters and settings.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/$(spamTestId)`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API authentication key |
| `spamTestId` | integer | Yes | - | The ID of the spam test (returned in POST response when creating test) |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/$(spamTestId)?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
{
  "id": 7527,
  "test_name": "RPT1",
  "test_type": "manual",
  "description": "",
  "folder_id": null,
  "link_checker": true,
  "test_with_sl_account": true,
  "campaign_id": 4924,
  "sequence_mapping_id": 4314,
  "provider_id": [27, 28, 15, 21, 20],
  "client_id": null,
  "user_id": 95,
  "created_at": "2024-12-09T05:23:02.757Z",
  "updated_at": "2024-12-09T06:04:55.170Z",
  "separator": ";",
  "schedule_start_time": null,
  "spam_filters": ["spam_assassin"],
  "min_time_btwn_emails": 10,
  "min_time_unit": "minutes",
  "all_email_sent_without_time_gap": false,
  "status": "COMPLETED",
  "test_end_date": null,
  "sequence_variant_id": null,
  "test_run_no": 0,
  "every_days": null,
  "is_warmup": false
}
```

### Error Response (400)

```json
{
  "message": "\"test_name\" is required"
}
```

---

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique test identifier |
| `test_name` | string | Name assigned to the test |
| `test_type` | string | Type of test: "manual" or "auto" |
| `description` | string | Test description |
| `folder_id` | integer/null | Folder organization ID |
| `link_checker` | boolean | Whether link blacklist checking is enabled |
| `test_with_sl_account` | boolean | Whether using SmartLead mailboxes |
| `campaign_id` | integer | Associated campaign identifier |
| `sequence_mapping_id` | integer | Sequence variant being tested |
| `provider_id` | array | Email provider IDs being tested against |
| `user_id` | integer | Test creator's user ID |
| `created_at` | string | ISO 8601 creation timestamp |
| `updated_at` | string | ISO 8601 last update timestamp |
| `spam_filters` | array | Spam filter systems tested (e.g., "spam_assassin") |
| `min_time_btwn_emails` | integer | Time gap between emails from each mailbox |
| `min_time_unit` | string | Unit for time gap: "minutes", "hours", or "days" |
| `all_email_sent_without_time_gap` | boolean | Whether all emails sent simultaneously |
| `status` | string | Test status: "ACTIVE", "COMPLETED", etc. |
| `is_warmup` | boolean | Whether warmup responses enabled |
