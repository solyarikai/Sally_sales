# Project Templates

Шаблоны проектов для быстрого создания в Linear. Каждый шаблон содержит:
- Название проекта (формула)
- Issues с описаниями
- Milestones
- Рекомендуемые labels

---

## campaign — New Campaign

**Название:** `[SEGMENT] [VERSION] Campaign` (пример: `IMAGENCY v6 Campaign`)

**Описание:** End-to-end outreach campaign from lead gathering to SmartLead launch.

### Milestones

| # | Milestone | Триггер завершения |
|---|-----------|-------------------|
| 1 | Leads Gathered | Steps 1-4 done |
| 2 | Leads Enriched | Steps 5-8 done |
| 3 | Sequences Ready | Steps 9-10 done |
| 4 | Campaign Live | Steps 11-12 done |

### Issues (12 steps matching universal pipeline)

| # | Title | Description | Labels |
|---|-------|-------------|--------|
| 1 | Gather companies | Run Apollo/Clay search with segment filters. Output: raw company list CSV. | `pipeline`, tool label |
| 2 | Dedup companies | Remove duplicates against existing leads in DB and Google Sheets. | `pipeline` |
| 3 | Blacklist check | Filter against blacklist (29k+ domains). Remove already-contacted. | `pipeline`, `ops` |
| 4 | Prefilter & classify | AI classification: ICP fit, company size, relevance scoring. | `pipeline` |
| 5 | Scrape & enrich companies | Website scraping, tech stack detection, social proof extraction. | `pipeline` |
| 6 | Export people | Extract contacts from qualified companies via Apollo People. | `pipeline`, `apollo` |
| 7 | Findymail verification | Verify emails via Findymail API. Export no-email contacts to GetSales. | `pipeline`, `findymail` |
| 8 | GetSales export | Prepare LinkedIn outreach CSV for contacts without verified email. | `pipeline`, `getsales` |
| 9 | Write sequences | Draft email sequences with social proof, geo-clustering, A/B variants. | `sequence` |
| 10 | Review sequences | Review copy: tone, variables, social proof accuracy, sender name. | `sequence` |
| 11 | Upload to SmartLead | Create campaign, upload leads, set sequences and schedule. | `campaign`, `smartlead` |
| 12 | Launch & monitor | Manual activation in SmartLead UI. Monitor first 24h deliverability. | `campaign`, `smartlead` |

**Resource links (добавить к проекту):**
- Google Sheet с лидами (создаётся на шаге 1)
- SmartLead campaign URL (создаётся на шаге 11)
- Apollo search URL (если применимо)

---

## segment — New Segment Launch

**Название:** `[SEGMENT] Segment Launch` (пример: `SOCIAL-COMMERCE Segment Launch`)

**Описание:** Research, define, and prepare a new ICP segment for outreach.

### Milestones

| # | Milestone | Триггер |
|---|-----------|---------|
| 1 | Research Complete | Steps 1-3 done |
| 2 | Pipeline Ready | Steps 4-6 done |
| 3 | Test Campaign Sent | Step 7 done |

### Issues (7 steps)

| # | Title | Description | Labels |
|---|-------|-------------|--------|
| 1 | Market research | Analyze market size, key players, competitors' approach. Use Exa for research. | `research` |
| 2 | Define ICP criteria | Document ideal customer profile: company size, geo, tech stack, job titles. | `research` |
| 3 | Build Apollo filters | Create v4 filter JSON via apollo-segment-builder skill. | `pipeline`, `apollo` |
| 4 | TAM estimation | Run Apollo search, estimate total addressable market. Document in segment docs. | `research`, `apollo` |
| 5 | Create segment docs | Write segment documentation in sofia/projects/OnSocial/docs/. | `ops` |
| 6 | Write test sequences | Draft initial 3-5 email sequence tailored to segment's pain points. | `sequence` |
| 7 | Run test campaign | Launch small batch (50-100 leads) to validate messaging and deliverability. | `campaign` |

---

## deliverability — Deliverability Audit

**Название:** `Deliverability Audit [DATE]` (пример: `Deliverability Audit 2026-04`)

**Описание:** Comprehensive check of email infrastructure health.

### Issues (6 steps)

| # | Title | Description | Labels |
|---|-------|-------------|--------|
| 1 | Inbox placement test | Run Instantly inbox placement test for all active mailboxes. | `infra`, `instantly` |
| 2 | Domain age analysis | Check domain age cohorts, identify domains eligible for volume increase. | `infra` |
| 3 | Warmup status review | Verify warmup state for all accounts in Instantly. | `infra`, `instantly` |
| 4 | Spam report check | Run spam report script, analyze results across providers. | `infra`, `instantly` |
| 5 | Blacklist freshness | Sync SmartLead → blacklist, verify domain count and freshness. | `ops`, `smartlead` |
| 6 | Audit report | Compile findings into deliverability report with recommendations. | `ops` |

---

## infra — Infrastructure Task

**Название:** `Infra: [DESCRIPTION]` (пример: `Infra: Migrate to new MCP server`)

**Описание:** Server, backend, or tooling infrastructure work.

### Issues (4 steps)

| # | Title | Description | Labels |
|---|-------|-------------|--------|
| 1 | Plan & scope | Define what needs to change, identify dependencies and risks. | `infra` |
| 2 | Implement | Execute the change (deploy, configure, code). | `infra` |
| 3 | Verify | Health check, test functionality, confirm no regressions. | `infra` |
| 4 | Document | Update CLAUDE.md, docs, or runbooks as needed. | `infra`, `ops` |

---

## weekly-ops — Weekly Operations

**Название:** `Weekly Ops [WEEK]` (пример: `Weekly Ops W15 2026`)

**Описание:** Recurring weekly maintenance and monitoring tasks.

### Issues (6 steps)

| # | Title | Description | Labels |
|---|-------|-------------|--------|
| 1 | Blacklist sync | Run sync_smartlead_to_blacklist.py, update domain count. | `ops`, `smartlead` |
| 2 | Reply handling | Review and categorize new replies in SmartLead campaigns. | `ops`, `smartlead` |
| 3 | Deliverability spot-check | Quick inbox placement check on 2-3 key mailboxes. | `infra`, `instantly` |
| 4 | Campaign metrics | Pull open/reply/bounce rates for active campaigns. | `ops`, `smartlead` |
| 5 | Pipeline progress | Check status of any running pipeline steps on Hetzner. | `ops` |
| 6 | Weekly report | Compile weekly summary for team sync. | `ops` |

---

## sequence — Sequence Sprint

**Название:** `Sequences: [SEGMENT] [VERSION]` (пример: `Sequences: IMAGENCY v5`)

**Описание:** Writing and reviewing email sequences for a campaign.

### Issues (5 steps)

| # | Title | Description | Labels |
|---|-------|-------------|--------|
| 1 | Research & angles | Analyze segment pain points, gather social proof, define messaging angles. | `research`, `sequence` |
| 2 | Draft sequences | Write 3-5 email sequences with role-based personalization (Founders/Creative/Ops). | `sequence` |
| 3 | Internal review | Review copy: tone, variable rendering, social proof accuracy, sender consistency. | `sequence` |
| 4 | A/B variants | Create B variants for email 1 of each sequence. | `sequence` |
| 5 | Upload & test | Upload to SmartLead, send test emails, verify rendering. | `sequence`, `smartlead` |
