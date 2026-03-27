# Save Search API Documentation

## Overview

Saves a search filter for the authenticated user.

**HTTP Method:** POST

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/save-search`

---

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

## Request Body (JSON)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `search_string` | string | Yes | Human-readable name for the saved search |
| `name` | array[string] | No | Contact names |
| `firstName` | array[string] | No | First names |
| `lastName` | array[string] | No | Last names |
| `title` | array[string] | No | Job titles |
| `excludeTitle` | array[string] | No | Titles to exclude |
| `includeTitle` | array[string] | No | Titles to include |
| `excludeCompany` | array[string] | No | Companies to exclude |
| `excludeCompanyDomain` | array[string] | No | Company domains to exclude |
| `includeCompany` | array[string] | No | Companies to include |
| `includeCompanyDomain` | array[string] | No | Company domains to include |
| `department` | array[string] | No | Departments |
| `level` | array[string] | No | Professional levels |
| `companyName` | array[string] | No | Company names |
| `companyDomain` | array[string] | No | Company domains |
| `companyKeyword` | array[string] | No | Company keywords |
| `companyHeadCount` | array[string] | No | Company employee counts |
| `companyRevenue` | array[string] | No | Company revenue ranges |
| `companyIndustry` | array[string] | No | Industries |
| `companySubIndustry` | array[string] | No | Sub-industries |
| `city` | array[string] | No | Cities |
| `state` | array[string] | No | States/Provinces |
| `country` | array[string] | No | Countries |
| `dontDisplayOwnedContact` | boolean | No | Exclude owned contacts |
| `limit` | number | No | Result limit (1-10000) |
| `titleExactMatch` | boolean | No | Match title exactly |
| `companyExactMatch` | boolean | No | Match company name exactly |
| `companyDomainExactMatch` | boolean | No | Match company domain exactly |

---

## Request Example

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-filters/save-search?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "search_string": "Directors in United States",
    "title": ["Director", "VP"],
    "country": ["United States"],
    "limit": 100
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Search saved successfully"
}
```

### Error Response (401)

```json
{
  "statusCode": 401,
  "success": false,
  "message": "Unauthorized",
  "error": "User not authenticated"
}
```
