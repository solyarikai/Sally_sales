# OnSocial — Mailbox Audit (Mar+Apr replies × Instantly inbox %)

**Date:** 2026-04-29
**Sources:**
- Replies: SmartLead `/campaigns/{id}/statistics` + `/leads/{lid}/message-history` (sender attribution)
- Inbox %: Instantly active manual tests started 2026-04-28 (sample 3–8 sends/mailbox, partial)
- Canonical mailbox list: Instantly default OnSocial test `019d6206-de23-75c1-8525-0ed92d5cafde` (27 mailboxes)

**Coverage:**
- April: 103/103 replies attributed (cat 9 echo-bug excluded, 14–21 Apr)
- March: 35/85 replies attributed (50 unattributed — message-history empty for old/paused campaigns)
- Inbox %: 26/27 mailboxes covered (missing `petr@prospects-crona.com`)

---

## Canonical rotation (27 mailboxes)

`Inbox %` for petr is measured at the domain level (Instantly test sends from `eleonora@<domain>`; real sender for OnSocial campaigns is `petr@<domain>`). Marked with ¹.

### Bhaskar (17)

| Mailbox | Mar replies | Apr replies | Inbox % (n) | Flag |
|---|---:|---:|---|---|
| bhaskar.v@onsocial-network.com | 0 | 10 | 100% (7) | |
| bhaskar@onsocial-data.com | 0 | 9 | 100% (4) | |
| bhaskar@onsocial-analytics.com | 0 | 8 | 100% (7) | |
| bhaskar.v@onsocial-analytics.com | 0 | 8 | 80% (5) | ⚠ 1 spam |
| bhaskar@onsocial-metrics.com | 0 | 8 | 100% (5) | |
| bhaskar@onsocial-platform.com | 0 | 8 | 100% (6) | |
| bhaskar@onsocial-influence.com | 0 | 7 | 100% (6) | |
| bhaskar.v@onsocial-insights.com | 0 | 7 | 100% (5) | |
| bhaskar.v@onsocial-platform.com | 0 | 6 | 100% (7) | |
| bhaskar.v@onsocial-metrics.com | 0 | 6 | 100% (5) | |
| bhaskar@onsocial-network.com | 0 | 6 | 100% (6) | |
| bhaskar@onsocial-insights.com | 0 | 3 | 80% (5) | ⚠ 1 spam |
| bhaskar.v@onsocial-data.com | 0 | 3 | 100% (4) | |
| bhaskar.v@onsocial-influence.com | 0 | 1 | 80% (5) | ⚠ 1 spam |
| bhaskar.v@onsocialmetrics.com | 4 | 3 | **62% (8)** | 🔴 3 spam — худший |
| bhaskar@onsocialmetrics.com | 4 | 1 | 100% (3) | |
| bhaskar.v@onsocialplatform.com | 2 | 0 | 100% (7) | замолчал в апреле |

### Petr (10)

| Mailbox | Mar replies | Apr replies | Inbox % (n) | Flag |
|---|---:|---:|---|---|
| petr@crona-flow.com | 0 | 2 | 100% (6)¹ | |
| petr@crona-force.com | 3 | 2 | 100% (4)¹ | |
| petr@segment-crona.com | 0 | 2 | 100% (4)¹ | |
| petr@leads-crona.com | 3 | 1 | 100% (4)¹ | |
| petr@cronaaiprospects.com | 0 | 1 | 100% (5)¹ | |
| petr@prospects-crona.com | 0 | 1 | — | нет в активных тестах |
| petr@crona-base.com | 2 | 0 | 100% (5)¹ | |
| petr@crona-b2b.com | 0 | 0 | 100% (4)¹ | 0 реплаев за 2 месяца |
| petr@crona-stack.com | 0 | 0 | 100% (5)¹ | 0 реплаев за 2 месяца |
| petr@cronaaipipeline.com | 0 | 0 | **71% (7)¹** | ⚠ 2 spam + 0 реплаев |

¹ Inbox % замерено по домену (тест-отправитель `eleonora@<domain>`).

---

## Объединённая таблица (все 27, sorted by Apr replies desc)

| # | Mailbox | Owner | Mar | Apr | Inbox % (n) | Flag |
|---:|---|---|---:|---:|---|---|
| 1 | bhaskar.v@onsocial-network.com | bhaskar | 0 | 10 | 100% (7) | |
| 2 | bhaskar@onsocial-data.com | bhaskar | 0 | 9 | 100% (4) | |
| 3 | bhaskar@onsocial-analytics.com | bhaskar | 0 | 8 | 100% (7) | |
| 4 | bhaskar.v@onsocial-analytics.com | bhaskar | 0 | 8 | 80% (5) | ⚠ |
| 5 | bhaskar@onsocial-metrics.com | bhaskar | 0 | 8 | 100% (5) | |
| 6 | bhaskar@onsocial-platform.com | bhaskar | 0 | 8 | 100% (6) | |
| 7 | bhaskar@onsocial-influence.com | bhaskar | 0 | 7 | 100% (6) | |
| 8 | bhaskar.v@onsocial-insights.com | bhaskar | 0 | 7 | 100% (5) | |
| 9 | bhaskar.v@onsocial-platform.com | bhaskar | 0 | 6 | 100% (7) | |
| 10 | bhaskar.v@onsocial-metrics.com | bhaskar | 0 | 6 | 100% (5) | |
| 11 | bhaskar@onsocial-network.com | bhaskar | 0 | 6 | 100% (6) | |
| 12 | bhaskar@onsocial-insights.com | bhaskar | 0 | 3 | 80% (5) | ⚠ |
| 13 | bhaskar.v@onsocial-data.com | bhaskar | 0 | 3 | 100% (4) | |
| 14 | bhaskar.v@onsocialmetrics.com | bhaskar | 4 | 3 | **62% (8)** | 🔴 |
| 15 | petr@crona-flow.com | petr | 0 | 2 | 100% (6)¹ | |
| 16 | petr@crona-force.com | petr | 3 | 2 | 100% (4)¹ | |
| 17 | petr@segment-crona.com | petr | 0 | 2 | 100% (4)¹ | |
| 18 | bhaskar.v@onsocial-influence.com | bhaskar | 0 | 1 | 80% (5) | ⚠ |
| 19 | bhaskar@onsocialmetrics.com | bhaskar | 4 | 1 | 100% (3) | |
| 20 | petr@leads-crona.com | petr | 3 | 1 | 100% (4)¹ | |
| 21 | petr@cronaaiprospects.com | petr | 0 | 1 | 100% (5)¹ | |
| 22 | petr@prospects-crona.com | petr | 0 | 1 | — | нет в тестах |
| 23 | bhaskar.v@onsocialplatform.com | bhaskar | 2 | 0 | 100% (7) | замолчал |
| 24 | petr@crona-base.com | petr | 2 | 0 | 100% (5)¹ | |
| 25 | petr@crona-b2b.com | petr | 0 | 0 | 100% (4)¹ | 0 за 2 мес |
| 26 | petr@crona-stack.com | petr | 0 | 0 | 100% (5)¹ | 0 за 2 мес |
| 27 | petr@cronaaipipeline.com | petr | 0 | 0 | **71% (7)¹** | ⚠ + 0 реплаев |
| | **Total (27)** | | **18** | **103** | | |

¹ Inbox % замерено по домену (тест-отправитель `eleonora@<domain>`).

---

## Off rotation (исторический контекст)

Ящики, давшие реплаи в марте и **отсутствующие** в каноническом 27 — сняты ранее (предположительно при подключении 14 новых apr-доменов). В отчёте только для полноты картины.

| Mailbox | Mar replies | Apr replies | Status |
|---|---:|---:|---|
| bhaskar@onsocialplatform.com | 5 | 0 | off rotation |
| bhaskar@onsocialinsights.com | 3 | 0 | off rotation |
| bhaskar@onsocialdata.com | 3 | 0 | off rotation |
| bhaskar@onsocialanalytics.com | 2 | 0 | off rotation |
| bhaskar@onsocialnetwork.com | 2 | 0 | off rotation |
| bhaskar.v@onsocialanalytics.com | 1 | 0 | off rotation |
| bhaskar.v@onsocialinsights.com | 1 | 0 | off rotation |

---

## Сводка

**Bhaskar (apr-домены, 14 ящиков):** новые домены работают — 0 → 90 реплаев за месяц. Inbox 80–100%, проблемных нет.

**Bhaskar (старые домены в ротации, 3 ящика):** `onsocialmetrics.com`/`onsocialplatform.com` ещё дают реплаи, но `bhaskar.v@onsocialmetrics.com` явно деградирует (62% inbox + просадка реплаев). `bhaskar.v@onsocialplatform.com` молчит апрель — проверить, шлёт ли вообще.

**Petr (10 ящиков):**
- 6 рабочих (давали реплаи в марте и/или апреле, inbox 100%)
- **3 «тихих»** за 2 месяца: `crona-b2b`, `crona-stack`, `cronaaipipeline`. Первые два — inbox OK, скорее низкий volume или плохой таргетинг. `cronaaipipeline` — единственный petr с inbox-проблемой (71%, 2 spam).
- Деградация petr month-over-month: Mar attributed 8 → Apr 9 — суммарно ровно, **но при росте общего числа реплаев в 1.4× и подключении 14 новых ящиков bhaskar доля petr упала**.

**Кандидаты на действие (но НЕ в этом отчёте — только пометки):**
- 🔴 `bhaskar.v@onsocialmetrics.com` — 62% inbox, единственный явный spam-сигнал в ротации.
- ⚠ `cronaaipipeline.com` — 71% inbox + 0 реплаев. Под вопросом весь домен.
- ⚠ Тройка bhaskar 80%-inbox (`onsocial-insights`, `v.influence`, `v.analytics`) — следить, ещё в пределах нормы.
- ❓ `crona-b2b`, `crona-stack`, `prospects-crona`, `bhaskar.v@onsocialplatform.com` — нет реплаев. Проверить, есть ли вообще отправки.

---

## Caveats

- Instantly тесты запущены 2026-04-28 ~сутки назад, сэмпл 3–8 писем/ящик — цифры будут уточняться.
- March attribution неполная (35/85): 50 реплаев привязаны к старым/паузным кампаниям с пустым `message-history` API. По распределению Mar replies реальная картина почти наверняка богаче для off-rotation домена (там реплаи и потерялись).
- Inbox % для petr — proxy через `eleonora@<domain>`. Корректно, если spam-классификация определяется доменом (что в основном так), но не учитывает per-mailbox reputation.
- Реплаи cat 9 (Sender Originated Bounce, эхо-баг 14–21 Apr) **исключены** из обоих месяцев.
