# Apollo MCP Behaviour — UX Analysis

Tested 2026-03-25 using `@thevgergroup/apollo-io-mcp@latest` (v2.2.0) — the most widely used community Apollo MCP. No official first-party Apollo MCP exists.

## What we tested

Apollo API directly + the community MCP server, with the same query types our pipeline uses:
- Organization search (company discovery)
- People search (free, no credits)
- People enrichment (email reveal, 1 credit/person)
- Organization enrichment (1 credit/company)
- Multi-page pagination
- Rate limiting behavior

~10 credits spent (out of 100 budget).

---

## Apollo MCP: 9 Tools

| Tool | What it does | Credits |
|------|-------------|---------|
| `apollo_search_people` | Search people with filters (titles, locations, seniority) | FREE |
| `apollo_search_companies` | Search companies with filters (keywords, location, size) | 1/page |
| `apollo_enrich_person` | Get email/phone for one person | 1/person |
| `apollo_enrich_company` | Get company details by domain | 1/company |
| `apollo_bulk_enrich_people` | Reveal emails for multiple people | 1/person |
| `apollo_bulk_enrich_organizations` | Enrich multiple companies | 1/company |
| `apollo_get_organization_job_postings` | Job postings by org ID | FREE |
| `apollo_get_complete_organization_info` | Full org details by ID | FREE |
| `apollo_search_news_articles` | News articles about companies | FREE |

## Critical UX Findings

### 1. ZERO confirmation before spending credits

The Apollo MCP has **no approval gates, no confirmation prompts, no cost warnings**. When Claude calls `apollo_enrich_person`, it immediately hits the API and spends 1 credit. There is no way for the operator to intervene.

If Claude decides to loop through 500 companies calling `apollo_bulk_enrich_people`, nothing stops it. The only protection is the AI's own judgment based on tool descriptions (which don't mention credit costs).

**Our advantage**: Our MCP has 3 mandatory checkpoints (CP1/CP2/CP3) that physically block the pipeline. FindyMail spend is gated behind CP3 approval. Apollo org search pages are tracked via `credits_used` on the GatheringRun.

### 2. No rate limiting awareness

Apollo allows ~200 req/min on paid plans. The MCP makes no attempt to throttle. 5 rapid requests all returned 200 in ~310ms each — no 429s at this volume. But sustained high-volume calls would hit limits.

**Our approach**: 0.3s delay between calls in `apollo_service.py`, exponential backoff on 429 (30s/60s/120s).

### 3. Search returns HIDDEN emails — enrichment is a separate paid step

`apollo_search_people` returns names, titles, and LinkedIn URLs but **emails are obfuscated** (last names show as "?" in search). You must call `apollo_enrich_person` or `apollo_bulk_enrich_people` (1 credit each) to reveal contact info.

This is the same 2-step flow our pipeline uses: search (free) → enrich (paid, gated behind CP3).

### 4. Organization search returns 0 results at per_page=5

Apollo's `/mixed_companies/search` sometimes returns 0 organizations when `per_page` is very low (5), even when `total_entries` shows 644. Works fine at per_page=25. This appears to be an API quirk.

**Our default**: per_page=25 in the Apollo adapter, which works reliably.

### 5. Pagination is inconsistent across pages

With the same query, page counts vary: page 1 returned 5 orgs, page 2 returned 7, page 3 returned 9, page 4 returned 18. Total available was 4,073 across 163 pages. The API doesn't guarantee uniform page sizes.

**Our approach**: We track `raw_results_count` and `new_companies_count` separately, dedup on domain, and report actual vs expected.

### 6. Tool descriptions don't mention credit costs

The Apollo MCP tool descriptions say things like "Search for people in Apollo with advanced filtering options" but never mention that enrichment costs credits. The AI has no way to know it's spending money unless it already knows Apollo's pricing model.

**Our advantage**: Our `tam_list_sources` tool explicitly states costs per source. The pipeline physically blocks at CP3 with a dollar estimate before any credit-spending step.

### 7. No deduplication or state management

Each Apollo MCP call is stateless. If you search the same companies twice, you get duplicate results and burn credits again. There's no run tracking, no history, no "already seen this domain" logic.

**Our advantage**: `DiscoveredCompany` table with unique constraint on (project_id, domain). Dedup happens at gather time. `GatheringRun` tracks every search with filter hash for replay detection.

### 8. No pipeline concept — just raw API wrappers

The Apollo MCP is 9 thin API wrappers. There's no workflow, no phases, no "gather → filter → analyze → verify" progression. The AI must orchestrate everything manually, deciding when to search, when to enrich, and how to combine results.

**Our advantage**: `run_full_pipeline` tool handles the entire flow with phase enforcement. The AI (or operator) just approves checkpoints.

---

## Patterns Stolen for Our MCP

### Good patterns (adopted)

1. **Filter schema in tool descriptions** — Apollo MCP puts detailed filter docs in `inputSchema.properties.filters.properties`, with descriptions like "Employee count ranges in comma format (e.g., ['11,20', '21,50'])". We do the same in `tam_gather`.

2. **Per-page pagination params** — `page` and `per_page` as direct tool params, not buried in filters. Clean UX.

3. **Separation of search (free) vs enrich (paid)** — The 2-step pattern is correct. Don't auto-enrich on search.

### Bad patterns (avoided)

1. **No credit cost in tool descriptions** — We explicitly document costs in `tam_list_sources` and CP3 scope.

2. **No confirmation on paid operations** — We have 3 mandatory checkpoints.

3. **No state/history** — We track everything in GatheringRun + DiscoveredCompany.

4. **Bulk operations without limits** — `apollo_bulk_enrich_people` takes an unbounded array. We cap at user-specified `max_pages` and per_page.

5. **`execution.taskSupport: "forbidden"`** — Apollo MCP disables MCP task support (long-running operations). We use SSE progress notifications instead.

---

## Community MCP Options (for reference)

| Package | Tools | Safety | Install |
|---------|-------|--------|---------|
| `@thevgergroup/apollo-io-mcp` | 9 | None | `npx @thevgergroup/apollo-io-mcp@latest` |
| `Chainscore/apollo-io-mcp` | 45 | Credit costs in descriptions | Clone + build |
| `BlockchainRev/apollo-mcp-server` | 34 | **DANGEROUS**: has `email_send`, `sequence_activate` | Python, uv |

**Recommendation**: None of these should be used in production. They bypass all safety rules (no confirmation, no gates, raw API access). Our MCP system is strictly better for our use case.
