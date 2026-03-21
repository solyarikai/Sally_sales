# Opus v7 Batch 2 Review — GPT-4o-mini Target Classification Audit

**Reviewed by**: Claude Opus 4.6
**Date**: 2026-03-21
**Source**: `/tmp/opus_review_ab`

## Summary

| Metric | Count |
|--------|-------|
| Total companies reviewed | 172 |
| OK | 165 |
| FALSE POSITIVE | 7 |
| False positive rate | 4.1% |

## Segment Breakdown

| Segment | Count | FP | FP Rate |
|---------|-------|----|---------|
| DIGITAL_AGENCY | 115 | 2 | 1.7% |
| EVENTS_AGENCY | 1 | 0 | 0% |
| GAME_STUDIO | 20 | 0 | 0% |
| IT_SERVICES | 36 | 5 | 13.9% |

## False Positives

### DIGITAL_AGENCY

1. **unmiss.com** (UNmiss.com) — This is a SaaS product ("AI Agent for Organic Growth through SEO & GEO"), not a service agency. No indication they hire freelancers; it is an automated tool/platform.

2. **usetwirl.com** (Twirl) — UGC creator marketplace/platform connecting brands with 900+ creators. This is a platform business, not a service agency that hires its own freelancers. The creators are the platform's supply side, not employees/contractors Twirl pays.

### IT_SERVICES

3. **caxus.net** (CAXUS) — Cybersecurity product company selling "QuantumShield" automated platform. Positioned as a luxury product, not a consulting/services firm that would hire freelance contractors.

4. **cybral.com** (Cybral) — Product company with "patented AI" for Data Security Posture Management. Has worldwide offices and R&D centers. This is a funded security product startup, not an IT services firm hiring freelancers.

5. **dmsisystems.com** (DMS Systems) — WhatsApp API partner / SaaS platform for business messaging (campaigns, OTP, chatbots). Product company, not a services firm.

6. **faradaysec.com** (Faraday) — "All-in-One Security Platform" for vulnerability management and attack simulations. Pure SaaS product company with subscription plans.

7. **gatefy.com** (Gatefy) — Email security product company ("handles millions of emails"). SaaS platform for inbound/outbound email protection, not a services business.

## Notes

- The DIGITAL_AGENCY segment is very clean (98.3% accuracy). GPT-4o-mini correctly identified agencies that do client work and likely hire freelancers.
- The GAME_STUDIO segment is perfect. All 20 are legitimate game studios, mostly Saudi-based indie studios that would benefit from EasyStaff for paying international freelance artists/developers.
- The IT_SERVICES segment has the highest FP rate (13.9%) because GPT-4o-mini conflates cybersecurity/SaaS product companies with IT service firms. The distinguishing signal: product companies sell a platform (subscriptions, "powered by AI"), while service companies sell people's time (consulting, managed services, outsourcing).
- No GPT_MISSED cases identified in this batch. All companies that were classified as targets are at least plausibly service businesses except the 7 listed above.
