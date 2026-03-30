# REALITY Test Plan — Testing Like a Real User

**Date**: 2026-03-30
**Rule**: Every test must use `claude --print` with real MCP SSE. No REST calls. No tool mocking.
**Framework**: `run_real_conversation_tests.py` (already built — launches claude --print agents)

---

## What "Reality Testing" Means

A real user opens Claude Code, connects to MCP, and has a CONVERSATION. They don't call tools — they write natural language. The agent decides what to do. The MCP responds. The UI updates. The DB records everything.

**Testing reality means testing ALL of this:**
1. User writes message → agent picks correct tool (or asks clarifying question)
2. MCP responds with correct data + asks the right next question
3. UI reflects the state (screenshot verification)
4. DB has the correct records (checksum)
5. Conversation history is logged (traceable)
6. Links provided by MCP actually work in browser

---

## Test Execution Method

```bash
# Each test = one claude --print session
# Input = natural language (like a real user would type)
# Output = captured, parsed, scored, screenshotted

cat << 'PROMPT' | claude --print --dangerously-skip-permissions 2>&1 | tee tests/tmp/{timestamp}.txt
[conversation prompt here]
PROMPT
```

**After each test session:**
1. Parse output for tool calls and results
2. Run Playwright/curl to screenshot UI pages
3. Query DB to verify state matches MCP responses
4. Write everything to `tests/tmp/` with timestamps

---

## THE TEST: Default SmartLead Campaign Flow

Line-by-line from `default_requirements.md`. Each line = one test step.

### Phase 1: Onboarding (steps 1-5)

```
TEST 1.1: First contact — no token
  User: "Hey I want to launch outreach for my company"

  VERIFY:
  - MCP responds ONLY with signup link, nothing else
  - Response contains "http://46.62.210.24:3000/setup"
  - Response does NOT list tools, does NOT proceed
  - Screenshot: /setup page shows signup form

  VARIATIONS:
  - "help me find leads"
  - "I need to start campaigns"
  - "привет, хочу запустить рассылку"

TEST 1.2: Token provided
  User: "Here's my token: mcp_xxx..."

  VERIFY:
  - login tool called, returns user_id + name
  - get_context auto-called (session state loaded)
  - MCP tells user to set up API keys if not configured
  - DB: mcp_users has this user, mcp_api_tokens has the token

TEST 1.3: Keys not configured
  User: "Let's gather some companies"

  VERIFY:
  - MCP says "set up keys first" with link to /setup
  - Lists WHICH keys are missing (Apollo, SmartLead, OpenAI, Apify)
  - Does NOT proceed to gathering
  - Screenshot: /setup shows disconnected services

TEST 1.4: Keys configured via UI
  [Configure keys via curl to /api/setup/integrations]
  User: "OK I set them up in the UI"

  VERIFY:
  - MCP detects keys are now present (via get_context or check_integrations)
  - Proceeds to ask "which segments?"
  - Screenshot: /setup shows all green dots

TEST 1.5: User hasn't mentioned offer
  User: "gather IT consulting in Miami and video production in London"

  VERIFY:
  - MCP asks "what's your website?" BEFORE anything else
  - Does NOT launch gathering
  - Does NOT parse segments yet
  - ONE question only (not "what's your website AND which campaigns AND...")
```

### Phase 2: Project Setup (steps 6-8)

```
TEST 2.1: Provide website
  User: "easystaff.io"

  VERIFY:
  - create_project called with website="https://easystaff.io/"
  - Website scraped, offer extracted
  - Response shows project name + link to /projects
  - Response asks about previous campaigns (ONE question)
  - Screenshot: /projects shows new project
  - DB: projects table has new record with target_segments containing scraped offer

TEST 2.2: Previous campaigns
  User: "yes, campaigns with petr in name"

  VERIFY:
  - set_campaign_rules called with campaign pattern
  - SmartLead campaigns loaded matching "petr"
  - Contacts loaded into blacklist
  - Reply analysis started in background
  - Response: "X contacts from Y campaigns loaded to blacklist"
  - Response: link to /crm filtered by project
  - Screenshot: /crm shows contacts from petr campaigns
  - DB: campaign_filters on project contains petr campaigns

  VARIATION: "I haven't launched any campaigns"
  VERIFY: MCP proceeds without blacklist, doesn't ask again

TEST 2.3: No previous campaigns
  User: "no, this is our first campaign"

  VERIFY:
  - MCP proceeds to gathering without blacklist
  - Does NOT ask about campaigns again
```

### Phase 3: Gathering (steps 9-12)

```
TEST 3.1: Segment request triggers filter preview
  User: "gather IT consulting in Miami"

  VERIFY:
  - parse_gathering_intent called → segments extracted
  - tam_gather called WITHOUT confirm_filters
  - Response shows filter preview:
    - Keywords from taxonomy (NOT GPT-invented garbage)
    - Location: Miami
    - Size: auto-inferred from offer (11-200 for payroll)
    - Total available: real number from Apollo probe (>1000)
    - Cost: "Default (≈30 targets): X credits"
    - Cost: "Full run (all N): X credits → ≈Y estimated targets"
    - Target conversion rate shown (35%)
  - Response does NOT show results (gathering hasn't started)
  - ONE question: "Proceed?"

  VARIATIONS:
  - "find me IT consulting companies in Miami area"
  - "I need consulting firms from Miami, medium sized"
  - User says 2 segments: "IT consulting Miami + video production London"
    → VERIFY: asks "separate pipelines or one?"

TEST 3.2: User confirms → gathering starts
  User: "yes, go ahead"

  VERIFY:
  - tam_gather called WITH confirm_filters=true
  - Response shows:
    - run_id
    - Companies found count
    - Credits spent + credits remaining
    - Next steps
    - Pipeline link
    - CRM link with pipeline filter
  - Asks about email accounts (next_question)
  - Screenshot: /pipeline shows new run with company count
  - DB: gathering_runs has new record, company_source_links populated

TEST 3.3: Email accounts asked during gathering
  MCP: "Which email accounts to use for the campaign?"
  User: "use Eleonora's accounts from the petr campaigns"

  VERIFY:
  - list_email_accounts called
  - Accounts filtered by name containing "eleonora"
  - Accounts from campaigns containing "petr" highlighted
  - Response: list of matching accounts with IDs
  - These account IDs saved for later push

  VARIATION: "use account 17062361"
  VARIATION: "all accounts from my previous campaigns"
```

### Phase 4: Pipeline Processing (steps 13-16)

```
TEST 4.1: Blacklist check
  [auto after gathering]

  VERIFY:
  - tam_blacklist_check creates Checkpoint 1
  - Shows: companies checked, passed, rejected
  - Rejected companies are from same project's campaigns (not other projects!)
  - Response includes gate_id
  - Screenshot: /pipeline/{id} shows blacklist phase completed

TEST 4.2: Approve Checkpoint 1
  User: "approve" or "looks good"

  VERIFY:
  - tam_approve_checkpoint called with gate_id
  - Pipeline advances to pre_filter → scrape → analyze
  - Response confirms approval

TEST 4.3: Classification results
  [auto after scrape + analyze]

  VERIFY:
  - Domain-specific rules generated by gpt-4.1-mini
  - Classification done by gpt-4o-mini
  - Checkpoint 2 created with:
    - targets_found count
    - target_rate percentage
    - segment_distribution (meaningful labels, NOT "YOU_ARE_CLASSIFYING")
    - targets_sufficient flag (need ≥34 for 100 contacts)
    - contacts_estimate (targets × 3)
    - suggest_exploration = true (if targets exist)
  - Next steps listed: approve / explore / re-analyze / feedback
  - Screenshot: /pipeline/{id} shows companies with target/rejected status
  - DB: discovered_companies have is_target, analysis_segment, analysis_reasoning

TEST 4.4: Exploration suggestion
  MCP: "Run exploration to discover better filters?"
  User: "yes, explore"

  VERIFY:
  - tam_explore called
  - Top 5 targets enriched in Apollo (5 credits)
  - New keywords discovered → taxonomy updated
  - Optimized filters returned
  - Response shows: original filters vs optimized
  - Asks: "Re-search with better filters?"
```

### Phase 5: Campaign Creation (steps 17-21)

```
TEST 5.1: Sequence generation
  User: "generate the email sequence"

  VERIFY:
  - god_generate_sequence called with project_id
  - 4-5 step sequence generated
  - Subjects contain {{first_name}} or {{company}} (normalized)
  - Response shows preview of each step
  - Asks for approval

TEST 5.2: Approve and push
  User: "looks good, push to SmartLead"

  VERIFY:
  - god_approve_sequence called
  - god_push_to_smartlead called with:
    - email_account_ids (from step 3.3)
    - target_country detected from gathered contacts
  - Campaign created as DRAFT (NOT ACTIVE)
  - Settings match reference 3070919 (no tracking, plain text, stop on reply)
  - Test email auto-sent to user's email
  - Response includes ALL 4 items:
    1. SmartLead campaign link ✓
    2. CRM contacts link with campaign filter ✓
    3. "Check your inbox at {email}" ✓
    4. "Approve to launch" ✓
  - Screenshot: /campaigns shows new DRAFT campaign with MCP badge
  - Screenshot: /crm?campaign={name} shows uploaded contacts
  - DB: campaigns table has DRAFT, monitoring_enabled=false

TEST 5.3: User approves launch
  User: "activate the campaign"

  VERIFY:
  - activate_campaign called with user_confirmation
  - Campaign status → ACTIVE
  - monitoring_enabled → true
  - Response mentions reply monitoring is ON
  - Asks about Telegram notifications
  - Screenshot: /campaigns shows ACTIVE + LISTENING badge
  - DB: campaigns.status = 'active', monitoring_enabled = true
```

### Phase 6: Post-Launch (steps 22-25)

```
TEST 6.1: Warm replies
  User: "which replies are warm?"

  VERIFY:
  - replies_summary called
  - Reply counts by category shown
  - Link to /crm with warm filter provided

TEST 6.2: Follow-ups needed
  User: "who needs a follow-up?"

  VERIFY:
  - replies_followups called
  - Leads needing follow-up listed
  - CRM link with follow-up filter

TEST 6.3: Session continuity
  [Disconnect and reconnect with same token]
  User: "what was I working on?"

  VERIFY:
  - get_context returns full state
  - Active project set correctly
  - Pending checkpoints shown
  - Draft campaigns shown
  - Recent activity listed
```

---

### Phase 7: Iterations — the Core Loop (steps 26-33)

The pipeline has ITERATIONS. Each change = new iteration. ALL must be visible in UI.

**Iteration lifecycle:**
```
Iteration 1: Initial search + classify (draft filters, initial prompt)
  → User/Opus reviews → provides feedback
Iteration 2: Improved prompt + optimized Apollo filters (from exploration enrichment)
  → Better accuracy, better target rate
Iteration 3+: Scale — same prompt + filters, more pages from Apollo
  → "find more" = increase max_pages, next offset
```

```
TEST 7.1: Iteration 1 visible in UI after first classify
  [After Checkpoint 2 from Phase 4]

  VERIFY:
  - Screenshot: /pipeline/{id} → iteration selector visible in top area
  - Iteration 1 selected by default
  - Shows: Apollo filters applied (keywords, industries, location, size)
  - Shows: GPT prompt used (or link to prompts page)
  - Shows: companies count, target count, target rate
  - Clicking a company row → modal shows reasoning from THIS iteration

TEST 7.2: Re-analyze creates Iteration 2
  User provides feedback: "Roobet is an operator, not a provider"
  → tam_re_analyze called

  VERIFY:
  - Iteration 2 created in pipeline_iterations table
  - UI: iteration selector now shows "Iter 1" and "Iter 2"
  - Iteration 2 selected by default (most recent)
  - Apollo filters may differ from Iter 1 (if exploration ran)
  - GPT prompt differs from Iter 1 (feedback incorporated)
  - Target count/rate different from Iter 1
  - Screenshot: compare Iter 1 vs Iter 2 in UI
  - DB: pipeline_iterations has 2 records for this run

TEST 7.3: ALL iterations selected by default shows latest result per company
  VERIFY:
  - When "All iterations" selected → each company shows LATEST classification
  - NO duplicate companies (same company from Iter 1 and Iter 2 = show Iter 2 result)
  - Target/rejected status from most recent iteration
  - Segment label from most recent iteration

TEST 7.4: Clicking Iteration 1 shows historical state
  User clicks "Iter 1" in selector

  VERIFY:
  - Companies show Iter 1 classifications (may differ from current)
  - Apollo filters shown are from Iter 1 (not Iter 2)
  - Target count/rate from Iter 1
  - Can compare: "Iter 1: 15 targets at 48%" vs "Iter 2: 25 targets at 81%"

TEST 7.5: Exploration changes filters → visible across iterations
  [After tam_explore enriches top 5 targets]

  VERIFY:
  - Iter 1 filters: original keywords (e.g. "IT consulting", "technology consulting")
  - Iter 2 filters: + new keywords from enrichment (e.g. "it services & it consulting", "managed services")
  - UI shows filter diff or at least both filter sets are viewable
  - Screenshot: /pipeline/{id} filters panel shows Iter 2 keywords

TEST 7.6: Scale = more pages, same filters → Iteration 3
  User: "find more companies with the same filters"

  VERIFY:
  - tam_gather called with same filters but higher max_pages or next page offset
  - Does NOT re-search already gathered companies (offset/page handling)
  - Does NOT spend credits on already-fetched pages
  - New companies added to the same pipeline run
  - Iteration 3 created with trigger="scale"
  - UI: iteration selector shows 3 iterations
  - Filters same as Iter 2 (only max_pages changed)
  - Screenshot: companies table has MORE rows than before
  - DB: new company_source_links added, gathering_run credits_used increased

TEST 7.7: Apollo filters visible per iteration
  VERIFY for EACH iteration:
  - Keywords shown (array of Apollo keyword tags)
  - Industries shown (if any)
  - Location shown
  - Size ranges shown
  - max_pages / per_page shown
  - Total available shown (from Apollo probe)
  - Credits used for this iteration shown

TEST 7.8: Prompt visible per iteration
  VERIFY:
  - Link to prompts page from pipeline detail
  - Prompts page shows: Iter 1 prompt, Iter 2 prompt (different)
  - Each prompt has a summary line (not just raw text)
  - No tool_call rows mixed in (filtered out per Pavel feedback #25)
```

---

## Edge Case Tests

```
EDGE 1: User provides 2 segments in one message
  User: "gather IT consulting Miami and video production London"
  VERIFY: Asks "separate pipelines or one?" before proceeding

EDGE 2: User tries to activate without email accounts
  VERIFY: MCP asks for email accounts, doesn't activate

EDGE 3: User changes mind about filters
  User: "actually, also include 201-500 size"
  VERIFY: tam_gather returns updated preview with new total_available

EDGE 4: User provides strategy doc
  User: "use this file: cases/IGAMING_PROVIDERS_BRIEF.md"
  VERIFY: Agent (Opus) reads file, extracts info, passes to MCP tools

EDGE 5: User asks about credits mid-pipeline
  User: "how many Apollo credits have I spent?"
  VERIFY: Response shows credits per run + total

EDGE 6: User has multiple projects, doesn't specify
  User: "gather fashion brands in Italy" (without selecting project)
  VERIFY: MCP asks which project

EDGE 7: Classification accuracy too low
  User sees 48% target rate → "exclude operators, they're not tech providers"
  VERIFY: provide_feedback → tam_re_analyze → new iteration → improved accuracy
```

---

## Verification Checklist (run after EVERY test)

| Check | Method | Pass criteria |
|-------|--------|--------------|
| **MCP response correct** | Parse claude --print output | Contains expected fields |
| **Tool called correctly** | Parse output for tool names | Right tool for the intent |
| **Links work** | curl each link, check HTTP 200 | All links return valid pages |
| **UI shows correct state** | Screenshot via Playwright/curl | Visual match |
| **DB matches MCP** | SQL query vs MCP response | Counts match |
| **Conversation logged** | Query mcp_conversation_logs | All tool calls present |
| **No cross-user leakage** | Check user_id on all records | Only this user's data |
| **One question at a time** | Count questions in response | Max 1 question per response |
| **Credits tracked** | Check credits in response + DB | Shown and accurate |
| **Segments meaningful** | Check segment labels | Not "YOU_ARE_CLASSIFYING" or "TARGET" |

---

## How to Run

```bash
# Full test (both users, all conversations)
cd mcp && python3 tests/run_real_conversation_tests.py

# Single user
cd mcp && python3 tests/run_real_conversation_tests.py --user pn@getsally.io

# Single conversation (pipe directly)
cat << 'PROMPT' | claude --print --dangerously-skip-permissions 2>&1 | tee tests/tmp/test_$(date +%Y%m%d_%H%M%S).txt
[test prompt]
PROMPT
```

**All results go to `tests/tmp/` and `tests/real_test_results/`**

---

## Reference Documents

- **Agent modules**: [AGENT_MODULES_20260330.md](AGENT_MODULES_20260330.md)
- **Implementation plan**: [IMPLEMENTATION_PLAN_20260330.md](IMPLEMENTATION_PLAN_20260330.md)
- **Pavel's feedback**: [../../pavel_feedback/index.md](../../pavel_feedback/index.md)
- **Default requirements**: [../requirements/default_requirements.md](../requirements/default_requirements.md)
- **Existing test runner**: [../../tests/run_real_conversation_tests.py](../../tests/run_real_conversation_tests.py)
