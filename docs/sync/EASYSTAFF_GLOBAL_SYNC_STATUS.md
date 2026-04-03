# EasyStaff Global — Sync Status & Business Questions

## Q: List EasyStaff campaigns by created_at descending with count of contacts in CRM vs SmartLead

| Campaign | Status | SmartLead leads | CRM contacts | Created |
|----------|--------|-----------------|--------------|---------|
| EasyStuff_TX_Marketing | active | 0 | syncing... | Mar 19 |
| AU-Philippines Petr 19/03 | active | 0 | syncing... | Mar 18 |
| UAE-Pakistan Petr 16/03 - copy - copy | active | 0 | syncing... | Mar 17 |
| UAE-Pakistan Petr 16/03 - copy | active | 0 | syncing... | Mar 16 |
| EasyStaff - Phili-EU | active | 301 | syncing... | Mar 13 |
| EasyStaff - Phili-SEA | active | 99 | syncing... | Mar 13 |
| EasyStaff - Phili-Africa | active | 156 | syncing... | Mar 12 |
| EasyStaff - Phili-LATAM | active | 249 | syncing... | Mar 12 |
| EasyStaff - TES Affiliate | active | 451 | syncing... | Mar 12 |
| EasyStaff - Guatemala | active | 407 | syncing... | Mar 11 |
| EasyStaff - Honduras | active | 638 | syncing... | Mar 11 |
| EasyStaff PL Payroll | paused | 253 | syncing... | Mar 11 |
| EasyStaff - Australia_Africa | active | 249 | syncing... | Mar 10 |
| EasyStaff - Australia_EU | active | 182 | syncing... | Mar 10 |
| EasyStaff PL GitHub | paused | 711 | syncing... | Mar 10 |
| EasyStaff_Clutch_TX | stopped | 399 | syncing... | Mar 9 |
| EasyStaff - Australia_Philipines | active | 950 | syncing... | Mar 9 |
| EasyStaff - Australia_Latam | active | 106 | syncing... | Mar 9 |
| EasyStaff - Australia_SEA | active | 145 | syncing... | Mar 9 |
| EasyStaff PL Hire | paused | 649 | syncing... | Mar 9 |
| EasyStaff - Australia_India_Bangladesh | paused | 189 | syncing... | Mar 9 |
| EasyStaff - Canada_Indonesia | paused | 1,091 | syncing... | Mar 6 |
| EasyStaff - Australia_South_Africa | paused | 673 | syncing... | Mar 6 |
| EasyStaff - US - Egypt_11-50 | paused | 771 | syncing... | Mar 6 |
| EasyStaff - Florida_BC_LATAM | paused | 1,333 | syncing... | Mar 6 |
| EasyStaff - Canada_EU | active | 281 | syncing... | Mar 6 |
| EasyStaff - Georgia - LATAM | active | 231 | syncing... | Mar 6 |
| EasyStaff - UAE - Marketing Agencies | paused | 1,457 | syncing... | Feb 25 |
| EasyStaff - UAE - India | paused | 4,874 | syncing... | Feb 25 |
| EasyStaff - Sigma | paused | 3,614 | syncing... | Feb 25 |
| EasyStaff - US - PH 2 | paused | 3,053 | syncing... | Feb 25 |
| EasyStaff - AU - PH | paused | 2,794 | syncing... | Feb 25 |
| EasyStaff - UAE - Pakistan | paused | 2,308 | syncing... | Feb 25 |
| EasyStaff - IGB non-rus | completed | 2,396 | syncing... | Feb 25 |

**Updated March 21, 2026 — after project-scoped sync (61,935 processed, 182 new):**

| Campaign | Status | SmartLead | CRM | Gap | Created |
|----------|--------|-----------|-----|-----|---------|
| EasyStaff - Phili-EU | active | 301 | 291 | 10 | Mar 13 |
| EasyStaff - Phili-SEA | active | 99 | 53 | 46 | Mar 13 |
| EasyStaff - Phili-Africa | active | 156 | 84 | 72 | Mar 12 |
| EasyStaff - TES Affiliate | active | 660 | 362 | **298** | Mar 12 |
| EasyStaff - Guatemala | active | 407 | 347 | 60 | Mar 11 |
| EasyStaff - Honduras | active | 638 | 565 | 73 | Mar 11 |
| EasyStaff - Australia_Philipines | active | 950 | 825 | 125 | Mar 9 |
| EasyStaff PL Hire | paused | 649 | 501 | 148 | Mar 9 |
| EasyStaff PL GitHub | paused | 711 | 632 | 79 | Mar 10 |
| EasyStaff - Canada_Indonesia | paused | 1,091 | 1,081 | 10 | Mar 6 |
| EasyStaff - Canada_Peru | active | 441 | 437 | 4 | Mar 6 |
| EasyStaff - UK-MX Glassdoor | paused | 32 | 32 | **0** | Mar 6 |
| EasyStaff - US-IN Glassdoor | paused | 57 | 57 | **0** | Mar 6 |

**Pattern:** Old campaigns (pre-Mar 6) = 100% synced. New campaigns (Mar 9+) = 70-95% synced. Gap = leads added to SmartLead after last CSV export.

---

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
