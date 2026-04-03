# Pipeline Iteration Log

## Iteration 3 (baseline — generic prompt, seniority scoring)
- **Companies**: 123 targets from 138 scraped
- **Opus verified**: 81/123 correct = **66%** (32 not-target, 10 wrong-segment)
- **People**: 179 total
- **Opus verified**: 111/179 correct = **62%** (68 wrong roles)
- **Issues**: Generic prompt "Classify if target", seniority ranking with "Product Owner"=rank 0

## Iteration 4 (via negativa prompt, hardcoded EXCLUDE_ROLES)
- **Companies**: 70 targets from 138 (51% target rate — stricter)
- **Opus verified**: 57/70 correct = **81%** (+15% improvement)
- **False negatives**: 13/68 rejections were wrong (19% — too aggressive on "B2C")
- **People**: 138 from 50 companies
- **Issues**: B2C exclusion too aggressive (Unlimit, Veriff, Jumio wrongly rejected). EXCLUDE_ROLES was HARDCODED.

## Iteration 5 (less aggressive B2C, GPT role selection — NO hardcoding)
- **Companies**: 88 targets from 138 (64% target rate)
- Classification: "WHEN IN DOUBT include", B2C clarified to "PURE B2C with NO B2B product"
- **People**: 149 from 60 companies
- Roles: CEO(12), CRO(7), Co-Founder(6), Head of Sales(3), CSO(3), CMO(3), VP Sales(4)
- **Key change**: Removed ALL hardcoded role exclusions. GPT-powered role selection — dynamic, works for any industry.
- Tested on Pavel's iGaming doc: correctly extracts CTO/Head of Product as target roles (IT outsourcing audience)
- **Opus verification**: PENDING (2 agents running)

## Changes Made

### Classification (streaming_pipeline.py)
- Via negativa prompt: EXCLUDE non-targets, keep everything else
- Dynamic segments from project.offer_summary
- "WHEN IN DOUBT: include" to reduce false negatives
- B2C exclusion: "PURE B2C with NO B2B product" (not just "sells to consumers")

### People (apollo_service.py)  
- Removed ALL hardcoded EXCLUDE_ROLES and EXCLUDE_SUBSTRINGS
- Added `_gpt_rank_candidates()`: sends candidate list + target roles to GPT-4o-mini
- GPT returns ranked indices of matching candidates
- Works for ANY industry — fintech gets CEO/CRO, iGaming gets CTO/Head of Product
- Cost: 1 GPT-4o-mini call per company (~$0.001)

### DB Schema (mcp-postgres)
- offer_summary, website, offer_approved columns on projects (were missing)
- target_people, max_people_per_company, pages_fetched, campaign_id on gathering_runs
- mcp_usage_logs table for prompt logging
- smartlead_accounts_cache + email_account_lists tables

### Document Flow (dispatcher.py)
- create_project accepts document_text parameter
- Extracts: offer, roles, segments, sequences, campaign settings
- Creates GeneratedSequence records from document sequences
- Creates draft Campaign linked to sequence
- Shows all extracted data to user for approval

## Iteration 6 (Agent #2 dynamic prompt, dynamic GPT role selection — ZERO hardcoding)
- **Companies**: 98 targets from 138 (71% target rate — more inclusive)
- Agent #2 generated classification prompt dynamically from offer text (1627 chars)
- NO hardcoded exclusion categories
- **People**: 125 from 60 companies
- GPT role prompt with ZERO hardcoded exclusion functions
- CEO(14), CRO(7), Co-Founder(6), Head of Sales(2), VP Sales(2), CMO(2)
- Still some CTO/DevOps getting through (GPT not strict enough on compound titles)
- **Opus verification**: PENDING
- **Sequence**: 100% match (4/4 emails from document)

### Pavel iGaming Case
- Document extraction: 8 segments correctly identified
- Target roles: CTO, Head of Development, Product Manager (correct for IT outsourcing audience)
- Agent #2 generated iGaming-specific classification prompt
- Apollo search: 0 results (iGaming not in Apollo keyword taxonomy)
- **BLOCKER**: Need seed-company enrichment approach (not keyword search) for niche industries
- Pipeline_spec.md describes this as "industry_first from enrichment" — enrich seed domains to get Apollo industry IDs

## Iteration 8 (minimal via negativa + gpt-4o for role selection)
- **Companies**: 116 targets from 138 (minimal prompt — very inclusive)
- **People**: 122 from 60 companies
- Roles: CEO(12), CRO(3), Head of Marketing(4), VP Marketing(3), CCO(4), Co-Founder(4), President(3)
- Only ~11 wrong roles (91% preliminary) — major improvement from 78% thanks to gpt-4o
- **Key change**: gpt-4o instead of gpt-4o-mini for _gpt_rank_candidates (~$0.005/call)
- **Opus verification**: PENDING

## Iteration 12 — BREAKTHROUGH (Agent #2 + exclusion list + "when in doubt include")
- **Companies**: 98.6% overall (86 targets, 52 rejected) — **EXCEEDS 90% TARGET**
- **Segment accuracy**: 97.6% — **EXCEEDS 90% TARGET**
- **People**: 78.4% (116/148 correct, 32 wrong)
- **Sequence**: 100% (word-for-word match)
- **Campaign settings**: 100% (all settings match, Rinat accounts attached)
- **Overall weighted score**: 92.9% — **EXCEEDS 90% MINIMUM**
- **Key change**: Agent #2 meta-prompt emphasizes "B2B product arm = include" + exclusion list
- People accuracy limited by Apollo candidate pool (no sales people at some companies)

## Key Decisions Made
1. Via negativa classification: GPT decides what to EXCLUDE based on offer context (dynamic, no hardcoding)
2. Agent #2 (Classification Prompt Generator): GPT generates the classification prompt per project
3. GPT role selection: Sends candidate list + target titles to GPT, returns matching indices
4. All approaches are fully dynamic — work for fintech, iGaming, or any other industry
5. Apollo keyword search works poorly for niche industries — need enrichment-based approach as fallback
