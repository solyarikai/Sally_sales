# Magnum Opus — System Documentation

Combined reference for the lead generation and outreach automation platform.

---

## Table of Contents

1. [CRM Design & UX Requirements](#crm-design--ux-requirements)
2. [CRM Architecture & Workflow](#crm-architecture--workflow)
3. [ArchiStruct ICP & Search Plan](#archistruct-icp--search-plan)
4. [SmartLead API Reference](#smartlead-api-reference)
5. [SmartLead Lead Categories](#smartlead-lead-categories)
6. [Validation Checklist](#validation-checklist)

---

## CRM Design & UX Requirements

### CRM Use Case: BDM Daily Workflow

1. Set campaign filter (autocomplete, multi-select)
2. Create project as "saved filters"
3. Edit project filters
4. Inside a project, click "Reply" button — only leads needing replies are shown, with "Processed" column (browser-local subtask for operator). Conversations shown with next/prev buttons, full communication history, auto-suggested reply, and button to reply in the selected campaign (default: most recent reply)
5. Recreate above flow for processing traffic on a slice of campaigns
6. Show conversation history, auto-suggested replies, and lead details in the same modal

### Key UX Principles

- Filters in max 2 rows, grid maximizes vertical space
- Searchable everything: every column has floating filter, campaign has autocomplete
- Status-first: color-coded status pills with counts are primary navigation
- Action-oriented: "Needs Reply" and "Follow-up" are prominent with count badges
- Saved views: any filter combination saved as project for instant recall
- AI-powered: analytics on any contact slice, self-learning from reply patterns

### Reply Categories (13 categories, GPT-classified)

| Category | Meaning |
|----------|---------|
| interested | Lead expressed interest |
| meeting_request | Wants to schedule a call/meeting |
| question | Has questions, needs more info |
| not_interested | Declined |
| out_of_office | OOO auto-reply |
| referral | Redirected to another person |
| unsubscribe | Explicit opt-out |
| already_using | Already has a similar solution |
| wrong_person | Not the right contact |
| pricing_request | Asking about pricing |
| other | Doesn't fit other categories |

Reply approval flow: `NULL → pending → approved/dismissed/replied_externally`

### Smart Projects (Saved Filter Presets)

| Project Name | Filters |
|---|---|
| SquareFi Active | campaign: SquareFi-*, status: contacted |
| Hot Leads | status: replied, needs_reply: true |
| FinTech Pipeline | search: fintech, status: qualified |
| LinkedIn Outreach | source: getsales, status: contacted |
| All Replied | status: replied |

### Analytics (per project)

**SQL-based (instant):**
- Total contacts, by status, by source, by campaign
- Top companies, job titles, locations
- Reply rate by campaign

**AI-generated (on demand):**
- Response pattern analysis
- GTM recommendations
- Pitch effectiveness comparison
- Segment performance ranking

### AI SDR System

Prompt template generation per project:
- Analyze communication history across all selected campaigns
- Generate prompt template using real conversations as reference
- Auto-refresh weekly based on latest communications
- Each generation creates a timestamped prompt template visible in Prompt Debug section

### Production Projects

Auto-create projects for: inxy, squarefi, easystaff, easystaff global, tfp, 2ndcapital, paybis, palark, gwc, deliryo, rizult, maincard, crowdcontrol, mifort

---

## CRM Architecture & Workflow

### Interface Layout

```
+---------------------------------------------------------------------+
| CRM Contacts  18,127                  [All Contacts v] [+] [Sync]   |
|                                                                      |
| [Search...] [* lead (5K) * contacted (12K) * replied (47) * qual]   |
| [Campaign v ___] [Source v] [!Needs Reply (12)] [Follow-up (34)]    |
+---------------------------------------------------------------------+
| # STATUS | EMAIL    | NAME     | COMPANY  | TITLE   | CAMPAIGN | .. |
|   [____] | [______] | [______] | [______] | [_____] | [______] |    |
+---------------------------------------------------------------------+
```

### Data Sources

- **SmartLead**: Email campaigns, leads, reply threading
- **GetSales**: LinkedIn campaigns, flow leads via API
  - Endpoint: `GET /flows/api/flows-leads` — returns all leads with status, flow, sender profile

### Implementation Sprints

1. **Foundation**: Fix status system, floating filters, campaign column, compact filter UI
2. **Power Features**: "Needs Reply" filter, saved presets (Smart Projects), project selector
3. **Intelligence**: SQL analytics dashboard, AI analysis + GTM generation, self-learning from reply patterns

---

## ArchiStruct ICP & Search Plan

### Campaign Intelligence (from SmartLead data)

- **25 campaigns** across SmartLead, **2 GetSales** campaigns
- **18,337 total leads** contacted
- **721 leads marked category 9** — ALL bounces, NOT real replies
- **4 real replies** — OOO auto-responses only

#### Campaign Segments Covered

| Segment | Campaigns | Leads | Geography |
|---------|-----------|-------|-----------|
| Developers Dubai | Dev 09/02, Devs 6 Dubai, Devs 4 | ~6,500 | Dubai |
| Developers outDubai | Devs out, Devs 6 outDubai | ~1,500 | Africa, UK, MENA |
| General Contractors | GENERAL_CONTRACTOR | 1,486 | Dubai/UAE |
| Architects Dubai | Архитекторы Дубай 5, Architects 4.12 | ~3,800 | Dubai |
| Architects out | Архитекторы outDubai, Архитекторы YG | ~1,575 | MENA/Global |
| Brokers | Brokers 1, 2, YG, Saudi | ~2,700 | Dubai, Saudi |
| Premium/Luxury Dev | PREMIUM_LUXURY_DEVELOPER | 185 | Dubai |
| Small/Mid Dev | SMALL_MID_DEVELOPER | 201 | Dubai |
| International entrants | INTERNATIONAL_MARKET_ENTRANT | 336 | Global→Dubai |

### ICP Definition

#### Target 1: Villa Developers/Builders (Primary)
- **MUST have villas on website** (mandatory — no large commercial-only)
- Website mentions development/construction
- Companies under 300M AED/year revenue
- **Geography**: ONLY Dubai and Abu Dhabi
- **Districts**: Palm Jumeirah, Dubai Hills, La Mer, Al Barari, Meydan, District One, Jumeirah Golf Estates, Damac Hills, Emirates Hills

#### Target 2: Brokers/Realtors Growing into Development
- Brokers offering villas (not apartments)
- Signs of development ambition
- Same geography constraints

#### Reference Companies
- btproperties.ae, ahs-properties.com, gulflandproperty.com, nakheel.developmentsales.com

### Search Plan: Yandex Pipeline

**Phase 1: Russian-language Queries**
- 7 query categories × 10 variations × 16 districts ≈ 1,120 queries + ~80 base queries

**Phase 2: English-language Queries**
- "villa construction company Dubai", "villa developer Dubai Russian", etc.
- Same district multiplication

**Phase 3: Blacklist**
- All domains already contacted in SmartLead (18k+ leads = ~5k unique domains)
- All domains from previous search jobs

### GPT Scoring Criteria
- **language_match**: Russian OR English (both OK for Dubai)
- **industry_match**: Must be construction/development/architecture for villas
- **service_match**: Must mention villas/residential. Auto-reject commercial-only
- **company_type**: Real builders > brokers > aggregators/portals
- **geography_match**: Dubai/Abu Dhabi only

### Blacklist Signals (false positives)
- Real estate portals/aggregators (bayut.com, propertyfinder.ae, dubizzle)
- News sites, job boards
- Commercial-only builders
- Property management companies

---

## SmartLead API Reference

Base URL: `https://server.smartlead.ai/api/v1`
Auth: Query param `api_key=<key>`

### Campaigns

```
GET /campaigns?api_key=X
→ [{id, name, status, ...}]
```
Status: ACTIVE, PAUSED, COMPLETED, ARCHIVED

### Campaign Leads

```
GET /campaigns/{campaign_id}/leads?api_key=X&limit=100&offset=0
→ {
    total_leads: "522",  // STRING, not int
    data: [{
      campaign_lead_map_id, lead_category_id,
      status: "INPROGRESS" | "COMPLETED",
      lead: { id, first_name, last_name, email, company_name, website, ... }
    }]
  }
```

**Important**:
- `total_leads` is a STRING
- `lead_category_id: 9` = BOUNCED (not replied!)
- `status` is sequence progress, NOT reply status
- Must paginate with `offset`

### Message History

```
GET /campaigns/{campaign_id}/leads/{lead_id}/message-history?api_key=X
→ {
    history: [{
      stats_id, from, to, type: "SENT" | "REPLY",
      message_id, time, email_body, subject, email_seq_number,
      attachments: [{file_url, file_name, file_type}]
    }],
    from, to
  }
```

**Important**:
- `type: "REPLY"` includes bounces from mailer-daemon!
- Must check `from` field to distinguish real replies from bounces
- Bounces: `mailer-daemon@googlemail.com` or `postmaster@*`

### Campaign Sequences

```
GET /campaigns/{campaign_id}/sequences?api_key=X
→ [{ id, seq_number, subject, email_body, sequence_variants }]
```

### Reply to Thread

```
POST /campaigns/{campaign_id}/reply-email-thread?api_key=X
Body: { email_stats_id, email_body, reply_message_id, reply_email_time, reply_email_body }
```

### Global Lead Search

```
GET /leads/global-leads?api_key=X&email=user@example.com
→ [{ id, email, first_name, last_name, company_name, campaigns }]
```

### Common Pitfalls

1. **Category 9 = bounces, not replies**
2. **`/leads/{id}/master-inbox` doesn't work** — use `/campaigns/{cid}/leads/{lid}/message-history`
3. **Response format varies**: Some endpoints return flat lists, others `{data: [...]}`
4. **total_leads is STRING**
5. **lead_id is nested**: Inside `data[].lead.id`, not `data[].id`

---

## SmartLead Lead Categories

| ID | Meaning | Notes |
|----|---------|-------|
| null | Not categorized | Default state |
| 1 | Interested | Lead expressed interest |
| 2 | Not Interested | Lead declined |
| 3 | Do Not Contact | Explicit opt-out |
| 4 | Wrong Person | Redirected/wrong contact |
| 5 | Meeting Booked | Meeting scheduled |
| 6 | Out of Office | OOO auto-reply |
| 7 | No Longer at Company | Left organization |
| 8 | Unsubscribed | Clicked unsubscribe |
| 9 | Bounced | Email bounced (mailer-daemon) |
| 10 | Responded | Generic catch-all |
| 11 | Warm | Showing some interest |
| 12 | Closed/Won | Deal closed |

**Key**: When filtering for real replies, EXCLUDE category 9 and check `from` field is not `mailer-daemon@*` or `postmaster@*`.

---

## Validation Checklist

Before deploying or after data sync changes, verify:

1. **Campaigns** — all campaigns fetched correctly from SmartLead and GetSales
2. **Replies** — including all conversation history, outbound messages too
3. **Contacts** — all contacts synced and merged properly

Ensure the data update setup (polling + webhooks) on the server is robust and working. Log issues and push fixes for server-side debugging.

---

## Environment & Credentials

### Server (Hetzner)

- **SSH**: `ssh hetzner`, user `leadokol`, path `~/magnum-opus-project/repo`
- **Docker**: v1 (`docker-compose`, not v2)

### Credentials

All API keys and secrets are in `backend/.env` on the server. **Never commit credentials to docs or code.**

Key integrations (all configured via `backend/app/core/config.py` → Pydantic `BaseSettings`):
- OpenAI (GPT scoring, classification, draft generation)
- SmartLead (email outreach campaigns)
- GetSales (LinkedIn outreach)
- Apollo (people enrichment)
- FindyMail (email verification)
- Yandex Search API (company discovery)
- Crona (JS-rendered website scraping)
- Telegram Bot (notifications)
- Google Service Account (Google Sheets sync)

### Docker Run Template (for one-off scripts)

```bash
docker exec -w /app -e PYTHONPATH=/app leadgen-backend python3 scripts/<SCRIPT_NAME>.py
```

### Config File Reference

All settings defined in `backend/app/core/config.py` via Pydantic `BaseSettings`. Loads from `.env` file or environment variables.

---

## Additional References

- **Crona API spec**: See `docs/crona.yaml` (vendor API specification for JS-rendered website scraping)
