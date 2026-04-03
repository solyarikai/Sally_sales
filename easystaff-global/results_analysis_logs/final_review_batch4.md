# Final Review — Batch 4 (batch_ad)

**Date:** 2026-03-21
**Total reviewed:** 92 (90 unique domains — 2 duplicates: g-f-y.com, pixelpilgrimstudios.com)
**OK:** 72
**FALSE_POSITIVE:** 18 (+ 2 duplicates removed)

---

## FALSE POSITIVES

### Wrong Location (not UAE/GCC) — 12

| Domain | Name | Segment | Reason |
|--------|------|---------|--------|
| g-f-y.com | Good For You | MEDIA_PRODUCTION | Based in Ridgewood, NYC. No UAE presence. (Also duplicate — appears twice, lines 25-26) |
| pixelpilgrimstudios.com | Pixel Pilgrim Studios, LLC | SOFTWARE_HOUSE | Based in Los Angeles, CA. No UAE presence. (Also duplicate — appears twice, lines 51-52) |
| lukasa.com | Lukasa | SOFTWARE_HOUSE | Unspecified location. No UAE indicators on website. "Mid-market companies" — likely US-based. |
| feldroy.com | Feldroy | TECH_STARTUP | Based in US (Audrey & Daniel Roy Greenfeld). 2-person open-source consultancy, not a company that hires freelancers. |
| sent.dm | Sent | TECH_STARTUP | Based in the United States. Messaging API SaaS. No UAE presence. |
| uselayers.com | Layers | TECH_STARTUP | Based in the United States. Shopify Plus AI search. No UAE presence. |
| hathora.dev | Hathora | TECH_STARTUP | Unspecified location, US VC-backed compute orchestration. No UAE presence. |
| subspace.com | Subspace 2.0 | TECH_STARTUP | Unspecified location, US-based network infrastructure. No UAE presence. |
| supademo.com | Supademo | TECH_STARTUP | Unspecified location. AI product demos SaaS. No UAE indicators. |
| phinite.ai | Phinite.ai | TECH_STARTUP | Unspecified location. Multi-agent AI platform. No UAE indicators. |
| fantix.ai | Fantix | TECH_STARTUP | Unspecified location. AI privacy platform. No UAE indicators. |
| slateteams.com | Slate | TECH_STARTUP | Unspecified location. AI content SaaS. No UAE indicators. |

### Not a Real Freelancer-Hiring Company — 4

| Domain | Name | Segment | Reason |
|--------|------|---------|--------|
| collabute.com | Collabute | TECH_STARTUP | AI productivity tool — early-stage SaaS product, not a company with freelancer hiring needs. No location. |
| enric.ai | Enric | TECH_STARTUP | Automated code refactoring SaaS. Pure product company, no freelancer needs indicated. No location. |
| getmojito.com | Mojito | TECH_STARTUP | Web3 loyalty platform. No location, no evidence of freelancer usage. |
| odynn.com | Odynn | TECH_STARTUP | AI loyalty/rewards platform. No location, no evidence of team or freelancer needs. |

### Competitor — 1

| Domain | Name | Segment | Reason |
|--------|------|---------|--------|
| smorchestra.ai | SMOrchestra | TECH_STARTUP | B2B lead generation / GTM agency for MENA. Direct competitor to outreach services — sells "signal-driven B2B revenue" and lead gen. |

### Borderline (segment mismatch, kept as OK) — 1

| Domain | Name | Segment | Note |
|--------|------|---------|------|
| olap.ae | Olap Digital Solutions | TECH_STARTUP | More accurately a SOFTWARE_HOUSE (Odoo ERP partner/implementor), not a startup. Kept as OK since it's UAE-based and hires developers. |

---

## Summary

- **90 unique companies** after removing 2 duplicates
- **72 OK** — real UAE/GCC companies in correct segments that plausibly hire freelancers
- **18 FALSE POSITIVES** — 12 wrong location, 4 not real freelancer-hiring companies, 1 competitor
- **False positive rate: 20%** (18/90)
- Nearly all FPs are in the TECH_STARTUP segment where the scraper picked up global SaaS companies with no UAE presence
- MARKETING_AGENCY and MEDIA_PRODUCTION segments are clean (only 1 FP each — both location issues)
- SOFTWARE_HOUSE segment mostly clean (2 FPs — location issues)
