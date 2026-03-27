# MCP Build & Test — Scheduled Agent Task

You are a FULLY AUTONOMOUS agent working on the MCP (Model Context Protocol) lead generation platform. This task runs every 30 minutes via cron. You must pick up where the previous agent left off and push forward.

## AUTONOMY RULES — READ FIRST

- **NEVER open plan mode** — you are not planning, you are DOING
- **NEVER wait for user approval** — all decisions are yours, just make them and move forward
- **NEVER ask questions** — simulate user responses as defined in the test scenario below
- **NEVER stop to confirm** — act, test, fix, continue
- You are one agent in a relay chain. The next agent (in 30 minutes) will continue your work. Make their job easy.

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
- [ ] Phase 1: Context loaded
- [ ] Phase 2: Questions answered → answers2603.md
- [ ] Phase 3: Implementation plan updated → implementation_plan.md
- [ ] Phase 4 Step 1: Registration tested
- [ ] Phase 4 Step 2: Project setup tested
- [ ] Phase 4 Step 2b: Background reply analysis launched
- [ ] Phase 4 Step 3: Gathering tested
- [ ] Phase 4 Step 4: Email accounts selected
- [ ] Phase 4 Step 5: Campaign created in SmartLead
- [ ] Phase 4 Step 6: Contact quality verified (≥90%)
- [ ] Phase 4 Step 7: Email verification done
- [ ] Phase 4 Step 8: Links shared and verified
- [ ] Phase 4 Step 9: Reply tracking confirmed
- [ ] Phase 4 Step 10: Intelligence questions answered
- [ ] Phase 5: All output files written
- [ ] KPI: All requirement files checked, 100% satisfied

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

**Step 1 — Fresh Registration (CLEAN SLATE EVERY RUN)**
- EVERY test run starts with a clean account. This is mandatory.
- Before creating a new account:
  1. **Soft-delete the previous test account** — do NOT hard-delete. Mark as `is_deleted=true` (or equivalent). The new account must NOT see any data from previous test runs — clean scope, as if a brand new user.
  2. **Keep all data in the database** — `discovered_companies`, `company_scrapes`, `company_source_links`, `gathering_runs`, `approval_gates` from ALL previous test runs must stay in the DB. These cost real Apollo credits. They are invisible to the new test account but queryable by us directly via SQL. If asked "what was gathered during test run N?", the data is there.
  3. **Log SmartLead campaign links BEFORE removing** — write the SmartLead campaign URL (`https://app.smartlead.ai/app/email-campaigns-v2/{id}/analytics`) to `testruns2603.md` and `build_log.md` for each test campaign created. Then DELETE the SmartLead test campaign via API — otherwise test emails will hit the operator's real inbox.
- Register fresh as `pn@getsally.io` with a new account
- Obtain MCP API token
- Log in `testruns2603.md`: previous account soft-deleted at {timestamp}, SmartLead campaigns removed (links preserved in log), new account created at {timestamp}

**Step 2 — Project Setup & Telegram Notifications**
- Tell the MCP: "Take 'petr' including campaigns as my EasyStaff-Global project setup"
- The system must: detect SmartLead campaigns matching "petr", import contacts as blacklist, create the EasyStaff-Global project
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

**Step 3 — Gathering (with Probe-and-Iterate Quality Loop)**
- Search for: "IT consulting companies in Miami"
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

**Verification**: After pushing sequence to SmartLead, fetch it back via API and verify EACH checklist point. Log pass/fail in `testruns2603.md`. If ANY point fails → regenerate with better prompt and re-push.

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

---

## PHASE 4b: SECOND USER TEST (USER-SCOPING VERIFICATION)

**This is a MANDATORY test.** After completing Phase 4 with pn@getsally.io, run the SAME flow with a DIFFERENT user to verify user-scoping works.

**Second test user:**
- Email: `petru4o144@gmail.com`
- Password: `qweqweqwe`
- Scenario: New user with NO existing SmartLead campaigns, wants to find "fashion brands in Italy"

**Steps:**
1. Register `petru4o144@gmail.com` as a new MCP account
2. Connect SmartLead + Apollo using the same shared API keys
3. Create project: "Fashion Brands Italy"
4. Run gathering: "fashion brands in Italy" (Apollo search)
5. Verify: this user sees ONLY their project — NOT the pn@getsally.io projects
6. Create campaign, upload contacts, send test email to `petru4o144@gmail.com`
7. Verify: `petru4o144@gmail.com` receives the test email
8. Switch back to pn@getsally.io and verify their data is unchanged

**Screenshots (minimum):**
- `test_user2_setup.png` — second user's setup page (clean, no projects)
- `test_user2_projects.png` — only "Fashion Brands Italy" visible (NOT EasyStaff-Global)
- `test_user2_pipeline.png` — only their pipeline runs visible
- `test_user1_unchanged.png` — pn@getsally.io still sees only their data

**CRITICAL USER-SCOPING CHECKS:**
- User 2 MUST NOT see User 1's projects
- User 2 MUST NOT see User 1's pipeline runs
- User 2 MUST NOT see User 1's contacts in CRM
- User 2's reply tools MUST NOT return User 1's replies
- Violating ANY of these = CRITICAL BUG → log in suck.md and fix immediately

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
- Required screenshots (minimum):
  - `test_setup_page.png` — setup/login page after registration
  - `test_project_created.png` — project page after EasyStaff-Global creation
  - `test_pipeline_running.png` — pipeline page during gathering
  - `test_pipeline_complete.png` — pipeline page after all phases
  - `test_crm_contacts.png` — CRM page showing gathered contacts
  - `test_campaign_created.png` — SmartLead campaign confirmation
  - `test_deep_links.png` — verify deep links resolve to correct pages
  - `test_replies_page.png` — Tasks/Replies page showing campaign replies are tracked
  - `test_crm_warm_filter.png` — CRM filtered to warm replies via deep link
  - `test_crm_followups.png` — CRM showing leads that need follow-ups
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
