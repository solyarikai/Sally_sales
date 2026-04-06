# References API Documentation

## Overview

The References page serves as a **glossary of key terms** used throughout the SmartLead API documentation. It provides definitions for core concepts required to effectively use the API.

---

## Key Terms Defined

### Campaign
"A campaign refers to an outreach sequence you want to run to a list of leads with certain conditions."

### Lead
"A lead in the API is the same as the lead in your app. They are the recipient of your email / the person you're trying to contact."

### Update
Update operations allow modification of existing campaign or lead data.

### Unsubscribe
"When someone no longer wants to hear from you, they unsubscribe, aka the no more touchy zone."

### Lead Status Values

| Status | Definition |
|--------|-----------|
| **STARTED** | Lead is scheduled to start; yet to receive the 1st email |
| **COMPLETED** | Lead has received all emails in the campaign |
| **BLOCKED** | Email bounced or lead added to global block list |
| **INPROGRESS** | Lead has received at least one email in sequence |
| **PAUSED** | Lead paused; no further mails will be sent |
| **STOPPED** | Lead status stopped; typically indicates reply received |

### Variables Reference

| Variable | Location | Example |
|----------|----------|---------|
| `campaign_id` | Campaign URL path | `1764810` from `https://app.smartlead.ai/app/email-campaign/1764810/analytics?edit=true` |
| `client_id` | Client section URL | `34998` from `https://app.smartlead.ai/app/client-views/34998` |

---

## Note

This is a **reference page only**—no API endpoints are documented here. Refer to specific endpoint sections for request/response examples and implementation details.
