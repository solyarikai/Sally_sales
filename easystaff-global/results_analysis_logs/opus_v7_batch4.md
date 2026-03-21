# Opus Review — v7 Batch 4 (AD segment file)

**Date**: 2026-03-21
**Source**: /tmp/opus_review_ad
**Reviewer**: Claude Opus 4.6

## Summary

| Metric | Count |
|--------|-------|
| Total reviewed | 173 |
| OK (true positives) | 167 |
| False positives | 6 |
| FP rate | 3.5% |

## Segment Breakdown

| Segment | Count | FPs |
|---------|-------|-----|
| MARKETING_AGENCY | 44 | 0 |
| MEDIA_PRODUCTION | 55 | 3 |
| PR_AGENCY | 1 | 0 |
| SOFTWARE_HOUSE | 24 | 1 |
| TECH_STARTUP | 5 | 2 |

## False Positives

### 1. manga.com.sa — Manga Productions (MiSK Foundation)
- **Classified as**: MEDIA_PRODUCTION
- **Problem**: Subsidiary of Mohammed bin Salman's MiSK Foundation. Government-backed institutional entity with formal procurement processes. Not a typical service business that hires freelancers through platforms like EasyStaff — they have in-house teams and government contracting rules.

### 2. mediacat.uk — MediaCat UK
- **Classified as**: MEDIA_PRODUCTION
- **Problem**: This is a media industry publication/news site. They publish articles, case studies, editor's picks, and newsletters about the advertising and media industry. They do not produce media content for clients. Wrong segment entirely — not a service business.

### 3. mockai.co — MockAI
- **Classified as**: MEDIA_PRODUCTION
- **Problem**: SaaS product company building an "3D Animation Copilot" tool. They sell software to animators — they do not produce media content for clients. Should be TECH_STARTUP. Not a service business that hires freelancers.

### 4. thekitefactorymedia.com — The Kite Factory
- **Classified as**: MEDIA_PRODUCTION
- **Problem**: Independent media buying/planning agency ("media strategies that move the needle on brand and business"). They plan and purchase ad placements — they do not produce media content. Misclassified segment. If anything this is a MARKETING_AGENCY subcategory, but media buyers are desk-based and unlikely to hire international freelancers through EasyStaff.

### 5. botmaker.com — Botmaker
- **Classified as**: SOFTWARE_HOUSE
- **Problem**: SaaS product company ("Platform for developing AI agents for WhatsApp"). They build and sell their own product — they do not do custom software development for clients. Should be TECH_STARTUP. A software house does client work; Botmaker does not.

### 6. heinonenventures.com — Heinonen Ventures
- **Classified as**: TECH_STARTUP
- **Problem**: Micro venture studio — "2 Ventures Created, 2 Entrepreneurs Backed" since 2023. This is essentially 1-2 people building side projects. Too small and early-stage to need contractor payroll infrastructure like EasyStaff.

## Notes

- GPT-4o-mini classification quality is strong at 96.5% accuracy for this batch.
- Marketing agencies and media production companies are well-identified — zero FPs in the 44 marketing agencies.
- Main weakness: conflating product companies (SaaS/tools) with service businesses, and misidentifying media publications as production companies.
- The TECH_STARTUP segment has the highest FP rate (40%) but tiny sample size (5 entries).
