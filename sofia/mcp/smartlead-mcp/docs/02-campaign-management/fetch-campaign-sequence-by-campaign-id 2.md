# Fetch Campaign Sequence By Campaign ID

## Endpoint Details

**Description:** This endpoint retrieves the complete sequence configuration and variant details associated with a specific campaign, including all email templates and their variations.

**HTTP Method:** `GET`

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/sequences`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The ID of the campaign for which to retrieve sequence data |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/sequences?api_key=${API_KEY}
```

---

## Response Examples

### Success Response (200)

```json
{
  "id": 8494,
  "created_at": "2022-11-08T07:06:35.990Z",
  "updated_at": "2022-11-08T07:34:03.667Z",
  "email_campaign_id": 3070,
  "seq_number": 1,
  "subject": "",
  "email_body": "",
  "sequence_variants": [
    {
      "id": 2535,
      "created_at": "2022-11-08T07:06:36.002558+00:00",
      "updated_at": "2022-11-08T07:34:04.026626+00:00",
      "is_deleted": false,
      "subject": "Subject",
      "email_body": "<p>Hi<br><br>How are you?</p>",
      "email_campaign_seq_id": 8494,
      "variant_label": "A"
    },
    {
      "id": 2536,
      "created_at": "2022-11-08T07:06:36.002558+00:00",
      "updated_at": "2022-11-08T07:34:04.373866+00:00",
      "is_deleted": false,
      "subject": "Ema a",
      "email_body": "<p>This is a new game a</p>",
      "email_campaign_seq_id": 8494,
      "variant_label": "B"
    },
    {
      "id": 2537,
      "created_at": "2022-11-08T07:06:36.002558+00:00",
      "updated_at": "2022-11-08T07:34:04.721608+00:00",
      "is_deleted": false,
      "subject": "C emsil",
      "email_body": "<p>Hiii C</p>",
      "email_campaign_seq_id": 8494,
      "variant_label": "C"
    }
  ]
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Sequence identifier |
| `created_at` | string | Creation timestamp |
| `updated_at` | string | Last update timestamp |
| `email_campaign_id` | integer | Associated campaign ID |
| `seq_number` | integer | Sequence number |
| `subject` | string | Email subject line |
| `email_body` | string | Email body content |
| `sequence_variants` | array | Array of email variants |
| `sequence_variants[].id` | integer | Variant identifier |
| `sequence_variants[].subject` | string | Variant subject line |
| `sequence_variants[].email_body` | string | Variant email body (HTML) |
| `sequence_variants[].variant_label` | string | Variant label (A, B, C, etc.) |
| `sequence_variants[].is_deleted` | boolean | Deletion status |
