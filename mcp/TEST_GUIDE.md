# MCP Test Guide — Quick Start for New Users

## 1. Access

- **MCP Frontend**: http://46.62.210.24:3000
- **MCP Backend API**: http://46.62.210.24:8002

## 2. Authorization

### In Browser (UI)
1. Go to http://46.62.210.24:3000 → redirected to Setup page
2. **Existing user**: Click **"Log In"** → email + password → done
3. **New user**: Click **"New Account"** → email + name + password → token shown once
4. After login: all pages accessible, token stored in browser

### For MCP (Claude Desktop / Cursor)
- The MCP only needs your **API token** (starts with `mcp_...`)
- Get it from the UI after login (Setup page → your token is shown)
- Paste into Claude Desktop MCP config

## 3. Connect Integrations

After login, on the Setup page connect these services:

| Service | API Key |
|---------|---------|
| **SmartLead** | `eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5` |
| **Apollo** | (same as platform — ask admin) |
| **OpenAI** | (same as platform — ask admin) |

Each key: paste → click Connect → should show green "Connected".

## 4. Test Flow A: Existing Campaigns (pn@getsally.io)

For users who already have SmartLead campaigns.

### Step 1: Login
- Email: `pn@getsally.io`, Password: `qweqweqwe`

### Step 2: Import Campaigns
Tell MCP: "Take 'petr' including campaigns as my EasyStaff-Global project setup"
- System imports contacts as blacklist
- Background reply analysis runs (3-tier: SmartLead → OOO filter → GPT-4o-mini)

### Step 3: Provide Company Context
Tell MCP: "My company website is https://easystaff.io/"
- System scrapes website, extracts offer (payroll/freelance payments)
- Stored in project knowledge for sequence generation

### Step 4: Gathering
Tell MCP: "Find IT consulting companies in Miami"
- Full pipeline: gather → blacklist → analyze → targets

### Step 5: Campaign Creation (DRAFT)
- System generates GOD_SEQUENCE with Gemini 2.5 Pro
- Creates SmartLead campaign as **DRAFT** (never auto-activated)
- Sends test email to your inbox
- Says: "Check your email — tell me to run once ready"

### Step 6: Review & Activate
- Check test email in inbox
- Review sequence in SmartLead
- Tell MCP: "activate the campaign" → only then it starts sending

### Step 7: Intelligence Questions
- "Which leads need follow-ups?" → specific leads with CRM links
- "Which replies are warm?" → filtered list + deep link
- Replies scoped to YOUR campaigns only (~119 for "petr", not 38K)

## 5. Test Flow B: New User (services@getsally.io)

For users with NO existing SmartLead campaigns.

### Step 1: Signup
- Email: `services@getsally.io`, Password: `qweqweqwe`

### Step 2: Provide Company Context
Tell MCP: "My company website is https://thefashionpeople.com/"
- System discovers offer blindly from URL (branded resale platform)

### Step 3: Gathering
Tell MCP: "Find fashion brands in Italy"
- No blacklist (no existing campaigns)
- Full pipeline: gather → analyze → targets

### Step 4: Email Accounts
- MCP asks: "Which email accounts should I use?"
- You select from available SmartLead accounts

### Step 5: Campaign (DRAFT) + Test Email
- GOD_SEQUENCE generated referencing YOUR offer (resale, not generic)
- Campaign created as DRAFT
- Test email sent to services@getsally.io
- "Check your email — tell me to run once ready"

### Step 6: Second Project (OnSocial)
Tell MCP: "I also need to find influencer platforms in UK for https://onsocial.ai/"
- New project created, different offer discovered
- Both projects visible, independent pipelines

## 6. Verification Checklist

- [ ] Unauthorized users redirect to /setup
- [ ] Login with email + password works
- [ ] Signup creates account + shows token
- [ ] All data is USER-SCOPED (only YOUR projects/contacts/replies)
- [ ] Pipeline page shows SmartLead campaign link (purple badge)
- [ ] CRM shows contacts filtered by pipeline (?pipeline=X)
- [ ] Campaign created as DRAFT (never auto-activated)
- [ ] Test email arrives in inbox with GOD_SEQUENCE content
- [ ] Activation requires explicit user confirmation
- [ ] Reply tools scoped to project's campaigns only
- [ ] Blind offer discovery extracts correct value proposition from URL
- [ ] Sequence references actual offer (not generic)
- [ ] Campaign settings match reference (no tracking, 1500/day, AI ESP)
- [ ] User feedback stored and used in next generation

## 7. Test Accounts

| Email | Password | Role |
|-------|----------|------|
| `pn@getsally.io` | `qweqweqwe` | Admin (has "petr" campaigns) |
| `services@getsally.io` | `qweqweqwe` | New user (no campaigns) |

## 8. SmartLead Campaign Links

| Campaign | URL |
|----------|-----|
| EasyStaff - Miami IT Services | https://app.smartlead.ai/app/email-campaigns-v2/3090921/sequences |
| TFP - Fashion Brands Italy | https://app.smartlead.ai/app/email-campaigns-v2/3093035/sequences |
| OnSocial - UK Influencer Platforms | https://app.smartlead.ai/app/email-campaigns-v2/3093040/sequences |

SmartLead login: services@getsally.io / SallySarrh7231

## 9. Ground Truth (for test evaluation only)

Located in `mcp/test_ground_truth/`:
- `offers/easystaff.json` — EasyStaff offer
- `offers/thefashionpeople.json` — The Fashion People offer
- `offers/onsocial.json` — OnSocial offer
- `sequences/reference_3070919.json` — GOD_SEQUENCE structure
- `settings/reference_campaign.json` — SmartLead settings

**RULE**: Ground truth used ONLY for comparing system output vs reality. Never injected into system prompts.
