# Search Contacts API Documentation

## Overview

Search for contacts based on various filters such as name, title, company, location, etc.

**HTTP Method:** POST

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-contacts`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

---

## Request Body Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | number | Number of contacts to return (1-500) |

### Optional Filter Parameters

| Parameter | Type | Max Items | Description |
|-----------|------|-----------|-------------|
| `name` | array[string] | 2000 | Filter by full name |
| `firstName` | array[string] | 2000 | Filter by first name |
| `lastName` | array[string] | 2000 | Filter by last name |
| `title` | array[string] | 2000 | Filter by job title |
| `department` | array[string] | 2000 | Filter by department |
| `level` | array[string] | 2000 | Filter by seniority level |
| `companyName` | array[string] | 2000 | Filter by company name |
| `companyDomain` | array[string] | 2000 | Filter by company domain |
| `companyKeyword` | array[string] | 2000 | Filter by company keyword |
| `companyHeadCount` | array[string] | 2000 | Filter by company headcount range |
| `companyRevenue` | array[string] | 2000 | Filter by company revenue |
| `companyIndustry` | array[string] | 2000 | Filter by industry |
| `companySubIndustry` | array[string] | 2000 | Filter by sub-industry |
| `city` | array[string] | 2000 | Filter by city |
| `state` | array[string] | 2000 | Filter by state |
| `country` | array[string] | 2000 | Filter by country |

### Optional Exclusion Parameters

| Parameter | Type | Max Items | Description |
|-----------|------|-----------|-------------|
| `excludeTitle` | array[string] | 2000 | Exclude contacts with these titles |
| `excludeCompany` | array[string] | 2000 | Exclude these companies |
| `excludeCompanyDomain` | array[string] | 2000 | Exclude these company domains |

### Optional Inclusion Parameters

| Parameter | Type | Max Items | Description |
|-----------|------|-----------|-------------|
| `includeTitle` | array[string] | 2000 | Include only these titles |
| `includeCompany` | array[string] | 2000 | Include only these companies |
| `includeCompanyDomain` | array[string] | 2000 | Include only these company domains |

### Optional Matching & Pagination Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `dontDisplayOwnedContact` | boolean | Exclude contacts already owned |
| `titleExactMatch` | boolean | Match title exactly |
| `companyExactMatch` | boolean | Match company exactly |
| `companyDomainExactMatch` | boolean | Match company domain exactly |
| `scroll_id` | string | Pagination scroll ID for next page |

---

## Request Example

```bash
curl -X POST "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-contacts?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": ["CEO", "Founder"],
    "department": ["Sales", "Marketing"],
    "level": ["Director-Level", "Manager-Level"],
    "companyHeadCount": ["51-200", "201-500"],
    "companyIndustry": ["Technology"],
    "country": ["United States"],
    "dontDisplayOwnedContact": true,
    "limit": 50,
    "scroll_id": "",
    "titleExactMatch": false
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Contacts searched successfully",
  "data": {
    "list": [
      {
        "id": "5f22b0e8cff47e0001616f81",
        "firstName": "John",
        "lastName": "Doe",
        "fullName": "John Doe",
        "title": "Director of Sales",
        "company": {
          "name": "Tech Corp",
          "website": "techcorp.com"
        },
        "department": ["Sales"],
        "level": "Director-Level",
        "industry": "Technology",
        "subIndustry": "Software",
        "companyHeadCount": "51-200",
        "companyRevenue": "$10M - 50M",
        "country": "United States",
        "state": "California",
        "city": "San Francisco",
        "email": "john@techcorp.com",
        "linkedin": "linkedin.com/in/johndoe",
        "emailDeliverability": 0.95,
        "address": "San Francisco, California"
      }
    ],
    "scroll_id": "FGluY2x1ZGVfY29udGV4dF91dWlkDXF1ZXJ5...",
    "filter_id": 327105,
    "total_count": 16064669
  }
}
```

### Error Response (400)

```json
{
  "statusCode": 400,
  "code": "FST_ERR_VALIDATION",
  "error": "Bad Request",
  "message": "body/title must NOT have more than 2000 items"
}
```

### Error Response (401)

```json
{
  "statusCode": 401,
  "success": false,
  "message": "Unauthorized",
  "error": "API key is required"
}
```

---

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request status |
| `message` | string | Response message |
| `data.list` | array | Array of contact objects |
| `data.scroll_id` | string | Pagination token for next page |
| `data.filter_id` | number | Filter identifier used |
| `data.total_count` | number | Total matching contacts available |

### Contact Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique contact identifier |
| `firstName` | string | First name |
| `lastName` | string | Last name |
| `fullName` | string | Complete name |
| `title` | string | Job title |
| `company.name` | string | Company name |
| `company.website` | string | Company website |
| `department` | array | Department list |
| `level` | string | Seniority level |
| `industry` | string | Industry classification |
| `subIndustry` | string | Sub-industry classification |
| `companyHeadCount` | string | Employee range |
| `companyRevenue` | string | Revenue range |
| `country` | string | Country |
| `state` | string | State/province |
| `city` | string | City |
| `email` | string | Email address |
| `linkedin` | string | LinkedIn profile URL |
| `emailDeliverability` | number | Deliverability score (0-1) |
