# Save Campaign Sequence API Documentation

## Endpoint Overview

**Title:** Save Campaign Sequence

**Description:** This endpoint saves a sequence within a campaign

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign-id}/sequences`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign-id` | string | Yes | - | The ID of the campaign to save sequence for |

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key |

---

## Request Body Parameters

**Content-Type:** `application/json`

### Sequence Object Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | integer | No | Sequence ID (exclude when creating, include when updating) |
| `seq_number` | integer | Yes | Sequence order number |
| `seq_delay_details.delay_in_days` | integer | Yes | Days to delay before sending |
| `variant_distribution_type` | enum | Conditional | Values: "MANUAL_EQUAL", "MANUAL_PERCENTAGE", "AI_EQUAL" |
| `lead_distribution_percentage` | integer | Conditional | Sample % size for finding winner |
| `winning_metric_property` | enum | Conditional | Values: "OPEN_RATE", "CLICK_RATE", "REPLY_RATE", "POSITIVE_REPLY_RATE" |
| `seq_variants` | array | Conditional | Array of email variants |
| `seq_type` | enum | Conditional | Values: "EMAIL", "MANUAL" |
| `subject` | string | Yes | Email subject line |
| `email_body` | string | Yes | HTML-formatted email content |

### Variant Object Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `subject` | string | Yes | Variant subject line |
| `email_body` | string | Yes | Variant HTML email body |
| `variant_label` | string | Yes | Label identifier (e.g., "A", "B", "C") |
| `id` | integer | No | Variant ID (exclude on create, include on update) |
| `variant_distribution_percentage` | integer | Yes | Percentage distribution for this variant |

---

## Request Example (cURL)

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/sequences?api_key=${API_KEY} \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "sequences": [
      {
        "id": 8494,
        "seq_number": 1,
        "seq_delay_details": {
          "delay_in_days": 1
        },
        "variant_distribution_type": "MANUAL_EQUAL",
        "lead_distribution_percentage": 40,
        "winning_metric_property": "OPEN_RATE",
        "seq_variants": [
          {
            "subject": "Subject",
            "email_body": "<p>Hi<br><br>How are you?</p>",
            "variant_label": "A",
            "id": 2535,
            "variant_distribution_percentage": 20
          },
          {
            "subject": "Email B",
            "email_body": "<p>This is variant B</p>",
            "variant_label": "B",
            "id": 2536,
            "variant_distribution_percentage": 60
          }
        ]
      },
      {
        "id": 8495,
        "seq_number": 2,
        "seq_type": "EMAIL",
        "seq_delay_details": {
          "delay_in_days": 1
        },
        "subject": "",
        "email_body": "<p>Bump up right!</p>"
      }
    ]
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "data": "success"
}
```

### Error Response (404)

```json
{
  "error": "Campaign not found - Invalid campaign_id."
}
```

---

## Notes

- Blank subject lines trigger threaded replies
- Do not include `id` field when creating new sequences
- Include `id` field when updating existing sequences
- Maximum 20 custom fields per lead supported in email body
- HTML formatting supported in `email_body`
