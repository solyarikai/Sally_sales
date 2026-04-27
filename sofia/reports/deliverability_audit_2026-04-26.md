# Deliverability Audit — OnSocial / Crona / EasyStaff

**Дата:** 2026-04-26 → 27
**Account:** SmartLead (admin key)

---

## TL;DR

Расследовали echo-errors на 10 петровых ящиках Crona. Корневая причина — **Google Workspace, не deliverability**: 9 из 10 mailbox'ов заблокированы с ошибкой `Mail service not enabled`. Параллельно нашли что 3 bhaskar-домена (`onsocial-analytics/influence/insights.com`) тонут в spam в Office365 (но 100% inbox в Gmail) — **сняты с 2 кампаний**. Eleonora-инфраструктура (10 ящиков) — здорова.

---

## Findings

### 🔴 Petr@ Crona — 9 ящиков заблокированы Workspace
- `petr@crona-force.com`, `petr@segment-crona.com`, `petr@crona-b2b.com`, `petr@crona-base.com`, `petr@crona-flow.com`, `petr@crona-stack.com`, `petr@leads-crona.com`, `petr@cronaaipipeline.com`, `petr@cronaaiprospects.com`
- `is_warmup_blocked: true`, `blocked_reason: "Error: Mail service not enabled"`
- Скорее всего — **Send mail as alias'ы** на одном primary `petr@prospectscrona.com` (единственный рабочий)
- **Action: проверить admin.google.com → User → Send mail as настройки на 9 alias-доменах**

### Сводная таблица здоровья всех 24 ящиков (10 petr@ + 14 bhaskar)

petr@crona-* — Send mail as алиасы на едином Workspace-аккаунте `petr@prospectscrona.com`. Gmail-deliverability на 9 алиасах померен через `eleonora@` на тех же доменах (мирроред-аккаунты, общий FROM-домен и DNS).

**Account Infra** — наличие записи в `Outreach: Internal → Accounts infra` (sheet `1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg`).

| # | Mailbox | Тип / Owner | Account Infra | Gmail | O365 | Статус |
|---|---|---|---|---|---|---|
| 1 | `petr@prospectscrona.com` | Primary Workspace / Petr | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 2 | `petr@crona-base.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | ✅ inbox (proxy) | ✅ inbox | Алиас, FROM ок |
| 3 | `petr@crona-flow.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | ✅ inbox (proxy) | ✅ inbox | Алиас, FROM ок |
| 4 | `petr@crona-force.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | 🟡 promo (proxy) | ✅ inbox | Алиас, Gmail в promo |
| 5 | `petr@segment-crona.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | 🟡 promo (proxy) | ✅ inbox | Алиас, Gmail в promo |
| 6 | `petr@leads-crona.com` | Alias (#1) / Petr | ❌ нет в реестре | 🟡 promo (proxy) | ✅ inbox | Алиас, Gmail в promo |
| 7 | `petr@cronaaiprospects.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | 🟡 promo (proxy) | ✅ inbox | Алиас, Gmail в promo |
| 8 | `petr@crona-stack.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | 🟡 promo (proxy) | ✅ inbox | Алиас, Gmail в promo |
| 9 | `petr@crona-b2b.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | ❌ spam (proxy) | ❌ 58% spam | **Проблемный FROM** |
| 10 | `petr@cronaaipipeline.com` | Alias (#1) / Petr | ✅ Pavel (eleonora@) | ❌ spam (proxy) | ❌ 50% spam | **Проблемный FROM** |
| 11 | `bhaskar@onsocial-platform.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 12 | `bhaskar.v@onsocial-platform.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 13 | `bhaskar@onsocial-network.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 14 | `bhaskar.v@onsocial-network.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 15 | `bhaskar@onsocial-metrics.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 16 | `bhaskar.v@onsocial-metrics.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 17 | `bhaskar@onsocial-data.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 18 | `bhaskar.v@onsocial-data.com` | Primary / — | ❌ нет в реестре | ✅ inbox | ✅ inbox | **Production-ready** |
| 19 | `bhaskar@onsocial-analytics.com` | Primary / — | ❌ нет в реестре | ✅ 100% inbox | ❌ 100% spam | **Gmail-only** |
| 20 | `bhaskar.v@onsocial-analytics.com` | Primary / — | ❌ нет в реестре | ✅ 100% inbox | ❌ 100% spam | **Gmail-only** |
| 21 | `bhaskar@onsocial-influence.com` | Primary / — | ❌ нет в реестре | ✅ 100% inbox | ❌ 100% spam | **Gmail-only** |
| 22 | `bhaskar.v@onsocial-influence.com` | Primary / — | ❌ нет в реестре | ✅ 100% inbox | ❌ 100% spam | **Gmail-only** |
| 23 | `bhaskar@onsocial-insights.com` | Primary / — | ❌ нет в реестре | ✅ 100% inbox | ❌ 100% spam | **Gmail-only** |
| 24 | `bhaskar.v@onsocial-insights.com` | Primary / — | ❌ нет в реестре | ✅ 100% inbox | ❌ 100% spam | **Gmail-only** |

**Сводка по реальным sender-аккаунтам:**
- 🟢 **Production-ready (9)**: 1 petr (`prospectscrona`) + 8 bhaskar
- 🟡 **Gmail-only кандидаты (6)**: 6 bhaskar на 3 проблемных доменах (`onsocial-analytics/influence/insights`)
- 🔵 **9 алиасов petr@** на едином аккаунте: 7 с приличным FROM, 2 (`crona-b2b`, `cronaaipipeline`) — спалённый FROM

**Gaps в Accounts infra реестре:**
- 16 bhaskar записей отсутствуют (вся инфра bhaskar не задокументирована)
- 2 крона-домена не в реестре: `prospectscrona.com`, `leads-crona.com`

### 🟡 Bhaskar OnSocial — 3 проблемных домена
- `onsocial-analytics.com`, `onsocial-influence.com`, `onsocial-insights.com`
- Тест 399820: 100% inbox в Google, 100% spam в Office365 (для всех 6 mailbox'ов на этих доменах)
- DNS чистый (SPF/DKIM/DMARC PASS, не в blacklist'ах)
- Это **domain-level reputation issue в Microsoft**, не контент

### 🟢 Eleonora EasyStaff — 10 ящиков здоровы
- `eleonora.s@easystaff{reports/portal/people/office/network/hr/direct/center/bridge/agile}.com`
- `warmup_reputation: 100`, не заблокированы, SMTP/IMAP OK
- 10/10 реальных тест-сендов прошли успешно, 0 bounces

---

## Lead Distribution (4502 lead'а в 12 active OnSocial-кампаниях)

| Provider | % leads |
|---|---|
| Google Workspace / Gmail | **64.2%** |
| Microsoft (Office365 + relays) | **29.0%** |
| Other (Zoho/Yandex/self-hosted) | 6.8% |

Кампании с экстремальным MS-exposure:
- **IMAGENCY_ACCOUNT_OPS**: 49.4% Microsoft
- **IMAGENCY_CREATIVE**: 42.4% Microsoft

---

## Что уже сделано

- ✅ Удалены 6 проблемных bhaskar-mailbox'ов из ACCOUNT_OPS (3124575) и CREATIVE (3124571) — там было ~50% MS-leak
- ✅ Верифицирована работоспособность eleonora-инфраструктуры через прямую отправку
- ✅ Идентифицирована корневая причина echo-errors (Workspace Mail Service)

---

## Pending (требуется от партнёра)

1. **[Workspace admin]** Проверить `admin.google.com` для 9 alias-доменов petr@:
   - Users → петр@ → Settings → "Send mail as" — есть ли alias'ы у `petr@prospectscrona.com`?
   - Если да — проверить SPF/DKIM на каждом alias-домене + Authorize в Gmail-настройках
   - Если нет — каждый из 9 это отдельный Workspace, проверить billing/license/Mail service ON
2. **[Deliverability]** Решить судьбу 3 проблемных bhaskar-доменов:
   - (a) Warmup 4-6 недель + повторный SD test
   - (b) Заменить домены и вывести из ротации
3. **[Optional]** A/B на одной кампании: включить **ESP Matching** (`enable_ai_esp_matching: true`) на `IM-FIRST_AGENCIES_C` (83% Gmail leads — низкий risk), замерить inbox-rate через 7 дней. Сейчас фича включена только на `INFLUENCER PLATFORMS ALL GEO #C` (3096747).

---

## ESP Matching — справка

**UI:** Campaign → Step 6: Schedule → Campaign Settings → "Enhanced Email Sending & Delivery" → ESP Matching toggle
**API:** `enable_ai_esp_matching: true`

**Что делает:** на каждом send-tick матчит sender ESP с lead ESP (Gmail→Gmail, Outlook→Outlook). Если match'а нет — всё равно отправляет несовпадающим sender'ом (фича = optimizer, не filter).

⚠️ **Не включать одновременно с "Isolated Lead Email Provider Sending"** — кампания зависнет в ACTIVE навсегда.

**Источник:** [helpcenter.smartlead.ai/en/articles/72](https://helpcenter.smartlead.ai/en/articles/72-understanding-esp-matching-in-smartlead)

---

## Артефакты сессии

- SmartDelivery test 399820 (Onsocial baseline) — 82.35% inbox / 17.65% spam
- SmartDelivery test 403888 (eleonora) — создан, но не получил seed-mail (особенности setup'а fresh-кампании, не дотянули)
- Test campaign 3235236 — рабочий артефакт, можно удалить
