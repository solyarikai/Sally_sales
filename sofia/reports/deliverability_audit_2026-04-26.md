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
