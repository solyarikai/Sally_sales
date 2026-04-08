---
last_updated: 2026-04-08
status: active
---

# OnSocial — Key Decisions Log

## Segmentation

**SOCCOM — новый сегмент (April 6, 2026):** Social Commerce Platforms — крупные корпоративные компании вне IMAGENCY/INFPLAT/AFFPERF.
- Первый батч: Kantar (220 raw → 62 после фильтрации)
- Фильтр: срезаем engineering/HR/IT ops/product owner; оставляем Brand Strategy, Growth & Strategy, Creative, Client Service, C-suite
- Питч-угол: Kantar измеряет маркетинг для брендов → OnSocial как data layer для influencer measurement в их исследованиях
- Лист: `OS | Leads | SOCCOM — 2026-04-06` (ID: 1wYC-na4M8cjF2FSaAV3hJ64PY03-YjIawT9Hr0GWz84)
- DM clusters: FOUNDERS_CSUITE (33), ACCOUNT_OPS (21), CREATIVE_LEADERSHIP (8)
- **Why:** 62 квалифицированных контакта достаточно для кампании; 70% среза — стандартная гигиена для enterprise

**"OTHER" batch redistribution (April 6, 2026):** 276 контактов из `OS | Import | OTHER from OnSocial` распределены:
- Patreon (19→7) → INFPLAT_NEW: creator monetization platform
- PFR Group (2→2) → IMAGENCY_NEW: Hungarian talent management
- inDrive (31→20) + Dovetail (2→1) → IMAGENCY_NEW account_ops: нет своего сегмента
- Kantar (220→62) → SOCCOM (новый сегмент)
- Cognizant (1→0): Senior Associate срезан как non-buyer

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

## Operations

**Linear as dedicated skill, not part of /sync (April 8, 2026):**
- Created `/linear` skill with full task management: templates, triage, reports, bulk ops
- Removed Linear/Notion from `/sync` — sync now handles only memory + docs
- Connected `linear-getsally` MCP (Sally workspace) with PAT auth in `.mcp.json`
- **Why:** Linear deserves dedicated workflow, not just "close tasks at end of session". Separate skill enables project creation, smart triage, weekly reports — things /sync couldn't do well.

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

## IMAGENCY v5 Decisions (April 2026)

**Geo: accept 52% person-location fallback.**
- 749/1441 leads had hq_country from person location (Step 3 fallback), not real company HQ
- Decision: proceed without re-enrichment for speed
- **Why:** build_smartlead_csvs.py already uses hq_country field correctly; re-enriching would delay launch

**Company HQ geo > person location for messaging.**
- Hooks (custom1-4) reference agency's market context (costs, clients, trends), not individual's
- **Why:** Sequence says "agencies in UK facing X" — must match company location, not person's city

**CTO/VP Engineering included for INFPLAT segment.**
- Previously excluded as non-buyers; added back for INFPLAT (platforms/tools)
- **Why:** At tech platforms (Meltwater, Spotter, LTK), engineering leadership decides on API integrations
- Pipeline script (`onsocial_clay_imagency_v4_allgeo_2026-03-31.py`) updated with these titles

**New lead batch (552) from "OS | Import | Mix from OnSocial") split into 3 segments:**
- 80 → IMAGENCY (merged into imagency_final_enriched.csv)
- 90 → INFPLAT (separate sheet, with tech roles)
- 275 → OTHER (Kantar, inDrive, Patreon — separate sheet, no dedup)
- **Why:** Original sheet was misnamed "IMAGENCY" but contained mixed company types
