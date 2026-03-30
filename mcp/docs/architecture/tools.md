# MCP LeadGen Tools — 26 Tools

Server: `http://46.62.210.24:8002/mcp/sse`

---

## Account (3)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 1 | `setup_account` | Create a new MCP account and get an API token. The token is shown once — save it. | `email`, `name` |
| 2 | `configure_integration` | Connect an external service (smartlead, apollo, findymail, openai, gemini) by providing your API key. Tests the connection automatically. | `integration_name`, `api_key` |
| 3 | `check_integrations` | List all connected integrations and their status. | — |

## Project (3)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 4 | `create_project` | Create a new sales project with ICP definition and sender identity. | `name` |
| 5 | `list_projects` | List all your projects. | — |
| 6 | `update_project` | Update a project's ICP or sender info. | `project_id` |

## Pipeline (9)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 7 | `tam_gather` | Phase 1: Gather companies from a source (Apollo, Clay, Google Sheets, CSV, manual domains). Creates a gathering run with deduplication. | `project_id`, `source_type`, `filters` |
| 8 | `tam_blacklist_check` | Phase 2: Check gathered companies against existing campaigns. Creates Checkpoint 1 gate. | `run_id` |
| 9 | `tam_approve_checkpoint` | Approve a pipeline checkpoint (CP1: scope, CP2: targets, CP3: cost). | `gate_id` |
| 10 | `tam_pre_filter` | Phase 3: Deterministic pre-filtering (remove trash domains, too-small companies). | `run_id` |
| 11 | `tam_scrape` | Phase 4: Scrape websites for all non-blacklisted companies. Free, no credits used. | `run_id` |
| 12 | `tam_analyze` | Phase 5: AI analysis to identify target companies. Optionally auto-refines until target accuracy reached. Creates Checkpoint 2 gate. | `run_id` |
| 13 | `tam_prepare_verification` | Creates Checkpoint 3 with FindyMail cost estimate before spending credits. | `run_id` |
| 14 | `tam_run_verification` | Phase 6: Run FindyMail email verification on approved targets. COSTS CREDITS. | `run_id` |
| 15 | `tam_list_sources` | List available gathering sources with their filter schemas. | — |

### Pipeline Flow

```
tam_gather → tam_blacklist_check → ★ CP1 (tam_approve_checkpoint)
  → tam_pre_filter → tam_scrape → tam_analyze → ★ CP2 (tam_approve_checkpoint)
  → tam_prepare_verification → ★ CP3 (tam_approve_checkpoint)
  → tam_run_verification
```

### Available Sources

| source_type | Description | Cost |
|-------------|-------------|------|
| `apollo.companies.api` | Apollo org search API | 1 credit/page |
| `apollo.people.emulator` | Apollo People tab via Puppeteer | Free |
| `apollo.companies.emulator` | Apollo Companies tab via Puppeteer | Free |
| `clay.companies.emulator` | Clay TAM export with ICP text | ~$0.01/company |
| `clay.people.emulator` | Clay People search by domains | ~$0.01/domain |
| `google_sheets.companies.manual` | Google Sheet import | Free |
| `csv.companies.manual` | CSV file/URL import | Free |
| `manual.companies.manual` | Direct domain list | Free |

## Refinement (2)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 16 | `refinement_status` | Get the current status of a self-refinement run: iteration count, accuracy history, patterns found. | `run_id` |
| 17 | `refinement_override` | Accept current accuracy and stop the refinement loop early. | `refinement_run_id` |

## GOD_SEQUENCE (5)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 18 | `god_score_campaigns` | Score and rank campaigns by quality (warm reply rate, meetings, volume). | — |
| 19 | `god_extract_patterns` | Extract reusable patterns from top-performing campaigns. | — |
| 20 | `god_generate_sequence` | Generate a 5-step email sequence using extracted patterns + project knowledge. | `project_id` |
| 21 | `god_approve_sequence` | Mark a generated sequence as approved. | `sequence_id` |
| 22 | `god_push_to_smartlead` | Push an approved sequence to SmartLead as a DRAFT campaign. Never activates or adds leads. | `sequence_id` |

### GOD_SEQUENCE Flow

```
god_score_campaigns → god_extract_patterns → god_generate_sequence
  → god_approve_sequence → god_push_to_smartlead
```

## Orchestration (2)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 23 | `run_full_pipeline` | Run the full pipeline end-to-end: gather → blacklist → filter → scrape → analyze (with optional auto-refine). Stops at each checkpoint for approval. | `project_id`, `source_type`, `filters` |
| 24 | `pipeline_status` | Get the current status of a pipeline run: phase, progress, next action needed. | `run_id` |

## Utility (2)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 25 | `estimate_cost` | Estimate the cost of a gathering run before starting. | `source_type`, `filters` |
| 26 | `blacklist_check` | Quick check: are these domains already in any campaign? | `domains` |

---

## Authentication

All tools (except `setup_account`) require an API token via:
- Header: `Authorization: Bearer mcp_...`
- Or: `X-MCP-Token: mcp_...`

## Claude Desktop Config

```json
{
  "mcpServers": {
    "leadgen": {
      "url": "http://46.62.210.24:8002/mcp/sse"
    }
  }
}
```
