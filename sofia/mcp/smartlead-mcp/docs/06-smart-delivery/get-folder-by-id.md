# Get Folder by ID

## Overview
Retrieve folder information using a specific folder ID from the Smart Delivery API.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/folder/$(folderId)`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folderId` | string | Yes | The unique identifier of the folder to retrieve |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/folder/$(folderId)?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
{
  "id": "folder_id_value",
  "name": "folder_name",
  "created_at": "2024-12-01T10:30:00.000Z",
  "updated_at": "2024-12-01T10:30:00.000Z",
  "test_count": 5
}
```

### Error Response (400)

```json
{
  "message": "Folder not found or invalid folder ID"
}
```
