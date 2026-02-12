# Platform Use Cases — LeadGen SaaS

## Overview

An AI-powered B2B lead generation platform for agencies. Operators use chat to describe target segments, the system automatically discovers companies via web search, scrapes websites, scores with GPT, extracts contacts, enriches via Apollo, and pushes to outreach platforms (SmartLead email, GetSales LinkedIn).

---

## Core Workflow

```
Operator Chat → GPT Query Gen → Web Search → Domain Filter → Website Scrape → GPT Scoring → Auto-Review
                                                                                                  ↓
Export/Campaign ← CRM Contact ← Promote ← Apollo Enrich ← Contact Extract ← Target Company ← Pipeline
```

---

## Use Case 1: Target Company Discovery (Data Search)

**Actor:** Agency operator
**Goal:** Find companies matching a specific ICP (ideal customer profile)

**Flow:**
1. Operator selects a project (e.g. "Deliryo") from the global project selector
2. Opens Data Search chat, types natural language: "Find HNWI service providers in Dubai and Cyprus"
3. System (GPT) generates 100-500 search queries in relevant languages (English, Russian, local)
4. Queries run via Yandex API and/or Google SERP (via Apify)
5. Results deduplicated against existing domains, blacklist, and campaign contacts
6. New domains scraped via Crona (JS-rendered) for website content
7. GPT-4o-mini scores each domain on 5 criteria (language, industry, service, company type, geography)
8. Auto-review (GPT second pass) confirms/rejects borderline cases
9. Pipeline auto-promotes confirmed targets
10. System iterates until target goal reached (e.g. 500 companies)

**Progress:** SSE streaming shows real-time stats (queries used, domains found, targets confirmed)

**Operator Feedback Loop:**
- "These results have too many property management companies, I only want sales agencies" → system refines queries, demotes bad patterns
- "Also try Indonesia and Montenegro" → system adds new geos to query generation
- "Stop searching, good enough" → system cancels running job

---

## Use Case 2: Contact Enrichment

**Actor:** Agency operator
**Goal:** Get decision-maker contacts for discovered target companies

**Flow:**
1. Operator views Pipeline page, filters by project + "Targets only"
2. Selects companies to enrich (or selects all)
3. **Website extraction:** GPT + regex parses scraped HTML for emails, phones, social links
4. **Apollo enrichment:** Searches Apollo for people matching title filters (CEO, Founder, Managing Director, etc.)
   - Operator configures: title keywords, max people per company, credit cap
   - System deduplicates against existing contacts
5. Extracted contacts appear in Pipeline detail view
6. Operator promotes contacts to CRM

**Key constraint:** Only enrich companies not previously enriched (`apollo_enriched_at IS NULL`, `contacts_count = 0`)

---

## Use Case 3: Outreach Campaign Management

**Actor:** Agency operator
**Goal:** Launch and monitor email/LinkedIn campaigns from discovered contacts

**Flow:**
1. Operator exports enriched contacts to Google Sheets (with campaign status columns)
2. Contacts imported to SmartLead (email) or GetSales (LinkedIn)
3. System syncs contacts bidirectionally:
   - SmartLead → CRM: lead status, campaign membership, reply events
   - GetSales → CRM: LinkedIn messages, flow membership, reply events
4. Webhooks capture real-time events (email sent, opened, replied, bounced)
5. Contacts in CRM show unified timeline across all channels

**Future:** Direct campaign creation from Pipeline page (push leads to SmartLead/GetSales without export)

---

## Use Case 4: Reply Processing & Auto-Classification

**Actor:** Agency operator
**Goal:** Efficiently triage and respond to campaign replies

**Flow:**
1. Operator opens Replies page, selects project
2. System shows only replies that need action ("needs reply" filter = no outbound after inbound)
3. Each reply has AI classification: meeting_request, interested, question, not_interested, wrong_person, out_of_office, other, unsubscribe
4. Operator reviews AI-generated draft reply
5. Approve & Send: sends via SmartLead thread API (with confirmation dialog)
6. Dismiss: marks as handled, removes from pending queue
7. Notifications: Telegram bot sends per-project alerts for new replies

**Priority:** meeting_request > interested > question > not_interested > wrong_person > out_of_office > other > unsubscribe

---

## Use Case 5: Multi-Project Dashboard

**Actor:** Agency owner / operator
**Goal:** Monitor all projects and their pipelines from one place

**Flow:**
1. Global project selector in header filters all pages
2. Pipeline page shows per-project stats: discovered, targets, new targets, in campaigns, rejected
3. Contact breakdown: Apollo contacts (with email/LinkedIn counts), website contacts
4. Cost tracking: Yandex API queries, OpenAI tokens, Crona credits, Apollo credits — all with USD equivalent
5. Query Investigation page shows search job history with effectiveness metrics per engine
6. CRM page shows contacts across all campaigns with source/channel/status filters

---

## Use Case 6: Feedback-Driven Search Refinement

**Actor:** Agency operator
**Goal:** Improve search accuracy based on results

**Flow:**
1. Operator reviews targets in Pipeline → spots false positives
2. Rejects bad companies with reasoning
3. System accumulates knowledge: good query patterns, bad keywords, anti-patterns
4. Next search iteration generates better queries, avoids previously seen bad patterns
5. Operator can also provide feedback via chat: "too many IT outsourcing firms, focus on fintech only"
6. System adjusts `target_segments` and demotes matching bad results

---

## Current Active Projects

| Project | Target Segment | Geos | Status |
|---------|---------------|------|--------|
| Deliryo | HNWI service providers + luxury real estate agencies selling to Russian HNWI | Thailand, UAE, Turkey, France, Spain, Cyprus, Greece, Indonesia, Georgia, Montenegro | Active search (471 targets found) |
| ArchiStruct | Architecture/construction firms | Various | Search complete, enrichment pending |
| Rizzult | Wellness/shopping apps | Global | Campaigns running |
| EasyStaff | HR/payroll services | US, Russia | Campaigns running |
| TFP | Fashion/apparel | Global | Campaigns running |
| SquareFi | Media buyers | Global | Campaigns running |
| Inxy | Trading/monetization | Global | Campaigns running |

---

## Technical Integrations

| System | Purpose | API Used |
|--------|---------|----------|
| Yandex Search API | Primary web search ($0.25/1K queries) | REST, folder_id + API key |
| Google SERP (Apify) | Secondary web search ($0.0017/result page) | Apify actors with proxy |
| Crona | JS-rendered website scraping | REST, email/password auth |
| Apollo.io | Contact enrichment (people search) | REST, X-Api-Key header |
| OpenAI GPT-4o-mini | Query generation, scoring, classification, review | Chat completions API |
| SmartLead | Email campaign management | REST, API key in query params |
| GetSales | LinkedIn outreach automation | REST, cookie-based auth |
| Google Sheets | Data export and reply logging | Service account (JSON credentials) |
| Telegram | Operator notifications | Bot API with polling |
| Redis | Caching, sync locks, reply dedup | Standard Redis protocol |

---

## Key Metrics Per Project

- **Target rate:** % of discovered domains that are confirmed targets (goal: >5%)
- **Contact yield:** contacts per target company (goal: 2-5 decision makers)
- **Reply rate:** % of contacted leads that reply (varies by channel)
- **Meeting rate:** % of replies that are meeting requests
- **Cost per target:** total API spend / confirmed targets
- **Cost per contact:** total API spend / enriched contacts with email
