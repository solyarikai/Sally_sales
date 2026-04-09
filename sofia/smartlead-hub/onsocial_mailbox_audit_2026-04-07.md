# OnSocial — Mailbox Audit
**Date:** 2026-04-07  
**Source:** SmartLead API `/email-accounts`  
**Sender:** Bhaskar Vishnu (all 17 accounts)

---

## Summary

| Metric | Value |
|--------|-------|
| Total mailboxes | 17 |
| Total daily capacity | **510 emails/day** |
| Sent today (Apr 7) | 414 emails |
| Capacity utilization | 81% |
| All warmup statuses | ACTIVE |
| Avg warmup reputation | ~99.5% |
| Account type | Gmail OAuth (all) |

---

## Mailbox Table

| # | Email | Domain | Limit/day | Sent today | Warmup rep | Created | Status |
|---|-------|--------|-----------|------------|------------|---------|--------|
| 1 | bhaskar.v@onsocial-analytics.com | onsocial-analytics.com | 30 | 13 | 100% | 2026-04-01 | warming |
| 2 | bhaskar@onsocial-platform.com | onsocial-platform.com | 10 | 10 | 100% | 2026-04-01 | warming |
| 3 | bhaskar@onsocial-network.com | onsocial-network.com | 30 | 13 | 100% | 2026-04-01 | warming |
| 4 | bhaskar@onsocial-metrics.com | onsocial-metrics.com | 10 | 10 | 100% | 2026-04-01 | warming |
| 5 | bhaskar@onsocial-insights.com | onsocial-insights.com | 30 | 13 | 100% | 2026-04-01 | warming |
| 6 | bhaskar@onsocial-influence.com | onsocial-influence.com | **50** | 50 | 100% | 2026-04-01 | ready |
| 7 | bhaskar@onsocial-data.com | onsocial-data.com | 30 | 13 | 100% | 2026-04-01 | warming |
| 8 | bhaskar@onsocial-analytics.com | onsocial-analytics.com | **50** | 50 | 98% | 2026-04-01 | ready |
| 9 | bhaskar.v@onsocial-platform.com | onsocial-platform.com | 30 | 14 | 100% | 2026-04-01 | warming |
| 10 | bhaskar.v@onsocial-network.com | onsocial-network.com | 30 | 14 | 100% | 2026-04-01 | warming |
| 11 | bhaskar.v@onsocial-metrics.com | onsocial-metrics.com | 10 | 10 | 100% | 2026-04-01 | warming |
| 12 | bhaskar.v@onsocial-insights.com | onsocial-insights.com | 30 | 14 | 100% | 2026-04-01 | warming |
| 13 | bhaskar.v@onsocial-influence.com | onsocial-influence.com | 10 | 10 | 100% | 2026-04-01 | warming |
| 14 | bhaskar.v@onsocial-data.com | onsocial-data.com | 10 | 10 | 97% | 2026-04-01 | warming |
| 15 | bhaskar@onsocialmetrics.com | onsocialmetrics.com | **50** | 50 | 98% | 2026-02-17 | ready |
| 16 | bhaskar.v@onsocialplatform.com | onsocialplatform.com | **50** | 50 | 100% | 2026-02-17 | ready |
| 17 | bhaskar.v@onsocialmetrics.com | onsocialmetrics.com | **50** | 50 | 100% | 2026-02-17 | ready |

---

## Capacity by Tier

| Tier | Count | Capacity |
|------|-------|----------|
| 50/day (fully warmed) | 5 | 250/day |
| 30/day (mid-warm) | 7 | 210/day |
| 10/day (early warm) | 5 | 50/day |
| **Total** | **17** | **510/day** |

### Warmup batches

**Batch 1 — Feb 2026** (3 accounts, onsocialmetrics + onsocialplatform)  
All at 50/day — fully warmed, production-ready.

**Batch 2 — Apr 2026** (14 accounts, all onsocial-* domains)  
Started 2026-04-01. As of Apr 7 = day 6.
- 2 already hit 50/day (bhaskar@onsocial-influence.com, bhaskar@onsocial-analytics.com)
- 7 at 30/day
- 5 still at 10/day

Typical Gmail warmup trajectory: 10 → 30 → 50 over ~3-4 weeks.  
**Estimated full capacity (17 × 50/day = 850/day): ~mid-April 2026**

---

## Capacity Projections

| Scenario | Mailboxes | Daily capacity | New leads/day (3-step) |
|----------|-----------|----------------|------------------------|
| **Now** | 17 | 510 | ~170 |
| **Mid-April** (fully warmed) | 17 | 850 | ~283 |
| **+10 new mailboxes** (27 total) | 27 | 1,350 | ~450 |

> Assumes 3 active sequence steps per lead. 1 step = 1 email/day.

---

## Issues & Flags

| # | Issue | Account(s) |
|---|-------|------------|
| 1 | Two accounts on same domain — deliverability risk if both hit inbox at same company | bhaskar@ + bhaskar.v@ on all onsocial-* domains |
| 2 | `minTimeToWaitInMins: null` on 5 accounts — no send delay set | bhaskar@onsocial-influence.com, bhaskar@onsocial-analytics.com, all 3 Feb accounts |
| 3 | Warmup reputation 97-98% on 3 accounts | onsocial-data.com (97%), onsocial-analytics.com (98%), onsocialmetrics.com (98%) |
| 4 | `campaign_count: 0` on all accounts | All 17 — accounts not directly linked to campaigns in API (normal for SmartLead round-robin) |

---

## Recommendations

1. **Raise limits on mid-warm accounts** as they hit 2-week mark (~Apr 15) — bump 30/day → 50/day manually in SmartLead if auto-warmup is slow
2. **Set minTimeToWaitInMins = 60** on the 5 accounts missing it to normalize send pacing
3. **Add 10 new mailboxes** to reach 27 total and unlock ~1,350/day capacity (target for Q2 send plan)
4. **Monitor onsocial-data.com** — 97% warmup rep is slightly low, watch for spam folder flags
