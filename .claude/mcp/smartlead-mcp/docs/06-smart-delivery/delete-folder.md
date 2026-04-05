# Delete Folder

## Overview
Delete a folder used for organizing spam delivery tests.

## Endpoint

**HTTP Method:** DELETE

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/folder/$(folderId)`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folderId` | string | Yes | The unique identifier of the folder to be removed |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your authentication API key |

---

## Request Example

```bash
curl --location -X DELETE \
  'https://smartdelivery.smartlead.ai/api/v1/spam-test/folder/$(folderId)?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
{
  "message": "Folder deleted successfully"
}
```

### Error Response (400)

```json
{
  "message": "Folder not found"
}
```

## Notes

- This endpoint permanently removes a folder and its organization associations
- Ensure the `folderId` exists before attempting deletion
