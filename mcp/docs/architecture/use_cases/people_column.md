# People Column — Requirements

## Current State
- People column shows count of extracted contacts per company
- Only visible when targets exist (has_targets flag)
- No links — just a number or empty

## New Requirements

### 1. CRM Deep Link for Every Company with People
For both **target** and **blacklisted** companies that have contacts:
- Show people count as clickable link
- Link opens CRM filtered to that company's domain: `/crm?domain={domain}`
- User sees which roles/people are gathered for that company

### 2. Blacklisted Companies with People
- Blacklisted companies from imported SmartLead campaigns have contacts
- Show people count + CRM link even for blacklisted rows
- User can review what roles are already contacted

### 3. Blacklist Override (Future)
- User may ask the agent: "I want to reach this blacklisted company with a different offer"
- The agent can override blacklist for specific companies via a new tool
- This is a conscious user decision — not automatic
- Track overrides in audit log

## UI Changes
- People column: always show count when > 0 (regardless of status)
- Count is a link to `/crm?domain={company_domain}`
- For blacklisted: show in muted color with CRM link
- For targets: show in primary color with CRM link
