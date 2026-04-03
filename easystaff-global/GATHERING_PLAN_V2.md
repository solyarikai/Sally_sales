# EasyStaff Global — Gathering Plan V2

**Date**: 2026-03-24
**Based on**: 27 qualified leads reverse-engineered through Apollo + pipeline validation

---

## Strategy: Shift from Website Analysis to Apollo Label Filtering

### Why

Pipeline validation showed that **website content analysis alone cannot identify our ICP**:
- V7 (service business focus): 47% recall — misses all product companies
- V10 (broad): 59% recall, 90% false positive rate
- V11 (balanced): 53% recall, 90% false positive rate

**Root cause**: Our qualified leads are companies that pay people abroad, but their WEBSITES don't say "we pay freelancers internationally." You can't tell from glasshardware.com that they have contractors in Dominican Republic. You can only tell from their REPLY to our outreach.

### New Approach: Apollo-First, Website-Second

```
1. Apollo filters (industry + size + keywords) → primary filtering
   High-recall: accept all companies matching our 4 segment profiles

2. Website scrape → secondary: ONLY to reject obvious garbage
   (empty sites, restaurants, real estate agencies)

3. GPT analysis → with V11 prompt BUT operating on
   Apollo labels + website content combined
```

This means the pipeline pre-filter step should inject Apollo metadata into the GPT prompt, not just website text.

---

## 4 Target Segments with Apollo Filters

### P1: Tech/SaaS Product Companies + Fintech (33% of qualified)

**Apollo Industries** (any of):
`information technology & services`, `computer software`, `financial services`, `banking`, `internet`, `primary/secondary education` (edtech), `research` (biotech)

**Apollo Keywords** (any of):
`b2b`, `saas`, `software development`, `fintech`, `edtech`, `enterprise software`, `computer software`, `finance technology`, `information technology & services`

**Size**: 5-500 employees
**Countries**: US, UK, Germany, Denmark, Estonia, Lithuania, Netherlands, Israel, India, Pakistan

**Estimated Apollo yield**: 50,000-100,000 companies globally at these filters

### P2: Gaming/iGaming (15% of qualified, highest revenue per lead)

**Apollo Industries** (any of):
`computer games`, `gambling & casinos`, `leisure, travel & tourism` (casino/igaming)

**Apollo Keywords** (any of):
`mobile games`, `igaming`, `casino`, `gaming`, `game development`, `esports`, `f2p`, `casual games`

**Size**: 3-1000 employees (gaming studios can be large)
**Countries**: US, UK, Denmark, Malta, Cyprus, Sweden, Finland, UAE, Canada, Australia

**Estimated Apollo yield**: 5,000-15,000 companies globally

### P3: Agencies/Consulting (15% of qualified, already well-covered)

**Apollo Industries** (any of):
`management consulting`, `marketing & advertising`, `design`, `internet`

**Apollo Keywords** (any of):
`digital agency`, `creative agency`, `marketing agency`, `it consulting`, `management consulting`, `business consulting`, `affiliate marketing`

**Size**: 5-200 employees
**Countries**: All (already covered by 7,919 existing targets)

**Already gathered**: 7,919 targets via current pipeline. Focus on expanding to new cities.

### P4: Media/Creative (7% of qualified)

**Apollo Industries** (any of):
`media production`, `broadcast media production & distribution`, `entertainment`, `music`

**Apollo Keywords** (any of):
`media production`, `video production`, `content creation`, `broadcast media`, `animation`, `digital media`

**Size**: 3-200 employees
**Countries**: US, UAE, UK, Germany, Australia

---

## Pipeline Changes Required

### 1. Inject Apollo Labels into GPT Prompt

Currently the pipeline only sends website text to GPT. The new approach:

```python
# In gathering_service.py analyze phase:
user_prompt = f"""
Company domain: {domain}
Apollo industry: {apollo_industry}
Apollo keywords: {', '.join(apollo_keywords)}
Apollo employees: {employee_count}
Apollo country: {country}

Website content:
{scraped_text}
"""
```

This gives GPT the context it needs. A company with `industry=computer games, employees=250, country=Denmark` should be auto-accepted even if the website is under construction.

### 2. New V11 GPT Prompt (already written)

The V11 prompt is stored at `/tmp/v11_prompt.txt` on Hetzner. Key changes from V7:
- Asks "could this company need to pay people internationally?" (not "is this a service business?")
- 4 explicit target segments: TECH_PRODUCT, GAMING, AGENCY, MEDIA_CREATIVE
- Does NOT exclude: fintech, e-commerce, staffing, gaming, manufacturing
- Only excludes: solo, physical-only, real estate sales, interior design, visa/legal, VC, government

### 3. Acceptance Rates by Segment

When Apollo labels are included, expected recall:

| Segment | Website-only Recall | Apollo+Website Recall |
|---------|--------------------|-----------------------|
| TECH_PRODUCT | ~60% | ~95% (auto-accept on industry match) |
| GAMING | ~80% (already good) | ~98% |
| AGENCY | ~90% (V7 already catches) | ~95% |
| MEDIA_CREATIVE | ~70% | ~90% |

---

## Execution Plan

### Phase 1: New Segments (P1 + P2) — Tech/SaaS + Gaming

These are the segments we're NOT currently gathering. Do them first.

1. **Apollo Companies Emulator** with P1 filters → gather across 20 cities
2. **Apollo Companies Emulator** with P2 filters → gather gaming companies globally
3. Scrape websites
4. GPT analysis with **Apollo labels injected** + V11 prompt
5. Opus verification → iterate prompt until ≥85% accuracy
6. People search → FindyMail → SmartLead campaigns

### Phase 2: Expand Existing (P3) — Agencies

Already have 7,919 agency targets. Expand to:
- Deep pagination (pages 2-10) for top keywords in top cities
- New cities: Manchester, Edinburgh, Copenhagen, Munich, Warsaw, Prague
- Use existing V7/V8 prompt (works well for agencies)

### Phase 3: Media (P4) — Lower Priority

Smaller segment. Run after P1+P2 are in campaigns.

---

## Prompt Validation Summary

| Version | Qualified Recall | FP Rate | Notes |
|---------|-----------------|---------|-------|
| V7 | 47% (8/17) | 17% | Too narrow: "service business" |
| V9 | 29% (5/17) | 40% | Requires "international operations" evidence |
| V10 | 59% (10/17) | 90% | Too broad: accepts everything |
| V11 | 53% (9/17) | 90% | Better balance but still too many FP |
| V11 + Apollo labels | ~90% (estimated) | ~30% | **PLANNED**: inject Apollo metadata into prompt |

**Next step**: Modify the pipeline to include Apollo labels in the analysis prompt, then re-validate. The 4 inaccessible sites (samlabs.com, gigengineer.io, lottermedia.com, and various empty sites) will pass because Apollo labels alone are sufficient for TECH_PRODUCT and GAMING segments.
