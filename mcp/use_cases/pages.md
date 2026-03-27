# MCP UI — Page Use Cases

## Login Page (`/` when not authenticated)

**Who**: Unauthenticated users
**Purpose**: Gate to the app. No data visible without login.

- Log In tab: email + password
- Sign Up tab: email + password (name auto-derived)
- Token login: link at bottom for MCP/API users
- After auth: redirect to Pipeline page

## Setup Page (`/setup`)

**Who**: Authenticated users managing their account
**Purpose**: API key management + MCP connection info

Shows:
- Account card: name, email, token preview, logout
- API Keys list: ALL services (SmartLead, Apollo, OpenAI, Gemini) with status
  - Green dot = connected, with status info (e.g., "1973 campaigns found")
  - Gray dot = not connected
  - Each has Connect/Update button — inline key entry
  - No "Connect a service" dropdown — every service is always visible
- MCP connection command for Claude Code

Does NOT show:
- Signup form (that's on Login page)
- Credits/usage (that's on Account page)

## Pipeline Page (`/pipeline`)

**Who**: Users running lead gathering
**Purpose**: List of all pipeline runs with status

Shows:
- Table: Run ID, Source, Companies, Target Rate, Credits, Phase, Date
- Click row → Pipeline Detail page
- User-scoped: only shows YOUR runs

## Pipeline Detail (`/pipeline/:id`)

**Who**: User managing a specific gathering run
**Purpose**: Company table with analysis results

Shows:
- Stage progress bar (Gather → Blacklist → Scrape → Analyze → Verify)
- Credits badge + Target rate badge
- Apollo Filters panel (collapsible)
- Company table: Domain, Name, Industry, Keywords, Size, Country, Segment, Confidence, Analysis, Status
- Click row → Company detail modal (scrape text, analysis reasoning, source data)
- "View in CRM" link when contacts found

## CRM Page (`/crm`)

**Who**: Users viewing their contacts
**Purpose**: Full contact database with filters

Shows:
- AG Grid table with 15+ columns (reused from main app)
- Filters: search, project, campaign, geo, reply category
- Contact detail modal on row click
- User-scoped: only YOUR project's contacts

## Tasks/Replies Page (`/tasks`)

**Who**: Users managing replies
**Purpose**: Reply queue by category

Shows:
- Tabs: Replies | Follow-ups | Meetings
- Sub-tabs: Inbox, All, Meetings, Interested, Questions, Not Interested, OOO, Wrong Person, Unsubscribe
- Reply cards with lead info, message preview, actions
- User-scoped: only replies from YOUR campaigns

## Projects Page (`/projects`)

**Who**: Users managing their projects
**Purpose**: Project CRUD + ICP configuration

Shows:
- Project list with name, ICP, industries, sender info
- Create/edit project
- Campaign rules (which SmartLead campaigns belong to this project)

## Learning Page (`/learning`)

**Who**: Users reviewing AI learning data
**Purpose**: Knowledge base + learning cycle analytics

Shows:
- Project knowledge items (ICP, outreach rules, examples)
- Learning cycle logs

## Logs/Conversations Page (`/conversations`)

**Who**: Admin/user reviewing MCP interactions
**Purpose**: Full conversation log of all MCP tool calls

Shows:
- Chronological list of all JSON-RPC messages
- Tool name, arguments, results, timestamps
- Session grouping
- User-scoped: only YOUR conversations

## Account Page (`/account`)

**Who**: Users tracking their usage
**Purpose**: Credits, stats, pipeline runs summary

Shows:
- Credits used: Apollo (gathering + discovery), OpenAI (analysis runs), MCP (tool calls)
- Your Stats: contacts, companies, campaigns, tool calls (user-scoped)
- Pipeline Runs table: per-run credits, target rates
- Connected Services list
- Usage by Tool breakdown
- Recent Activity log
