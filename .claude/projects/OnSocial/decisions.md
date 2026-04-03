---
last_updated: 2026-04-03
status: active
---

# OnSocial — Key Decisions Log

## Segmentation

**v3 rework (March 2026):** Пересмотрели сегменты после месяца данных.
- Agencies разделили: убрали PR firms (0.20% reply), micro-agencies, marketing holds
- INFPLAT расширили диапазон: 5-200 → 5-5,000 employees (impact.com был strong outlier)
- Добавили AFFPERF как новый сегмент (affiliate/performance platforms)
- **Why:** Первый месяц показал что mixed agency segment не работает, нужна чистая сегментация по core business

**v4 ALL GEO (March 31):** Убрали географические ограничения из Apollo фильтров.
- v3: 2,700-4,800 contacts с geo-фильтрами
- v4: 5,300-9,500 contacts без geo-фильтров (2x reach)
- **Why:** MENA+APAC показали 10x конверсию, ограничивать гео нет смысла
- **Risk:** ~40-50% overlap с v3 exports, dedup обязателен

## Architecture

**Blacklist: approved_targets removed.**
- Раньше был механизм `blacklist_approved_targets` для обхода blacklist
- Убрали — CRM sync is the correct mechanism for managing pipeline
- **Why:** approved_targets создавал путаницу и risk of re-contacting негативных респондентов

## Channel Strategy

**Germany → LinkedIn only.**
- UWG (Gesetz gegen den unlauteren Wettbewerb) требует prior consent для cold email
- Решение: все German leads идут в GetSales/LinkedIn, не в SmartLead
- **Why:** Юридический риск перевешивает потенциальный reach

**LinkedIn parallel to email (April 2026):**
- 342 leads с 0% email opens → GetSales LinkedIn campaigns
- 3 campaigns по гео/сегменту (India agencies, India platforms, MENA+APAC)
- **Why:** Email не доходит (spam/wrong email), LinkedIn как fallback channel

## Messaging

**Pricing transparency shift:**
- 70% of interested replies спрашивают pricing, но CTA предлагал только "book a call"
- Решение: dual CTA — pricing doc vs walkthrough
- **Why:** Теряли 60% reply→meeting конверсии (6.1% vs industry 15-25%)

**Email length reduction:**
- v2/v3: 80-100 words
- v4: 40-65 words
- **Why:** Industry benchmark 75-100 max, короче = выше reply rate

**White-label positioning for India:**
- India agencies: "data under your brand" конвертит 100% warm replies
- Остальные рынки: mix of pain points
- **Why:** India market specifics — agencies actively want to rebrand/white-label everything

## Campaign Operations

**500-email pause rule:**
- Auto-pause campaign at 500 emails sent with 0 replies
- **Why:** Previous violations wasted 1,141+ emails on dead campaigns
- **How:** Manual check or system auto-pause in SmartLead

**Tiered sending allocation:**
- T1 (67%): proven performers — IM agencies US&EU, India, MENA+APAC
- T2 (27%): promising but less data
- T3 (6%): testing new segments/geos
- **Why:** 750/day capacity constraint, must maximize ROI per send

**Dead campaigns paused (March 26):**
- PR firms, old platforms, marketing agencies, IMAGENCY Europe, AFFPERF
- 19,645 leads freed for reallocation
- **Why:** All had 300+ sends with 0 positive replies
