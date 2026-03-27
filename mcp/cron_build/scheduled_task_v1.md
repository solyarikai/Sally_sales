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

## PHASE 2: ANSWER ALL QUESTIONS

Read `requirements_source.md` line by line. Every question, concern, or "decide yourself" directive in that file needs an answer.

**Output**: Write all answers to `mcp/answers2603.md`. Format: quote the original question/concern, then provide your answer with rationale.

---

## PHASE 3: IMPLEMENTATION PLAN (DELTA ONLY)

Compare what `requirements_source.md` asks for against what's ALREADY BUILT in the codebase. Do NOT list completed work as TODO.

**How to check what's done**: Read the actual source code in `mcp/backend/` and `mcp/frontend/`. Read `suck.md` for fixed issues. Read `test_mcp_flow.py` for tested flows. If a feature exists in code, it's DONE — mark it as such.

**Output**: Write or extend `mcp/implementation_plan.md` with only what's LEFT to build. Group by priority. For each item: what it is, which files need changes, estimated complexity.

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

**Step 3 — Gathering**
- Search for: "IT consulting companies in Miami"
- GEO filter is REQUIRED before initiating the pipeline — the system must collect geographic context (country, city, timezone) from the user's search query. This is mandatory, not optional. The gathered contacts' timezone determines campaign timing (see Step 5).
- Apollo budget: max 20 credits per test run (companies + people combined)
- Target: 50 companies, up to 3 people per company (this is a HARD LIMIT — make it a configurable requirement, user can override explicitly if they want more)

**Step 4 — Email Account Selection**
- When the system asks "which email accounts to use", answer: "Use my email accounts from the campaigns I mentioned before, but only for Eleonora first name, so make sure the signature is for Eleonora"
- The system must filter accounts to only Eleonora's, set proper signature

**Step 5 — Campaign Creation in SmartLead**
- Campaign must be created in SmartLead with:
  - Accounts selected per user's instruction (Eleonora only)
  - **Campaign timing: 9:00 AM to 6:00 PM in the TIMEZONE OF THE GATHERED CONTACTS** — not your local timezone, not UTC. The GEO filter from Step 3 determines this. For "Miami" that's America/New_York (EST/EDT). This is non-negotiable.
  - **All other campaign settings must match the reference campaign** — see https://app.smartlead.ai/app/email-campaigns-v2/3070919/analytics for the exact settings to replicate. This means delivery optimization, send limits, warmup settings, reply handling, and every other non-timing setting. Copy them exactly from this reference campaign via SmartLead API.
  - Test email sent to `pn@getsally.io` (SmartLead has a test email API endpoint)
- Sequences must be high quality — compare against existing campaigns, think like a top SDR
- Sequences must have normalized subject lines: first names and company names clean, human-readable, no special characters or encoding artifacts

**Step 6 — Contact Quality Verification**
- ALL contacts in the newly created SmartLead campaign must be:
  - C-level or roles relevant to EasyStaff Global's offer (payroll, HR, finance decision-makers)
  - From companies that FULLY match the user's search prompt ("IT consulting companies in Miami")
- Verify using scraped website content (it's stored in the database after scraping) — reuse it, don't re-scrape
- Cross-check via Opus: are these companies actually IT consulting firms? Are the contacts actually decision-makers?
- If accuracy is below 90%: write ALL problems to `suck.md` with specific recommendations (change Apollo filters? change GPT-4o-mini prompts? both?)
- Split company analysis into batches if needed (Opus context is large but not infinite)

**Step 7 — Email Verification**
- For simplicity in this test: skip FindyMail, use Apollo verified emails only for contacts

**Step 8 — Link Sharing**
- Verify that MCP shares all relevant links per requirements (SmartLead campaign link, CRM deep links, pipeline page link)

**Step 9 — Reply Tracking & Autoreply Integration**
- Verify that the newly created campaign's replies are tracked in the autoreply system
- New replies must be visible in the Tasks page → Replies subpage
- Confirm the reply processing pipeline is connected: SmartLead webhook → reply classification → ProcessedReply → visible in UI

**Step 10 — Post-Campaign Intelligence Questions**
- After campaign creation and reply analysis is complete, test the MCP's ability to answer these questions about ALL connected campaigns (not just the new one):
  1. "Which leads need follow-ups?" (example: dileep@thinkchain.co) — MCP must return specific leads with context
  2. "Which replies are warm? Provide link in CRM to see them" — MCP must return a CRM deep link with filters pre-set to show warm replies (e.g. `?category=warm&project=EasyStaff-Global`)
  3. Other analytical questions covering all connected campaigns
- Every answer must include CRM deep links to the relevant filtered view — not just text, actual clickable links to the CRM with the correct filters applied
- Track how much time the system needs to answer each question — log durations in `testruns2603.md`
- If the background reply analysis from Step 2b isn't complete yet, the system must handle this gracefully (show progress, partial results, or wait)

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
