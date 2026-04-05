# Delete Smart Delivery Tests in Bulk

## Overview

This API endpoint allows you to delete multiple Smart Delivery spam tests at once using their test IDs.

## Endpoint Details

**HTTP Method:** `POST`

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/delete`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |

---

## Request Body

**Content-Type:** `application/json`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestIds` | array (integer) | Yes | List of test IDs to be deleted |

```json
{
  "spamTestIds": [151]
}
```

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/delete?api_key=${API_KEY}' \
--data '{
  "spamTestIds": [151]
}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "message": "Tests deleted successfully"
}
```

### Error Response (400)

```json
{
  "message": "Test not belongs to user"
}
```

## Error Scenarios

- **Invalid Test ID:** Returns error if the spam test ID does not exist
- **Unauthorized Access:** Returns error if the test does not belong to the authenticated user
- **Missing Parameters:** Returns error if required parameters are not provided
