# Get All Folders

## Overview

Gets the list and details of all the folders created inside Smart Delivery. It will also show all the tests inside the folder.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/folder`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API Key for authentication |
| `limit` | integer | Yes | - | Number of folders to retrieve per request |
| `offset` | integer | Yes | - | Pagination offset for results |
| `name` | string | No | - | Filter folders by name |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/folder?api_key=$(API_KEY)&limit=10&offset=0&name=foldername'
```

---

## Response Examples

### Success Response (200)

Returns an array of folder objects with associated tests and metadata.

### Error Response (400)

Standard error response with message field indicating validation or processing issues.
