# Rizzult Replies — CORRECTED Report
Generated: 2026-02-12 15:52:54

## BUGS FOUND

1. **891 out of 913 (97%) reply senders are NOT in the contacts table**
   - `processed_replies` captures Smartlead webhook data correctly
   - But the CRM sync never imported most campaign contacts into `contacts` table
   - So querying `contacts WHERE has_replied = true` returns almost nothing

2. **15 contacts that DO exist have `has_replied = false` despite having replies**
   - The sync pipeline doesn't properly update `has_replied` flag
   - Multiple code paths can set it but race conditions and incomplete syncs leave it as false

3. **GetSales/LinkedIn uses placeholder emails** (`linkedin_xxx@placeholder.local`)
   - Can't join with real contact emails
   - Only 24 LinkedIn reply activities tracked vs 133+ in Google Sheet

---

## CORRECTED NUMBERS

| Source | Metric | Count |
|---|---|---|
| Smartlead (email) | Total reply messages | **922** |
| Smartlead (email) | Unique people who replied | **913** |
| Smartlead (email) | Meaningful replies (interested/meeting/question) | **79** |
| GetSales (LinkedIn) | Reply activities in DB | **11** |
| Google Sheet | Total reply rows across all tabs | ~1500+ |

### By AI Category (Smartlead)

| Category | Messages | Unique People |
|---|---|---|
| other | 479 | 478 |
| out_of_office | 183 | 183 |
| wrong_person | 157 | 156 |
| meeting_request | 61 | 61 |
| not_interested | 19 | 19 |
| question | 9 | 9 |
| interested | 9 | 9 |
| unsubscribe | 5 | 5 |

### By Campaign

| Campaign | Messages | Unique People |
|---|---|---|
| Rizzult Shopping Web Latam Aleks 18.01.26 | 540 | 536 |
| Rizzult Fintech 22.11.25 Aleks | 114 | 114 |
| Rizzult Performance Agencies 22.11.25 Aleks | 75 | 75 |
| Rizzult Shopping Aleks 09.12.25 | 48 | 48 |
| Rizzult Telemedicine & Checkups 01.02.26 Aleks | 45 | 42 |
| Rizzult QSR 22.11.25 Aleks | 39 | 39 |
| Rizzult Soico Lookalike Agencies 03.12.25 Aleks | 15 | 15 |
| Rizzult Food&Drink 24.01.26 Aleks | 14 | 14 |
| Rizzult Custom Aleks 02.02.26 | 13 | 13 |
| Rizzult Mobility 17.12.25 Aleks | 7 | 7 |
| Rizzult Foodtech 22.11.25 Aleks | 7 | 7 |
| Rizzult Wellness 12.01.26 Aleks | 4 | 4 |
| Rizzult Streaming 06.02.26 Aleks | 1 | 1 |

## Google Sheet Report
New tabs added to: https://docs.google.com/spreadsheets/d/1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s/edit
- **DB Report 02.12** — Summary + bug info
- **Meaningful Replies 02.12** — 79 interested/meeting/question replies
- **All Replies 02.12** — 922 total email replies
- **LinkedIn Replies 02.12** — 11 LinkedIn reply activities