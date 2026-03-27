# Schedule History for Automated Tests

## Overview

This will provide the list and summary of all the tests that ran for a particular Automated Test.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/schedule-history`

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
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/schedule-history?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

Returns schedule history data for the automated test including list and summary of all test runs.

### Error Response (400)

```json
{}
```

## Notes

- This endpoint is specifically for automated tests
- The `spamTestId` parameter must be obtained from the test creation response
