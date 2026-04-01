# God-Level Plan: Fix All MCP Flow UX Issues

## Priority 1: Flow Order (Critical — breaks user experience)

### Fix A: Move blacklist BEFORE gathering
**Current**: preview → confirm (gathers) → ask blacklist → stuck
**Target**: preview → ask blacklist → confirm (gathers with exclusions) → email accounts

**Changes:**
1. `tam_gather` preview response: after showing filters, ask "Proceed? Also — have you launched campaigns for this segment before?"
2. `tam_gather` confirm: accepts `blacklist_campaigns` parameter — excludes contacts before gathering
3. Remove separate blacklist step — merge into tam_gather flow

### Fix B: Pipeline created at preview step (pending_approval)
**Current**: GatheringRun created only on confirm (when companies are fetched)
**Target**: GatheringRun created on PREVIEW with status=pending_approval, filters stored

**Changes:**
1. `tam_gather` preview: create GatheringRun with status="pending_approval", store filters
2. Return pipeline link in preview response
3. `tam_gather` confirm: update existing run, start gathering

### Fix C: After blacklist "no" → proceed (not stuck)
**Current**: pipeline stuck in blacklist phase
**Target**: "no" blacklist → skip to email accounts

**Changes:**
1. Check `tam_blacklist_check` handler — why does it get stuck?
2. When user says "no blacklist", tam_gather confirm should skip blacklist phase entirely
3. Set run.current_phase to next phase after blacklist

## Priority 2: Chat Message Quality

### Fix D: Remove "How many target companies?" question
**Root cause**: Claude AI generates own questions from tool descriptions
**Changes:**
1. tam_gather tool description: "NEVER ask about target count. Use default 100."
2. tam_gather preview response `_instructions`: "Show this EXACTLY as-is. Do NOT add questions."
3. Remove `target_count` from tam_gather input schema (use default)

### Fix E: Cost estimate uses user's target_count + show pages
**Current**: always shows "for ~100 contacts", "2 credits"
**Changes:**
1. Cost estimator: use actual target_count from args (default 100)
2. Show: "10 pages × 100/page, ~600 companies expected, 10 credits"
3. Remove "Max if exhausted" line
4. Show full filter reasoning: WHY industry-first, what keywords generated

### Fix F: Project link in create_project message
**Current**: link at bottom, Claude doesn't show it
**Changes:**
1. Put link in FIRST line: "Project 'X' created: http://..."
2. Already done but verify it's deployed correctly

## Priority 3: Pipeline UI

### Fix G: Hover tooltips content
- (?) for seniority filter: explain what each level means
- (?) for target roles: explain they come from offer analysis
- (?) for "verified only": explain email verification
- (?) for max per company: explain the limit

### Fix H: Infinite scroll for company list
- Replace "Load more" button with IntersectionObserver
- Load next 50 when user scrolls to bottom

### Fix I: Show ALL keywords (not truncated)
- Backlog section shows only 6 keywords — show all 33
- Make scrollable if too many

## Implementation Order

1. **Fix C** (5 min): blacklist "no" → don't get stuck
2. **Fix A** (30 min): merge blacklist into tam_gather flow  
3. **Fix B** (20 min): create pipeline at preview step
4. **Fix D** (10 min): remove target_count question
5. **Fix E** (20 min): fix cost estimate + filter reasoning
6. **Fix F** (5 min): verify project link shows
7. **Fix G** (30 min): hover tooltip content
8. **Fix H** (15 min): infinite scroll
9. **Fix I** (10 min): show all keywords
