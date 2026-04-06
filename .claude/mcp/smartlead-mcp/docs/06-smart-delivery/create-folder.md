# Create Folder

## Overview
Create a folder in Smart Delivery to organize spam tests for better management and grouping.

## Endpoint

**HTTP Method:** POST

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/folder`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your authentication API key |

## Request Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folder_name` | string | Yes | Name for the new folder |
| `description` | string | No | Optional folder description |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/folder?api_key=${API_KEY}' \
--header 'Content-Type: application/json' \
--data-raw '{
  "folder_name": "Q4 Email Tests",
  "description": "Folders for Q4 campaign testing"
}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "id": 456,
  "folder_name": "Q4 Email Tests",
  "description": "Folders for Q4 campaign testing",
  "created_at": "2024-12-10T10:30:00.000Z",
  "updated_at": "2024-12-10T10:30:00.000Z",
  "user_id": 95
}
```

### Error Response (400)

```json
{
  "message": "\"folder_name\" is required"
}
```
