# Email Accounts UX — Future Implementation Plan

## Date: 2026-04-01

### 1. Pre-load SmartLead accounts on API key connect
- When user connects SmartLead API key via Setup page, immediately paginate ALL accounts
- Cache in DB (table: `smartlead_email_accounts_cache`)
- Refresh on demand or every 24h
- Makes `align_email_accounts` instant instead of 30s pagination

### 2. Email Accounts page in UI (Campaigns section)
- Add "Email Accounts" button/tab on Campaigns page
- Shows ALL SmartLead accounts with search/filter
- Search by name, email, domain
- Save searches as presets (e.g. "Elnar TFP accounts", "Petr Crona accounts")

### 3. Saved account presets → MCP link
- User saves a search preset → gets a link/ID
- In MCP chat: "use preset 'elnar-tfp'" or "take accounts from http://host/campaigns/accounts?preset=elnar-tfp"
- `align_email_accounts` accepts preset_id parameter

### 4. Show email accounts on Campaigns page [Image #114]
- Campaign card shows "14 accounts" but doesn't list them
- Expand campaign card → show all connected email accounts (from_email, from_name)
- Clickable to see full account details

### 5. Account groups
- Group accounts by sender persona (Elnar, Petr, Rinat, etc.)
- Auto-detect from from_name
- MCP: "use all Elnar accounts" → finds group automatically
