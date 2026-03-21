# V8 Full Review — Batch 07 (MARKETING_AGENCY)

**Date**: 2026-03-22
**Reviewer**: Claude Opus 4.6
**Source file**: `/tmp/v8_review_ag`
**Total entries reviewed**: 278
**Segment**: MARKETING_AGENCY

## Summary

| Metric | Count |
|--------|-------|
| Total reviewed | 278 |
| OK (real service agency with freelancers) | 268 |
| False positives | 10 |
| FP rate | 3.6% |

## False Positives

| # | Domain | Name | Reason |
|---|--------|------|--------|
| 1 | digitalhubaustralia.com.au | Digital Hub Australia | Compromised/spam site. Website text contains injected PHP code ("Boss SEO Backlink - Cache Bypass") — not a legitimate operating agency. |
| 2 | disishiphop.com | Dis Is Hip Hop | Content/media platform, not a service agency. Describes itself as a "Content Networking Hub" promoting creators — media property, not a business that hires freelancers for client work. |
| 3 | fiftyfiveandfive.com | Fifty Five and Five | Product/SaaS company, not a service agency. "We build AI tools for sales and marketing teams" — sells software products to enterprises, not marketing services. |
| 4 | gilescain.com.au | Giles Cain Media | Solo consultant/personal brand. Named after an individual ("Giles Cain"), positioned as a niche property digital marketing consultant — no team indicators. |
| 5 | hoole.co | Hoole Marketing | Solo consultant/personal brand. "Melanie Hoole.co" — personal-brand site for a single real estate social media consultant. Sells DIY programs, not agency services. |
| 6 | inseekidentity.com.au | InSeek Identity | Solo freelancer selling DIY templates. Offers "DIY Packages" and "Free resources for savvy" businesses — not a service agency with a team hiring contractors. |
| 7 | kyra.com | Kyra | Ad-tech/SaaS platform. "AI-powered influencer team" — a technology platform for influencer marketing at scale, not a traditional service agency with freelancers. |
| 8 | luna-park-media.com | Luna Park Media | Ad-tech/media platform. "We operate consumer online communities" and manage "a portfolio of digital media" — operates owned media properties, not a client-services agency. |
| 9 | mintegral.com | Mintegral | Ad-tech platform/SDK. Provides "AI-powered marketing solutions for user acquisition and monetization" — mobile ad network and SDK provider, not a service agency. |
| 10 | midasacademy.com.sg | Midas Academy | Training academy, not a service agency. "Academy" in the name, positioned as a training/education provider for marketing, not an agency hiring freelancers for client work. |

## Notes

- The batch is overwhelmingly clean (96.4% OK). The MARKETING_AGENCY segment is well-targeted for EasyStaff Global.
- Most entries are legitimate marketing/PR/creative agencies across AU, UK, SG, US, and KSA — all geographies where agencies routinely hire freelancers and contractors.
- Borderline calls kept as OK: very small agencies (gimucco.com, moriahventures.net), holding companies (miromaset.com, msqpartners.com), and niche consultancies (gold-goose.com, getwildidea.com) — all still plausibly hire freelancers.
