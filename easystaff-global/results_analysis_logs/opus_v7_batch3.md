# Opus Review — Batch 3 (AC file)

**Reviewer:** Claude Opus 4.6
**Date:** 2026-03-21
**Source:** /tmp/opus_review_ac

## Summary

| Metric | Count |
|--------|-------|
| Total reviewed | 172 |
| OK (true targets) | 158 |
| False Positives | 14 |
| FP rate | 8.1% |

**Segments reviewed:** IT_SERVICES (57), MARKETING_AGENCY (115)

---

## False Positives

### IT_SERVICES

| # | Domain | Company | Reason for FP |
|---|--------|---------|---------------|
| 1 | innoplanet.net | Innovation Planet | Hardware reseller/VAR (Dell, HP workstations, business email). Sells boxes, not services. Unlikely to hire freelancers. |
| 2 | intelliipro.com | IntelliiPRO Technologies | Website is just a page title — zero content to validate. Classification based on speculation. |
| 3 | lenience.sa | LENIENCE | Startup accelerator + IT solutions. Accelerators invest, they don't typically hire freelancers at scale. |
| 4 | lunixa.sa | Lunixa Cloud Solutions | Just a page title and language toggle — no actual content to validate the classification. |
| 5 | mdscs.sa | MDS for Computer Systems | Just "Best IT Services Provider" — no content to confirm they actually deliver services vs resell hardware. |
| 6 | neomtech.com | Neom Tech | Captive technical partner for a single insurance platform (BCare). Not a multi-client service business — one dedicated client relationship. |
| 7 | nodetech.com.sa | Node Technologies | Page title only, no website content to validate. |
| 8 | skyviewads.com | Skyview Smart Solutions | Page title only, no website content to validate. |
| 9 | upixnetworks.com | UPIX | Telecom infrastructure provider (connectivity, fiber, network ecosystem). Sells bandwidth and network capacity, not professional services requiring freelancers. |
| 10 | zenitharabia.com | Zenith Arabia | Website says "Samtia" — sells smart classroom hardware, AV equipment, medical devices. Education/healthcare hardware distributor, not a service business. |

### MARKETING_AGENCY

| # | Domain | Company | Reason for FP |
|---|--------|---------|---------------|
| 11 | agencymarketingmachine.com | Agency Marketing Machine | Productized marketing service for insurance agencies (templates, lead gen tools). More SaaS/tooling than an agency hiring freelancers. |
| 12 | brandmyagent.com | The Limitless Agent Company | "PayPerClose Leads" — lead gen product for real estate agents. Productized service, not a creative agency with freelancer teams. |
| 13 | onar.com | ONAR (OTCQB:ONAR) | Publicly traded holding company that acquires marketing businesses. A conglomerate/investment vehicle, not an operating service business. |
| 14 | rtrsports.com | RTR Sports Marketing LTD | Italian-language motorsport sponsorship broker. Matches sponsors to racing teams — deal brokerage, not a service business with freelancer workforce. |

---

## Notes

- IT_SERVICES batch is generally well-classified. Most Saudi/global IT service companies genuinely deliver projects using mixed teams (employees + contractors). Good targets for EasyStaff.
- MARKETING_AGENCY batch is strong. Agencies are textbook EasyStaff targets — they routinely hire freelance designers, copywriters, developers across borders.
- The 5 "page title only" FPs (intelliipro, lunixa, mdscs, nodetech, skyviewads) could be re-scraped. If real content exists, they may actually be valid targets. Scrape failures, not classification errors.
- StarkCloud (starkcloud.com) is Spanish/LATAM-based — kept as OK since EasyStaff Global covers international corridors and cloud consultancies hire remote talent.
