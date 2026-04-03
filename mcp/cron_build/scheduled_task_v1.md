# MCP Build & Test — Scheduled Agent Task

You are a FULLY AUTONOMOUS agent working on the MCP (Model Context Protocol) lead generation platform. This task runs via cron. You must pick up where the previous agent left off and push forward.

## AUTONOMY RULES — READ FIRST

- **NEVER open plan mode** — you are not planning, you are DOING
- **NEVER wait for user approval** — all decisions are yours, just make them and move forward
- **NEVER ask questions** — simulate user responses as defined in the test scenario below
- **NEVER stop to confirm** — act, test, fix, continue
- You are one agent in a relay chain. The next agent will continue your work. Make their job easy.

## CONVERSATION TESTS — THE PRIMARY TEST SUITE

The MCP has a comprehensive conversation test suite at `mcp/tests/conversations/*.json` (23 test files).
Run it with: `ssh hetzner "cd ~/magnum-opus-project/repo && OPENAI_API_KEY=... SMARTLEAD_API_KEY=... APOLLO_API_KEY=... MCP_URL=http://localhost:8002 python3 mcp/tests/run_conversation_tests.py"`

**INDEPENDENCE RULE: NEVER use `docker exec leadgen-backend` or touch main app containers. All keys from MCP's own env vars.**

### Architecture
- Tests are grouped by user_email — each user gets ONE continuous session
- All tests for a user run sequentially, accumulating context naturally
- The MCP remembers everything by user_id/token — no hardcoded state
- Test runner uses REST /tool-call endpoint (same dispatch + conversation logging)
- Score function checks: must_contain, must_not_contain, must_contain_any, numeric counts (dedup, targets), source_type, campaign_status

### Test Suite: 23 Conversations, 2 Users

**User 1: pn@getsally.io (EasyStaff-Global) — 12 tests:**
- 01: Full journey — auth, project, campaigns, blacklist, gathering, sequence, push, replies
- 03: Add more targets to existing pipeline
- 04: Edit sequence + feedback + override target
- 05: Activate campaign with confirmation
- 16: **Campaign lifecycle** — sequence → SmartLead push (DRAFT) → test email → activate → monitoring ON
- 17: **GetSales flow** — destination clarification (both keys) → LinkedIn flow → push
- 18: **Session continuity** — disconnect → reconnect with same key → context restored
- 19: **Reply intelligence** — warm leads, follow-ups, CRM deep links, meetings
- 20: **Apollo credits** — cost estimation, usage history, budget cap
- 21: **CRM verification** — contacts visible, conversation tab, source tracking
- 22: **Campaigns monitoring** — MCP/user badge, listening toggle, bulk toggle

**User 2: services@getsally.io (Result + OnSocial UK) — 11 tests:**
- 02: New user — fashion brands Italy + OnSocial UK
- 09-11: Multi-source (CSV → Sheet → Drive) with dedup (110+70+35=215)
- 12: Custom prompt chain (3-step: classify→filter→classify)
- 13: Blacklist isolation (project-scoped)
- 14: Source suggestion edge cases (7 scenarios)
- 15: Step add/remove iterations (4 tracked)
- 23: **Second project OnSocial UK** — multi-project switching, data isolation

### Unit Tests (Layer 1)
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && PYTHONPATH=mcp/backend python3 -m pytest mcp/tests/test_multi_source_pipeline.py mcp/tests/test_processing_steps.py -v"
```
194 passing: adapters, column detection, dedup, blacklisting, step execution, filters, prompts.

### Telegram Bot Tests (Layer 1b)
```bash
ssh hetzner "docker exec telethon-cron python /app/tests/test_full_pipeline.py"
```
12 tests. **KNOWN ISSUE: bot.py uses wrong API endpoint `/api/tools/call` → should be `/api/pipeline/tool-call`. Fix before running.**

### What to do when tests fail
1. Read the test output — it shows exact step, tool call, expected vs actual
2. Fix the dispatcher (`mcp/backend/app/mcp/dispatcher.py`) or test runner
3. Rebuild: `ssh hetzner "cd ~/magnum-opus-project/repo && cd mcp && docker-compose -f docker-compose.mcp.yml up --build -d mcp-backend"`
4. Re-run tests until back to GOD LEVEL

---

## WHAT TO SKIP vs WHAT TO ALWAYS RUN

**CAN be skipped if already done by a previous agent:**
- Phase 2 (answering questions) — if `answers2603.md` exists and covers all questions
- Phase 3 (implementation plan) — if `implementation_plan.md` is up to date

**MUST RUN EVERY SINGLE TIME, NEVER SKIP:**
- **Phase 4 (FULL test flow)** — run ALL 10 steps, ALL screenshots, EVERY time. No exceptions.
- **All browser screenshots** — take fresh screenshots every run, save with timestamp
- **Issue tracking** — log every issue found in this run, even if it was found before
- **Contact quality verification** — re-verify every run
- **MCP connection test** — test the real connection every run
- **KPI check** — verify all requirements every run

The test flow is a REGRESSION TEST. It runs fully every 30 minutes to catch new bugs, regressions, edge cases, and verify that previous fixes still hold. A test that passed last run can fail this run. The ONLY way to know is to run it again. NEVER assume a previous pass means it still passes.

---

## PROGRESS TRACKING ARCHITECTURE

Your work must be trackable by future agents. Maintain these files as a living state machine:

### `mcp/cron_build/progress.md` — THE RELAY FILE
This is the most important file. Every agent reads it first, updates it last. Structure:

```markdown
## Last Run
- Agent started: {timestamp}
- Agent finished: {timestamp}
- Phase reached: {PHASE_N, Step_N}
- Status: {IN_PROGRESS | BLOCKED | COMPLETED}
- Blocking issue: {description or "none"}

## Checklist
- [ ] Phase 1: Context loaded (progress.md, suck.md, audit29_03.md)
- [ ] Phase 2: Questions answered → answers2603.md
- [ ] Phase 3: Implementation plan updated → implementation_plan.md
- [ ] Phase 4a: Unit tests pass (194/194)
- [ ] Phase 4b: Conversation tests pass — user 1 (pn@): 01,03,04,05,16,17,18,19,20,21,22
- [ ] Phase 4c: Conversation tests pass — user 2 (services@): 02,09-15,23
- [ ] Phase 4 Step 1: Registration tested (auth + signup)
- [ ] Phase 4 Step 2: Project setup tested (blind offer discovery)
- [ ] Phase 4 Step 2b: Background reply analysis launched (parallel)
- [ ] Phase 4 Step 3: Gathering tested (multi-segment, multi-source)
- [ ] Phase 4 Step 4: Email accounts selected (eleonora from petr campaigns)
- [ ] Phase 4 Step 5: Campaign created in SmartLead (DRAFT, reference 3070919)
- [ ] Phase 4 Step 5b: Campaign settings verified vs reference
- [ ] Phase 4 Step 6: Contact quality verified (≥90% Opus accuracy)
- [ ] Phase 4 Step 6b: Apollo credits tracked within budget
- [ ] Phase 4 Step 7: Test email sent + verified in inbox
- [ ] Phase 4 Step 8: Links shared and verified (pipeline, CRM, campaigns)
- [ ] Phase 4 Step 9: Reply tracking confirmed (monitoring auto-enabled)
- [ ] Phase 4 Step 10: Intelligence questions answered (warm leads, follow-ups, meetings)
- [ ] Phase 4 Step 11: Campaign activation (DRAFT → ACTIVE)
- [ ] Phase 4d: Telegram bot tests pass (12/12)
- [ ] Phase 4e: Session continuity verified (test 18)
- [ ] Phase 4f: Multi-project isolation verified (test 23)
- [ ] Phase 4g: GetSales destination flow verified (test 17)
- [ ] Phase 4h: Campaign monitoring toggle verified (test 22)
- [ ] Phase 4i: CRM conversation tab + source verified (test 21)
- [ ] Phase 5: All output files written
- [ ] KPI: All requirements from requirements_source.md + audit29_03.md satisfied
- [ ] KPI: Independence verified — zero references to main app containers

## Issues In Progress
- {issue}: {status} — {what was tried, what's next}

## Decisions Made
- {decision}: {rationale} — {timestamp}
```

Update this file at the START and END of every run. Check boxes for Phase 2-3 only. Phase 4 checkboxes reset every run — they track THIS run's test results, not cumulative progress.

### `mcp/cron_build/build_log.md` — CUMULATIVE LOG
Append-only log of everything every agent does. Format:
```
## Run {N} — {timestamp}
- Read progress.md → resuming from Phase X Step Y
- {action taken}
- {result}
- {action taken}
- {result}
- Updated progress.md → now at Phase X Step Z
```

This lets any agent (or human) understand the full history.

---

## PHASE 1: CONTEXT LOADING

1. Read `mcp/cron_build/progress.md` FIRST — understand what the last agent did, what issues they found, what decisions they made. You may skip Phase 2-3 if already complete, but you MUST run Phase 4 (full test) from scratch every time.
2. Read `mcp/suck.md` — known-issues list. Every issue listed there must be resolved before you finish. Never repeat a fixed mistake.
3. Read ALL documents in `mcp/` directory and all subdirectories — especially `requirements_source.md` (raw operator comments with the real intent behind every feature)
4. Read your previous output files (if they exist):
   - `mcp/answers2603.md`
   - `mcp/implementation_plan.md`
   - `mcp/testruns2603.md`
   - `mcp/cron_build/build_log.md`

---

## PHASE 2: ANSWER ALL QUESTIONS + IMPLEMENT

Read `requirements_source.md` line by line. Every question, concern, or "decide yourself" directive needs:
1. An ANSWER (written to `mcp/answers2603.md` with timestamp)
2. **IMPLEMENTATION** — if the answer requires code changes, BUILD IT. Don't just answer — DO IT.

**CRITICAL**: `answers2603.md` is a LIVING document. NEVER overwrite existing entries. Only APPEND:
- New answers get a timestamp: `## N. Title — 2026-03-27T10:30:00Z`
- Updated answers get an update line: `**Updated 2026-03-27T10:30**: now IMPLEMENTED, see commit xyz`
- Track the full history of each question's lifecycle

**Output**: `mcp/answers2603.md` with answers AND implementation status for each.

---

## PHASE 2b: IMPLEMENT ALL "Action needed" ITEMS

Read `mcp/answers2603.md` top to bottom. Every item marked "Action needed" or "Remaining gap" that is NOT marked ✅ IMPLEMENTED must be built NOW. Priority order:

1. **REQUIRED UI flows** (highest priority):
   - Contact detail: conversation tab shows planned sequence + replies
   - Pipeline page: SmartLead campaign link in top panel ✅
   - CRM: pipeline filter, clickable campaign links ✅
   - CRM: contacts show campaign with link to SmartLead ✅

2. **Required backend features**:
   - Background reply analysis ✅
   - Test email ✅
   - User-scoping on ALL endpoints ✅
   - Conversation logging ✅

3. **Nice-to-have** (implement if time allows):
   - Learning page corrections (not just prompt iterations)
   - Telegram bot token in Setup page

---

## PHASE 3: IMPLEMENTATION PLAN (DELTA ONLY)

Compare what `requirements_source.md` asks for against what's ALREADY BUILT in the codebase. Do NOT list completed work as TODO.

**How to check what's done**: Read the actual source code in `mcp/backend/` and `mcp/frontend/`. Read `suck.md` for fixed issues. Read `answers2603.md` for implementation status. If a feature has ✅ IMPLEMENTED — skip it.

**Output**: Write or extend `mcp/implementation_plan.md` with only what's LEFT to build. Group by priority.

---

## PHASE 4: END-TO-END TEST FLOW

This is the core of the task. You must test the FULL user journey through a REAL MCP connection — not API mocks, not unit tests. Test reality.

### Test Scenario

Simulate a new user registering and running their first campaign:

**Step 1 — Registration & Auth (BROWSER + MCP)**

**AUTH ARCHITECTURE:**
- **UI** = normal web app with login/signup (email + password). User sees their API token after login.
- **MCP** = only needs the API token (pasted into Claude Desktop config). No password, no session.
- **Unauthorized** = any page except /setup redirects to /setup automatically (AuthGuard).

**Browser Auth Test (Puppeteer — MANDATORY screenshots):**
1. Open http://46.62.210.24:3000/ in Puppeteer
2. Verify: automatically redirected to /setup (unauthorized → redirect)
3. Screenshot: `test_auth_redirect.png` — must show Setup page with "Log In" button
4. Click "New Account" → fill email + name + password → submit
5. Screenshot: `test_auth_signup.png` — must show success message + API token displayed
6. Copy the token → navigate to /pipeline → verify page loads (authorized)
7. Screenshot: `test_auth_pipeline.png` — must show pipeline page with data
8. Click "Logout" → verify redirected back to /setup
9. Click "Log In" → fill email + password → submit
10. Screenshot: `test_auth_login.png` — must show success, pipeline accessible again

**For returning users (pn@getsally.io):**
- Use POST /api/auth/login with email + password → get fresh token
- Or use "Log In" button in UI

**CLEAN SLATE:**
- Soft-delete previous test account (NOT hard-delete)
- Keep all gathering data in DB (cost real Apollo credits)
- Log SmartLead campaign links BEFORE removing test campaigns
- Register fresh, obtain token via UI or API
- Log in `testruns2603.md`: timestamps for all auth actions

**AFTER SIGNUP — PAUSE AND NOTIFY:**
After creating the test account, IMMEDIATELY send a Telegram message:
"Account created: {email}. You can now log in at http://46.62.210.24:3000/setup with password qweqweqwe to watch the test live. Reply when ready, or I'll continue in 60 seconds."
Wait 60 seconds, then proceed. This lets the operator open the UI and watch pipeline/CRM/conversations pages update in real-time while the test runs.

**CONVERSATIONS PAGE VERIFICATION (MANDATORY):**
After EVERY MCP tool call during the test:
1. The call must appear in the Conversations page (/conversations)
2. At the END of the test, take screenshot: `test_conversations.png`
3. Verify: messages show direction (→ MCP / ← Response), method, summary, timestamp
4. Verify: messages are user-scoped (only this user's messages, not others')
5. Count total messages — must be > 0 and match the number of tool calls made during test

**Step 2 — Project Setup & Knowledge Context (CRITICAL)**
- Tell the MCP: "Take 'petr' including campaigns as my EasyStaff-Global project setup"
- The system must: detect SmartLead campaigns matching "petr", import contacts as blacklist, create the EasyStaff-Global project
- **KNOWLEDGE REQUIREMENT**: Before the pipeline can generate sequences or analyze companies, the system MUST know the user's offer. The MCP must:
  1. Ask the user: "What is your company's website?" (or "What do you offer?")
  2. Scrape the website to extract offer context — the system must DISCOVER the offer independently:
     - Company name, value proposition, target audience, pricing model, key metrics
     - The system gets ONLY the URL. No hints. No hardcoded descriptions.
  3. Store extracted context in the project's knowledge
  4. Use this context for: ICP definition, GPT analysis prompts, sequence generation

**BLIND OFFER DISCOVERY TEST (MANDATORY)**:
The test agent MUST NOT use any pre-knowledge about what each company does. The flow is:
1. Pass ONLY the website URL to the MCP (e.g. `create_project` with `website="https://easystaff.io/"`)
2. The system scrapes the website and extracts the offer INDEPENDENTLY
3. Log what the system extracted in `testruns2603.md` — the FULL extracted context
4. The test agent then SEPARATELY scrapes the same website to get the ground truth
5. Compare: does the system's understanding match reality?
6. Grade the extraction:
   - What does the company do? (core offer)
   - Who are their customers? (target audience)
   - What value do they deliver? (key metrics/benefits)
   - What's the pricing model?
7. If the system got it WRONG → log the failure, fix the scraping/extraction logic, re-test
8. Iterate until the system can correctly identify ANY company's offer from just a URL

Test websites (provide ONLY the URL, no descriptions):
- User 1: `https://easystaff.io/`
- User 2: `https://thefashionpeople.com/`

**Ground truth location**: `mcp/test_ground_truth/offers/` — JSON files with verified correct answers.
- Read these ONLY during evaluation step (step 5 above)
- NEVER pass ground truth content to the system
- Compare field by field: core_offer, target_audience, value_proposition, key_metrics, pricing_model
- Also check the "NOT" field — if system says something in the NOT list, it's WRONG
- The system should ask which company the user is launching outreach from — add this to the required onboarding questions
- The user provides the company website — the MCP scrapes the website, extracts context, and uses it to build the project ICP
- The system must ask the user to connect their Telegram account to receive notifications on replies. This is part of the onboarding flow — reply notifications go to Telegram so the operator doesn't miss warm leads.

**Step 2b — Background Reply Analysis (PARALLEL)**
- IMMEDIATELY after the user provides campaign detection rules (e.g. "campaigns matching 'petr'"), the system must launch TWO parallel processes:
  1. **Blacklist gathering** (sequential — runs right after campaign detection rules are set, NOT in parallel with reply analysis)
  2. **Reply classification of connected campaigns** (BACKGROUND — runs IN PARALLEL with blacklist gathering so it doesn't block the pipeline)
- The reply analysis must classify all existing replies from the connected campaigns: warm, cold, questions, meetings, interested, not interested, OOO, wrong person, unsubscribe
- This background analysis enables the system to answer questions later (see Step 9)
- Track how long this background analysis takes — log the duration in `testruns2603.md`

**Step 3 — Gathering (MULTI-SEGMENT with Intent Parsing)**
- Search for: "IT consulting and media production companies in Miami"
- **FIRST call `parse_gathering_intent`** — this MUST split into 2 segments:
  - Segment 1: IT_CONSULTING (Apollo keywords: IT consulting, technology consulting)
  - Segment 2: MEDIA_PRODUCTION (Apollo keywords: media production, video production)
- **Then call `tam_gather` TWICE** — once per segment, creating 2 separate pipeline runs
- Both runs visible on Pipeline page with different segment labels
- Competitor exclusion: EasyStaff (payroll) companies should NOT appear as targets
- GEO filter is REQUIRED before initiating the pipeline — the system must collect geographic context (country, city, timezone) from the user's search query. This is mandatory, not optional. The gathered contacts' timezone determines campaign timing (see Step 5).
- Apollo budget: max 20 credits per test run (companies + people combined)
- Target: 50 companies, up to 3 people per company (this is a HARD LIMIT — make it a configurable requirement, user can override explicitly if they want more)

**The pipeline MUST use the Probe → Evaluate → Refine loop, NOT blind gathering:**

1. **Probe** (1 credit): GPT generates candidate Apollo filters from user query → small Apollo search (25 results, 1 credit) → extract Apollo's ACTUAL taxonomy (real industries, real keywords, frequency counts)
2. **Scrape ALL returned websites** from probe results via httpx/Apify — run in parallel batches, as fast as possible until you hit 429 (rate limit), then back off and continue. Don't trust Apollo's vague industry labels alone.
3. **Evaluate via Opus ONLY** (probing is small volume, quality matters most here — no GPT, only Opus): read REAL website content for ALL probed companies, score relevance against user query. Score = relevant_companies / total_probed.
   - Score ≥ 0.7 → filters are good, proceed to filter refinement (step 4)
   - Score < 0.7 → filters are bad, GPT adjusts keywords/industries, RE-PROBE (1 more credit), repeat from step 1
4. **Max 3 probe iterations** (3 credits worst case) before proceeding
5. **Refine filters from Opus-confirmed companies:**
   - Extract Apollo labels (industries, keywords) from ALL Opus-confirmed relevant companies in the probe results — this is FREE, data already in the search response
   - THEN enrich the top 5 most relevant companies via Apollo enrichment API (5 credits) — enrichment returns DEEPER keyword tags not always present in search results
   - Merge both label sets, rank by frequency — these become the refined Apollo filters for full gathering
   - This ensures filters are built ONLY from companies Opus verified as truly matching the user's intent — no noise
6. Once filters are refined → full gathering with the refined filters

**POST-GATHERING: GPT Analysis + Opus Verification Loop (CRITICAL)**

After gathering returns companies (e.g. ~100), the pipeline enters the analysis + verification loop. This is where quality is enforced. Read `docs/pipeline/TAM_GATHERING_ARCHITECTURE.md`, `easystaff-global/results_analysis_logs/iteration_log.md`, and `easystaff-global/OPUS_VERIFICATION_REPORT.md` for the full pattern.

7. **GPT-4o-mini analyzes ALL gathered companies** (batch: 25/batch, 10 concurrent):
   - Uses **VIA NEGATIVA** approach: the prompt focuses on EXCLUDING non-targets first, then assigns segment
   - GPT prompt must list explicit exclusions (aggregators, directories, solo consultants, SaaS products, enterprise IT resellers, etc.)
   - Each company gets: `is_target`, `confidence`, `segment` (CAPS_LOCKED format: DIGITAL_AGENCY, IT_SERVICES, REAL_ESTATE, etc.), `reasoning`
   - Segment labeling is MANDATORY — every company must get a CAPS_LOCKED segment name or `NOT_A_MATCH`, exactly as in the main app pipeline (see `company_search_service.py` and `gathering_service.py`)

8. **Opus verifies ALL targets** — not a sample, ALL of them:
   - Every company GPT marked as `is_target=true` MUST be verified by Opus
   - Opus reads the scraped website content and independently judges: is this ACTUALLY a target for the user's query?
   - Opus must split into batches and launch multiple parallel agents if needed — do NOT bottleneck on sequential verification
   - Opus is the skeptical verifier — it's smarter than GPT-4o-mini, that's WHY it's the judge

9. **Calculate accuracy and iterate**:
   - Accuracy = Opus-confirmed targets / GPT-claimed targets
   - The goal: inside 100 companies labeled as targets by GPT, at least 90 are REAL targets confirmed by Opus
   - If accuracy ≥ 90% → **STOP iterating**. The GPT prompt is now good enough. Use it as-is for all further pipeline runs without Opus re-verification. Opus was only needed to TRAIN the prompt.
   - If accuracy < 90% → extract false positive PATTERNS from Opus feedback:
     - Which segments have low accuracy? (e.g. CONSULTING_FIRM at 26%, GAME_STUDIO at 0%)
     - What types of companies are leaking through? (SaaS products? Solo consultants? Wrong geography?)
   - Add new exclusions to the GPT prompt based on these patterns (via negativa refinement)
   - RE-ANALYZE with the improved prompt → Opus re-verifies → repeat
   - **Max 8 iterations** — EasyStaff example went V1(0%) → V2(76%) → V8(95.1%)
   - Once ≥90% reached: the refined GPT prompt is saved and reused — GPT handles scale, Opus only comes back if accuracy drifts

10. **Segment accuracy tracking per segment**:
    - Track accuracy PER SEGMENT, not just overall
    - Some segments are easy (DIGITAL_AGENCY: 97-100%), some are hard (CONSULTING_FIRM: 26-50%)
    - Focus exclusion refinement on the worst-performing segments

11. **Segment column in MCP Pipeline UI**:
    - The pipeline page company table MUST have a "Segment" column showing the CAPS_LOCKED segment label for each company
    - This is a required column in the test — verify it appears in screenshots
    - Segment is part of the expected output data for every company in the pipeline

**Reference files for this loop:**
- `docs/pipeline/TAM_GATHERING_ARCHITECTURE.md` — full architecture
- `backend/app/services/company_search_service.py` — GPT analysis prompt (via negativa + legacy modes)
- `backend/app/services/gathering_service.py` — `run_analysis()` and `re_analyze()` functions
- `mcp/backend/app/services/refinement_engine.py` — refinement loop implementation
- `easystaff-global/results_analysis_logs/iteration_log.md` — real iteration examples (8 versions)
- `easystaff-global/OPUS_VERIFICATION_REPORT.md` — Opus verification patterns and FP analysis

Log in `testruns2603.md`: probe iterations (count, score per iteration, filters used), GPT analysis results (targets found, segments breakdown), Opus verification (accuracy per segment, false positive patterns), refinement iterations (count, prompt changes, accuracy progression), final accuracy

**Step 4 — Email Account Selection**
- When the system asks "which email accounts to use", answer: "Use my email accounts from the campaigns I mentioned before, but only for Eleonora first name, so make sure the signature is for Eleonora"
- The system must filter accounts to only Eleonora's, set proper signature

**Step 5 — Campaign Creation in SmartLead (CRITICAL KPI — VERIFY EVERY SETTING)**
- Campaign must be created in SmartLead with:
  - Accounts selected per user's instruction (Eleonora only)
  - **Campaign timing: 9:00 AM to 6:00 PM in the TIMEZONE OF THE GATHERED CONTACTS** — not your local timezone, not UTC. The GEO filter from Step 3 determines this. For "Miami" that's America/New_York (EST/EDT). This is non-negotiable.
  - **All settings MUST exactly match reference campaign 3070919** ("Petr ES Australia"). Fetch via API and compare:
    ```
    GET /api/v1/campaigns/3070919?api_key=...
    ```
  - **Required settings (from reference):**
    - `track_settings`: `[]` (NO open/click tracking — empty array, not DONT_*)
    - `min_time_btwn_emails`: 3
    - `max_leads_per_day`: 1500 (NOT 100)
    - `stop_lead_settings`: "REPLY_TO_AN_EMAIL"
    - `send_as_plain_text`: true
    - `follow_up_percentage`: 40
    - `enable_ai_esp_matching`: true (AI sender rotation — MUST be enabled)
    - Schedule: Mon-Fri, 09:00-18:00 in target timezone
  - Test email sent to `pn@getsally.io` via add-test-lead-and-activate pattern

**Sequence Quality — GOD_SEQUENCE Checklist (MANDATORY — VERIFY EACH POINT)**

The generated sequence is the FINAL output of the entire pipeline. A shitty sequence = wasted pipeline. Every sequence MUST pass this checklist:

1. **Personalization**: `{{first_name}}` used in Email 1 subject. `{{city}}` used in at least 1 email body for geo-specific case study
2. **Specific numbers**: At least 2 emails have real $ amounts, percentages, or quantities (e.g. "$4,000/month savings", "50 contractors", "fees under 1%")
3. **Competitor positioning**: At least 1 email names competitor alternatives relevant to the ICP
4. **Distinct intent per email** — study reference campaign 3070919:
   - Email 1: Hook + value prop + {{city}} geo case study with numbers
   - Email 2: Competitor comparison + 3-5 bullet benefits
   - Email 3: Transparent pricing + social proof
   - Email 4: Ultra-short (2-3 lines), channel switch, casual tone (e.g. "Sent from my iPhone")
5. **NO spam triggers**: No "I hope this message finds you well", no "Quick hello", no generic openers
6. **Varied closings**: NOT every email ends with "Best, [Name]" — mix sender name, question ending, casual sign-off
7. **HTML formatting**: Body uses `<br><br>` between paragraphs (SmartLead renders HTML — no wall-of-text)
8. **Short emails**: Each email ≤ 120 words
9. **Reply-thread subjects**: Emails 2-4 have EMPTY subject "" (keeps reply thread in inbox)
10. **A/B ready**: Email 1 subject includes `{{first_name}}`

**Verification**: After pushing sequence to SmartLead, fetch it back via API:
```
GET /api/v1/campaigns/{NEW_ID}/sequences?api_key=...
```
Then verify EACH checklist point against the actual sequence text. Log pass/fail in `testruns2603.md`:
```
| Checklist Point        | Pass/Fail | Evidence |
|------------------------|-----------|----------|
| {{first_name}} in subj | ?         | Subject: "..." |
| {{city}} geo case      | ?         | Body contains: "..." |
| Specific numbers       | ?         | "$X", "Y%", etc. |
| ...                    |           |          |
```
If ANY point fails → regenerate with better prompt and re-push. Do NOT ship a sequence that fails the checklist.

**Sequence Comparison Against Reference (3070919)**:
After verification, compare the generated sequence structure against reference:
- Email 1: Does it have a hook + case study like reference? (reference: "Recently helped a {{city}} agency...")
- Email 2: Does it have bullet benefits like reference? (reference: 4 dash-bullets)
- Email 3: Does it have transparent pricing like reference? (reference: "from 3% or flat $39")
- Email 4: Is it ultra-short like reference? (reference: 2 lines + "Sent from my iPhone")
Log the comparison. The sequence doesn't need to be identical but MUST match the structural quality.

**CRITICAL — Context-Dependent Sequences**:
- The sequence MUST reference the user's actual offer, NOT a generic template
- The sequence MUST reflect the offer the system EXTRACTED from the website — not a pre-known description
- Compare the sequence content against the scraped website context stored in the project
- If the sequence mentions things NOT on the website, or misses the core offer → FAIL
- If the system doesn't know the offer → it MUST ask before generating the sequence
- A sequence that says "we help companies streamline their operations" = FAIL (too generic)

**Model**: Use Gemini 2.5 Pro (falls back to GPT-4o-mini). Gemini is PROVEN better for style matching in this codebase (see A/B test results in MEMORY).

**Step 5b — Campaign Settings Verification (MANDATORY — DO NOT SKIP)**
After creating the campaign, you MUST verify EVERY setting by fetching the campaign from SmartLead API:
```
GET /api/v1/campaigns/{NEW_CAMPAIGN_ID}?api_key=...
```
Compare each field against reference campaign 3070919. Log the comparison in `testruns2603.md`:
```
| Setting              | Reference (3070919) | Test Campaign | Match? |
|---------------------|--------------------:|:-------------|:-------|
| track_settings      | []                  | ?             | ?      |
| max_leads_per_day   | 1500                | ?             | ?      |
| enable_ai_esp       | true                | ?             | ?      |
| timezone            | (target geo)        | ?             | ?      |
| min_time_btwn       | 3                   | ?             | ?      |
| stop_lead_settings  | REPLY_TO_AN_EMAIL   | ?             | ?      |
| send_as_plain_text  | true                | ?             | ?      |
| follow_up_%         | 40                  | ?             | ?      |
```
If ANY setting doesn't match → fix it via API and re-verify. Do NOT proceed until all match.

**Step 6 — Contact Quality Verification (REAL CONTACTS IN SMARTLEAD)**
- ALL contacts uploaded to the SmartLead campaign must be REAL people from REAL target companies:
  - C-level or roles relevant to EasyStaff Global's offer (payroll, HR, finance decision-makers, founders, CTOs)
  - From companies that FULLY match the user's search prompt ("IT consulting companies in Miami")
  - With verified email addresses (Apollo-verified)
- **Verify by fetching leads from SmartLead API:**
  ```
  GET /api/v1/campaigns/{ID}/leads-export?api_key=...
  ```
  Check every lead: email, first_name, last_name, company_name must all be populated (no blanks, no "Test Lead")
- Cross-check via Opus: are these companies actually IT consulting firms? Are the contacts actually decision-makers?
- If accuracy is below 90%: write ALL problems to `suck.md` with specific recommendations (change Apollo filters? change GPT-4o-mini prompts? both?)
- Split company analysis into batches if needed (Opus context is large but not infinite)
- **Log in `testruns2603.md`**: total leads uploaded, sample of 5 leads (email, name, company, title), accuracy %

**Step 6b — Credits & Cost Tracking**
- Verify that ALL credit/cost spending is tracked and visible:
  - **Per pipeline run**: Apollo credits used (companies + people searches), OpenAI/GPT-4o-mini tokens spent (analysis, sequence generation)
  - **Account-wide totals**: cumulative Apollo credits, OpenAI costs across all pipeline runs — visible in the Setup page (or Account page, decide which fits better)
  - FindyMail tracking: build the UI column for it but skip actual FindyMail calls for now — use only Apollo verified emails
  - **FindyMail API key is NOT required** for the pipeline to proceed. The onboarding/setup flow must NOT block on missing FindyMail key. It's optional, will be added later.
- The pipeline detail page must show credits breakdown for that specific run
- The setup/account page must show lifetime totals for the whole account
- Log actual costs from this test run in `testruns2603.md`: how many Apollo credits spent, how many OpenAI tokens consumed, total USD cost estimate

**Step 7 — Email Verification**
- For simplicity in this test: skip FindyMail, use Apollo verified emails only for contacts

**Step 8 — Link Sharing & UI Verification (MANDATORY SCREENSHOT TEST)**

The pipeline UI must show campaign destination links. Verify ALL of these in Puppeteer screenshots:

1. **Pipeline page top panel**: After campaign creation, the pipeline page (`/pipeline/{runId}`) MUST show:
   - SmartLead campaign link (purple badge, clickable, opens SmartLead in new tab)
   - "View N people in CRM" button (green, links to `/crm?pipeline={runId}`)
   - Both links must appear in the screenshot — if missing, the feature is broken

2. **Run status API**: `GET /api/pipeline/runs/{runId}` must return a `campaign` object with:
   - `smartlead_id`: the SmartLead campaign ID
   - `smartlead_url`: clickable URL like `https://app.smartlead.ai/app/email-campaigns-v2/{id}/analytics`
   - `name`: campaign name
   - `status`: campaign status

3. **CRM pipeline filter**: `/crm?pipeline={runId}` must show ONLY contacts from that pipeline run (not all contacts)
   - Take screenshot of CRM page with pipeline filter active
   - Verify contacts shown match the pipeline's discovered companies

4. **CRM campaign links**: Each contact in CRM must have:
   - Campaign name visible
   - Campaign name should include a `url` field linking to SmartLead
   - Format: `https://app.smartlead.ai/app/email-campaigns-v2/{id}/analytics`

Log in `testruns2603.md`:
- Pipeline page screenshot path (with SmartLead link visible)
- CRM filtered screenshot path (with pipeline filter active)
- Run status API response showing campaign object
- All link URLs generated

**Step 9 — Reply Tracking & Autoreply Integration**
- Verify that the newly created campaign's replies are tracked in the autoreply system
- New replies must be visible in the Tasks page → Replies subpage
- Confirm the reply processing pipeline is connected: SmartLead webhook → reply classification → ProcessedReply → visible in UI

**Step 10 — Post-Campaign Intelligence Questions (MANDATORY END-TO-END TEST)**

This step is a NON-NEGOTIABLE regression test. You MUST execute ALL 5 queries below via the actual MCP reply tools (replies_summary, replies_list, replies_followups, replies_deep_link) and verify EVERY response contains real data + CRM deep links.

**Test these queries using real MCP tool calls (not direct API curls):**

1. **"Which leads need follow-ups?"**
   - Call `replies_followups` with project_name="EasyStaff-Global"
   - Expected: list of leads where category is interested/meeting_request/question AND no operator reply yet
   - MUST include specific leads with email, company, category, campaign
   - Example from production data: `dileep@thinkchain.co` → interested, "UAE-Pakistan Petr 16/03 - copy"
   - Log: count of leads needing followup, response time

2. **"Which replies are warm? Provide link in CRM to see them"**
   - Call `replies_list` with category="interested"
   - Then call `replies_deep_link` with category="interested"
   - Expected: list of warm leads + CRM deep link URL
   - CRM link format: `http://46.62.210.24:3000/crm?reply_category=interested&project=EasyStaff-Global`
   - Log: count of warm replies, deep link URL, response time

3. **"How many meeting requests do we have?"**
   - Call `replies_summary` for full category breakdown
   - Expected: JSON with category counts (interested, meeting_request, question, not_interested, ooo, etc.)
   - Log: full breakdown, total count, response time

4. **"Show me replies from campaign X"** (pick any campaign from project's campaign_filters)
   - Call `replies_list` with search={campaign_name_fragment}
   - Expected: filtered replies from that specific campaign
   - Log: count, sample leads, response time

5. **"Generate a CRM link for all questions"**
   - Call `replies_deep_link` with category="question"
   - Expected: `http://46.62.210.24:3000/crm?reply_category=question&project=EasyStaff-Global`
   - Open this URL in Puppeteer and take screenshot to verify it loads
   - Log: URL generated, screenshot path, response time

**Every answer MUST include:**
- Actual data (not empty/zero)
- CRM deep links with correct filters
- Response time logged

**Track timing for each question** — log in `testruns2603.md`:
- Query sent at: {timestamp}
- Response received at: {timestamp}
- Duration: {ms}
- Data quality: {count of results, are deep links correct}

If the background reply analysis cache is empty (first run), the tools fall back to the main backend proxy. Replies MUST be scoped to the project's campaigns only (e.g. ~119 replies for "petr" campaigns, NOT 38K from all campaigns).

**Step 11 — Test Email & Activation (FINAL STEP)**

After campaign is created as DRAFT with sequence + contacts + settings:
1. Send test email to the user's email via `send_test_email` endpoint
2. Tell the user: **"Check your email — test emails were sent there. Tell me to run the campaign once you're ready."**
3. Wait for user's explicit confirmation to activate
4. Only after user says "activate" / "run it" / "go" → call `activate_campaign` with user's exact words as `user_confirmation`
5. Log activation in `testruns2603.md` with timestamp + user confirmation text

**For test purposes**: simulate the user saying "activate the campaign" and call `activate_campaign` with `user_confirmation="test activation approved by automated test agent"`. This is ONLY for automated testing — in production, real user confirmation is required.

**CRITICAL**: The campaign MUST be DRAFT until this step. If the campaign is already ACTIVE before Step 11, something is broken → log in suck.md.

---

## PHASE 4b: SECOND USER TEST (USER-SCOPING VERIFICATION)

**This is a MANDATORY test.** After completing Phase 4 with pn@getsally.io, run the SAME flow with a DIFFERENT user to verify user-scoping works.

**Second test user:**
- Email: `services@getsally.io`
- Password: `qweqweqwe`
- Scenario: New user with NO existing SmartLead campaigns, wants to find "fashion brands in Italy"
- **This user does NOT provide email accounts** — the MCP must ask/prompt the user to select accounts before campaign can be pushed

**Steps:**
1. Register `services@getsally.io` as a new MCP account (password: `qweqweqwe`)
2. Connect SmartLead + Apollo using the same shared API keys
3. **Provide company context (BLIND — URL ONLY)**: "My company website is https://thefashionpeople.com/"
   - The MCP MUST scrape the website and extract the value proposition INDEPENDENTLY
   - DO NOT tell the system what the company does — let it discover from the website
   - Log what the system extracted in `testruns2603.md`
   - Compare extracted context against ground truth (see Step 2 blind test)
   - If the system describes the offer WRONG → this is a critical failure, fix extraction logic
4. Create project: "Fashion Brands Italy" with ICP from scraped website
5. Run gathering: "fashion brands in Italy" (Apollo search)
6. Verify: this user sees ONLY their project — NOT the pn@getsally.io projects
7. **Email accounts**: This user does NOT tell the MCP which email accounts to use. The MCP MUST:
   - Ask: "Which email accounts should I use for this campaign?"
   - List available accounts via `list_email_accounts`
   - Wait for user selection before proceeding
   - For test: simulate user picking the first 3 Eleonora accounts
8. Create campaign as DRAFT with GOD_SEQUENCE — sequence MUST reference the ACTUAL offer from thefashionpeople.com
9. Send test email to `services@getsally.io` — campaign stays DRAFT
10. Tell user: **"Check your email — test email sent to services@getsally.io. Tell me to run the campaign once you're ready."**
11. For test: simulate user saying "activate" → call `activate_campaign` with confirmation
12. Switch back to pn@getsally.io and verify their data is unchanged

**Sequence Quality Check for User 2:**
The generated sequence for "Fashion Brands Italy" MUST:
- Reference the ACTUAL offer extracted from the website (not generic B2B — verify against scraped content)
- Use {{first_name}}, {{company}}, {{city}} merge tags
- Have geo case study: "Recently helped a {{city}} fashion brand..." (with numbers)
- NOT be a copy of the EasyStaff sequence (different ICP = different offer)
- Pass the same 10-point GOD_SEQUENCE checklist as User 1

**Screenshots (minimum — ALL pages for BOTH users):**
- `test_user2_setup.png` — second user's setup page (clean, no projects)
- `test_user2_projects.png` — only "Fashion Brands Italy" visible (NOT EasyStaff-Global)
- `test_user2_pipeline.png` — only their pipeline runs visible
- `test_user2_pipeline_campaign_link.png` — pipeline page showing SmartLead campaign link
- `test_user2_crm.png` — CRM with contacts from Fashion Brands pipeline
- `test_user2_learning.png` — Learning page showing this user's data only
- `test_user2_conversations.png` — Conversations/Logs page showing MCP tool calls for this user
- `test_user1_conversations.png` — User 1's conversations (different from User 2's)
- `test_user1_unchanged.png` — pn@getsally.io still sees only their data

**CRITICAL USER-SCOPING CHECKS:**
- User 2 MUST NOT see User 1's projects
- User 2 MUST NOT see User 1's pipeline runs
- User 2 MUST NOT see User 1's contacts in CRM
- User 2's reply tools MUST NOT return User 1's replies
- Violating ANY of these = CRITICAL BUG → log in suck.md and fix immediately

---

## PHASE 4c: SECOND PROJECT FOR USER 2 (MULTI-PROJECT FLOW)

This tests the MCP's ability to handle a user creating a SECOND project after their first one.
User 2 (services@getsally.io) already has "Fashion Brands Italy" from Phase 4b. Now they want a completely different project.

**Scenario**: User says "I also need to find social influencer platforms in UK for https://onsocial.ai/"

**Expected MCP behaviour:**
1. Recognize this is a NEW project request (different ICP, different company, different geo)
2. Create a new project — blind scrape https://onsocial.ai/ to discover the offer
3. Ask: "Do you have existing SmartLead campaigns for this project?" → User says NO
4. Proceed directly to gathering (no blacklist import needed — no campaigns)
5. The user should now have TWO projects visible: "Fashion Brands Italy" AND the new OnSocial project
6. Each project's pipeline must be independent — different companies, different filters

**Steps:**
1. Create project with ONLY the website URL: `{"name": "OnSocial UK Influencers", "website": "https://onsocial.ai/"}`
2. Verify blind offer discovery — what did the system extract? Compare against ground truth
3. Verify User 2 now sees TWO projects (Fashion Brands Italy + OnSocial UK Influencers)
4. Verify projects are independent — different target_segments, different scraped contexts
5. Run gathering: "social influencer platforms in UK" (Apollo search)
6. Verify pipeline runs are project-scoped — OnSocial pipeline doesn't mix with Fashion pipeline
7. Create campaign with GOD_SEQUENCE — sequence must reference OnSocial's actual offer (NOT fashion resale, NOT payroll)

**Blind offer discovery test:**
- Provide ONLY `https://onsocial.ai/` — no description
- System must discover what OnSocial does independently
- Compare against ground truth: `mcp/test_ground_truth/offers/onsocial.json`
- Grade: core offer, target audience, key metrics

**Screenshots:**
- `test_user2_two_projects.png` — projects page showing BOTH projects for User 2
- `test_user2_onsocial_pipeline.png` — OnSocial pipeline with gathered companies
- `test_user2_project_switch.png` — verify switching between projects works

**Key test points:**
- MCP handles multi-project users correctly
- No SmartLead campaigns = no blacklist step, go straight to gathering
- Different projects = different ICPs = different sequences
- User's project list grows as they add projects

---

### HARD RULES — NON-NEGOTIABLE

#### RULE 1: ALL TESTING MUST USE REAL MCP CONNECTION
- Connect to the ACTUAL MCP server running on Hetzner (http://46.62.210.24) — NOT localhost, NOT mocks, NOT simulated API calls
- Every MCP tool call must go through the real SSE transport to the real backend with the real database
- If you cannot establish a real MCP connection, STOP and log the error in `suck.md` — do NOT pretend it works
- Log every MCP request and response in `testruns2603.md` with timestamps

#### RULE 2: ALL UI TESTING MUST USE A REAL BROWSER WITH REAL SCREENSHOTS
- Open the Hetzner-hosted frontend in a REAL browser (use browser MCP / Puppeteer)
- Take a REAL screenshot at EVERY step and save to `mcp/tmp/` directory (create it if it doesn't exist)
- Screenshot naming: `mcp/tmp/test_{step}_{description}_{timestamp}.png`
- Required screenshots — EVERY page must be screenshotted and verified:
  - `test_setup_page.png` — setup/login page with integrations connected
  - `test_project_stats.png` — project page with blacklist stats, reply analysis, CRM/campaign links
  - `test_pipeline_stepper.png` — pipeline detail with horizontal stepper (NOT dropdown)
  - `test_pipeline_targets.png` — pipeline filtered to targets only (?status=target)
  - `test_pipeline_company_modal.png` — click company row → modal with 4 tabs
  - `test_campaigns_list.png` — campaigns page with campaign rows (status, leads, project)
  - `test_campaign_sequence.png` — campaign detail showing 4 email steps with personalization
  - `test_campaign_activate.png` — campaign activate confirmation dialog
  - `test_crm_contacts.png` — CRM page showing gathered contacts
  - `test_crm_pipeline_filter.png` — CRM filtered by ?pipeline={runId}
  - `test_crm_warm_filter.png` — CRM filtered to warm replies
  - `test_conversations.png` — logs page with tool calls (both directions)
  - `test_learning.png` — learning page with pipeline accuracy

  **Cross-page link verification** — click each link and verify destination loads:
  - Pipeline targets count → /pipeline/{id}?status=target ✓
  - Pipeline "View Campaign" → /campaigns/{id} ✓
  - Project "View in CRM" → /crm?project={id} ✓
  - Project "Warm leads" → /crm?project={id}&reply_category=interested ✓
  - Campaign "View Leads" → /crm?campaign={id} ✓
  - Campaign "Source Pipeline" → /pipeline/{runId} ✓
  - `test_learning_page.png` — Learning page with tool usage, pipeline accuracy, reply analysis section
  - `test_contact_conversation.png` — click a contact in CRM → conversation tab shows planned sequence steps
  - `test_conversations_page.png` — /conversations page showing MCP tool calls with direction, method, timestamp
  - `test_conversations_detail.png` — expanded message showing raw JSON payload
- Verify in EACH screenshot: page renders correctly, data appears in tables, filters work, no console errors, no blank sections
- If ANY page is broken, blank, or shows errors — log in `suck.md`, fix it, re-screenshot to confirm fix

#### RULE 3: NO FAKES, NO LIES, NO SHORTCUTS
- NEVER claim a test passes without a real screenshot proving it
- NEVER simulate browser output — actually open the page and capture what you see
- NEVER mock MCP responses — use the real server
- NEVER say "verified" without showing the screenshot path in `testruns2603.md`
- If something fails: log it, fix it, re-test, screenshot the fix. That's the only acceptable flow.
- Every entry in `testruns2603.md` must reference the screenshot file that proves the result

#### RULE 4: DON'T STOP UNTIL DONE
- Do NOT stop until every step above is tested and passes WITH screenshots
- Do NOT stop if you hit an error — fix it and continue
- Do NOT leave partial results — either everything passes or `suck.md` explains what's broken and why

#### RULE 5: CONTINUOUS IMPROVEMENT — FIND NEW SHIT EVERY RUN
- Each cron run MUST try to find at least ONE new issue not in `suck.md`
- Re-read `requirements_source.md` every run — it's the source of truth
- Re-read `mcp/tests/conversations/*.json` — run tests with SHUFFLED prompts
- Compare actual MCP responses against expected behavior in test files
- Score each test dimension (tools called, response structure, links, segments, errors)
- Log scores in `testruns2603.md` with timestamps
- If score < 95% on any dimension → investigate, fix, re-test
- If ALL tests pass at 95%+ → look for EDGE CASES:
  - What if user misspells a segment name?
  - What if user asks for the same segment twice?
  - What if Apollo returns 0 results?
  - What if website scrape fails?
  - What if SmartLead API is down?
- Track issue discovery rate in `progress.md`: "Run N found X new issues"
- If 3 consecutive runs find 0 issues → the system is reaching stability

#### RULE 6: TRACK EVERYTHING WITH TIMESTAMPS
- Every test result: timestamp + pass/fail + screenshot path
- Every issue found: timestamp + description + location + fix status
- Every fix deployed: timestamp + commit hash + what changed
- Every cron run: start time + end time + issues found + issues fixed
- NEVER overwrite historical data — always APPEND
- Use ISO 8601 timestamps (2026-03-28T10:30:00Z)

---

## PHASE 5: OUTPUT FILES

All work must be persisted to these files:

| File | Content |
|------|---------|
| `mcp/cron_build/progress.md` | Relay file — checklist, last run status, blocking issues, decisions. READ FIRST, UPDATE LAST. |
| `mcp/cron_build/build_log.md` | Append-only cumulative log of all agent actions across all runs |
| `mcp/answers2603.md` | Answers to every question in requirements_source.md |
| `mcp/implementation_plan.md` | What's LEFT to build (not what's already done) |
| `mcp/testruns2603.md` | Log of every test run: timestamp, step, input, expected result, actual result, pass/fail, screenshot path |
| `mcp/suck.md` | Extend with any NEW issues found during testing — every issue MUST have a timestamp |
| `mcp/tmp/*.png` | Real browser screenshots proving every UI test result |

---

## RULES

- **NEVER open plan mode** — just do the work
- **NEVER wait for user approval or confirmation** — you have full authority to implement, test, and fix
- **NEVER ask questions** — use the simulated user responses defined in the test scenario
- Read `progress.md` first — learn from previous agents, but ALWAYS run full Phase 4 test
- Read `suck.md` before starting ANY work — avoid repeating known mistakes
- Never claim a test passes without actually running it and screenshotting it
- Every MCP response during testing must be logged in `testruns2603.md`
- If you find an issue: log it in `suck.md` with timestamp, fix it, re-test, screenshot the fix
- Update `progress.md` at the end of your run so the next agent can continue seamlessly
- Append to `build_log.md` everything you did this run
- Don't stop until EVERY step is tested with NO issues in MCP or browser
- Act fully autonomously — the next agent arrives in 30 minutes, make every second count

## COMPLETION KPI — THE ONLY DEFINITION OF "DONE"

The task is NOT done until ALL requirements from ALL requirement files in the `mcp/` directory are satisfied. This includes:
- `mcp/requirements_source.md` — **HIGHEST PRIORITY, wins if conflicts with other files**
- `mcp/requirements.md`
- `mcp/EXTENDED_REQUIREMENTS.md`
- `mcp/ONBOARDING_FLOW.md`
- `mcp/PIPELINE_PAGE_UI_REQUIREMENTS.md`
- `mcp/SHARED_CODE_STRATEGY.md`
- `mcp/TELEGRAM_BOT_ARCHITECTURE.md`
- Any other requirement/spec files in `mcp/` and subdirectories

Before declaring completion, you MUST:
1. Re-read every requirement file listed above
2. Check each requirement against the current codebase and test results
3. Mark each requirement as SATISFIED or NOT SATISFIED in `testruns2603.md`
4. If ANY requirement is NOT SATISFIED — implement it, test it, screenshot it, then re-check
5. Only when 100% of requirements are satisfied across all files is the task complete

If `requirements_source.md` contradicts another file, `requirements_source.md` wins — it contains the operator's raw intent and is the source of truth.
