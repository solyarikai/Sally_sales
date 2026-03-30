# MCP Agent Modules — Complete Registry

**Date**: 2026-03-30
**Rule**: One agent = one task. If an agent does two things, split it.

---

## Overview

```
USER MESSAGE → [A0: Router] → intent-specific chain → response
```

Every user message first hits the Router. The Router decides what the user wants, then hands off to the right chain. Each chain has its own guard (preflight) that knows exactly what data is needed.

---

## A0: ROUTER (intent classifier)

| Field | Value |
|-------|-------|
| **Model** | gpt-4o-mini |
| **Single task** | Classify user intent into one of ~12 categories |
| **Input** | Raw user message + session context (active project, phase, pending gates) |
| **Output** | `{intent: "gather", ...}` or `{intent: "edit_sequence", ...}` etc. |
| **Does NOT** | Execute anything. Ask questions. Make decisions. |

**Intent categories:**

| Intent | Description | Triggers chain |
|--------|-------------|---------------|
| `auth` | User provides MCP token | → Direct: login tool |
| `setup_keys` | User wants to configure API keys | → Direct: "go to Setup page [link]" |
| `create_project` | User describes their offer/company | → A1 guard → create_project |
| `gather` | User wants to find companies | → A1 guard → gathering chain |
| `gather_from_file` | User provides file/examples for gathering | → A1 guard → enrich-from-examples chain |
| `edit_sequence` | User wants to change campaign sequence | → A5 guard → edit tool |
| `edit_targets` | User overrides target/not-target | → A5 guard → override tool |
| `provide_feedback` | User gives classification feedback | → Direct: provide_feedback tool |
| `activate_campaign` | User wants to launch | → A6 guard → activate tool |
| `check_status` | User asks about pipeline/replies/credits | → Direct: get_context / pipeline_status / replies_summary |
| `re_analyze` | User wants to re-run classification | → Direct: tam_re_analyze |
| `approve_checkpoint` | User approves/rejects a gate | → Direct: tam_approve_checkpoint |

**Critical question: Should the Router be an MCP agent (gpt-4o-mini) or the user's agent (Opus)?**

Answer: The user's agent IS the router. When user says "gather IT consulting in Miami" in Claude Code, Opus decides to call `parse_gathering_intent` → `tam_gather`. MCP tools are already named clearly enough that Opus routes correctly.

**BUT** — Opus sometimes routes WRONG (Bug 2: auto-launched tam_gather without confirmation). So MCP tools THEMSELVES must enforce the correct flow. The guard is IN the tool, not a separate agent.

**Decision: No separate Router agent needed.** The user's agent (Opus) routes. MCP tools self-guard.

---

## Guards — Built into tools, not separate agents

Each tool that requires prerequisites checks them INSIDE the tool call. If something's missing, it returns an error telling what's needed. This is simpler and more reliable than a separate guard agent.

```python
# Example: tam_gather self-guards
if not project.target_segments:
    return {"error": "offer_unknown", "message": "What's your website?"}
if "api" in source_type and not args.get("confirm_filters"):
    return {"status": "awaiting_filter_confirmation", ...}
```

**Why not separate guard agents?**
1. Context would need to be passed between guard → executor (doubles API calls)
2. Guard would need to know all tool internals (tight coupling)
3. If guard passes but tool finds another issue → confusing double-error
4. Current approach: tool returns missing info, agent asks user, tool called again

---

## Agent Modules (MCP-side, each called via tools)

### A1: Intent Parser (`parse_gathering_intent`)

| Field | Value |
|-------|-------|
| **Model** | gpt-4o-mini |
| **Single task** | Split user's gathering query into segments with geo |
| **Input** | "IT consulting in Miami and video production in London" + offer context |
| **Output** | `[{segment: "IT consulting", geo: "Miami"}, {segment: "video production", geo: "London"}]` |
| **Does NOT** | Map to Apollo filters. Decide source. Calculate pages. |

**Scope critique:** Currently this agent also suggests competitor exclusions from the offer. That's fine — it's part of understanding the query. But it should NOT auto-select Apollo filters. That's A2's job.

---

### A2: Filter Mapper (`filter_mapper.py → map_query_to_filters`)

| Field | Value |
|-------|-------|
| **Model** | gpt-4.1-mini |
| **Single task** | Map segment description → Apollo filter set using taxonomy |
| **Input** | Segment query + offer text + industry map (112) + keyword shortlist (30-50 from embedding pre-filter) + employee ranges (8) |
| **Output** | `{industries: [...], keywords: [...], employee_ranges: [...], locations: [...]}` |
| **Does NOT** | Search Apollo. Classify companies. Generate sequences. |

**Sub-steps (inside A2, no separate agents needed):**
- Step A: Embedding pre-filter (pgvector, no GPT) → shortlist 30-50 keywords
- Step B: GPT picks from shortlists (one prompt, structured output)
- Step C: Location extraction (regex, no GPT)
- Step D: Assembly + validation (code, no GPT)

**Scope critique:** This is correct. One focused task. The model (gpt-4.1-mini) is appropriate — needs to reason about business segments but from constrained lists.

---

### A3: Classification Prompt Creator (inside `gathering_service.analyze`)

| Field | Value |
|-------|-------|
| **Model** | gpt-4.1-mini |
| **Single task** | Craft domain-specific via negativa exclusion rules for THIS segment |
| **Input** | Offer description + segment + user feedback (if any) |
| **Output** | 3-5 exclusion rules like "Casino operators USE the tech, they don't BUILD it → NOT_A_MATCH" |
| **Does NOT** | Apply the rules. Classify companies. |

**Why separate from A4:** Different model, different task. A3 needs business reasoning (gpt-4.1-mini). A4 just follows rules at scale (gpt-4o-mini).

---

### A4: Company Classifier (inside `gathering_service.analyze`)

| Field | Value |
|-------|-------|
| **Model** | gpt-4o-mini |
| **Single task** | Apply via negativa rules to ONE company's website text → target or not |
| **Input** | Company domain + scraped website text + via negativa rules (from A3) |
| **Output** | `{is_target: true/false, segment: "IGAMING_PLATFORM", reasoning: "..."}` |
| **Does NOT** | Decide rules. Adjust prompt. Handle feedback. |

**Runs in parallel** — up to 10 concurrent API calls. ~500 companies in ~60 seconds.

---

### A5: Sequence Generator (`campaign_intelligence.generate_sequence`)

| Field | Value |
|-------|-------|
| **Model** | gpt-4o-mini |
| **Single task** | Generate 4-5 step email sequence for SmartLead |
| **Input** | Offer context + project knowledge + campaign patterns |
| **Output** | `[{step: 1, day: 0, subject: "...", body: "..."}, ...]` |
| **Does NOT** | Push to SmartLead. Select email accounts. Activate campaign. |

---

### A6: Filter Optimizer (inside `exploration_service → _build_optimized_filters`)

| Field | Value |
|-------|-------|
| **Model** | gpt-4o-mini |
| **Single task** | Select which NEW keywords (from enrichment) to ADD to search filters |
| **Input** | Original keywords + new keywords discovered from top 5 targets + segment |
| **Output** | Optimized keyword_tags list (original + selected new ones) |
| **Does NOT** | Run the search. Enrich companies. Classify anything. |

---

## Agents NOT in MCP (run on user's side)

### U1: File Processor (User's Opus)

| Field | Value |
|-------|-------|
| **Model** | Claude Opus |
| **Single task** | Read large strategy docs/files → extract structured data for MCP |
| **Input** | 160-line brief, CSV with examples, strategy PDF |
| **Output** | Structured JSON: project, offer, segment, geo, size, examples, exclusions |
| **Why Opus** | Files can be 10K+ tokens. gpt-4o-mini context window is adequate but reasoning is not. Opus reads, understands business context, produces clean JSON. |

### U2: Quality Reviewer (User's Opus)

| Field | Value |
|-------|-------|
| **Model** | Claude Opus |
| **Single task** | Review target list, provide corrections and feedback |
| **Input** | Target companies with segments and reasoning |
| **Output** | "Roobet is an operator, not a provider. Exclude operators." |
| **Why Opus** | Needs domain expertise and judgment that gpt-4o-mini lacks |

---

## Execution Order — Gathering Chain

```
User: "gather iGaming providers in Malta"
                    │
                    ▼
[GUARD: offer known?] ─── NO → "What's your website?" → wait
                    │
                   YES
                    │
                    ▼
A1: Intent Parser → [{segment: "iGaming providers", geo: "Malta"}]
                    │
                    ▼
A2: Filter Mapper → {keywords: [...], industries: [...], size: [...]}
                    │
                    ▼
[GUARD: confirm?] → Show preview + total_available + cost → wait for "yes"
                    │
                   YES
                    │
                    ▼
Apollo Search (1-4 credits) → N companies
                    │
                    ▼
Blacklist Check → M companies passed
                    │
                    ▼
[CHECKPOINT 1: approve scope?] → wait
                    │
                   YES
                    │
                    ▼
Scrape Websites (Apify proxy, free)
                    │
                    ▼
A3: Prompt Creator (gpt-4.1-mini) → domain-specific exclusion rules
                    │
                    ▼
A4: Classifier (gpt-4o-mini × N) → target/not-target per company
                    │
                    ▼
[CHECKPOINT 2: review targets?] → show list, ask feedback
                    │
                    ├── User: "looks good" → continue
                    ├── User: "exclude operators" → A3 re-crafts rules → A4 re-classifies (tam_re_analyze)
                    │
                    ▼
Exploration: Enrich top 5 targets (5 credits) → new keywords
                    │
                    ▼
A6: Filter Optimizer → optimized filters
                    │
                    ▼
"Better filters found. Re-search?" → if yes, loop back to Apollo Search
                    │
                    ▼
[CHECKPOINT 3: cost for contacts enrichment?] → approve
                    │
                    ▼
People → Contacts gathered
                    │
                    ▼
A5: Sequence Generator → 4-5 email steps
                    │
                    ▼
[GUARD: email accounts selected?] → ask if not
                    │
                    ▼
Push to SmartLead (DRAFT) → test email sent
                    │
                    ▼
"Check inbox. Approve to launch." → activate
```

---

## Execution Order — Brief/File Chain

```
User: "Use cases/IGAMING_PROVIDERS_BRIEF.md"
                    │
                    ▼
U1: File Processor (Opus) → extracts structured JSON
                    │
                    ▼
[GUARD: check all 10 items] → missing: email_accounts → ask ONE question
                    │
                    ▼
Enrich examples (tam_enrich_from_examples) → discover real Apollo keywords
                    │
                    ▼
[same chain as above from Filter Preview onwards]
```

---

## What's different from v1 plan

| v1 (AGENT_CHAIN_PLAN.md) | v2 (this doc) | Why changed |
|--------------------------|---------------|-------------|
| Separate Router agent (A0) | No Router — user's Opus routes | MCP tool names are self-descriptive, Opus routes correctly |
| Separate Guard agents | Guards built INTO tools | Simpler, no context passing overhead |
| Intent parser also selects filters | Intent parser ONLY splits segments | One agent, one task |
| One classification model | A3 (gpt-4.1-mini) creates rules, A4 (gpt-4o-mini) applies | Smart creates, cheap executes |
| Exploration as manual tool | Exploration auto-runs after Checkpoint 2 | Users don't know to call tam_explore |
| Two modes (step-by-step vs brief) | One adaptive flow with checklist | Same flow, different entry points |

---

## Summary: 6 MCP agents + 2 user-side agents

| ID | Agent | Model | Task |
|----|-------|-------|------|
| A1 | Intent Parser | gpt-4o-mini | Split query → segments with geo |
| A2 | Filter Mapper | gpt-4.1-mini | Segment → Apollo filter set from taxonomy |
| A3 | Prompt Creator | gpt-4.1-mini | Craft domain-specific via negativa rules |
| A4 | Company Classifier | gpt-4o-mini | Apply rules to N companies → target/not-target |
| A5 | Sequence Generator | gpt-4o-mini | Create email sequence from offer + patterns |
| A6 | Filter Optimizer | gpt-4o-mini | Select new keywords from enrichment data |
| U1 | File Processor | Opus (user) | Read large docs → structured JSON |
| U2 | Quality Reviewer | Opus (user) | Review targets → corrections |
