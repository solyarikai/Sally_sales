# Pipeline Page — UI Requirements

Based on wireframe screenshots and user feedback. This is the spec for implementation.

---

## Core Concept: Pipeline = Segment

One pipeline = one business segment. A segment may have **multiple iterations** — different Apollo filters, different GPT prompts, different pages. The user decides what belongs to one pipeline. Changing filters or prompts creates a new iteration within the same pipeline.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Iteration ▼]   [Stage: Verification ▼]   [Prompts →]                  │
│                                                                          │
│  ── hidden by default (collapsible) ──────────────────────────────────── │
│  [User Prompt History ▼]    [Apollo Filters ▼]                           │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TABLE (CRM-style with column filters, lazy loading)                     │
│  ┌─────┬──────┬────────┬─────────┬──────┬───────┬──────┬────────┬──────┐ │
│  │DOM. │NAME  │INDUSTRY│KEYWORDS │SIZE  │COUNTRY│CITY  │SCRAPED │STATUS│ │
│  │  ▼  │  ▼   │   ▼    │   ▼     │  ▼   │  ▼    │  ▼   │  ▼     │  ▼  │ │
│  ├─────┼──────┼────────┼─────────┼──────┼───────┼──────┼────────┼──────┤ │
│  │row  │      │        │         │      │       │      │        │      │ │
│  │row  │      │        │         │      │       │      │        │      │ │
│  │...  │      │        │         │      │       │      │        │      │ │
│  │                                                                      │ │
│  │ [loader spinner if gathering in progress]                             │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Top Bar Controls

### 1. Iteration Selector (top-left)
- **Same UX as project selector** in the header — dropdown button
- Lists all iterations (gathering runs) for this pipeline/segment
- Each iteration shows: `#ID — filters summary — date — companies count`
- "All" option shows companies from all iterations combined
- When you click an iteration from the Prompts or Filters subpage, it navigates back here with that iteration pre-selected

### 2. Stage Indicator (top-center)
- Shows current pipeline stage: Gather, Blacklist, CP1, Pre-Filter, Scrape, Analysis, CP2, Verification, CP3, Done
- **Current stage highlighted** (blue/orange for checkpoints)
- **Past stages show as passed** (checkmark)
- **Future stages shown in dropdown** — clicking a future stage does nothing (disabled)
- NOT a stepper — it's an informational indicator with dropdown showing all stages

### 3. Prompts Button (top-right)
- Opens **Prompts subpage** (see below)
- Shows count of prompts used: `Prompts (3)`

### 4. Hidden Dropdowns (collapsed by default, toggle to show)

#### User Prompt History
- Expandable panel showing the conversation between the user and MCP agent
- Every message the user sent + every MCP response
- Sourced from `mcp_usage_logs` table
- Purpose: track what instructions the user gave, what decisions were made

#### Apollo Filters Panel
- Expandable panel showing Apollo filter sets used across iterations
- Each filter set: keywords, locations, employee ranges, funding stages, pages
- Shows per-filter-set: how many companies returned, how many became targets
- Clickable — clicking a filter set filters the table to that iteration

---

## Companies Table

### Pattern: Same as CRM
- **Column header filters** — each column has an embedded filter (dropdown/search) in the header
- **Click row → modal opens** with full company detail
- **Lazy loading** — loads 50 companies at a time, spinner at bottom loads more on scroll
- **Sortable** — click column header to sort

### Columns

| Column | Description | Filter type |
|--------|-------------|-------------|
| **Domain** | Company domain, clickable link to website | Text search |
| **Name** | Company name from Apollo | Text search |
| **Industry** | Industry classification | Dropdown (unique values) |
| **Keywords** | Apollo keyword tags that matched | Dropdown multi-select |
| **Employee Size** | Number of employees | Range filter (min-max) |
| **Country** | Country | Dropdown |
| **City** | City, State | Text search |
| **Scraped Website** | Scrape status: success (with text size) / error / pending | Dropdown (success/error/pending) |
| **Website Analysis** | GPT analysis summary — 1-line reasoning. Full reasoning in modal. | Text search |
| **Status** | Pipeline status for this company (see below) | Dropdown |

### Status Column (replaces separate Target true/false column)

Status is a **single column** showing the current pipeline state of each company:

| Status | Color | Meaning |
|--------|-------|---------|
| `gathered` | gray | Just found by Apollo, not yet processed |
| `blacklisted` | red | Rejected by blacklist check |
| `filtered` | gray | Removed by pre-filter (trash domain, too small) |
| `scraping` | blue | Website scrape in progress |
| `scraped` | default | Website scraped successfully |
| `scrape_failed` | orange | Website scrape failed |
| `analyzing` | blue | GPT analysis in progress |
| `target` | green | GPT marked as target (final positive) |
| `rejected` | gray | GPT marked as not-target (final negative) |
| `verifying` | blue | FindyMail verification in progress |
| `verified` | green + bold | Target with verified emails |

No separate "target true/false" column. Status tells the full story.

---

## Company Detail Modal (on row click)

Opens a modal (same pattern as CRM ContactDetailModal) with tabs:

### Tab 1: Details
- All Apollo fields: domain, name, industry, employee count, revenue, founded year, city, state, country, phone, LinkedIn URL
- Description (if available)
- **Source link**: clickable link to the company on Apollo (`https://app.apollo.io/...`)
- Website link
- Status badge

### Tab 2: Analysis
- GPT prompt that was used (full text)
- GPT reasoning (full text, not truncated)
- Confidence score with visual indicator
- Segment classification
- Iteration # that produced this analysis

### Tab 3: Scrape
- Scraped website text (first 500 chars preview, expandable)
- Scrape status, HTTP code, text size
- Scrape timestamp
- Error message if failed

### Tab 4: Source
- Raw Apollo data (JSON, collapsible)
- All 70 fields Apollo returned for this company
- SIC/NAICS codes, headcount growth, funding info

---

## Prompts Subpage (`/pipeline/:runId/prompts`)

Navigated to from the "Prompts" button in the top bar.

### Table columns:

| Column | Description | Filter |
|--------|-------------|--------|
| **Created** | When the prompt was created | Date |
| **Prompt ID** | Unique identifier, selectable by query string and by embedded filter with searchable autocomplete | Autocomplete search |
| **Iteration** | Which iteration used this prompt — clickable link back to main pipeline page with iteration filter applied | Link |
| **Prompt Body** | The full GPT prompt text (truncated in table, full in modal) | Text search |
| **Passed Companies** | How many companies this prompt was applied to | Number |
| **Identified Targets** | How many companies were marked as targets | Number |
| **Accuracy** | Accuracy as measured by MCP's verification agent (Opus comparing against independent assessment) | Number |

Clicking a row opens the prompt detail (full body, comparison with parent prompt if exists).

---

## Apollo Filters Subpage (`/pipeline/:runId/filters`)

Navigated to from the "Apollo Filters" collapsible panel.

### Table columns:

| Column | Description |
|--------|-------------|
| **Created** | When filters were applied |
| **Iteration** | Which run — clickable link back to main page with filter applied |
| **Keywords** | Apollo keyword tags |
| **Locations** | Countries/cities |
| **Employee Range** | Size filter |
| **Funding Stage** | If applied |
| **Pages Fetched** | How many Apollo pages |
| **Companies Found** | Raw count from Apollo |
| **Targets from This Set** | How many became targets |

---

## Loading State

When gathering is in progress:
- Table shows already-gathered companies
- **Spinner at the bottom** of the table with text: "Gathering in progress... X companies found so far"
- New companies appear in real-time as they're gathered (polling every 5s or SSE)
- No blocking — user can browse already-found companies while gathering continues

When scraping is in progress:
- Each company row updates its "Scraped Website" column in real-time
- Scraping companies show `scraping` status with a spinner icon

When analyzing is in progress:
- Each company row updates its "Website Analysis" and "Status" columns in real-time
- Companies being analyzed show `analyzing` status

---

## What to REMOVE from current implementation

- Checkpoint History section at the bottom — not needed
- Separate "Confidence" column — confidence is shown in the modal under Analysis tab
- Horizontal phase bar — replaced by the Stage dropdown indicator
- Stats row (63 companies, 50 new...) — replaced by table count + filter feedback
- Inline expandable rows — replaced by modal (same as CRM)

---

## Key UX Principles

1. **Same table pattern as CRM** — embedded column filters, click-to-modal, lazy loading
2. **Iterations are first-class** — user can switch between iterations or view all combined
3. **Status tells the story** — single column from `gathered` → `target`/`rejected`, no separate boolean
4. **Prompts and filters are trackable** — subpages with full history, linked back to main table
5. **Progress is visible** — spinners during gathering/scraping/analyzing, real-time updates
6. **Modal has everything** — Apollo raw data, GPT reasoning, scrape text, source link
