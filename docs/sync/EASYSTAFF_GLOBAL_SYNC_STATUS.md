# EasyStaff Global — Sync Status & Business Questions

## Q: How many contacts total in our CRM for EasyStaff Global?
**A: 114,855 contacts across 55,375 unique company domains.**

## Q: Where did they come from?
| Source | Contacts | Domains |
|--------|----------|---------|
| SmartLead (email campaigns) | 58,908 | 33,821 |
| GetSales (LinkedIn campaigns) | 26,115 | 9,275 |
| Clay (TAM imports) | 27,693 | 13,939 |
| Google Sheets | 5 | 5 |

## Q: How many SmartLead campaigns do we have?
**A: 152 campaigns total.** 28 active, 99 paused, 12 completed, 10 stopped, 3 drafted.

## Q: How many leads across all SmartLead campaigns?
**A: 61,801 leads total in SmartLead** (sum of leads_count from DB).

Top campaigns by size:
| Campaign | Status | Leads | Created |
|----------|--------|-------|---------|
| UAE - India | paused | 4,874 | Feb 25 |
| Sigma | paused | 3,614 | Feb 25 |
| US - PH 2 | paused | 3,053 | Feb 25 |
| AU - PH | paused | 2,794 | Feb 25 |
| IGB non-rus | completed | 2,396 | Feb 25 |
| UAE - Pakistan | paused | 2,308 | Feb 25 |

## Q: Is the CRM fully synced with SmartLead?
**A: Syncing now.** 354K records processed, 151 new contacts found. Last full sync was March 15 (5 days ago). After this sync completes, CRM will be up to date.

## Q: Is the CRM synced with GetSales?
**A: GetSales sync pending** — will start after SmartLead finishes.

## Q: How many of our new 428 target companies are already in campaigns?
**A: 83 out of 428 (19%).** These were already in outreach — the blacklist should have caught them but the CRM was 5 days stale when blacklist ran.

**After sync completes:** Will re-run blacklist, remove these 83, refresh materialized view.

## Q: How many active campaigns are sending right now?
**A: 28 SmartLead active + 18 GetSales active = 46 active campaigns.**

Recent active (March 2026):
| Campaign | Leads | Created |
|----------|-------|---------|
| Australia - Philippines | 950 | Mar 9 |
| Honduras | 638 | Mar 11 |
| TES Affiliate | 451 | Mar 12 |
| Canada - Peru | 441 | Mar 6 |
| Guatemala | 407 | Mar 11 |
| Phili - EU | 301 | Mar 13 |
| Canada - EU | 281 | Mar 6 |
| Phili - LATAM | 249 | Mar 12 |
| Australia - Africa | 249 | Mar 10 |
| Georgia - LATAM | 231 | Mar 6 |

## Q: What's the total reach (unique people contacted)?
**A: ~61,801 via SmartLead + ~26,115 via GetSales = ~88K contacts reached** (with overlap — some contacts in both platforms).
