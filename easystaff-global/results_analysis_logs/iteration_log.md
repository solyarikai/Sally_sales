# EasyStaff Dubai — Analysis Iteration Log

## Goal: 95%+ accuracy on target labeling

---

## Iteration 1 — V1 Scoring Rubric (FAILED)

**Prompt:** Complex 5-dimension scoring (language/industry/service/company_type/geography)
**Result:** Wrong segment names (OTHER_HNWI, INVESTMENT). Hardcoded system prompt overrode custom prompt.
**Accuracy:** ~0% useful (wrong segments entirely)
**Root cause:** GPT-4o-mini can't handle complex multi-dimensional scoring. System prompt was hardcoded.
**Action:** Scrapped V1. Built V2 via negativa.

---

## Iteration 2 — V2 Via Negativa (76% accuracy)

**Prompt:** Exclude shit first, then assign CAPS_LOCKED segment
**Result:** 81 targets, 42 correct (76%), 6 geography errors, 2 solo consultants, 5 borderline
**Accuracy:** 76%

**Errors found:**
| Error type | Count | Examples | Root cause |
|-----------|-------|----------|------------|
| Geography (non-UAE) | 6 | adfa.ir (Iran), click.sd (Sudan), vteck.in (India), cygnusconsulting.com.au (Australia), harshitinfosolutions.com (India), hindtechzone.com (India) | Prompt has no geography filter |
| Solo consultant | 2 | marianwulz.com (1 person), atbc.co (solo advisor in Kerala) | Prompt doesn't exclude individuals |
| Borderline | 5 | anisha.agency (very niche), elifglobal.io (thin site), miden.xyz (global Web3) | Edge cases, acceptable |

**Action:** Build V3 prompt with geography + solo consultant exclusions.

---

## Iteration 3 — V3 (pending)

**Changes from V2:**
1. Added GEOGRAPHY exclusion: "Must be UAE-based or have UAE office"
2. Added SOLO exclusion: "Solo consultants, 1-person operations = NOT_A_MATCH"
3. Added domain TLD check: ".in, .ir, .pk, .com.au without UAE address = suspect"

**Target accuracy:** 95%+
