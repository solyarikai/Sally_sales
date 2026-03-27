# MCP Test Guide — Quick Start for New Users

## 1. Access

- **MCP Frontend**: http://46.62.210.24:3000
- **MCP Backend**: http://46.62.210.24:8002

## 2. Create Account

Go to http://46.62.210.24:3000/setup → "New Account"

| Field | Value |
|-------|-------|
| Email | `petru4o144@gmail.com` (or your email) |
| Name | Your name |
| Password | `qweqweqwe` |

Click "Create Account" → you'll get an API token. Save it.

## 3. Connect Integrations

On the Setup page, connect these services using the shared API keys:

| Service | API Key |
|---------|---------|
| **SmartLead** | `eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5` |
| **Apollo** | (same as platform — ask admin) |
| **OpenAI** | (same as platform — ask admin) |

Each key: paste → click Connect → should show green "Connected".

## 4. Test Flow A: New User (No Existing Campaigns)

This flow is for users who don't have SmartLead campaigns yet.

### Step 1: Create Project
Tell the MCP: "I want to find fashion brands in Italy for EasyStaff outreach"

### Step 2: Gathering
The system will:
- Search Apollo for Italian fashion companies
- Scrape websites
- Analyze with GPT-4o-mini (via negativa)
- Show you targets at Checkpoint 2

### Step 3: Campaign Creation
After approving targets:
- System generates GOD_SEQUENCE (Gemini 2.5 Pro)
- Creates SmartLead campaign with proper settings
- Uploads verified contacts
- Sends test email to your address

### Step 4: Verify
- Check SmartLead for the campaign
- Check your inbox for the test email
- Pipeline page shows SmartLead link (purple badge)

## 5. Test Flow B: Existing Campaigns (e.g., pn@getsally.io)

This flow is for users who already have SmartLead campaigns.

### Step 1: Import Campaigns
Tell the MCP: "Take 'petr' including campaigns as my EasyStaff-Global project setup"

### Step 2: Reply Analysis
System automatically:
- Imports contacts from matching campaigns as blacklist
- Runs background reply analysis (3-tier: SmartLead → OOO filter → GPT-4o-mini)

### Step 3: Intelligence Questions
Ask:
- "Which leads need follow-ups?" → returns leads from YOUR campaigns only
- "Which replies are warm?" → returns interested/meeting leads with CRM link
- "Show me a CRM link for warm replies" → clickable deep link

### Step 4: New Gathering
Tell the MCP: "Find IT consulting companies in Miami"
→ Full pipeline: gather → blacklist → analyze → campaign creation

## 6. What to Check

- [ ] All data is USER-SCOPED (you only see YOUR projects and campaigns)
- [ ] Pipeline page shows SmartLead link after campaign creation
- [ ] CRM shows contacts filtered by pipeline
- [ ] Reply tools only show replies from YOUR campaigns
- [ ] Test email arrives in your inbox
- [ ] Campaign settings match reference (no tracking, 1500 leads/day, AI ESP matching)

## 7. Test Accounts

| Email | Password | Role |
|-------|----------|------|
| `pn@getsally.io` | `qweqweqwe` | Admin (has "petr" campaigns) |
| `petru4o144@gmail.com` | `qweqweqwe` | New user (no campaigns) |
