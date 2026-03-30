# MCP UI — Complete Page Use Cases

## Login Page (`/` when not authenticated)

**Purpose**: Gate. No data without auth.

**Use cases**:
- New user signs up: email + password → gets token + session → redirected to Pipeline
- Returning user logs in: email + password → session → redirected to Pipeline
- MCP/API user: "Login with token" link → paste mcp_ token → session

**State**: Full screen, no header, centered card. After auth: full app with header.

---

## Pipeline List (`/pipeline`)

**Purpose**: All gathering runs at a glance.

**Columns**: Run ID, Project, Segment labels, Source, Raw companies, Targets (link to pipeline detail filtered), People (link to CRM), Credits, Phase, Date+Time

**Use cases**:
- See all runs across projects with key metrics
- Filter by project (top-left dropdown)
- Click run → Pipeline Detail page
- Click targets count → filtered pipeline view (status=target)
- Click people count → CRM filtered by pipeline

**Data**: User-scoped. Only YOUR project's runs. Counts per-run via CompanySourceLink.

---

## Pipeline Detail (`/pipeline/:id`)

**Purpose**: Company discovery and analysis results for a gathering run.

### Top bar
- **Iteration selector**: filter companies to specific run or "All iterations"
- **Phase badge**: current pipeline stage (clickable for stage history)
- **Credits badge**: Apollo credits spent on this run
- **Target rate badge**: percentage of targets found
- **Prompts button**: view/compare GPT prompts used
- **Apollo Filters**: collapsible panel showing filter sets used
- **Export CSV**: download companies as spreadsheet

### Companies table
**Columns** (configurable — hide/show via Columns button):
| Column | Purpose |
|--------|---------|
| Domain | Opens website in new tab (click). Click row elsewhere → modal |
| Name | Company name from Apollo |
| Industry | Apollo industry classification |
| Keywords | Apollo keyword tags (from Apollo taxonomy) |
| Size | Employee count |
| Country | Country |
| City | City |
| Scraped | Website scrape preview (truncated) or status icon |
| Segment | AI classification: IT_OUTSOURCING, SAAS_COMPANY, etc. (dropdown filter) |
| Confidence | 0-100% with color coding (green >80, yellow >50, gray <50) |
| Analysis | GPT reasoning (truncated, full in modal) |
| Status | gathered → blacklisted → scraped → target/rejected → verified |
| People | Contact count with CRM deep link (both targets and blacklisted) |
| Iteration | Which run(s) gathered this company |

**Use cases**:
- Browse gathered companies with column filters
- Filter by status (targets only, blacklisted only)
- Filter by segment (IT_OUTSOURCING only)
- Filter by iteration (only companies from run #14)
- Click domain → opens website in new tab
- Click row → company detail modal (Analysis tab by default)
- Export filtered results to CSV
- Review targets at Checkpoint 2 before proceeding

### Company Detail Modal
**Tab: Analysis** (default)
- Segment badge + confidence badge + status badge
- Full GPT reasoning text
- GPT prompt used (collapsible)

**Tab: Details**
- Industry, Keywords (from Apollo), Employees, Founded, Country, City
- LinkedIn URL with copy button (opens in new tab)
- Apollo link with copy button (opens in new tab)
- Company description

**Tab: Scrape**
- Status, HTTP code, size, timestamp
- Page scraped: / (root) — future: /about, /team, /contact
- Full scraped text (expandable "View full text")

**Tab: Source**
- Raw Apollo JSON data

### Checkpoint panels
- **CP1** (after blacklist): project scope confirmation, campaign rejection breakdown
- **CP2** (after analysis): target list review, segment distribution, borderline rejections
- **CP3** (before FindyMail): cost approval with email count breakdown

### Loading states
- During gathering: spinner + "X companies found so far", table updates live
- During scraping: individual company status updates
- During analysis: status column updates live

---

## CRM (`/crm`)

**Purpose**: All contacts across all pipelines and campaigns.

**Reused from main app** via @main alias (AG Grid, same component).

**Columns**: Client Status, Email, Name, Company, Title, Campaign, Source, Geo, Location, Website, LinkedIn

**Use cases**:
- View all contacts imported from SmartLead campaigns
- View contacts gathered via pipeline
- Filter by project, campaign, domain, geo, reply category
- Filter by pipeline: `/crm?pipeline=14` shows only contacts from that run
- Filter by domain: `/crm?domain=techmind.ae` shows contacts from that company
- Click row → contact detail modal (conversation history, company info)
- Search by name/email/company
- Deep links from pipeline People column

**Data**: User-scoped. Only contacts from YOUR projects.

---

## Tasks/Replies (`/tasks`)

**Purpose**: Reply management queue. Review AI drafts, approve/dismiss/regenerate.

**Tabs**: Replies | Follow-ups | Meetings

**Sub-tabs**: Inbox, All, Meetings, Interested, Questions, Not Interested, OOO, Wrong Person, Unsubscribe

**Use cases**:
- See all incoming replies categorized by intent
- Review AI-generated draft responses
- Approve draft → queued for sending (NEVER auto-sent)
- Dismiss reply → mark as handled
- Regenerate draft → with operator instructions
- View full conversation thread
- Filter by campaign, search by name/company
- Follow-ups tab: leads needing follow-up action

**Data**: User-scoped. Only replies from YOUR campaigns.

**Key rule**: NEVER sends automatically. Only queues approved drafts. Operator sends via UI.

---

## Projects (`/projects`)

**Purpose**: Project CRUD — ICP definition, sender identity, campaign rules.

**Use cases**:
- Create new project: name, website (scraped for value proposition), ICP, sender info
- Edit project: update ICP, industries, sender identity
- View project campaigns: which SmartLead campaigns belong to this project
- Set campaign rules: prefix matching, tag matching, contains matching
- Import campaigns as blacklist
- View contact count (blacklist size)
- Link to CRM filtered by project
- Link to pipeline runs for this project

**Project detail shows**:
- Name, ICP description, target industries
- Sender: name, position, company
- Campaign rules (auto-detection config)
- Matched campaigns with lead counts
- Knowledge base entries (ICP, outreach rules, examples)

---

## Learning (`/learning`)

**Purpose**: AI learning analytics — operator corrections, pattern extraction, quality metrics.

**Use cases**:
- View operator correction log: what AI suggested vs what operator sent
- See quality metrics: approve rate, edit rate, regenerate rate over time
- Review learned patterns: "operator shortens pricing", "prefers Russian for RU market"
- Manage reference examples: golden examples, quality scores
- Filter by date, category, project
- Export correction log as CSV

**Data sources**: OperatorCorrection table, ReferenceExample table, LearningLog table.

---

## Conversation Logs (`/conversations`)

**Purpose**: Full MCP interaction history — every tool call, every argument, every result.

**Use cases**:
- See chronological list of all MCP protocol messages
- Filter by session (group messages from one conversation)
- See tool name, arguments, result summary
- View raw JSON-RPC messages
- Track what the user's Claude agent requested
- Debug tool call failures

**Data**: User-scoped. Only YOUR conversations. Stored in mcp_conversation_logs table.

---

## Setup (`/setup`)

**Purpose**: API key management + MCP connection info. NOT signup (that's Login page).

**Shows** (when authenticated):
- Account card: name, email, token preview, logout
- API Keys: all 4 services (SmartLead, Apollo, OpenAI, Gemini) with status
  - Green dot = connected, with status info
  - Gray dot = not connected
  - Each has Connect/Update button (inline key entry)
- MCP connection command for Claude Code
- Token for pasting into MCP client

**Use cases**:
- Connect a new API key (paste key, click Save, auto-tests connection)
- Update an existing key (click Update, paste new key)
- See connection status for all services
- Copy MCP connection command for Claude Code setup
- Logout

---

## Account (`/account`)

**Purpose**: Usage tracking — credits, stats, pipeline run history.

**Shows**:
- Credits Used: Apollo (gathering + filter discovery), OpenAI (analysis runs), MCP (tool calls)
- Your Stats: contacts, companies, campaigns, tool calls (all user-scoped)
- Pipeline Runs table: per-run ID, source, companies, targets, credits, phase, date
- Connected Services: same as Setup but read-only
- Usage by Tool: breakdown of which MCP tools called how many times
- Recent Activity: last 20 tool calls with timestamps

**Use cases**:
- Track Apollo credit consumption across all runs
- See which pipeline runs cost the most
- Monitor total tool calls for billing
- Review recent activity log
- Compare target rates across runs

---

## Cross-Page Patterns

### Data isolation
Every endpoint returns empty when no auth. Every query filtered by user's project IDs.

### Deep linking
- Pipeline → CRM: `/crm?pipeline=14` or `/crm?domain=techmind.ae`
- Pipeline → Targets: `/pipeline/14?status=target`
- Replies → CRM: deep link with project context
- Account → Pipeline: click run row → pipeline detail

### Table pattern
Same everywhere: column header filters, click row for modal, lazy loading, sortable, filterable.

### Links in MCP responses
Every MCP tool response includes `_links` with relevant UI URLs so the agent can share them with the user.

### localStorage persistence
- Column visibility preferences
- Theme (dark/light)
- Selected project
- Auth token
