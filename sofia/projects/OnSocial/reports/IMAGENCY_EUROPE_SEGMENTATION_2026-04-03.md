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

~900 уникальных company_name в CSV.

### Checkpoint CP2 — Enrichment Script

**Script:** `sofia/scripts/enrich_imagency_company_hq.py`
**Method:** Apollo `/mixed_companies/api_search` (FREE) -> поиск по company_name -> HQ country/city из top match
**Rate:** 0.35s/call, ~900 companies = ~5.5 min
**Output:** enriched CSV + JSON cache
**Runs on:** Hetzner (APOLLO_API_KEY from .env)

**Status:** Script ready, deploying to Hetzner...

### Checkpoint CP3 — Match Rate

Pending.

### Checkpoint CP4 — Geo Distribution (Company HQ)

Pending.

---

## Phase 4: Final Segmentation Matrix

Pending CP3-CP4 results.

## Phase 5: Deep Research — Pains per Cluster

Pending.

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
