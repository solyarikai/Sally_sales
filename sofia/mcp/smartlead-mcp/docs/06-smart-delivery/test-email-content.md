# Test Email Content

## Overview
Retrieve detailed email content information from spam tests, including raw and HTML formats, along with associated campaign and sequence details.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/email-content`

---

## Path Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spamTestId` | Integer | Yes | The ID of the spam test |

## Query Parameters
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | String | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/email-content?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
{
  "email_content": {
    "subject": "email subject",
    "from": "sender@domain.com",
    "raw_content": "raw email body",
    "html_content": "<html>email body</html>",
    "campaign_id": 4957,
    "sequence_mapping_id": 4347,
    "email_track_id": "unique-tracking-id"
  }
}
```

### Error Response (400)

```json
{
  "message": "error description"
}
```
