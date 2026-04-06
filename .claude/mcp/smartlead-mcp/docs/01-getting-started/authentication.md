# Authentication API Documentation

## Overview

The Authentication endpoint provides instructions for obtaining and using API credentials to authenticate requests with the SmartLead API.

## Getting Started

### Step 1: Activate API Access
Navigate to the settings section on your SmartLead dashboard and click the "Activate API" button.

### Step 2: Obtain API Key
If your plan includes API access, your unique API key will be provided in the settings. **Important**: Do not share this key with anyone, as it serves as your account identity.

### Step 3: Make Authenticated Requests

**API Base URL:**
```
https://server.smartlead.ai/api/v1
```

**Authentication Method:**
Attach your API key as a query string parameter to all requests:
```
?api_key=yourApiKey
```

---

## Request Format

All API requests should follow this pattern:

```
GET/POST/DELETE https://server.smartlead.ai/api/v1/[endpoint]?api_key=yourApiKey
```

---

## Key Points

- The API key is mandatory for all requests
- Include it as a query parameter in the URL
- Treat your API key like a password—keep it confidential
- The API base URL is `https://server.smartlead.ai/api/v1` for all endpoints

---

## Important Notes

- API access depends on your subscription plan
- All subsequent API calls documented in this reference require the API key authentication
- Use the provided key across all campaign management, lead management, email account, and analytics endpoints
