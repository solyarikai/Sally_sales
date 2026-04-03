# MCP Implementation Plan — 2026-03-30

**Sources**: default_requirements.md, exploration.md, requirements_source.md, Pavel's bugs, AGENT_MODULES_20260330.md
**What exists**: 55 audit fixes, exploration tests (5 steps), prompt_tuner.py, filter_mapper.py, taxonomy (2K keywords)

---

## Default SmartLead Campaign Flow — Line-by-Line Requirements Checklist

From default_requirements.md — EVERY line mapped to implementation status:

| # | Requirement | Status | What's missing |
|---|-------------|--------|---------------|
| 1 | Before MCP token → only "go sign up" message | ✅ Tool descriptions say this | Enforcement in SSE greeting |
| 2 | After token → "provide Apollo, OpenAI, SmartLead, Apify keys" | ⚠️ Works via configure_integration | MCP should auto-check and tell what's missing |
| 3 | Keys set ONLY via UI (Setup page) for security | ❌ Keys can be set via MCP tool too | Remove key from tool args OR accept both |
| 4 | After keys → "which segments?" | ⚠️ Not automatic | MCP doesn't auto-detect keys set in UI |
| 5 | Before gathering → must know offer/website | ✅ Offer gate in tam_gather | Implemented |
| 6 | Scrape website → extract offer → create project | ✅ create_project scrapes | Working |
| 7 | "Have you launched campaigns before?" | ❌ NOT ASKED | No tool/flow asks about previous campaigns |
| 8 | Load previous campaign contacts → blacklist | ⚠️ Works via set_campaign_rules | Not automatically triggered |
| 9 | Company size auto-inferred from offer | ✅ offer_analyzer.py exists | Needs wiring into filter mapper |
| 10 | Show filter preview + Apollo total + cost | ✅ Implemented today | confirm_filters gate |
| 11 | Replies processing in background after campaigns loaded | ✅ Bug fix: background analysis trigger | In tam_blacklist_check |
| 12 | Link to CRM after campaign contacts loaded | ⚠️ Links returned in responses | Not auto-triggered with filters |
| 13 | "Which email accounts?" asked WHILE gathering | ❌ NOT ASKED automatically | Only checked at push time |
| 14 | Email accounts from previous campaigns by name | ⚠️ list_email_accounts shows campaign associations | Agent must know to filter |
| 15 | People filters = C-level by default, offer-adjusted | ❌ NOT IMPLEMENTED | No people filter selection step |
| 16 | After people gathered → campaign with sequence | ✅ god_generate_sequence + push | Working |
| 17 | Test email sent automatically after push | ✅ Auto in god_push_to_smartlead | Working |
| 18 | Response includes: SL link, CRM link, "check inbox", "approve" | ⚠️ SL link + inbox yes | CRM link with campaign filter missing |
| 19 | User can edit sequence before activation | ✅ edit_sequence_step tool | Working |
| 20 | Activation requires explicit approval | ✅ user_confirmation required | Working |
| 21 | Warm replies / followup questions answered | ✅ replies_summary, replies_list, replies_followups | Working |
| 22 | ONE question at a time, never multiple | ❌ NOT ENFORCED | Tools can return multi-question responses |
| 23 | Exploration: enrich top 5 → reverse-engineer filters | ✅ tam_explore tool | Just wired today |
| 24 | At least 100 contacts per campaign (3/company) | ❌ No target enforcement | Pipeline doesn't check if enough contacts gathered |
| 25 | Pipeline iterations tracked in UI | ✅ PipelineIteration model | Other agent building |
| 26 | All links include proper filters in query string | ⚠️ Some links correct | CRM links missing campaign filter |

---

## Exploration Requirements Checklist

From exploration.md:

| # | Requirement | Status | What's missing |
|---|-------------|--------|---------------|
| 1 | Keyword map, industry map, employee range map | ✅ taxonomy_service.py (2K keywords, 112 industries) | JSON file, not DB |
| 2 | Maps grow from each enrichment call | ✅ add_from_enrichment method | Working |
| 3 | Embedding pre-filter for keywords | ✅ filter_mapper.py | Working |
| 4 | Per-filter-type agent (keywords, industries, size, location) | ❌ Single GPT call instead | Plan says single call is better (coherent output) |
| 5 | Initial intent → split into segments | ✅ parse_gathering_intent | Working |
| 6 | Each segment maps to Apollo filters | ✅ filter_mapper | Working |
| 7 | Confirm filters before running | ✅ Implemented today | Working |
| 8 | Exploration: search → scrape → classify → enrich top 5 | ✅ exploration_service.py | Wired via tam_explore |
| 9 | Filter optimization from enrichment | ✅ _build_optimized_filters | In exploration_service |
| 10 | Prompt improvement loop until 90%+ | ✅ prompt_tuner.py | Other agent building |
| 11 | User feedback → re-analyze same companies | ✅ tam_re_analyze | Working |
| 12 | BUILDS vs USES distinction in via negativa | ✅ Added to gathering_service | Implemented |
| 13 | gpt-4.1-mini for prompt creation, gpt-4o-mini for application | ✅ Implemented | In gathering_service |
| 14 | Example companies → reverse-engineer filters | ✅ tam_enrich_from_examples | Implemented today |
| 15 | Cases dir: user provides strategy doc | ⚠️ Tool exists | User's Opus must extract and pass to MCP |

---

## What's Actually Working End-to-End Right Now

A user connecting via Claude Code can:
1. ✅ Login with token
2. ✅ Configure integrations (SmartLead, Apollo, OpenAI, Apify, GetSales)
3. ✅ Create project with website scraping
4. ✅ Gather companies (Apollo API, CSV, Sheet, Drive)
5. ✅ See filter preview with total_available + cost breakdown
6. ✅ Blacklist check with project-scoped isolation
7. ✅ Scrape websites with Apify proxy
8. ✅ Classify targets with domain-specific rules (gpt-4.1-mini creates, gpt-4o-mini applies)
9. ✅ Re-analyze with feedback (tam_re_analyze)
10. ✅ Exploration enrichment (tam_explore) — discover better keywords
11. ✅ Reverse-engineer from examples (tam_enrich_from_examples)
12. ✅ Generate sequence + approve
13. ✅ Push to SmartLead (DRAFT) + auto test email
14. ✅ Activate campaign + auto-enable monitoring
15. ✅ Reply intelligence (summary, list, followups)
16. ✅ Session continuity (get_context restores state)

---

## What's NOT Working — Implementation Priority

### P0: Critical flow gaps (default_requirements violations)

| # | Gap | Effort | Impact |
|---|-----|--------|--------|
| 1 | **"Which email accounts?"** not asked automatically during gathering | 2h | Flow breaks at push — no accounts selected |
| 2 | **"Previous campaigns?"** not asked after project creation | 2h | No blacklist loaded, contacts may be re-contacted |
| 3 | **People filters** not auto-adjusted to offer (C-level default, no mapper) | 3h | Wrong contacts gathered (HR for payroll vs CEO for SaaS) |
| 4 | **CRM links** missing campaign filter in query string | 1h | User sees all contacts, not filtered to new campaign |
| 5 | **100 contacts minimum** not enforced — pipeline doesn't check count | 2h | Campaign may launch with 5 contacts |
| 6 | **One question at a time** not enforced in tool responses | 1h | UX violation — user confused by multi-question responses |

### P1: Exploration integration (other agent building)

| # | Gap | Effort | Who |
|---|-----|--------|-----|
| 7 | PipelineIteration model + migration | 2h | Other agent (in progress) |
| 8 | Prompt tuner integration into tam_re_analyze | 2h | Other agent (building prompt_tuner.py) |
| 9 | Exploration auto-run after Checkpoint 2 | 1h | Wire tam_explore into analyze response |
| 10 | Taxonomy to pgvector DB (from JSON file) | 4h | Migration + embed on insert |

### P2: Quality + UX

| # | Gap | Effort |
|---|-----|--------|
| 11 | Pavel's iGaming test — verify domain-specific rules work | 2h |
| 12 | Account page: credit breakdown by project/date | 3h |
| 13 | Pipeline UI: iteration selector + filter history | 3h |
| 14 | Cost estimation: $20/mo for 20 campaigns — calculate and display | 2h |

---

## Flow Gaps Detail

### Gap 1: Email accounts must be asked during gathering

**Requirement**: "while pipelines are gathering, tell which email accounts to use"
**Current**: Email accounts only checked at push time (god_push_to_smartlead requires them)
**Fix**: After tam_gather starts, the response should include: "While gathering runs, which email accounts should we use? Here are yours: [list]"
**Implementation**: Add to tam_gather response (after confirm_filters=true succeeds):
```python
return {
    ...,
    "next_question": {
        "type": "email_accounts",
        "message": "While gathering runs, which email accounts to use for the campaign?",
        "accounts": accounts_list,
    }
}
```

### Gap 2: Previous campaigns must be asked

**Requirement**: "have you launched campaigns for this project before?"
**Current**: Never asked. User must know to call set_campaign_rules.
**Fix**: After create_project, response should include: "Before gathering, have you launched campaigns for [project] before? If yes, tell me the campaign name pattern for blacklist."
**Implementation**: Add to create_project response.

### Gap 3: People filters auto-adjusted

**Requirement**: "adjust people filters to the offer"
**Current**: No people filter selection. Apollo people search uses defaults.
**Fix**: Add A7 agent — People Filter Mapper:
- Input: offer description
- Output: {titles: ["VP HR", "CHRO", ...], seniorities: ["director", "vp"]}
- For payroll: HR/Finance. For SaaS: CTO/VP Engineering. For fashion: Brand Director.

### Gap 5: 100 contacts minimum enforcement

**Requirement**: "100 contacts must be in each campaign"
**Current**: Pipeline gathers whatever Apollo returns, no minimum check.
**Fix**: After classification, if targets < 34 (100 contacts / 3 per company):
- Auto-suggest: "Only {N} targets found. Need at least 34 for 100 contacts. Want to expand search with broader filters?"
- If user says yes → re-search with expanded keywords/size ranges

---

## What Other Agent Is Building (from screenshot)

1. ✅ PipelineIteration model + migration
2. ✅ prompt_tuner.py — GPT prompt adjustment loop
3. 🔄 Wire enrichment → taxonomy map (Gaps 1-4)
4. 🔄 Enhanced MCP tool responses + agent feedback handler
5. 🔄 Tests: step-by-step exploration + full E2E

**My work should NOT overlap with theirs.** I focus on:
- Flow gaps (P0 items 1-6)
- Architecture docs
- Testing via real MCP SSE

---

## Other Agent's Test Results (from ~120 iterations)

The other agent ran 7 phases of testing. Key findings to incorporate:

| Phase | Iterations | Best result | Key learning |
|-------|-----------|-------------|-------------|
| 1. Classification prompt | 20 combos | gpt-4o-mini × via negativa = 87% target rate | Via negativa beats scoring |
| 2. Classification + ground truth | 15 combos | gpt-4o-mini × v9_negativa = **97% accuracy** | v9 prompt is the winner |
| 3. Intent parser | 40 combos | gpt-4o × p7_coverage = **94%** | Need smart model for intent |
| 4. Apollo API behavior | 23 API calls | Keywords=OR, industry names=8.5x, size=AND | Industry names as keywords give 8.5x more results |
| 5. E2E with keyword map | 9 tests | gpt-4.1-mini wins (18 targets) | Taxonomy-backed mapper beats GPT guessing |
| 6. Industry selection | 20 combos | gpt-4o-mini × self-check = **100%** | Industry picker is solved |
| 7. Final E2E | 3 segments | 50%/100%/30% target rates | OnSocial too broad (internet industry) |

**Filter evolution (EasyStaff IT consulting):**
- Hardcoded start: "IT consulting" → 2,063 companies
- + industry names: + "information technology & services" → 3,908 (+89%)
- + real Apollo tags: + "it services & it consulting" → 3,621

**Keyword map growth**: 0 → 1,491 (seed) → 2,014 (enrichment feedback)

**Gap identified by other agent**: Tests ran each step in isolation — never logged the full before→after picture of how filters and prompts evolved through the exploration loop. Test plan Layer 7 addresses this.

**Reference**: See [AGENT_MODULES_20260330.md](AGENT_MODULES_20260330.md) for agent definitions. See [TEST_PLAN_20260330.md](TEST_PLAN_20260330.md) for comprehensive test strategy.

---

## Testing Strategy

**Layer 1**: Unit tests (194 passing) — other agent maintains
**Layer 2**: REST dispatcher tests (15 conversations) — regression safety net
**Layer 3**: Real MCP SSE tests — the ONLY valid test (my responsibility)
**Layer 4**: Exploration quality tests (5 steps) — other agent building

All real tests write results to `tests/tmp/` with timestamps.
NO REST mock tests for new features — only real MCP SSE.
