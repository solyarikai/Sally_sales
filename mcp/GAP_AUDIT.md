# GAP AUDIT — Requirements vs Reality — 2026-03-28

## CRITICAL GAPS (NOT tested, NOT built)

### 1. Blacklist import flow — NOT end-to-end tested
- User says "campaigns with petr" → import_smartlead_campaigns → contacts loaded to CRM
- **Gap**: We never tested that imported contacts appear in CRM page
- **Gap**: We never tested that blacklist blocks companies in subsequent pipeline runs
- **Gap**: No blacklist stats shown on project page (counts, import log)
- **Test needed**: After import, go to /crm and verify contacts are there with campaign names

### 2. Campaign contacts in CRM — NOT tested
- After importing "petr" campaigns, contacts should be visible in CRM
- Each contact should show: campaign name (clickable to SmartLead), company, title
- **Gap**: CRM page never tested with imported contacts
- **Test needed**: Screenshot /crm after campaign import, verify contacts visible

### 3. Contact conversation history — NOT tested in browser
- Click contact in CRM → first tab should show planned sequence OR conversation
- **Gap**: Backend endpoint exists but never verified in browser UI
- **Test needed**: Screenshot contact detail modal with conversation tab

### 4. Campaigns page — imported campaigns NOT shown
- Only MCP-created campaigns show on /campaigns page
- User's existing SmartLead campaigns (imported for blacklist) should ALSO appear
- Need a "source" column: "MCP" vs "Imported" (or "SmartLead existing")
- **Gap**: Campaigns page only shows MCP-created campaigns

### 5. Reply analysis — NOT tested end-to-end in browser
- After importing campaigns, background reply analysis should run
- Results should be visible: warm count, meeting count, etc.
- CRM should show reply_category column
- **Gap**: Reply analysis runs in background but results never verified in UI
- **Test needed**: After import, check /crm with reply_category filter

### 6. Reply intelligence questions — NOT tested via real MCP
- "Which leads need follow-ups?" → should return leads with CRM link
- "Which replies are warm?" → should return filtered list
- **Gap**: Tested via direct curl, not via REST /tool-call with conversation logging
- **Test needed**: Call via /tool-call, verify response, verify in conversations page

### 7. Performance measurement — NOT done
- How long does blacklist import take? (N campaigns, M contacts)
- How long does gathering take? (per 25 companies)
- How long does analysis take? (per company)
- **Gap**: No timing logged anywhere
- **Test needed**: Log timing for each step in testruns2603.md

### 8. Multi-project single prompt — NOT tested
- "Gather IT consulting for EasyStaff AND influencer platforms for OnSocial"
- Should detect 2 projects, ask about campaigns for each
- **Gap**: Only single-project tested
- **Test needed**: Test 02 covers this partially but not the project detection

### 9. CRM reply_intent column — NOT verified
- CRM from main app should show reply intent (interested/meeting/question)
- **Gap**: CRM page shown in screenshots but reply columns not verified
- **Test needed**: Filter CRM by reply_category, verify column visible

### 10. Prompts page content — NOT verified
- Prompts page shows entries but prompt body was empty/truncated
- **Gap**: Prompt text not properly displayed
- **Test needed**: Expand a prompt entry, verify full text visible

## PARTIALLY DONE (built but not fully tested)

### 11. Sequence quality check — NOT automated
- GOD_SEQUENCE checklist exists but not automatically scored
- **Gap**: Manual comparison only, no automated scoring
- **Needed**: Score each generated sequence against 10-point checklist

### 12. Blind offer discovery — tested but not scored
- Website scraping works but extraction quality not scored against ground truth
- **Gap**: No automated comparison (system output vs ground truth JSON)

### 13. A/B subject variants — NOT verified in SmartLead
- Code generates subject_b but SmartLead API rejected inline variants
- **Gap**: Variants may not actually appear in SmartLead

## STATUS SUMMARY
- **CRITICAL gaps**: 10 (need building or testing)
- **PARTIAL gaps**: 3 (built but not verified)
- **KPI honest estimate**: ~75% (not 95% as previously claimed)
