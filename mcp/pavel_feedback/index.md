# MCP UI/UX Feedback — Pavel L. (2026-03-30)

## Testing Context
- User: pavel.l@getsally.io (user_id: 29)
- Task: Gather iGaming technology providers for Mifort project
- Mifort = IT outsourcing company (mifort.org), clients = iGaming providers

---

## Bug 1: Token not shown after signup
- **Where:** Setup page → Sign Up flow
- **What:** After registration, frontend silently saves token to localStorage and redirects. User never sees the full token.
- **Impact:** Token is needed for Claude Code MCP connection. Only way to get it = DevTools console `localStorage.getItem('mcp_token')`
- **Expected:** Modal with full token + Copy button after signup
- **Files:** `LoginPage.tsx` (lines 40-41), `SetupPage.tsx` (line 66 — shows only `token.slice(0,24)...`)

## Bug 2: MCP does not confirm filters before gathering
- **Where:** `tam_gather` flow
- **What:** MCP immediately launches gathering without showing Apollo filters to user for approval
- **Impact:** User cannot review/correct keywords, industries, size before credits are spent
- **Expected:** MCP shows proposed filters → user confirms → then gather starts

## Bug 3: Apollo keyword_tags not validated — garbage filters
- **Where:** `tam_gather` → Apollo API call
- **What:** MCP generates arbitrary keyword strings ("iGaming", "slot developer", "casino game studio") that don't exist in Apollo's taxonomy. First run (emulators): 0 results. API run: 502 companies but 98% irrelevant.
- **Impact:** 2% target rate on run 241 (6 targets out of 330 analyzed). Wasted credits.
- **Expected:** Exploration phase should probe Apollo first, discover real taxonomy, then build filters from confirmed targets (exploration_service.py exists but NOT wired into tam_gather)

## Bug 4: Gemini integration error
- **Where:** Setup page
- **What:** Clicking "Connect" for Gemini shows `{"detail":"Unsupported integration: gemini"}`
- **Impact:** Minor — Gemini not required for core flow
- **Expected:** Either support Gemini or remove from UI

## Bug 5 (CRITICAL): Apollo/Clay emulators not implemented in MCP
- **Where:** `gathering_service.py` → `_get_adapter()`
- **What:** `apollo.companies.emulator`, `apollo.people.emulator`, `clay.companies.emulator` — listed in docs and tools but no adapters exist. Returns None silently.
- **Impact:** Free gathering impossible. Only paid Apollo API works.
- **Expected:** Either implement emulators or clearly indicate they're unavailable

## Bug 6: No Apollo credit tracking visible to user
- **Where:** Pipeline page, Setup/Account page
- **What:** After `tam_gather` runs, user has no idea how many Apollo credits were spent
- **Impact:** User cannot track spend or budget
- **Expected:** Show credits used per pipeline run + cumulative on Account page

## Bug 7: tam_analyze crashes with KeyError 'confidence'
- **Where:** `gathering_service.py` lines 567-571, 630, 642
- **What:** `target_list.append(...)` doesn't include "confidence" key, but later code tries to sum/sort by it
- **Impact:** Analysis phase crashes on first attempt
- **Status:** Fixed by MCP agent during test session (auto-fix)

## Bug 8: 29% of companies not scraped (137/471)
- **Where:** Scraper service
- **What:** Without Apify proxy, scraper fails on many sites (Cloudflare, JS-heavy, rate limits)
- **Impact:** Potential targets lost — can't analyze what you can't scrape
- **Status:** Apify key added to MCP env by Petr after feedback. New runs should be better.

## Bug 9: MCP connection breaks after container rebuild
- **Where:** Claude Code ↔ MCP SSE connection
- **What:** When MCP agent rebuilds the backend container, SSE connection drops. Login fails with "MCP error -32602: Invalid request parameters" and "Received request before initialization was complete"
- **Impact:** User must fully restart Claude Code session (exit + relaunch)
- **Expected:** Graceful reconnect or clear error message with instructions

## Bug 10: No Apify field in Setup UI
- **Where:** Setup page → API Keys section
- **What:** Only SmartLead, Apollo, OpenAI, Gemini shown. No Apify field.
- **Impact:** User cannot connect Apify proxy through UI. Had to be inserted directly into DB/env.
- **Additional:** Scraper reads Apify from env vars, not from user's integration_settings. So even if field existed, it wouldn't work per-user.
- **Expected:** Add Apify to Setup + make scraper read from user's settings

## Bug 11: MCP does not understand client vs competitor context
- **Where:** `tam_analyze` GPT prompt
- **What:** For Mifort (IT outsourcer), iGaming providers are CLIENTS, not competitors. But GPT prompt described ICP as "iGaming technology providers" and then rejected 321 companies as "direct competitors" because they provide iGaming solutions.
- **Impact:** 97.3% of companies marked NOT_A_MATCH. Run 241: only 6 targets.
- **Root cause:** MCP did not ask "what do YOU sell?" before gathering. Without understanding Mifort's offer (outsourcing), it confused the ICP (clients) with competitors.
- **Expected:** MCP must scrape sender's website (mifort.org) first, understand the offer, and build the GPT prompt with correct client/competitor distinction. Exploration phase should handle this.

## Bug 12: GPT segment naming broken — "YOU_ARE_CLASSIFYING"
- **Where:** `tam_analyze` → GPT response parsing
- **What:** GPT took a chunk of the prompt text ("YOU ARE CLASSIFYING") as a segment name instead of real segments (SLOT_DEVELOPER, CASINO_PLATFORM, etc.)
- **Impact:** 6 out of 7 targets got nonsense segment names
- **Status:** MCP agent attempted re-analyze with fixed prompt

## Bug 13: Exploration service exists but not connected
- **Where:** `exploration_service.py` exists, `EXPLORATION_PHASE_PLAN.md` documents the approach
- **What:** The god-level exploration system (probe → enrich → reverse-engineer filters) is built but NOT wired into `tam_gather`. MCP goes straight to full search with unvalidated filters.
- **Impact:** This is the root cause of bugs 3, 11, 12 — bad filters, no context, bad prompts
- **Expected:** Wire exploration_service.py into tam_gather as the default first step

---

## Pipeline Page UI Feedback (screenshot: [8.PNG](8.PNG))

### Issue 14: "Project" column is confusing
- **Where:** Pipeline page → PROJECT column
- **What:** Shows "Mifort iGaming" but my project is just "Mifort". "iGaming" is the segment, not the project name.
- **Expected:** Project column should show just the project name ("Mifort"). Segment info belongs in the Segment column.

### Issue 15: Segment column unclear
- **Where:** Pipeline page → SEGMENT column
- **What:** Shows tags like CASINO_PLATFORM, SLOT_GAME_DEVELOPER, TARGET. These are GPT classification labels, not the segment I asked for. I asked for "iGaming providers" — that should be the segment name.
- **Expected:** Segment should show what the user requested (e.g. "iGaming Providers"), not internal GPT labels. GPT labels (CASINO_PLATFORM etc.) should be visible inside the pipeline detail, not in the list view.

### Issue 16: Source column shows "api" / "emulator" — meaningless to user
- **Where:** Pipeline page → SOURCE column
- **What:** Shows "api", "emulator", "clay.emulator". User doesn't know what this means.
- **Expected:** Show the actual source in human-readable format: "Apollo Search", "Apollo (free)", "Clay", "CSV Import", "Google Sheet". Technical source_type should be hidden or in a tooltip.

### Issue 17: "Raw" and "Targets" columns need explanation
- **Where:** Pipeline page → RAW and TARGETS columns
- **What:** "Raw" = total companies found by Apollo. "Targets" = companies GPT marked as relevant. But there's no label/tooltip explaining this. "Raw" is a technical term.
- **Expected:** Rename: "Raw" → "Companies Found" or just "Found". "Targets" is ok but could be "Matched" or have a tooltip "Companies matching your ICP". Also show the conversion rate (e.g. "31/471 = 7%").

---

## Pipeline Detail Page — Top Bar Feedback (screenshot: [7.PNG](7.PNG))

### Issue 18: "Blacklis" — typo, missing letter "t"
- **Where:** Pipeline detail → stepper bar
- **What:** Shows "Blacklis" instead of "Blacklist"
- **Expected:** Fix typo → "Blacklist"

### Issue 19: Stepper bar — unclear what each step means for the user
- **Where:** Pipeline detail → stepper bar (Gather → Blacklis → Filter → Scrape → Analysis → Verifica → Done → Done)
- **What:** User sees green checkmarks and step names but doesn't understand:
  - What does each step do?
  - Why are there two "Done" steps?
  - "Verifica" is truncated — should be "Verification" or "Verify"
  - "Filter" vs "Blacklist" — what's the difference from user perspective?
- **Expected:** Either add tooltips explaining each step, or simplify to fewer user-meaningful steps (e.g. "Collecting → Analyzing → Ready"). Two "Done" steps make no sense — should be one.

### Issue 20: "13 credits" — credits for what?
- **Where:** Pipeline detail → green badge "13 credits"
- **What:** Shows "13 credits" but user doesn't know:
  - Credits for what service? (Apollo? OpenAI? Total?)
  - Is 13 a lot or a little? What's the budget?
  - Were these already spent or estimated?
- **Expected:** Tooltip or expanded view: "Apollo: 10 credits (search), OpenAI: ~$0.03 (analysis)". Or at minimum label it: "13 Apollo credits used"

### Issue 21: "14% target rate" — unclear what this refers to
- **Where:** Pipeline detail → green badge "14% target rate"
- **What:** Shows "14% target rate" but user doesn't understand:
  - 14% of what? (of all companies found? of scraped? of analyzed?)
  - Is this good or bad? What should it be?
  - How many companies is that in absolute numbers?
- **Expected:** Show absolute numbers too: "7 targets / 50 analyzed (14%)" or make it clickable to filter table to targets only

---

## Prompts Page Feedback (screenshot: [6.PNG](6.PNG))

### Issue 22: No way to edit prompts before running
- **Where:** Prompts page (`/pipeline/:id/prompts`)
- **What:** Prompts are read-only. User cannot edit a prompt and re-run analysis with the updated version.
- **Expected:** User should be able to:
  1. See all prompts/filters BEFORE pipeline starts (pre-launch review)
  2. Edit a prompt inline or in a modal
  3. Click "Re-run with this prompt" to re-analyze
  4. Compare results between original and edited prompt
- **Why it matters:** SDR needs to control what GPT looks for. If the prompt is wrong (e.g. confusing clients with competitors), user must be able to fix it without going back to chat.

### Issue 23: No prompt summary — hard to scan
- **Where:** Prompts page → PROMPT BODY column
- **What:** Shows raw prompt text truncated. With multiple prompts it's impossible to quickly understand what each one does and how they differ.
- **Expected:** Auto-generated short summary (3-5 words) for each prompt, e.g.:
  - "iGaming target classification (via negativa)"
  - "Re-analyze: exclude operators"
  - "Blacklist check: mifort campaigns"
  This way user can scan the list and quickly find which prompt to edit or compare results.

### Issue 24: "YOU_ARE_CLASSIFYING" and "TARGET" labels are broken/confusing
- **Where:** Prompts page → PROMPT BODY column, first two rows
- **What:** Shows tags like `YOU_ARE_CLASSIFYING` and `TARGET` as green/purple badges. These are:
  - `YOU_ARE_CLASSIFYING` — GPT literally took a piece of the prompt instruction as a segment name (Bug 12)
  - `TARGET` — the segment label GPT assigned to matched companies
  - `tool` rows (tam_blacklist_check, tam_scrape, tam_analyze) have no tags — inconsistent
- **Expected:** These internal labels should not be shown as badges. If showing segment labels, use the actual requested segment ("iGaming Providers"). The `system` vs `tool` distinction is also unclear to the user — what's the difference?

### Issue 25: Tool rows (tam_blacklist_check, tam_scrape, tam_analyze) show 0/0 — why are they here?
- **Where:** Prompts page → last 3 rows
- **What:** Shows tam_blacklist_check, tam_scrape, tam_analyze with 0 companies, 0 targets, no accuracy. These are pipeline step calls, not prompts.
- **Expected:** Prompts page should only show actual GPT prompts used for classification/analysis. Pipeline tool calls belong in the Logs page, not here. Mixing them is confusing.

---

## Companies Table Feedback (screenshot: [5.PNG](5.PNG))

### Issue 26: Table columns not resizable
- **Where:** Pipeline detail → companies table
- **What:** Columns are static width. No drag handle to grab and resize columns left/right. Table is cramped — can't make a column wider to see full content or narrower to save space.
- **Expected:** Draggable column borders to resize, like in any spreadsheet or CRM table.

### Issue 27: "TARGET: false" column is redundant when status = rejected
- **Where:** Companies table → TARGET column
- **What:** If status is "rejected", the TARGET column shows "false". This is saying the same thing twice in different columns. If it's rejected, of course it's not a target.
- **Expected:** Remove TARGET column entirely. Status column already tells the story (rejected = not target, target = target). Per PIPELINE_PAGE_UI_REQUIREMENTS.md, there should be no separate target boolean column.

### Issue 28: Segment values — not agreed with user, unclear how they're determined
- **Where:** Companies table → SEGMENT column
- **What:** Shows values like `NOT_A_MATCH` but raises fundamental questions:
  - How are segments determined? Where is the initial list of segments?
  - For example, is `CASINO_PLATFORM` a segment? `SLOT_GAME_DEVELOPER`? Who decided these names?
  - GPT apparently invents segment names on its own without showing them to the user first
  - User was NEVER shown or asked to confirm segment categories before analysis started
  - This ties back to the bigger problem (Bug 2, Bug 11): MCP doesn't agree the GPT prompt with the user before running, so user has no control over what segments exist
- **Expected:** Before analysis, MCP should propose segments: "I'll classify companies into: SLOT_DEVELOPER, CASINO_PLATFORM, GAME_AGGREGATOR, PAYMENT_PROVIDER, NOT_A_MATCH. Ok?" User confirms, edits, or adds segments. Only then run analysis.

### Issue 29: "Load more" button broken — pagination doesn't work
- **Where:** Companies table → bottom of list (shows top 50)
- **What:** The button to load more companies beyond the initial 50 is broken:
  - Sometimes doesn't respond to clicks at all
  - Sometimes results disappear/reset after clicking
  - The number options change inconsistently — shows "load 50" then "100" then "200"
  - End result: user can only see top 50 companies, can't access the rest
- **Expected:** Reliable lazy loading. Either infinite scroll with spinner, or a working "Load more" button that consistently adds rows without losing existing ones.

### Issue 30: INDUSTRY column — same value for everyone, useless
- **Where:** Companies table → INDUSTRY column
- **What:** Shows "Information Technology" for almost every single company. This comes from Apollo, but it's so generic that it provides zero useful information — of course iGaming tech companies are in "Information Technology".
- **Expected:** Either show more specific Apollo sub-industry categories, or hide this column by default. When every row shows the same value, the column is just noise.

### Issue 31: KEYWORDS column shows SIC/NAICS codes — NOT keywords
- **Where:** Companies table → KEYWORDS column
- **What:** Column is labeled "KEYWORDS" but shows values like "7993, Web & Search", "7999, 71329", "7933, 71329". Looking at the Source JSON, these are `sic_codes` (7993 = Coin-Operated Amusement Devices) — NOT keyword tags.
  - The column header says "Keywords" but the data is industry classification codes
  - Are actual Apollo keyword tags even being collected? If so, where are they?
  - If keyword tags weren't collected from Apollo, that's a separate backend issue
  - It seems like INDUSTRY and KEYWORDS columns are pulling from the same SIC/NAICS data — they might be the same list displayed differently
- **Expected:** Show actual Apollo `q_organization_keyword_tags` that matched the search. These are the tags like "iGaming", "casino software", "game developer" that Apollo uses for company classification. If the company has no keyword tags, show empty — NOT SIC codes labeled as keywords. SIC/NAICS codes should be a separate field if shown at all.

### Issue 32: Can't tell if there are more columns after CITY — no horizontal scroll
- **Where:** Companies table → rightmost visible column
- **What:** CITY appears to be the last visible column, but there's no way to know if more columns exist to the right:
  - No horizontal scrollbar
  - No indicator of hidden columns
  - No column visibility toggle
  - User literally cannot tell if the table ends at CITY or if there's more data off-screen
- **Expected:** Either a visible horizontal scrollbar, or a column visibility toggle button (like CRM pages typically have) showing all available columns with checkboxes to show/hide.

---

## Company Detail Modal Feedback (screenshots: [4.PNG](4.PNG) Analysis, [3.PNG](3.PNG) Details, [2.PNG](2.PNG) Scrape, [1.PNG](1.PNG) Source)

### Issue 33: Analysis tab — 3 badges that all say the same thing, unclear what they relate to
- **Where:** Company modal → Analysis tab
- **What:** Shows 3 badges: `NOT_A_MATCH`, `0% confidence`, `rejected`. Problems:
  - All three say the same thing — "not a match" = "rejected" = "0% confidence of being a target". Why show it 3 times?
  - What do these statuses relate to? What criteria were used? What was the GPT even looking for?
  - "0% confidence" — confidence in what exactly? In the rejection? In being a target? This is meaningless without context
  - Maybe if the pipeline had worked correctly (proper segments, proper offer context), these badges would make more sense. But right now with broken prompts, it's just 3 pieces of confusing noise
- **Expected:** One clear verdict with context. Example: "Verdict: NOT A TARGET. Reason: [one line]. Segment: GAME_DEVELOPER (but excluded because Mifort already provides similar services)." Remove confidence entirely — per Petr's own feedback, GPT is terrible at providing confidence scores, it only confuses things.

### Issue 34: Analysis reasoning is WRONG — GPT thinks our CLIENT is our COMPETITOR
- **Where:** Company modal → Analysis tab → reasoning text
- **What:** Says "1X2 Network is a direct competitor as it provides iGaming solutions and develops games, which is the same service that Mifort offers."
  - This is FACTUALLY WRONG. 1X2 Network is a slot/game developer — they are a POTENTIAL CLIENT for Mifort's outsourcing/outstaffing services
  - Mifort does NOT develop games. Mifort builds custom software FOR companies like 1X2 Network (anti-fraud, ML systems, dashboards — see Mifort's iGaming case studies)
  - The scraped text on the Scrape tab clearly says "1X2 Network is a leading provider of iGaming solutions, offering a wide range of innovative games" — this is EXACTLY what Mifort's clients look like
  - GPT confused "who we're looking for" (iGaming tech providers) with "who we are" (also tech, but outsourcing/outstaffing, not games)
- **Root cause:** MCP never scraped mifort.org to understand what Mifort actually sells. Without knowing Mifort = IT outsourcer, GPT has no way to distinguish clients from competitors. This is Bug 11 — the exploration phase must understand the sender's offer first.
- **Expected:** After proper offer discovery, reasoning should say something like: "1X2 Network develops casino games and slots — potential client for Mifort's development services. They likely need backend engineers, ML specialists, QA — matches Mifort's offering."

### Issue 35: Details tab — Keywords field shows SIC codes instead of actual keywords
- **Where:** Company modal → Details tab → Keywords field
- **What:** Shows "7993, Web & Search". Looking at the Source tab JSON, `sic_codes: ["7993"]` — this is SIC code 7993 (Coin-Operated Amusement Devices), NOT an Apollo keyword tag.
  - The field is labeled "Keywords" but displays industry classification codes
  - Were actual Apollo keyword tags (`q_organization_keyword_tags`) even collected during the search?
  - If yes, why aren't they displayed? If no, why not — they're crucial for understanding why Apollo returned this company
- **Expected:** Display actual Apollo keyword tags that this company has in its Apollo profile. If the company has no keyword tags in Apollo, show "No keywords available". SIC/NAICS codes should be displayed separately under their correct labels, not mixed into a "Keywords" field.

### Issue 36: Details tab — missing useful data that exists in Source JSON
- **Where:** Company modal → Details tab vs Source tab
- **What:** Details shows: Industry, Employees, Country, City, Revenue, Phone, Founded, View on Apollo. But the Source tab JSON has MORE useful fields that aren't surfaced in Details:
  - `linkedin_url: "http://www.linkedin.com/company/1x2-network"` — LinkedIn company page, very useful for SDR, NOT shown in Details
  - `headcount_6m_growth: 0` and `headcount_12m_growth: 0.214` — company is growing 21% in last year, useful signal for outreach timing, NOT shown
  - `num_contacts_in_apollo: 17` — tells SDR how many people they can find at this company, NOT shown
  - The data is literally RIGHT THERE in the system, just not displayed on the user-facing tab
- **Expected:** Add to Details tab: LinkedIn link (clickable), headcount growth (as "Growing: +21% last 12mo"), contacts in Apollo count. These are directly useful signals for SDR work.

### Issue 37: Scrape tab — wall of text, could be formatted better
- **Where:** Company modal → Scrape tab
- **What:** Scraped text is a raw dump — no paragraphs, no structure. Contains "Read more" button artifacts, navigation menu text, game titles, news snippets all mashed together. Hard to read for a human.
- **Expected:** Not critical since this is mainly for AI consumption, not human reading. But could improve with: paragraph breaks between sections, stripping navigation/menu elements, or generating a short AI summary at the top ("1X2 Network: iGaming content supplier, develops slots and table games, aggregation platform, Brighton UK, est. 2002") with raw text below.

### Issue 38: Source tab — raw JSON dump, unclear purpose, useful data buried
- **Where:** Company modal → Source tab
- **What:** Shows raw Apollo JSON with no context. User questions:
  - What is this? (no header/label saying "Raw data from Apollo")
  - Why would I need this? (no explanation of when this is useful)
  - If there's useful data here (LinkedIn, growth, contacts count), why isn't it on the Details tab?
  - This tab feels like a debug/developer view, not a user-facing feature
- **Expected:** Either: (1) Label it clearly "Raw Apollo Data (debug)" and collapse by default, surfacing useful fields into Details tab. Or (2) rename to "Apollo Profile" and display the JSON in a more structured, human-readable format with field labels instead of raw key-value pairs.

---

## Summary

| # | Bug | Severity | Status |
|---|-----|----------|--------|
| 1 | Token not shown after signup | Medium | Open |
| 2 | No filter confirmation before gather | High | Open |
| 3 | Apollo filters not validated | Critical | Open (root: exploration not connected) |
| 4 | Gemini integration error | Low | Open |
| 5 | Emulators not implemented | Critical | Open |
| 6 | No credit tracking | Medium | Open |
| 7 | KeyError 'confidence' in analyze | High | Fixed (auto) |
| 8 | 29% scrape failures | High | Partially fixed (Apify added to env) |
| 9 | MCP connection breaks on rebuild | Medium | Open |
| 10 | No Apify in Setup UI | Medium | Open |
| 11 | Client/competitor confusion | Critical | Open (root: no offer context) |
| 12 | GPT segment naming broken | High | Partially fixed (re-analyze) |
| 13 | Exploration service not connected | Critical | Open |
