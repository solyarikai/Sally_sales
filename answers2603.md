# Answers to requirements_source.md — 2026-03-26

Decisions and rationales for every question, concern, or "decide yourself" raised.

---

## 1. Cloud vs local deployment

> "what is better for usage of this stuff? For operator to use, like, to deploy instantly his own databases locally and run everything locally, or it should be directly on my cloud"

**Decision**: Cloud (Hetzner). Already implemented this way.

**Rationale**: Users connect via MCP protocol (SSE) to your server. No local Docker setup for them. Their machine only runs Claude Desktop / Cursor. Single deployment = one codebase to monitor, one DB to back up, simpler onboarding (just paste the MCP URL).

---

## 2. Apollo MCP vs direct API integration

> "Apollo has MCP. Is it for my purpose efficient to integrate with another MCPs? Or as you know all endpoints, it's more efficient to just use API integration?"

**Decision**: Direct API. Already implemented via `apollo_service.py`.

**Rationale**: Apollo's MCP is a general-purpose wrapper. You need specific control: credit limits per call, probe-first-then-gather pattern, filter auto-discovery via `filter_intelligence.py`. Wrapping an MCP inside your MCP adds latency and removes control over credit spend. The 5 endpoints you actually use (search, enrich, people match) are trivial to call directly.

---

## 3. MCP auto-refinement to 90% accuracy

> "is it possible that MCP asks like really agent using this MCP to verify yourself these targets?"

**Decision**: Yes, implemented two approaches that coexist.

1. **Agent-driven loop** (current, working): `tam_analyze` + `tam_re_analyze` MCP tools. Opus reviews GPT's targets, finds false positives, rewrites the prompt, calls re-analyze. Iterates until satisfied. This is the primary path.
2. **Automated refinement** (`refinement_engine.py`, 193 lines): GPT-4o-mini analyzes, GPT-4o verifies a stratified sample, Gemini improves the prompt. Runs without agent intervention. Exists but NOT end-to-end tested in production.

**What remains**: The automated engine needs real-world testing. The agent loop works today and is more reliable because Opus can reason about domain-specific FP patterns GPT misses.

---

## 4. UX for auth: signup vs API token

> "API TOKEN IS PROBABLY MORE SIMPLE FOR AUTH"

**Decision**: API token. Already implemented.

**Rationale**: `POST /api/auth/signup` returns `mcp_<32hex>` token. User pastes it into Claude Desktop config once. No JWT refresh, no OAuth redirect, no session expiry. Token stored as bcrypt hash. Multiple tokens per user for revocation. Token prefix shown in UI for identification.

---

## 5. SSE notifications

> "SSE notifications probably better"

**Decision**: SSE via MCP protocol + Redis pub/sub. Already implemented in `mcp/progress.py`.

**Rationale**: MCP protocol natively supports SSE. Progress updates (scraping 23/78, analysis iteration 3/8) stream to Claude Desktop in real-time. Redis pub/sub bridges background tasks to the SSE connection.

---

## 6. Isolation from existing system

> "MAKE THIS NEW TOOL TOTALLY INDEPENDENT OF CURRENT SYSTEM... CONTAINERS EVEN NOT AFFECT EACH OTHER"

**Decision**: Fully isolated. Separate docker-compose, ports, DB, Redis, network. Already implemented.

| Resource | Existing | MCP |
|----------|----------|-----|
| Postgres | :5432, `leadgen` | :5433, `mcp_leadgen` |
| Redis | :6379 | :6380 |
| Backend | :8000 | :8002 |
| Frontend | :80 | :3000 |

**Code sharing strategy**: Frontend uses `@main` alias to import CRM and Tasks pages from main app (fix once = fixed everywhere). Backend services are copied, not imported at runtime. Models share structure but have independent Base classes.

---

## 7. UI pages to keep

> "there will be only useful pages: pipeline, tasks with replies, project page, actions page, knowledge/learning"

**Decision**: 7 pages in MCP UI.

| Page | Status | Source |
|------|--------|--------|
| Setup (API keys) | DONE | MCP-native |
| Projects | DONE | MCP-native |
| Pipeline (company table + filters + modal) | DONE | MCP-native |
| Prompts (iteration history) | DONE | MCP-native |
| Account | DONE | MCP-native |
| CRM (contacts table) | DONE | Reused from @main via alias |
| Tasks/Replies | DONE (stub) | Reused from @main via alias |

**NOT building** (explicitly excluded): Analytics page, Monitoring page, separate Targets page. Pipeline page already shows targets inline with status column.

---

## 8. Reusable UI kit / backend shared between old and new

> "I want what I fix in one place to be fixed in both applications"

**Decision**: Frontend shares via `@main` Vite alias. Backend does NOT share at runtime.

**Frontend**: `import { ContactsPage } from '@main/pages/ContactsPage'` resolves to `frontend/src/pages/ContactsPage.tsx` in the main app. Theme, Toast, table components all shared. Change in main app = change in MCP UI.

**Backend**: Services copied. Intentional. Backend isolation matters more than DRY because: (a) MCP adds per-user key injection (`UserServiceContext`), (b) MCP has refinement engine, filter intelligence, (c) independent deployability. The cost of copy-drift is low since the pipeline logic is stable.

---

## 9. Pipeline page: what user sees for each company

> "I want to see all filters, all data Apollo provided, GPT reasoning, prompt applied, everything"

**Decision**: Implemented in PipelinePage.tsx company modal with 4 tabs.

- **Details tab**: domain, industry, employees, revenue, founded year, headcount growth, keywords, Apollo link, country, city
- **Analysis tab**: GPT reasoning (full text), confidence score, segment label, target/rejected status, prompt that was applied
- **Scrape tab**: full scraped website text, HTTP status, scrape timestamp, text size
- **Source tab**: raw `source_data` JSON from Apollo (all original fields)

The table columns show: domain, name, industry, employees, country, keywords, status (gathered/scraped/target/rejected/verified), segment, confidence, contacts count. Each column has embedded filter dropdowns.

---

## 10. Iterations (different Apollo filters or GPT prompts = same pipeline)

> "one business segment per pipeline, but might be gathered in different ways"

**Decision**: Implemented. Each `GatheringRun` is an iteration within a project. PromptsPage shows all iterations with their filters and prompts. Pipeline page shows companies from all runs for a project, filterable by run.

**Current gap**: No dedicated "Apollo filters applied" sub-page. The filters are visible in the run detail and in the Prompts page, but there's no per-filter "how many targets came from this keyword" breakdown. This is a remaining item.

---

## 11. Campaign timing: 9-18 in target country timezone

> "CAMPAIGN TIMING MUST BE FROM 9 TILL 6 FOR THE TIMEZONE OF GATHERED CONTACTS"

**Decision**: Implemented in `smartlead_service.py`. `COUNTRY_TIMEZONES` maps 30+ countries to IANA zones. `god_push_to_smartlead` MCP tool requires `target_country` parameter. Campaign schedule set to Mon-Fri 9:00-18:00 in that timezone.

---

## 12. Email accounts for campaign creation

> "Which email accounts to use? List accounts used in campaigns stated as used before"

**Decision**: Implemented. `list_email_accounts` MCP tool fetches accounts from SmartLead. `god_push_to_smartlead` tool description says "BEFORE calling this, you MUST ask the user which accounts" and "call list_email_accounts first to show options."

**Remaining gap**: The tool exists in tools.py but the SmartLead service endpoint for listing accounts per campaign needs testing. The dispatcher wiring should be verified.

---

## 13. Apollo filter auto-discovery (user should NOT pick keywords)

> "user mustn't be engaged into this shit, it must be our superfeature"

**Decision**: Implemented. `filter_intelligence.py` (305 lines) + `suggest_apollo_filters` MCP tool.

Flow: User says "find IT consulting in London." Agent calls `suggest_apollo_filters(query="IT consulting in London")`. Service calls GPT to generate candidate filters, probes Apollo with 1 credit, scrapes top 10 websites, returns results to agent. Agent evaluates quality, adjusts if needed. User never sees keyword lists.

**Remaining gap**: Background cron to discover/update Apollo industry taxonomy. The `apollo_filters/PLAN.md` (199 lines) describes the approach but the cron is not implemented.

---

## 14. Background reply analysis in parallel with blacklist

> "AFTER KNOWING USER'S CAMPAIGNS THE SYSTEM MUST LAUNCH ANALYSIS OF CONNECTED CAMPAIGNS REPLIES IN BACKGROUND"

**Decision**: `reply_analysis_service.py` exists (140 lines) with keyword-based classification. It classifies replies into: meeting, interested, question, not_interested, out_of_office, wrong_person, unsubscribe.

**Remaining gap**: NOT wired to run automatically when campaigns are imported. Currently a standalone service that needs to be called. Needs: (a) trigger from `import_smartlead_campaigns`, (b) actual SmartLead reply fetching (currently just classification logic), (c) storing results in DB so CRM can filter by reply type.

---

## 15. CRM deep links with filters

> "with links in CRM to certain-way filtered contacts"

**Decision**: `query_contacts` MCP tool returns a `crm_link` with filter params applied. CRM page from @main supports URL query params for filtering.

**Remaining gap**: The `crm_link` construction exists in the tool dispatcher but the actual CRM page URL param handling (e.g., `?reply_category=interested&project=5`) needs testing end-to-end.

---

## 16. Probing: scrape via Apify or let Opus visit websites?

> "scrape probe companies websites via apify so that opus can analyze their website content -- or easier ask opus to visit websites?"

**Decision**: Apify scrape (implemented in `filter_intelligence.py`).

**Rationale**: Opus cannot visit URLs. The agent reads scraped text returned by the tool. Apify residential proxy scraping is free, parallel (10 sites in ~3s), and returns clean text. This is exactly what the probe-and-iterate loop does.

---

## 17. Post-GPT verification by Opus (batches, via negativa, segments)

> "those X MUST BE ANALYZED BY OPUS UNTIL THERE ARE DEFINITELY TARGET, gpt PROMPT must focus on excluding shit VIA NEGATIVA"

**Decision**: Implemented as the agent loop pattern. GPT does the cheap bulk analysis via negativa. Opus reviews GPT's output at CP2. If false positives found, Opus adjusts the prompt and calls `tam_re_analyze`. This loops until 90%+ accuracy.

**Segment labels**: GPT assigns CAPS_LOCKED segment labels (IT_OUTSOURCING, SAAS_COMPANY, AGENCY, etc.) during analysis. Shown in pipeline table and company modal.

**Batching**: For large volumes, multiple sequential `tam_re_analyze` calls. No parallel agent spawning (not possible in current MCP architecture).

---

## 18. Only Opus for probing, GPT for pipeline

> "in probing for best quality on small volume only opus, but for pipeline after gpt as need scalable approach once 90% accuracy achieved"

**Decision**: Correct and implemented.

- **Probing** (filter_intelligence.py): Opus evaluates 10-15 company summaries + website excerpts directly. No GPT intermediary.
- **Pipeline** (gathering_service.py): GPT-4o-mini analyzes 100+ companies at $0.003 each. Opus reviews results at checkpoints.

---

## 19. Sequence subject line normalization

> "subject either company names or person first names ALL NORMALIZED, names without any shit, human readable"

**Decision**: This is a gap in `campaign_intelligence.py`. The sequence generation uses Gemini 2.5 Pro which should produce clean names, but there is no explicit post-processing step to normalize `{{first_name}}` or `{{company}}` merge tags.

**Action needed**: Add normalization in `push_to_smartlead` — strip special chars, capitalize properly, verify merge tag syntax matches SmartLead's expected format.

---

## 20. Test email sending after campaign creation

> "AFTER CREATING TEST CAMPAIGN SEND TEST EMAIL TO THE ACCOUNT OF THE USER"

**Decision**: Not implemented. SmartLead has `POST /api/v1/campaigns/{id}/test-email` endpoint.

**Action needed**: Add `send_test_email` call after `god_push_to_smartlead` succeeds. Use the user's signup email as the test recipient.

---

## 21. Conversation tab in CRM contact detail

> "when you click on contact, first tab is conversation tab — planned sequence OR already happened conversation"

**Decision**: Not implemented in MCP CRM. The @main CRM contact detail shows conversation history for existing replies but does not show the planned/scheduled sequence.

**Action needed**: Add sequence preview to contact detail modal — show the generated sequence steps with their scheduled timing. This requires joining extracted_contacts with generated_sequences through the pipeline run.

---

## 22. How many companies gathered by default?

> "How many companies will be gathered by default?"

**Decision**: 10 target companies (test mode). The `target_count` parameter on `tam_gather` defaults to 10. At ~30% target rate, this means gathering ~33 companies from Apollo (~1 page). For production, user specifies the number.

---

## 23. Learning page

> "knowledge page, only for about how learning was made from actions for specific replies"

**Decision**: Not implemented. The Prompts page shows GPT prompt iterations but not operator-correction-based learning.

**Action needed**: Build a Learning page showing: operator corrections (sent vs suggested), learned patterns, quality scores over time. Low priority until reply tracking is wired up.

---

## 24. Onboarding: Telegram notification prompt

> "AFTER IMPLEMENTING ABOVE, test how connecting to mcp behaves, describe initial flow for a new user"

**Decision**: Not implemented. No Telegram integration in MCP. The main app sends Telegram notifications; MCP does not.

**Action needed (low priority)**: After reply tracking works, add optional Telegram bot token configuration in Setup page. For now, the MCP agent itself IS the notification channel (it tells the user about new replies via the chat interface).

---

## 25. Track every user interaction

> "track every person interaction with you in database so that I can see what people write to this MCP"

**Decision**: Implemented via `MCPUsageLog` table. Every MCP tool call is logged with: user_id, tool_name, action, metadata (input params, result summary), timestamp. Visible via `GET /api/pipeline/usage-logs`.

**Remaining gap**: The raw conversation text (what user typed to Claude) is NOT stored — only the tool calls. Full conversation logging would require MCP protocol-level middleware.
