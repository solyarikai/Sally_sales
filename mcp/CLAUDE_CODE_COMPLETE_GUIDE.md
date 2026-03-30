# MCP LeadGen — Claude Code Guide

## 1. Setup (30 seconds)

```bash
claude mcp add leadgen --transport sse http://46.62.210.24:8002/mcp/sse

mkdir ~/leadgen && cd ~/leadgen
cat > CLAUDE.md << 'EOF'
# LeadGen MCP Operator
You are a lead generation assistant. Use the **leadgen** MCP tools for everything.
Never skip pipeline checkpoints. Campaigns are always DRAFT.
UI: http://46.62.210.24:3000
EOF

claude
```

## 2. API Keys (copy-paste)

| Service | Key |
|---------|-----|
| **SmartLead** | `eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5` |
| **Apollo** | `9yIx2mZegixXHeDf6mWVqA` |
| **OpenAI** | `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` |

## 3. First Session

**Step 1:** Sign up at http://46.62.210.24:3000/setup → get your `mcp_` token

**Step 2:** In Claude Code:
```
You: Login with token mcp_250f8ab8a1b753a0...
     Connect SmartLead with key eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
     Connect Apollo with key 9yIx2mZegixXHeDf6mWVqA
     Connect OpenAI with key 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
```

Done. Logged in + 3 integrations connected.

## 4. Example: Find Companies + Create Campaign

```
You: I sell payroll services for companies hiring freelancers abroad.
     Website: easystaff.io
     Find IT outsourcing companies in Dubai that might hire contractors.
     Sender: Rinat Karimov, BDM at Easystaff

Claude: [creates project, scrapes your website for value proposition]
        [probes Apollo → scrapes 10 websites → shows you what it found]
        [gathers 400 companies → blacklist check → scrapes websites]
        [GPT analyzes via negativa → labels segments]

        CHECKPOINT 2: 89 targets found (IT_OUTSOURCING, MANAGED_SERVICES, AGENCY...)
        Review?

You: Looks good

Claude: [generates 5-step email sequence from your website content]
        [creates SmartLead campaign with production settings]
        [sends test email to pn@getsally.io]

        Done. Check your inbox. SmartLead link: https://app.smartlead.ai/...
```

## 5. Example: Import Existing Campaigns + Check Replies

```
You: Import my SmartLead campaigns matching "ES Global" as blacklist

Claude: Importing 12 campaigns, 2,847 contacts...
        45 replies: 12 interested, 8 meetings, 15 questions

You: Show warm replies

Claude: 12 interested leads with details + browser link

You: Now find NEW companies in the same geo — avoid overlap with imported ones

Claude: [uses imported contacts as blacklist, gathers fresh companies]
```

## 6. Example: Test Email for Any Sequence Step

```
You: Send me step 3 of campaign 3091234

Claude: Test email for step 3 sent to pn@getsally.io
```

## 7. Tools

To see all available tools:
```
You: List all available MCP tools
```

The system has 35+ tools. Most important ones:

| What you say | What happens |
|-------------|-------------|
| "Find X companies in Y" | Probes Apollo, scrapes websites, gathers |
| "Import my SmartLead campaigns" | Imports as blacklist + analyzes replies |
| "Show warm replies" | Lists interested/meeting leads |
| "Create campaign from these targets" | Generates sequence + creates in SmartLead |
| "Send test email" | Sends via SmartLead native API to your inbox |
| "What's my pipeline status?" | Shows current phase + credits spent |
| "Show my credits" | Account page with Apollo/OpenAI usage |

## 8. UI

All pages at http://46.62.210.24:3000 — user-scoped, you only see your data.

| Page | What |
|------|------|
| `/pipeline` | Gathering runs, credits, target rates |
| `/pipeline/{id}` | Company table with segments + confidence |
| `/crm` | All contacts with filters |
| `/tasks` | Reply queue by category |
| `/account` | Credits spent, usage stats |
| `/setup` | API key management |

## 9. Costs

| Action | Cost |
|--------|------|
| Apollo search | 1 credit / page of 100 companies |
| Apollo enrichment | 1 credit / company |
| Website scraping | Free |
| GPT analysis | ~$0.003 / company |
| SmartLead campaign | Free |
| Test email | Free |

