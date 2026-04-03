# Pipeline Estimation — EasyStaff Test Run
**Date**: 2026-03-31
**Project**: EasyStaff (ID 392, user pn3)
**Offer**: Global payroll platform for remote teams

## Segments

### Segment 1: IT Consulting — Miami, FL
| Parameter | Value |
|-----------|-------|
| **Apollo total available** | **3,395 companies** |
| Keywords | information technology & services, IT consulting, software development, managed IT services |
| Location | Miami, Florida, United States |
| Company size | 11–200 employees |
| Observed target rate (from run 390) | ~23% (12 targets per 52 companies) |

### Segment 2: Video Production — London, UK
| Parameter | Value |
|-----------|-------|
| **Apollo total available** | **4,303 companies** |
| Keywords | media production, video production, film production, motion graphics, content creation |
| Location | London, England, United Kingdom |
| Company size | 11–200 employees |
| Observed target rate (from run 391) | ~45% (9 targets per 20 companies) |

## Apollo Filters Applied

```json
{
  "segment_1_miami_it": {
    "q_organization_keyword_tags": ["information technology & services", "IT consulting", "software development", "managed IT services"],
    "organization_locations": ["Miami, Florida, United States"],
    "organization_num_employees_ranges": ["11,200"],
    "per_page": 100
  },
  "segment_2_london_video": {
    "q_organization_keyword_tags": ["media production", "video production", "film production", "motion graphics", "content creation"],
    "organization_locations": ["London, England, United Kingdom"],
    "organization_num_employees_ranges": ["11,200"],
    "per_page": 100
  }
}
```

## Apollo Pagination

- `/mixed_companies/search` supports up to **100 companies per page**
- 1 credit per page regardless of per_page value
- Pagination: `page=1`, `page=2`, etc. — each costs 1 credit
- Total available is returned in response — can plan pages needed upfront

## Cost & Time Estimation

### Per Segment (target: 100 contacts, max 3/company, ~34 target companies)

| Step | Volume | Credits | Cost | Time (optimized) |
|------|--------|---------|------|-------------------|
| **Iteration 1 (exploration)** | | | | |
| Apollo search (1 page × 25) | 25 companies | 1 | $0.01 | 2s |
| Scrape websites (50 concurrent) | 25 sites | — | $0.01 | 3s |
| GPT classify (batched, 5/call) | 5 GPT calls | — | $0.01 | 3s |
| Filter improvement | 1 GPT call | — | $0.00 | 1s |
| **Subtotal iteration 1** | | **1** | **$0.03** | **~10s** |
| | | | | |
| **Iteration 2+ (scaling)** | | | | |
| Apollo search (3 pages × 100) | 300 companies | 3 | $0.03 | 6s |
| Exploration (enrich top 5) | 5 companies | 5 | $0.05 | 5s |
| Scrape websites (50 concurrent) | 300 sites | — | $0.15 | 30s |
| GPT classify (batched, 10/call) | 30 GPT calls | — | $0.03 | 15s |
| People search (5 concurrent) | ~34 companies | — | — | 15s |
| People bulk_match (emails) | ~100 emails | 100 | $1.00 | 10s |
| **Subtotal iteration 2+** | | **108** | **$1.26** | **~80s** |
| | | | | |
| **TOTAL per segment** | | **~109** | **~$1.29** | **~90s** |

### Both Segments Combined

| Metric | Segment 1 (Miami IT) | Segment 2 (London Video) | **Total** |
|--------|---------------------|-------------------------|-----------|
| Apollo available | 3,395 | 4,303 | 7,698 |
| Companies to process | ~325 | ~225 | ~550 |
| Target rate | ~23% | ~45% | ~30% avg |
| Target companies | ~34 | ~34 | ~68 |
| Target contacts | ~100 | ~100 | ~200 |
| Apollo credits | ~109 | ~109 | **~218** |
| OpenAI cost | ~$0.04 | ~$0.04 | ~$0.08 |
| Apify cost | ~$0.15 | ~$0.10 | ~$0.25 |
| People credits | ~100 | ~100 | ~$2.00 |
| **Total cost** | **~$1.29** | **~$1.29** | **~$2.58** |
| **Time (optimized)** | **~90s** | **~90s** | **~3 min** |

## Speed Optimization Plan

Current bottleneck: GPT classification is per-company (1 API call per company = 300 calls).

### Optimizations needed:
1. **Batch GPT classification** — 10 companies per GPT call instead of 1 → 30 calls instead of 300 → **10x faster**
2. **Scraping already parallel** — 50 concurrent via Apify proxy ✓
3. **People extraction already parallel** — 5 concurrent ✓
4. **Apollo per_page=100** — max throughput per credit ✓
5. **Iteration 1 = 25 (exploration), iteration 2+ = 100/page (scaling)** ✓

### Target timing:
- Iteration 1 (exploration): 10 seconds
- Iteration 2 (full batch): 80 seconds
- SmartLead campaign creation: 10 seconds
- **Total per segment: ~90 seconds**

## SmartLead Campaign Creation

After contacts gathered:
1. Generate sequence (GPT) — 3 emails, adjusted to EasyStaff payroll offer
2. Create campaign in SmartLead (DRAFT)
3. Send test email to pn@getsally.io
4. Return campaign link for review

## Notes
- Target rate 35% assumed by system, observed 23% (Miami) and 45% (London)
- London video has higher rate because keywords are more specific
- Miami IT is broad — "information technology" catches many non-target companies
- After iteration 1 improvement, target rate should increase to 30-40%
