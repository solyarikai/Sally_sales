# Final Review — Batch 3 (AC targets)

**Date:** 2026-03-21
**Total reviewed:** 100 lines (98 unique companies — 2 duplicates)
**OK:** 90
**FALSE_POSITIVE:** 8

---

## FALSE POSITIVES

| # | Domain | Segment | Reason |
|---|--------|---------|--------|
| 1 | `agentrypr.com` | MARKETING_AGENCY | **Wrong location.** Based in New York, NY — NOT UAE. The AI reasoning itself states "Company is based in New York, NY." Appears twice in list (lines 55+56, duplicate entry). |
| 2 | `nanowebgroup.com` | MARKETING_AGENCY | **Wrong location.** Based in New York, NY — NOT UAE. The AI reasoning itself states "Company is based in New York, NY." Appears twice in list (lines 92+93, duplicate entry). |
| 3 | `credocomms.com` | MARKETING_AGENCY | **Wrong location.** AI says "Abu Dhabi" but website content shows address: "PO Box 16122 Collins Street West Victoria 8007 Australia." Likely Australia-based. |
| 4 | `este.systems` | IT_SERVICES | **Solo consultant.** "Independent consulting" with "30+ Years Experience" — reads as one-person advisory, not a company that hires freelancers. No team indicators on the site. |
| 5 | `chaptersmarketing.com` | MARKETING_AGENCY | **Solo/micro consultancy.** Founded by one person (Selini Bishop) who quit her job in 2023. "Founder Story" framing, no team mentioned — likely a solo operator, not a freelancer-hiring agency. |
| 6 | `breachsimrange.io` | IT_SERVICES | **Niche specialist, unlikely freelancer hirer.** Offensive cybersecurity red-teaming firm in Masdar City. Extremely specialized ops security work — these teams are typically small, in-house only, would not use a freelancer payment platform. |
| 7 | `kahani.ae` | MARKETING_AGENCY | **Solo/micro operation.** "Storytelling-led" personal branding, content creation. The site copy reads as a one-person creative shop, no team or company structure visible. |
| 8 | `gotracktech.com` | IT_SERVICES | **Segment mismatch — FZC financial services company.** Listed as IT_SERVICES but prominently offers "financial services" and is structured as an FZC (Free Zone Company). More of a financial/corporate services hybrid than a pure IT services firm that would hire tech freelancers. |

---

## DUPLICATES (same domain appears twice)

| Domain | Lines | Action |
|--------|-------|--------|
| `agentrypr.com` | 55, 56 | Remove both (false positive — wrong location) |
| `nanowebgroup.com` | 92, 93 | Remove both (false positive — wrong location) |

---

## SUMMARY

- 52 IT_SERVICES companies reviewed — 49 OK, 3 FP (este.systems, breachsimrange.io, gotracktech.com)
- 48 MARKETING_AGENCY companies reviewed — 41 OK, 5 FP (agentrypr.com x2, nanowebgroup.com x2, credocomms.com, chaptersmarketing.com, kahani.ae)
- Location accuracy: 95/98 correct UAE location (3 wrong: 2x New York, 1x Australia)
- Segment accuracy: 97/98 correct labels (1 mismatch: gotracktech.com)
- The bulk of IT_SERVICES and MARKETING_AGENCY targets are legitimate UAE companies with teams that would plausibly hire freelancers.
