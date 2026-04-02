# Test Run Issues — User qwe333@qwe.qwe, Project 430 "Fintech Outreach"

**Date**: 2026-04-02
**Document used**: outreach-plan-fintech.md
**Project URL**: http://46.62.210.24:3000/projects?project=430

## Issues Found

### 1. Sequences not showing on project page
- **Status**: FIXED (deployed)
- **Cause**: Sequences stored in `generated_sequences` table but not in `offer_summary.sequences`. API wasn't reading from the table.
- **Fix**: API now injects sequences from `generated_sequences` into project response.

### 2. Sequences show only subjects, no email bodies
- **Status**: FIXED (deployed)
- **Cause**: Frontend only rendered `Day X: {subject}`, not the body text.
- **Fix**: Expandable email cards showing Day badge + subject + full body text (scrollable).
- **File**: `mcp/frontend/src/pages/ProjectsPage.tsx`

### 3. Only 6 segments extracted (document has 8)
- **Status**: OPEN
- **Observed**: PAYMENTS, LENDING, REGTECH, BAAS/EMBEDDED FINANCE, WEALTHTECH, CRYPTO/DEFI INFRA
- **Document has**: PAYMENTS, LENDING, BANKING-AS-A-SERVICE, REGTECH, INSURTECH, WEALTHTECH, CRYPTO/DEFI, EMBEDDED FINANCE
- **Missing**: INSURTECH, and BaaS + EMBEDDED FINANCE merged into one
- **Cause**: GPT extraction merged similar segments. INSURTECH may have been dropped.

### 4. Only 1 exclusion rule extracted
- **Status**: OPEN
- **Observed**: "generic agencies — To focus on targeted, signal-driven outreach"
- **Expected**: Document doesn't have explicit "Shit List" like Pavel's doc, so only 1 implicit exclusion extracted. This is correct behavior — the extractor only finds what's in the document.

### 5. Campaign settings not shown on project page
- **Status**: FIXED (deployed)
- **Fix**: Added campaign_settings to offer_summary. Frontend shows: tracking, stop on reply, daily limit, plain text as colored tags.

### 6. Geo filters not visible on project page
- **Status**: FIXED (deployed)
- **Fix**: Frontend now shows apollo_filters.locations (Geo), funding_stages (Funding), employee_range (Size) in "Search Filters" section.

### 7. Funding info not visible on project page
- **Status**: FIXED (deployed)
- **Fix**: Same as #6 — shown in Search Filters section.

### 8. Approval flow — what happens after user approves?
- **Status**: TRACKING
- **Details**: User sees "APPROVAL PENDING". After approve, MCP should ask about previous campaigns, then email accounts, then launch pipeline.

### 9. MCP tool calls fail with -32602 after server restart
- **Status**: KNOWN ISSUE (mistake #7 in DOCUMENT_BASED_FLOW.md)
- **Cause**: mcp-backend was restarted (code deploy). Old SSE session invalidated. Claude Code sends tool calls to stale session → "Received request before initialization was complete"
- **Fix**: User must restart Claude Code to get fresh SSE connection with proper initialization handshake.

### 10. confirm_offer fails with "Invalid request parameters"
- **Status**: Same as #9 — stale session after server restart
- **Fix**: Restart Claude Code

### 11. 3 draft campaigns created instead of 1
- **Status**: FIXED (deployed)
- **Fix**: create_project now creates ALL GeneratedSequence records but only ONE Campaign (linked to primary/first sequence). Alternative sequences stored as GeneratedSequence records for later selection.

### 12. "Fintech Outreach Campaign" has 138 accounts but 3 sequence campaigns don't
- **Status**: FIXED (deployed)
- **Fix**: align_email_accounts now REUSES existing mcp_draft campaign (created by create_project) instead of creating a new one. 1 campaign gets both sequence + accounts.

### 13. "No sequence data available" on the main campaign
- **Status**: FIXED (deployed)
- **Fix**: Same as #12 — campaign reuse means the campaign that gets accounts is the same one with the primary sequence linked.

### 14. Email accounts subpage NOT built (from DOCUMENT_BASED_FLOW.md)
- **Status**: OPEN
- **Requirement**: DOCUMENT_BASED_FLOW.md section "Email Accounts Subpage UX" specifies:
  - URL: /campaigns/accounts
  - Show all 2400+ accounts from SmartLead cache
  - Search bar to filter by name/email
  - Saved lists section (e.g. "Rinat TFP" = 14 accounts)
  - Click list → shows all accounts
  - Create new list from filter
- **Current**: No accounts subpage exists. Accounts shown only as count on campaign card.

### 15. 4 campaigns instead of 1 — confusing UX
- **Status**: FIXED (deployed)
- **Fix**: create_project creates 1 campaign (not 1 per sequence). align_email_accounts reuses it. Result: 1 campaign with sequence + accounts + settings.

### 16. CRITICAL: After accounts setup, MCP asks user to describe segments AGAIN
- **Status**: CRITICAL — OPEN
- **Observed**: After align_email_accounts confirms 138 accounts, MCP asks "Now describe your target segment — what audience should we go after?"
- **Expected**: The document ALREADY has all target info (6 segments, keywords, geo US/UK/EU/UAE/SG, size 20-500, funding Series A-D). After accounts are set, MCP should AUTOMATICALLY:
  1. Run filter_mapper using extracted data from offer_summary
  2. Call tam_gather (preview) with those filters
  3. Show Apollo probe results + filters to user
  4. User approves → pipeline starts automatically
- **Cause**: The `confirm_offer` response tells Claude to ask about target segment, but when document_text was provided, the target is ALREADY known.
- **Fix**: `confirm_offer` response should check if offer_summary has segments/keywords. If yes, skip the "describe your segment" question and tell Claude to proceed to tam_gather directly with the extracted filters.
- **File**: `mcp/backend/app/mcp/dispatcher.py` — confirm_offer handler response + align_email_accounts response

### 17. 4 campaigns but only 1 has accounts — sequence not linked to account campaign
- **Status**: FIXED (deployed)
- **Fix**: Single campaign architecture — create_project creates 1 campaign with primary sequence, align_email_accounts reuses same campaign and adds accounts.

### 18. Email accounts not visible when clicking on campaign
- **Status**: OPEN
- **Observed**: Campaign card shows "138 accounts" but clicking/expanding doesn't show the actual account list (emails, names).
- **Expected**: Clicking on campaign should show all 138 email accounts with their email addresses and sender names.
- **Related**: Issue #14 (email accounts subpage not built). At minimum, the campaign detail should show account list inline.

### 19. Pipeline preview shows Run ID without link
- **Status**: OPEN
- **Observed**: "Run ID: 477 | Strategy: keywords_first" — just a number, not clickable
- **Expected**: "Run ID: 477 (link)" → http://46.62.210.24:3000/pipeline/477
- **File**: `dispatcher.py` — tam_gather preview response should include pipeline link

### 20. CRITICAL: Keywords shown in Locations field
- **Status**: FIXED (deployed)
- **Cause**: filter_mapper regex matched "companies **in** payments, lending..." from target_segments text — treated segment names as locations.
- **Fix**: After filter_mapper runs, dispatcher now reads project.offer_summary.apollo_filters.locations and OVERRIDES whatever filter_mapper produced. Document-extracted geo is authoritative.

### 21. Only 52 companies found from probe (expected 100+)
- **Status**: EXPECTED TO RESOLVE with #20 fix
- **Notes**: With correct locations (US/UK/EU instead of "payments, lending"), Apollo should return many more companies. Re-test after #20 fix.

### 22. Cost estimate seems low
- **Status**: TRACKING  
- **Observed**: "~$1.01 (101 credits — 1 search + 100 people enrichment)"
- **Notes**: Only counting 1 search page. Real pipeline will use 25-150 pages. Estimate should reflect actual pages needed.

### 23. Funding filters not applied from document
- **Status**: FIXED (deployed)
- **Cause**: Document extractor saves funding_stages in offer_summary.apollo_filters but tam_gather never read them. filter_mapper doesn't extract funding.
- **Fix**: After filter_mapper, dispatcher reads offer_summary.apollo_filters.funding_stages and sets filters["organization_latest_funding_stage_cd"]. Preview now shows "Funding: Series A, Series B, Series C, Series D". Pipeline L0 streams use funded filters.

## Deployed (2026-04-02)

All fixes deployed to mcp-backend + mcp-frontend:
- dispatcher.py: doc filter override (#20, #23), 1-campaign architecture (#11-#15-#17), campaign reuse (#12-#13), campaign_settings in offer_summary (#5), funding in preview message
- ProjectsPage.tsx: Search Filters section (geo/funding/size), Campaign Settings section, sequence bodies (#2)
