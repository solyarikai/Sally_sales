# Opus Verification — Iteration 2 (REAL, not keyword matching)

## Companies (61 targets verified by Opus)

| Batch | Checked | Correct | Wrong Segment | Not Target | Accuracy |
|-------|---------|---------|---------------|------------|----------|
| 1-20 | 20 | ~12 | ~3 | ~5 | ~60% |
| 21-40 | 20 | 10 | 3 | 7 | 50% |
| 41-61 | 21 | 4 | 3 | 14 | 19% |
| **Total** | **61** | **~26** | **~9** | **~26** | **~43%** |

### Issues:
- Many companies are NOT B2B fintech (recruitment agencies, media companies, consulting firms)
- The keywords "fintech" are too broad — catches fintech-adjacent but not fintech companies
- Segment labels sometimes wrong (banking company labeled PAYMENTS instead of BANKING-AS-A-SERVICE)

## People (121 contacts verified by Opus)

| Batch | Checked | Correct Role | Wrong Role | Accuracy |
|-------|---------|-------------|------------|----------|
| 1-40 | 40 | 22 | 18 | 55% |
| 41-80 | 40 | ~30 | ~10 | ~75% |
| 81-121 | 41 | 29 | 12 | 71% |
| **Total** | **121** | **~81** | **~40** | **~67%** |

### Issues:
- Wrong roles: Chief People Officer, Head of BI, Head of Engineering (HR/tech, not sales/growth)
- Some companies are not even fintech → people at wrong companies
- Need stricter role filtering in enrich_by_domain

## Sequence
- Need to verify extracted sequence matches document word-by-word
- Agent started comparison but output truncated

## Campaign/Accounts
- Campaign 570 no longer exists (was deleted during cleanup)
- Need to re-create and verify

## OVERALL REAL SCORE
- Companies: ~43% (target: 95%)
- People: ~67% (target: 95%)
- FAR BELOW TARGET — MUST ITERATE

## What Needs to Change
1. Classification prompt must be MUCH stricter about what's "fintech"
2. Exclude: recruitment agencies, media, consulting, non-B2B
3. People search must only enrich VP Sales/CRO/CEO/CMO/Head of Growth — not random "Head of" roles
4. Need to re-run pipeline with improved prompts and re-verify
