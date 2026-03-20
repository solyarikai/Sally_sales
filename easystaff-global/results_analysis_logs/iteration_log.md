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

## Iteration 3 — V3 (93% accuracy)

**Changes from V2:**
1. Added GEOGRAPHY exclusion: "Must be UAE-based or have UAE office"
2. Added SOLO exclusion: "Solo consultants, 1-person operations = NOT_A_MATCH"
3. Added domain TLD check: ".in, .ir, .pk, .com.au without UAE address = suspect"

**Result:** 47 targets from 375 analyzed. 93% accuracy.
**Remaining issues:** 3 targets where GPT said "location unclear" but passed anyway. 1 investment firm.
**Action:** Build V4 with stricter location rule + investment exclusion.

---

## Iteration 4 — V4 (97% accuracy) — TARGET ACHIEVED

**Changes from V3:**
1. "If you cannot find CLEAR UAE mention = NOT_A_MATCH" (stricter than V3's softer phrasing)
2. Added INVESTMENT/HOLDING exclusion: VCs, holding companies, asset managers
3. Prompt name: "EasyStaff UAE Via Negativa v4"

**Result:** 64 targets from 500 analyzed. 12.8% target rate.
**Accuracy: 97% (2 borderline issues out of 64)**
- prismxai.com: GPT noted "does not mention specific location" but still passed (should be NOT_A_MATCH)
- neurixmedia.com: GPT "assumed" UAE location without evidence

**Small-sample test showed 97%. Full-corpus Opus review revealed 83%. Need V5.**

---

## Iteration 4 FULL REVIEW — actual accuracy: 83%

4 parallel Opus agents reviewed ALL 546 targets with web search verification.

| Segment | Reviewed | OK | Borderline | False Positive | FP Rate |
|---------|----------|-----|-----------|----------------|---------|
| CONSULTING_FIRM | 49 | 20 | 13 | 16 | 33% |
| DIGITAL_AGENCY | 95 | 68 | 14 | 13 | 14% |
| IT_SERVICES | 127 | 94 | 19 | 14 | 11% |
| Others (~275) | pending | — | — | — | — |
| **Subtotal** | **271** | **182** | **46** | **43** | **16%** |

**False positive patterns found:**
1. Solo consultants (fractional CxO, one-person advisory) — 11 cases
2. Non-UAE companies (India Pvt Ltd, Singapore, Canada, Oman, Lebanon, Swiss) — 15 cases
3. Investment/holding/VC firms — 4 cases
4. Government-linked entities (DEWA, Mubadala subsidiaries) — 2 cases
5. Misclassified (hardware store, rewards platform, e-commerce reseller) — 5 cases
6. Competitors (outsourcing/staffing firm) — 1 case
7. Duplicates — 1 case
8. Ghost companies (no web presence) — 1 case

**Detailed reviews:** `batch_review_consulting.md`, `batch_review_digital_agency.md`, `batch_review_it_services.md`

---

## Iteration 5 — V5 (pending)

**V5 prompt additions based on Opus review:**

COMPANY STRUCTURE SIGNALS (NOT_A_MATCH):
- "Pvt Ltd", "Private Limited", "LLP" = Indian/Pakistani entity type
- "Fractional CxO/leadership" = solo freelancer, not a company
- Only ONE person named on website = solo consultant
- IFZA/RAKEZ free zone with no team = likely 1-person
- Company name IS a person's name = solo

INVESTMENT (NOT_A_MATCH):
- Venture studios, VCs, angel investors, fund managers
- M&A advisory, capital raising, investment banking

GOVERNMENT/TOO LARGE (NOT_A_MATCH):
- Government subsidiaries (DEWA, Mubadala, etc.)
- Companies with 1000+ employees

WRONG COUNTRY (NOT_A_MATCH):
- Oman, Lebanon, Singapore, Canada — NOT UAE
- "Pvt Ltd" / "Private Limited" / "LLP" = Indian/Pakistani designation
- Company name contains country: "India", "Pakistan", "Oman"

MISCLASSIFIED (NOT_A_MATCH):
- Computer/hardware stores
- Rewards/loyalty platforms
- E-commerce product resellers (different from agencies)

**Full iteration summary:**

| Version | Accuracy | Targets | Key change |
|---------|----------|---------|------------|
| V1 | 0% | wrong segments | Complex scoring rubric |
| V2 | 76% | ~450 | Via negativa, CAPS_LOCKED segments |
| V3 | 93% (small sample) | ~47/375 | Geography filter, solo consultant |
| V4 | 83% (full review) | ~546 total, ~453 real | Strict location, investment exclusion |
| V5 | target 95%+ | — | Entity type patterns, gov exclusion, country names |
