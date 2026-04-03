# IMAGENCY Europe — DM Segmentation Report

**Date:** 2026-04-03
**Source:** OS_Leads_IMAGENCY-EUROPE_20260403_1658.csv
**Total leads:** 1,441

## Goal

Разбить лидов на сегменты ЛПР (по должности) + гео компании -> создать уникальные SmartLead кампании с tailored sequences для каждой группы. Текущий reply rate ~0.25% — нужно поднять за счёт релевантности месседжа.

---

## Phase 1: Анализ данных и принятие решений

### Исходные данные CSV

| Метрика | Значение |
|---------|----------|
| Всего лидов | 1,441 |
| Без статуса (новые) | 1,194 |
| STARTED | 122 |
| INPROGRESS | 109 |
| COMPLETED | 14 |
| PAUSED | 1 |
| Website заполнен | 8 из 1,441 (0.5%) |

### Топ должностей (raw)

| Должность | Кол-во |
|-----------|--------|
| Creative Director | 77 |
| Account Director | 67 |
| Art Director | 55 |
| Managing Director | 34 |
| Senior Art Director | 26 |
| Senior Account Executive | 26 |
| Associate Creative Director | 22 |
| Director | 21 |
| Senior Copywriter | 18 |
| Founder | 17 |
| CEO | 17 |
| Co-Founder | 16 |
| Chief Executive Officer | 15 |

### Гео сотрудников (person location, НЕ компании)

| Страна | Кол-во |
|--------|--------|
| Germany | 161 |
| United Kingdom | 145 |
| Philippines | 87 |
| France | 86 |
| Spain | 76 |
| Turkey | 47 |
| Saudi Arabia | 44 |
| Poland | 42 |
| Argentina | 37 |
| UAE | 35 |

**Проблема:** Philippines (87), Turkey (47), Saudi Arabia (44), Argentina (37) — не Europe. Person location != company HQ.

---

## Phase 2: Решения (обсуждение с пользователем)

### Decisions Log

| # | Вопрос | Решение | Обоснование |
|---|--------|---------|-------------|
| D1 | Какие лиды берём? | **Все 1,441** (вкл. STARTED/INPROGRESS) | Re-segment и relaunch всех кампаний |
| D2 | Сколько кампаний? | **3 кампании** | Founders/C-Suite + Creative Leadership + Account/Ops |
| D3 | Art Directors/Copywriters? | **Исключить из email** (~105 лидов) | Не ЛПР для SaaS; перенаправить в GetSales LinkedIn |
| D4 | Гео: person location или company HQ? | **Company HQ через Apollo** | Сотрудник в Manila может работать на UK-агентство |
| D5 | Метод enrichment | Apollo `/mixed_companies/api_search` по company_name | Бесплатно, ~95% точность |

### Предварительные кластеры ЛПР (до enrichment)

| Кластер | ~Кол-во | Примеры должностей | Угол атаки |
|---------|---------|-------------------|------------|
| **Founders/C-Suite** | ~200 | CEO, Founder, Co-Founder, COO, President | Бизнес/revenue, client retention, margins |
| **Creative Leadership** | ~110 | Creative Director, Executive CD (без Art Directors) | Инструменты, data-driven creative, efficiency |
| **Account/Ops** | ~1,000+ | Account Director, Managing Director, Business Director, Head of X | Client service, reporting, upsell |
| ~~Art/Copy~~ | ~~~105~~ | ~~Art Director, Copywriter~~ | ~~Исключены — не ЛПР~~ |

---

## Phase 3: Apollo Company HQ Enrichment

### Checkpoint CP1 — Unique Companies

458 уникальных company_name в CSV.

### Checkpoint CP2 — Apollo Enrichment

**Script:** `sofia/scripts/enrich_imagency_company_hq.py`
**Method:** Apollo `/v1/mixed_companies/search` (FREE) -> поиск по company_name
**Result:** 370/458 matched (81%), домены найдены. НО Apollo search НЕ возвращает country/city — только domain + linkedin.
**Проблема:** первый запуск на `/api/v1/mixed_companies/api_search` вернул 404 для всех. Фикс: правильный endpoint `/v1/mixed_companies/search`.

### Checkpoint CP3 — Geo Resolution (3-step)

| Шаг | Метод | Компаний | Лидов |
|-----|-------|----------|-------|
| 1 | **ccTLD** (.de→Germany, .fr→France...) | 144 | 430 |
| 2 | **Website scrape + Gemini 2.5 Flash Lite** | 83 | 260 |
| 3 | **Person location fallback** | 135 | 749 |
| — | Unknown | — | 2 |
| **Total** | | **362** | **1,441** |

**Проблемы по пути:**
- Gemini 2.0 Flash → 404. Модель deprecated. Фикс: `gemini-2.5-flash-lite`
- 47 empty pages, 34 fetch failed → fallback на person location

### Checkpoint CP4 — Final Geo Distribution

| Country | Leads | % |
|---------|-------|---|
| United Kingdom | 147 | 10.2% |
| Germany | 135 | 9.4% |
| France | 83 | 5.8% |
| Philippines | 79 | 5.5% |
| Spain | 76 | 5.3% |
| India | 53 | 3.7% |
| Saudi Arabia | 47 | 3.3% |
| Turkey | 45 | 3.1% |
| Colombia | 44 | 3.1% |
| Brazil | 42 | 2.9% |
| Poland | 41 | 2.8% |
| South Africa | 35 | 2.4% |
| Argentina | 34 | 2.4% |
| Hungary | 34 | 2.4% |

**Вывод:** Реальная база — global, не Europe. Europe (UK+DE+FR+ES+IT+PL+NL+BE+AT+CH+DK+IE+HU+BG+CZ) = ~650 лидов (45%). Остальные 55% — MENA, APAC, LATAM, Africa.

---

## Phase 4: Final Segmentation Matrix

### DM Cluster Distribution

| Кластер | Лидов | % от total | Файл |
|---------|-------|-----------|------|
| **FOUNDERS_CSUITE** | 292 | 20.3% | `data/imagency_founders_csuite.csv` |
| **CREATIVE_LEADERSHIP** | 139 | 9.6% | `data/imagency_creative_leadership.csv` |
| **ACCOUNT_OPS** | 876 | 60.8% | `data/imagency_account_ops.csv` |
| ~~EXCLUDED~~ | 134 | 9.3% | Excluded (Art Directors, Copywriters) |
| **Активных** | **1,307** | **90.7%** | |

### Cluster x Top Geo

**FOUNDERS_CSUITE (292):** Spain 22, Germany 20, France 19, UK 17, Netherlands 12, Indonesia 12, Turkey 11
**CREATIVE_LEADERSHIP (139):** Philippines 25, Germany 13, UK 10, Saudi Arabia 7, Egypt 6
**ACCOUNT_OPS (876):** UK 115, Germany 89, France 52, Spain 47, India 46, Colombia 31, Brazil 30

### Файлы данных

| Файл | Описание |
|------|----------|
| `data/imagency_final_enriched.csv` | Все 1,441 лида с hq_country, geo_source, company_domain, dm_cluster |
| `data/imagency_founders_csuite.csv` | 292 Founders/C-Suite |
| `data/imagency_creative_leadership.csv` | 139 Creative Leadership |
| `data/imagency_account_ops.csv` | 876 Account/Ops |

---

## Phase 5: Deep Research — Geo & DM Cluster Analysis

### Sources
- Exa: Kolsquare/NewtonX 2025 (613 marketers, 12 countries), Sales.co (2M+ emails), Dealfront (EU cold email law)
- Audience Research agent: Reddit/HN + industry reports
- OnSocial internal docs analysis

### 5.1 Cold Email Legal Risk by Country

| Country | Risk | Rule | Recommendation |
|---------|------|------|---------------|
| **Germany** | 🔴 HIGH | UWG stricter than GDPR — prior consent required even B2B | LinkedIn outreach (GetSales), NOT email |
| **France** | 🟡 MODERATE | B2B cold email OK under legitimate interest (CNIL) | Email OK, French language preferred |
| **UK** | 🟢 LOW | PECR allows B2B cold email with opt-out | Email OK, English |
| **Spain** | 🟡 MODERATE | GDPR OK, but 38% English proficiency | Email OK, Spanish preferred |
| **Netherlands** | 🟢 LOW | Direct culture, high English | Email OK |
| **Nordics** | 🟢 LOW | Data-driven, high English | Email OK |
| **Poland/CEE** | 🟢 LOW | GDPR OK | Email OK, show local knowledge |
| **MENA** | 🟢 LOW | Permissive, relationship-first | Email OK, formal tone |
| **India/PH/APAC** | 🟢 LOW | Permissive, fast culture | Email OK, direct CTA |

**Impact: 135 German leads should go to GetSales LinkedIn, NOT SmartLead email.**

### 5.2 Regional IM Market Differences (Kolsquare/NewtonX 2025)

| Dimension | UK | Germany | France | Spain | Nordics |
|-----------|-----|---------|--------|-------|---------|
| IM Budget | £849K avg | €5.74M (лидер!) | €3.45M | <€50K (30%) | Mid-range |
| Оплата creators | Gifting + affiliate | Fixed fees (81%) | Fixed fees (77%) | Осторожный | Long-term |
| Главная боль | Balance freedom/brand (42%) | Выбор правильных инфлюенсеров | Agent friction (37%) | Cost inflation (36%) | **Data reliability (51%)** |
| ROI tracking | Data-driven | **Most analytical (44% ROAS)** | Ethics-first | ROI concerns | Metric-focused |
| Язык контента | English | **Only German** | French preferred | Spanish preferred | English OK |
| Тон | Performance, dry humour | Structured, critical | Authentic, storytelling | Lifestyle, emotional | Direct, egalitarian |

### 5.3 Cold Email Benchmarks (Sales.co, 2M+ emails, 2026)

- Average reply rate: **2.09%** (only 0.64% positive/interested)
- **European countries reply 2-3x more than US** (lower inbox saturation)
- Marketing Agencies industry: **5-9% reply rate** (agencies actively seek partnerships)
- Signal-triggered vs cold list: **4-8% vs 1-2%**
- C-level positive rate: **14.16%** (3.3x higher than managers)
- Small companies (1-10): **18.20% positive** vs Enterprise (10K+): **3.43%**

### 5.4 Pain Points by DM Cluster x Region

**FOUNDERS/C-SUITE:**
- Universal: Revenue impact, client retention, margin protection
- UK/Nordics: ROI measurement, performance metrics
- Germany: Compliance, fraud detection, data accuracy
- MENA/India: White-label for margin protection (15-25% margins)
- Spain/LATAM: Budget efficiency, cost optimization

**CREATIVE LEADERSHIP:**
- Universal: Creator discovery, content quality, campaign efficiency
- UK: Balance influencer freedom with brand guidelines
- Germany: Choosing right influencers (compliance-driven selection)
- France: Agent friction, creative control
- APAC: Platform fragmentation (TikTok vs IG vs YouTube)

**ACCOUNT/OPS:**
- Universal: Client reporting, multi-dashboard fatigue, time savings
- UK: Performance tracking across campaigns
- Germany: Structured analytics, ROAS proof
- Nordics: Data reliability (#1 concern at 51%)
- India: Scalable discovery across 38M+ creators

### 5.5 Recommended Tone & CTA by Region

| Region | Tone | CTA Style | Language |
|--------|------|-----------|---------|
| UK | Professional-casual | "Worth a quick chat?" | English |
| Germany | N/A — LinkedIn only | N/A | German |
| France | Formal, relationship | "Would you be open to discussing...?" | French preferred |
| Spain | Warm, collaborative | "Let's explore..." | Spanish preferred |
| Netherlands | Direct, egalitarian | Calendar link | English |
| Nordics | Transparent, metric | Straightforward ask | English |
| Poland/CEE | Respectful, local-aware | "Brief call to explore fit?" | English OK |
| MENA | Formal, rapport-building | Low-pressure | English |
| India/PH | Friendly, fast | "Quick 15-min call?" + link | English |

## Phase 6: Sequence Drafts

Pending.

## Phase 7: SmartLead Campaign Creation

Pending.

---

## Context: Prior Campaign Performance

| Campaign | Leads | Sent | Reply % | Notes |
|----------|-------|------|---------|-------|
| IMAGENCY India | 1,395 | 383 | **0.8%** | Best performer |
| IMAGENCY Global | 1,395 | 290 | 0.3% | Baseline |
| IMAGENCY Europe | 7,659 | 559 | 0.0% | Concise version failed |
| IMAGENCY Americas | 4,485 | 338 | 0.0% | Expanded intro failed |

**Key insight:** India's 0.8% suggests list quality matters more than geo. Segmentation by DM role may unlock better results.

## Context: Existing Sequence Assets

- **v4_im_first_agencies.md** — current 5-email sequence with A/B variants
- **Team Charlie correction** — Ярик+Соня HYP B ("White-Label Your Data") never deployed, expected stronger
- **Operator playbook** — reply handling scripts ready
