# MCP Onboarding & Pipeline Flow — UX Requirements

Based on the user flow schema. This is the definitive flow from first query to pipeline start.

---

## The Flow

```
USER QUERY                     SYSTEM CHECKS                    SYSTEM ACTIONS
─────────────                  ──────────────                   ──────────────

"Find IT consulting            1. Has account?
 companies in US"              ├── NO → "Sign up first"
                               │         → link to UI /setup
                               │         → or: "what's your email?"
                               │
                               └── YES
                                    │
                               2. Apollo key connected?
                               ├── NO → "I need your Apollo API key
                               │         to search companies"
                               │
                               └── YES
                                    │
                               3. All required filters?
                               ├── segment/industry ✓ (from query)
                               ├── geo/country ✓ (from query)
                               ├── employee min-max? MISSING
                               ├── max pages? MISSING
                               │
                               └── ASK: "What company size?
                                         How many pages (credits)?"

USER: "50-200 employees,
 4 pages max"                  4. SmartLead key connected?
                               ├── NO → "To create campaigns later,
                               │         connect SmartLead. Skip for now?"
                               │
                               └── YES
                                    │
                               5. Existing campaigns?
                               │   "Have you launched campaigns
                               │    before for this segment?"
                               │
                               ├── NO → skip blacklist import
                               │
                               └── YES: "Which campaigns?
                                    How do I identify them?"
                                    │
                                    User provides:
                                    - Campaign names/prefixes
                                    - Tags in SmartLead
                                    - "All campaigns starting with ES Global"
                                    │
                                    ▼
                               6. LOAD EXISTING CAMPAIGNS
                                  → Fetch campaigns from SmartLead API
                                  → Match by rules (prefix/tag/contains)
                                  → Export contacts from matched campaigns
                                  → Load into MCP CRM
                                  → Report: "Found 3 campaigns,
                                    4,200 contacts loaded as blacklist"
                                    │
                                    ▼
                               7. CREATE PROJECT
                                  → Name from context
                                  → ICP from filters
                                  → Sender from user (ask if not given)
                                  → Campaign rules saved
                                  → Blacklist = loaded contacts
                                    │
                                    ▼
                               8. CONFIRM & START
                                  "Ready to gather:
                                   - Project: EasyStaff Global - US IT
                                   - Filters: IT consulting, US, 50-200 emp
                                   - Apollo: 4 pages, ~100 companies, ~4 credits
                                   - Blacklist: 4,200 contacts from 3 campaigns
                                   - SmartLead: connected

                                   Start gathering?"
                                    │
                                    ▼
                               9. PIPELINE RUNS
                                  gather → blacklist → CP1 → filter →
                                  scrape → analyze → CP2 → verify →
                                  CP3 → campaign creation
```

---

## Step-by-Step Requirements

### Step 1: Account Check

When user sends first message:
- Call `check_integrations` (will fail with "Missing API token" if no account)
- If no account: ask for email + name, call `setup_account`
- Show: "Save your token: mcp_xxx... You won't see it again."
- Link: http://46.62.210.24:3000/setup

### Step 2: Apollo Key Check

Before any gathering:
- Check if Apollo is connected via `check_integrations`
- If not: "I need your Apollo API key to search companies. Paste it here or add it at http://46.62.210.24:3000/setup"
- Call `configure_integration` with the key
- Show result: "Apollo connected" or "Invalid key"

### Step 3: Essential Filters

Parse the user's natural language query. Extract what's there, ask for what's missing:

| Filter | Required? | Example from query |
|--------|-----------|-------------------|
| Industry/keywords | YES | "IT consulting" → `["IT consulting"]` |
| Country/geo | YES | "in US" → `["United States"]` |
| Employee range | YES — ASK if missing | "50-200" → `["51,200"]` |
| Max pages | YES — ASK if missing | "4 pages" → `4` |
| Funding stage | Optional — suggest | Not mentioned → skip |

If anything required is missing, ask. Don't guess. Don't use defaults silently.

### Step 4: SmartLead Key Check

- Check if SmartLead is connected
- If not: "To create campaigns and track blacklists, connect SmartLead. Want to add it now or skip?"
- If user skips: proceed without campaign creation capability (gathering still works)

### Step 5: Existing Campaigns (BLACKLIST)

**This is the critical step.** If SmartLead is connected:

Ask: "Have you already launched campaigns for this type of companies? I need to know so I don't gather contacts you already have."

User might say:
- "No, this is new" → skip blacklist import
- "Yes, campaigns starting with 'ES Global'" → use prefix rule
- "Yes, tagged with 'easystaff-global'" → use tag rule
- "Yes, these specific campaigns: [list]" → use exact match

### Step 6: Load Existing Campaigns

New MCP tools needed:

#### `import_smartlead_campaigns`
```
Input: { project_id: 1, rules: { contains: ["Petr"] } }
```

**CRITICAL: This tool DOWNLOADS actual contacts from SmartLead, not just campaign names.**

Flow:
1. Fetch ALL campaigns from SmartLead API
2. Match against rules (prefix/contains/exact)
3. **For each matched campaign:**
   - **Call `/campaigns/{id}/leads-export`** → CSV with ALL leads
   - Parse: email, first_name, last_name, company_name
   - Extract domain from email (e.g. `john@acme.com` → `acme.com`)
   - **Save each contact** in `extracted_contacts` (visible in CRM)
   - **Create blacklisted DiscoveredCompany** for each domain (`is_blacklisted=True`)
4. Save campaign names on project

**After import, `tam_blacklist_check` uses these domains:**
- New Apollo companies → check domain against blacklisted domains
- Match → rejected ("existing_campaign_contact")
- This prevents gathering companies the user already contacts

#### `list_smartlead_campaigns`
```
Input: { search: "easystaff" }  // optional filter
```
- Fetch campaigns from SmartLead API
- Return list with: name, lead count, status, created date
- Helps user identify which campaigns are relevant

### Step 7: Create Project

Auto-create from gathered context:
```json
{
  "name": "EasyStaff Global - US IT",          // from conversation
  "target_segments": "US IT consulting, 50-200 emp",  // from filters
  "target_industries": "IT consulting, software development",
  "sender_name": "Marina Mikhaylova",          // ASK if not provided
  "sender_company": "easystaff.io",            // ASK if not provided
  "campaign_rules": {                           // from step 5
    "prefixes": ["ES Global"],
    "tags": [],
    "contains": []
  }
}
```

### Step 8: Confirm & Start

Show summary before starting:
```
Ready to gather:
  Project: EasyStaff Global - US IT
  Filters: IT consulting, United States, 50-200 employees
  Apollo: 4 pages × 25 = ~100 companies, ~4 credits
  Blacklist: 4,200 contacts from 3 SmartLead campaigns
  SmartLead: connected (for campaign creation later)

  → http://46.62.210.24:3000/pipeline/{runId}

  Start gathering?
```

Only proceed when user says yes.

### Step 9: Pipeline

Standard flow: gather → blacklist (checks against loaded contacts) → checkpoints → analyze → campaign

---

## Project Page UI

When a project is created with campaign rules, the project page shows:

### Campaign Rules Section
- How campaigns are detected: prefixes, tags, contains rules
- List of matched campaigns with lead counts
- "Refresh campaigns" button to re-scan SmartLead
- Same UX as main app's project setup page

### CRM Section
- Contact count loaded from SmartLead campaigns
- Link to CRM filtered by this project: `/crm?project={id}`
- "These contacts are your blacklist for new gatherings"

---

## New MCP Tools Needed

| Tool | Purpose |
|------|---------|
| `list_smartlead_campaigns` | Browse user's SmartLead campaigns (search, filter) |
| `import_smartlead_campaigns` | Load contacts from matched campaigns into MCP CRM |
| `set_campaign_rules` | Save campaign detection rules on a project |

---

## What This Changes in Current Flow

1. **Before gathering, always check for existing campaigns** — don't just gather and blacklist later
2. **Blacklist is built BEFORE gathering** — by importing SmartLead contacts
3. **Project creation includes campaign rules** — not just ICP
4. **CRM gets populated before pipeline** — with existing contacts from SmartLead
5. **The confirmation step is richer** — shows blacklist size, campaign count, credit estimate

---

## Does This Make Sense? Analysis.

The schema flow is logical and correct. Here's what it gets right:

1. **Account → API keys → Filters → Blacklist → Gather** — this is the right order
2. **SmartLead before gathering** — you need the blacklist BEFORE searching, not after
3. **Campaign rules are flexible** — prefix/tag/contains covers all real patterns
4. **User confirms before spending credits** — both for Apollo and for scope

What I'd add:

1. **"Quick start" path** — if user has no campaigns, skip steps 5-6 entirely. Don't make them answer questions about campaigns they don't have.
2. **Campaign auto-detection** — if SmartLead is connected, automatically list campaigns and suggest matches based on the project name. "I see 47 campaigns. 3 start with 'ES Global' — are these relevant?"
3. **Incremental blacklist** — after the first pipeline run, future runs automatically include all gathered contacts in the blacklist. No manual import needed.
4. **Reply tracking setup** — once a SmartLead campaign is created and contacts added (by user), the system should start tracking replies. This is the "SmartLead campaign setup and reply tracking enabled" box in the schema.
