# Reply Processing Stats — Mar 21, 2026

## Overview

Total replies in system: **37,147** across all sources.

## By Source

| Source | Total | Approved | Qualified |
|--------|-------|----------|-----------|
| SmartLead | 35,568 | 34 | 36 |
| GetSales | 1,360 | 12 | 3 |
| Manual | 13 | 0 | 13 |
| (empty) | 201 | 0 | 1 |
| Test | 5 | 0 | 0 |

**Approval rate**: ~0.1% (46 approved out of ~37k)
**Qualification rate**: ~0.1% (50 qualified)

---

## GetSales Sender Distribution

Top 20 senders by reply count:

| Sender UUID | Count |
|-------------|-------|
| b10a34f2-e7d0-490e-bc67-012b7ccd35b8 | 199 |
| 4419a283-4c5f-4e2b-87cd-f892ef8a47be | 80 |
| 0d22a72e-5e30-4f72-bac7-0fac29fe8121 | 63 |
| 789eba43-d87f-4412-8f2a-20557f5bf5e2 | 62 |
| 29fd2e4e-d218-4ddc-b733-630e68a98124 | 56 |
| cdeb709c-17c6-4b31-ad6b-271354cdd3a9 | 55 |
| 4cbc70b5-4fb6-4a76-9088-f50a4ef096e7 | 53 |
| b3b69a39-6b46-4043-85b1-ef4ce22239d5 | 53 |
| 91fb80ab-4430-4b07-bc19-330d3f4ac8fd | 51 |
| d67e1028-cf06-4ae8-bcc3-16e41710f19c | 50 |
| d4d17541-2b69-4cc3-acd5-cb39ce9df4b6 | 46 |
| 7f829fca-20b8-4f0d-a19e-ec1b3f76704e | 44 |
| 430e90e2-adfb-47d6-a986-3b8a75f4c80e | 43 |
| c58462db-beda-44a5-ba32-12e436d55bba | 42 |

---

## Projects with Sender Filters Configured

10 projects have `getsales_senders` configured:

| Project | Sender Count | Senders |
|---------|-------------|---------|
| mifort | 4 | 0d22a72e, 430e90e2, c58462db, d4d17541 |
| easystaff ru | 9 | b10a34f2, 4d1effeb, 7f829fca, 07d392a8, 5ecc3a67, 774af09b, d67e1028, b3b69a39, cf73001d |
| easystaff global | 2 | 4419a283, e7cd7b0f |
| Rizzult | 6 | 29fd2e4e, 91fb80ab, 41b709f2, 2529a3dd, 94aeceb5, 4cbc70b5 |
| Inxy | 3 | aab81b67, 448339f7, 25598cb7 |
| tfp | 2 | cdeb709c, b970588c, 3c65f66c |
| paybis | 1 | b0399ffb |
| OnSocial | 3 | 980cdeb3, f4ddb17a, d5c18723 |
| SquareFi Fedor | 2 | 8c7d77fa, 765a68b2 |
| squarefi evgeny | 2 | 789eba43, d15d89ff |

---

## Mifort Project Deep Dive

### Configured Senders (4)
```
0d22a72e-5e30-4f72-bac7-0fac29fe8121 → 63 replies
d4d17541-2b69-4cc3-acd5-cb39ce9df4b6 → 46 replies
430e90e2-adfb-47d6-a986-3b8a75f4c80e → 43 replies
c58462db-beda-44a5-ba32-12e436d55bba → 42 replies
```
**Total mifort sender replies**: 194

### Campaign Name Match Analysis
When filtering by `campaign_name ILIKE '%mifort%'`:
- 0d22a72e: 63 replies (100% match)
- d4d17541: 45 replies (1 non-matching)
- 430e90e2: 43 replies (100% match)
- c58462db: 41 replies (1 non-matching)
- Other senders appearing in mifort campaigns: 2fca5b15 (14), 94aeceb5 (5), others (9)

**Issue**: Some non-configured senders appear in "mifort" campaigns. These would be filtered OUT by sender check in `_build_project_campaign_filter()`.

---

## Sender-Based Filtering Implementation

### Schema (DONE ✅)
- `processed_replies.getsales_sender_uuid` — top-level column for sender UUID
- `projects.getsales_senders` — JSONB array of allowed sender UUIDs

### Filter Logic (DONE ✅)
`_build_project_campaign_filter()` in `replies.py`:

1. **Tier 1 — Explicit campaign_filters**: Always trusted, no sender check needed
2. **Tier 2 — Prefix match**: Applies sender validation for LinkedIn replies

```python
sender_uuids = project.getsales_senders or []
if sender_uuids:
    # Check raw_webhook_data for sender UUID
    sender_check = OR(
        channel != "linkedin",  # Email always passes
        sender_uuid.in_(sender_uuids),  # LinkedIn: must be in allowlist
        sender_uuid.is_(None),  # Or sender unknown
    )
```

**Status**: FULLY IMPLEMENTED ✅

---

## Gathering Runs Status

Currently running: **10 runs** for `tfp` project (project_id=13)

| Phase | Status | Count |
|-------|--------|-------|
| gathered | running | 6 |
| scraped | running | 4 |
| awaiting_targets_ok | completed | 4 |
| gathered | cancelled | 14 |
| filtered | running | 3 |

---

## Recent Git Commits

```
6f6f674 fix: Phase 1 cleanup script — dedup results, output refs, placeholder domains
882ba41 feat: universal Apollo city scraper — any city, full filters stored as arrays
f5aedc8 plan: Phase 1 (fix 7 pipeline issues) + Phase 2 (15 cities × 5K targets each)
3976aeb audit: 8 pipeline issues found — summary filters, 6K duplicates, placeholder domains
ce16e5f docs: implementation plan — SmartLead analytics-based diff detection
725448c perf: SmartLead sync skips unchanged campaigns (diff check)
```

---

## Action Items

1. **Mifort sender filtering** — ✅ Already implemented. Verify behavior in UI.
2. **Monitor cross-sender replies** — 24 replies from non-mifort senders in "mifort" campaigns (see above). These are correctly filtered out.
3. **TFG gathering runs** — 10 runs in progress. Check if this is expected.

---

## Related Files

- `backend/app/api/replies.py` — `_build_project_campaign_filter()`, reply API
- `backend/app/models/reply.py` — ProcessedReply model
- `backend/app/models/contact.py` — Project model with `getsales_senders`
