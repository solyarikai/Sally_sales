# Place Order API

## Overview

This API places an order to purchase domain(s) and provision mailbox(es) through a selected Smart Senders vendor, with optional white-label credentials and domain forwarding configuration.

**HTTP Method:** `POST`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/place-order`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key used to authenticate and authorize the request |

## Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `Content-Type` | string | Yes | Must be `application/json` |

## Body Parameters (JSON)

### Root Level

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vendor_id` | integer | Yes | Unique identifier of the vendor with whom the order will be placed |
| `domains` | array | Yes | Array containing domain name and mailbox details |
| `forwarding_domain` | string | Yes | Domain to which purchased domains will forward (e.g., smartlead.ai) |
| `user_details` | object | No | Customer/billing/contact details required by vendor |
| `name` | string | No | Additional name field |

### Domains Array Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain_name` | string | Yes | Domain name to be purchased in this order |
| `mailbox_details` | array | No | List of mailboxes to provision under the domain |

### Mailbox Details Array Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mailbox` | string | Yes | Full mailbox email address to be created/provisioned |
| `first_name` | string | Yes | First name associated with mailbox identity/profile |
| `last_name` | string | Yes | Last name associated with mailbox identity/profile |
| `profile_pic` | string | Yes | Profile picture URL for the mailbox identity |

### User Details Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | No | User's email address for order contact/confirmation |
| `firstName` | string | No | First name for customer profile |
| `lastName` | string | No | Last name for customer profile |
| `company` | string | No | Company/organization name (can be empty string) |
| `country` | string | Yes | ISO country code (non-empty string) |
| `city` | string | Yes | City for billing/registration |
| `addressLineOne` | string | Yes | Primary address line |
| `addressLineTwo` | string | No | Secondary address line (optional) |
| `addressLineThree` | string | No | Additional address line (optional) |
| `postalCode` | string | Yes | ZIP/postal code for billing/registration |
| `state` | string | Yes | State/region for billing/registration |
| `phoneCc` | string | Yes | Phone country calling code |
| `phone` | string | Yes | Phone number without country code |
| `languagePreference` | string | No | Preferred language for vendor communication (e.g., "en") |

---

## Request Example

```bash
curl --location --globoff 'https://smart-senders.smartlead.ai/api/v1/smart-senders/place-order?api_key={api_key}' \
--header 'Content-Type: application/json' \
--data-raw '{
  "vendor_id": 6,
  "forwarding_domain": "example.com",
  "user_details": {
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "company": "Acme Corp",
    "country": "US",
    "city": "New York",
    "addressLineOne": "123 Main Street",
    "addressLineTwo": "Suite 400",
    "addressLineThree": "",
    "postalCode": "10001",
    "state": "NY",
    "phoneCc": "1",
    "phone": "2125551234",
    "languagePreference": "en"
  },
  "domains": [
    {
      "domain_name": "erwerwerwer34rfdvcxgroup.com",
      "mailbox_details": [
        {
          "mailbox": "manjit.singh@erwerwerwer34rfdvcxgroup.com",
          "first_name": "John",
          "last_name": "Doe",
          "profile_pic": "https://example.com/profile.jpg"
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
{
  "status": "success",
  "order_id": "895641"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Result status of order placement request |
| `order_id` | string | Unique order reference ID generated for purchase request |

### Error Response (400)

```json
{
  "status": "error",
  "message": "\"domains[0].domain_name\" must contain a valid domain name",
  "context": "Error creating domain"
}
```

---

## Notes

- All required fields must be provided for successful order placement
- Domain names must be valid format
- The `user_details` object requires minimum address information for vendor processing
- Phone numbers should be provided without country code in the `phone` field
