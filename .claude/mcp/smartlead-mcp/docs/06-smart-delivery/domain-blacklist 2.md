# Domain Blacklist

## Overview
Retrieves the list of all blacklisted domains found within email content from a completed spam test.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/{spam_test_id}/domain-blacklist`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spam_test_id` | integer | Yes | The unique identifier of the spam test |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/{spam_test_id}/domain-blacklist?api_key=${API_KEY}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "domain": "example.com",
  "totalBlacklist": 5,
  "totalTestedOk": 210,
  "totalTests": 222,
  "totalTimedOut": 7
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `domain` | string | The domain name that was tested |
| `totalBlacklist` | integer | Count of blacklist hits for this domain |
| `totalTestedOk` | integer | Number of successful tests performed |
| `totalTests` | integer | Total tests conducted against this domain |
| `totalTimedOut` | integer | Number of tests that timed out |

### Error Response (400)

```json
{
  "message": "Error description"
}
```

## Notes

- The `link_checker` option must be enabled when creating the spam test to generate domain blacklist data
