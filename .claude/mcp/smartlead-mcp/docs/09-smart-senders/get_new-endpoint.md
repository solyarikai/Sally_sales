# Auto Generate Mailboxes

## Overview

This endpoint automatically generates multiple mailbox email addresses for one or more domains based on provided user details.

**HTTP Method:** `POST`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/auto-generate-mailboxes`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key used to authenticate and authorize the request |

## Headers

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | Yes |

## Request Body

**Content-Type:** `application/json`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vendor_id` | string | Yes | Unique identifier of the vendor whose mailbox generation logic will be used |
| `domains` | array | No | List of domains for which mailboxes need to be generated |
| `domains[].domain_name` | string | No | Domain name for which mailboxes will be created |
| `domains[].mailbox_details` | array | No | List of user details used to generate mailbox variations |
| `domains[].mailbox_details[].first_name` | string | No | First name of the user, used to generate mailbox prefixes |
| `domains[].mailbox_details[].last_name` | string | No | Last name of the user, used to generate mailbox prefixes |
| `domains[].mailbox_details[].profile_pic` | string | No | Profile picture URL or identifier associated with the mailbox (optional) |

---

## Request Example

```bash
curl --location --globoff 'https://smart-senders.smartlead.ai/api/v1/smart-senders/auto-generate-mailboxes?api_key={api_key}' \
--header 'Content-Type: application/json' \
--data '{
 "vendor_id": 1,
 "domains": [
   {
     "domain_name": "testdemo.com",
     "mailbox_details": [
       {
         "first_name": "fffffff",
         "last_name": "rrrrrr",
         "profile_pic": "jjjjjj"
       },
       {
         "first_name": "qqqqq",
         "last_name": "www",
         "profile_pic": "pppp"
       }
     ]
   },
   {
     "domain_name": "adsdasasads.com",
     "mailbox_details": [
       {
         "first_name": "Dfgd",
         "last_name": "Xxxxdfgxx",
         "profile_pic": ""
       }
     ]
   }
 ]
}'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "domain_name": "testdemo.com",
    "mailbox_details": [
      {
        "mailbox": "fffffff.rrrrrr@testdemo.com",
        "first_name": "fffffff",
        "last_name": "rrrrrr",
        "profile_pic": "jjjjjj"
      }
    ]
  }
]
```

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `domain_name` | string | Domain name for which mailboxes were generated |
| `mailbox_details` | array | List of generated mailbox email addresses for the domain |
| `mailbox_details[].mailbox` | string | Generated email address based on first name, last name, and domain |
| `mailbox_details[].first_name` | string | First name used to generate the mailbox |
| `mailbox_details[].last_name` | string | Last name used to generate the mailbox |
| `mailbox_details[].profile_pic` | string | Profile picture associated with the mailbox (if provided in request) |
