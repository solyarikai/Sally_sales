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
