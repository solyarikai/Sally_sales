# MCP LeadGen — Complete Claude Code Guide

The definitive guide for using MCP via Claude Code CLI. Covers setup, API keys, real usage examples, and the full pipeline from first message to sent campaign.

## 1. One-Time Setup (30 seconds)

```bash
# Add MCP server
claude mcp add leadgen --transport sse http://46.62.210.24:8002/mcp/sse

# Verify
claude mcp list
# Should show: leadgen (sse) — http://46.62.210.24:8002/mcp/sse

# Create a project directory with CLAUDE.md
mkdir ~/leadgen && cd ~/leadgen
cat > CLAUDE.md << 'EOF'
# LeadGen MCP Operator

You are a lead generation assistant. Use the **leadgen** MCP tools for everything.

Rules:
- Set up account first (setup_account), then connect integrations
- Always confirm project context before pipeline work
- Never skip pipeline checkpoints — show results and wait for approval
- Campaigns are always created as DRAFT — never auto-activate
- Share UI links: http://46.62.210.24:3000/pipeline/{runId}
- After campaign creation, test email is sent automatically to user's email
EOF

# Start Claude Code from this directory
claude
```

## 2. Required API Keys

These keys are needed for the full pipeline. Connect them via `configure_integration` tool after account creation.

| Service | Key | What It Does |
|---------|-----|-------------|
| **SmartLead** | `eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5` | Campaign management, email sending, lead import |
| **Apollo** | Same as main platform (ask admin) | Company search (1 credit/page of 100), org enrichment (1 credit/company) |
| **OpenAI** | Same as main platform (ask admin) | GPT-4o-mini for analysis ($0.003/company), filter generation, sequence writing |

Optional:
| Service | What It Does |
|---------|-------------|
| **FindyMail** | Email verification ($0.01/email) — only at Checkpoint 3 |
| **Gemini** | Alternative model for sequence generation |

## 3. First Session — Account + Integrations

Just talk naturally. No need to mention tool names.

```
You: Set up my account as Petr, pn@getsally.io

Claude: Account created! Your API token: mcp_250f8ab8...
        Save this token — it won't be shown again.

You: Connect SmartLead with key eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5

Claude: SmartLead connected. Found 47 campaigns.

You: Connect Apollo with key 9yIx...

Claude: Apollo connected. Ready for company search.

You: Connect OpenAI with key sk-...

Claude: OpenAI connected. GPT-4o-mini ready for analysis.
```

## 4. Flow A — New User (No Existing Campaigns)

### Step 1: Create Project (REQUIRES company website or offer description)

```
You: I want to find IT consulting companies in Dubai for EasyStaff outreach.
     Our website is easystaff.io

Claude: [scrapes easystaff.io to understand the offer]
        Creating project "EasyStaff - Dubai IT"
        ICP: IT consulting/services companies in Dubai, 50-500 employees
        Sender: [asks for sender name/position]

You: Sender is Rinat Karimov, BDM at Easystaff

Claude: Project created (ID: 5). Ready to start gathering.
```

**CRITICAL**: The `create_project` tool requires a website or offer description. Without it, sequences will be generic garbage. Claude will scrape the website to extract value proposition.

### Step 2: Gathering Pipeline

```
You: Find IT outsourcing companies in Dubai

Claude: Starting filter discovery...
        [Probe: 100 companies from Apollo — 1 credit]
        [Scrapes 10 websites to verify quality]

        Probe results — 15 companies with website excerpts:
        1. Techmind (techmind.ae) — "IT outsourcing for enterprises..."
        2. CloudBridge (cloudbridge.ae) — "Managed cloud services..."
        ...

        These look like the right kind of companies. Proceeding to gather.

        [Enriches top 5 for keyword taxonomy — 5 credits]
        Refined filters: keywords=["IT outsourcing", "managed services", ...]

        Gathering: 400 companies across 4 pages (4 credits)
        → CHECKPOINT 1: Scope review

        Project: EasyStaff - Dubai IT (ID: 5)
        Companies gathered: 387 new, 13 duplicates
        Blacklist check: 12 rejected (overlap with existing campaigns)

        Proceed?

You: Yes

Claude: [Scraping 375 websites...]
        [GPT-4o-mini analyzing via negativa — $0.003/company]

        → CHECKPOINT 2: Target review

        TARGETS: 89 companies (24% target rate, avg confidence 0.78)
        Segments: IT_OUTSOURCING(45), MANAGED_SERVICES(22), SAAS_COMPANY(15), AGENCY(7)

        Top targets:
        - techmind.ae (0.92) IT_OUTSOURCING — "Full-stack IT outsourcing..."
        - cloudbridge.ae (0.88) MANAGED_SERVICES — "Cloud infrastructure..."
        ...

        Borderline rejections (0.4-0.6):
        - designstudio.ae (0.55) — "Web design only, no IT services"

        Review the target list. Remove false positives?

You: Looks good, proceed

Claude: → CHECKPOINT 3: FindyMail cost
        89 target companies × ~3 contacts each = ~267 emails
        Estimated cost: $2.67

        Approve?

You: Yes

Claude: [Verifying emails via FindyMail...]
        Verified: 201 emails (75% hit rate)

        Ready to create campaign. Generate sequences?

You: Yes

Claude: [Generating 5-step sequence via GPT-4o-mini]
        Campaign: "EasyStaff - Dubai IT Outsourcing"
        5 emails, 3-5 day intervals, plain text, no tracking

        [Creating in SmartLead...]
        [Assigning 26 email accounts]
        [Setting schedule: Mon-Fri 9:00-18:00 Asia/Dubai]

        Campaign created! Test email sent to pn@getsally.io — check your inbox.

        SmartLead: https://app.smartlead.ai/app/email-campaigns-v2/3091234/analytics
        Pipeline: http://46.62.210.24:3000/pipeline/15
```

### Step 3: Review Test Email

Check inbox for the test email. If the copy needs changes:
```
You: Send me step 2 of the sequence as test

Claude: [send_test_email(campaign_id=3091234, sequence_number=2)]
        Test email for step 2 sent to pn@getsally.io
```

## 5. Flow B — Existing SmartLead Campaigns

For users who already have campaigns running and want to import them as blacklist + check replies.

```
You: Import my existing SmartLead campaigns for EasyStaff project

Claude: Found 47 campaigns. Which ones match this project?
        - "ES Global - AU IT Consulting" (234 leads)
        - "ES Global - US SaaS" (567 leads)
        - "ES Global - DACH Tech" (189 leads)
        ...

You: All "ES Global" ones

Claude: Importing 12 campaigns, 2,847 contacts as blacklist...
        [Background: analyzing replies via 3-tier classification]

        Import complete:
        - 2,847 contacts imported (blacklist for future gathering)
        - 45 replies detected
        - Categories: 12 interested, 8 meetings, 15 questions, 10 not interested

        CRM: http://46.62.210.24:3000/crm?project_id=5

You: Show me warm replies

Claude: [replies_list(category="interested", project_name="EasyStaff - Dubai IT")]

        12 warm replies:
        1. John Smith (john@techcorp.ae) — "Sounds interesting, let's schedule a call"
        2. ...

        Open in browser: http://46.62.210.24:3000/tasks?project=EasyStaff+-+Dubai+IT&tab=interested
```

## 6. Pipeline Stages & Credits

| Stage | What Happens | Cost |
|-------|-------------|------|
| **Filter Discovery** | Probe search + website scraping + enrichment | 1-8 Apollo credits |
| **Gather** | Apollo search, 100 companies per page | 1 credit/page |
| **Blacklist** | Cross-check with imported campaigns | Free |
| **Scrape** | Website scraping via httpx + Apify proxy | Free |
| **Analyze** | GPT-4o-mini via negativa + segment labeling | ~$0.003/company |
| **Verify** | FindyMail email verification | $0.01/email |
| **Campaign** | SmartLead campaign creation + sequence | Free |
| **Test Email** | SmartLead native send-test-email API | Free |

## 7. MCP Tools Quick Reference

### Account & Setup (4)
- `setup_account` — create account (email, name)
- `configure_integration` — connect API keys (smartlead, apollo, openai, findymail, gemini)
- `check_integrations` — status of all connected services
- `set_active_project` — switch project context

### Project (2)
- `create_project` — new project (REQUIRES website or offer description)
- `list_projects` — show all user's projects

### Pipeline (10)
- `suggest_apollo_filters` — probe + scrape + evaluate filters (agent reviews)
- `tam_gather` — start gathering run
- `tam_blacklist` — run blacklist check → Checkpoint 1
- `tam_scrape` — scrape company websites
- `tam_analyze` — GPT analysis via negativa → Checkpoint 2
- `tam_re_analyze` — re-run analysis with adjusted prompt (if accuracy <90%)
- `tam_prepare_verification` — FindyMail cost estimate → Checkpoint 3
- `pipeline_status` — current pipeline state
- `approve_gate` — approve a checkpoint
- `import_smartlead_campaigns` — import existing campaigns as blacklist

### Campaign (4)
- `god_generate_sequence` — generate email sequence via GPT
- `god_push_to_smartlead` — create SmartLead campaign (auto-sends test email)
- `send_test_email` — send test email for any sequence step
- `list_email_accounts` — show available sending accounts

### Replies (4)
- `replies_summary` — reply counts by category
- `replies_list` — list replies with filters
- `replies_followups` — leads needing follow-up
- `replies_deep_link` — browser link to view replies

### CRM (2)
- `search_contacts` — search across all contacts
- `enrich_domains` — enrich company domains via Apollo

## 8. UI Pages

All user-scoped. Only shows your own data.

| Page | URL | What It Shows |
|------|-----|--------------|
| Pipeline | http://46.62.210.24:3000/pipeline | All gathering runs with credits |
| Pipeline Detail | http://46.62.210.24:3000/pipeline/{id} | Companies, segments, targets, confidence |
| CRM | http://46.62.210.24:3000/crm | Contacts with filters, campaigns, segments |
| Tasks/Replies | http://46.62.210.24:3000/tasks | Reply queue by category |
| Projects | http://46.62.210.24:3000/projects | Project management |
| Setup | http://46.62.210.24:3000/setup | Account + API key management |
| Account | http://46.62.210.24:3000/account | Credits spent, usage stats, pipeline runs |

## 9. Test Accounts

| Email | Role | Has Campaigns |
|-------|------|--------------|
| `pn@getsally.io` | Test admin | Yes — "petr" SmartLead campaigns |
| `services@getsally.io` | Test new user | No |

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| Tools not showing | `claude mcp list` — if empty, re-add: `claude mcp add leadgen --transport sse http://46.62.210.24:8002/mcp/sse` |
| "Authentication required" | Set up account first or reconnect token |
| "Integration not connected" | Connect API key via `configure_integration` |
| Pipeline stuck | Check `pipeline_status` — may be waiting at a checkpoint |
| Test email not received | Check spam. Verify SmartLead key connected. Try `send_test_email` manually. |
| CRM shows no data | You're a new user — run a pipeline first |
| Wrong project context | Use `set_active_project` to switch |

## 11. What's Logged

Every interaction is tracked:
- **Tool calls**: stored in `mcp_usage_logs` (tool name, args, credits spent, latency)
- **Conversations**: stored in `mcp_conversation_logs` (full JSON-RPC messages, session grouping)
- **Pipeline runs**: credits per run, target rates, timestamps
- **View logs**: `GET /api/account/conversations` or Account page in UI
