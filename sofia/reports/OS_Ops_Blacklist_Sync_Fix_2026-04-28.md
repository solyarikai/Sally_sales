# OnSocial Blacklist Sync — Fix & Backfill

**Date:** 2026-04-28
**Author:** Sofia
**Status:** Closed. Backfill done, daily cron live on Hetzner.
**Trigger:** Hype Lab (`olie@hype-lab.co.uk`) и Rosas Agency (`daniele.cicini@rosasagency.com`) ответили "Not Interested" в `c-OnSocial_IMAGENCY_FOUNDERS` несмотря на то, что эти же люди уже отказали в более старой OnSocial-кампании.

---

## TL;DR

Лиды, ответившие SmartLead-категориями `Not Interested / Do Not Contact / Negative Reply / Not Qualified` или отписавшиеся, **не попадали в `project_blacklist`**. Pipeline их домены не знал → брал повторно в новые раны. Дыра существовала с момента запуска OnSocial.

Починили: написали скрипт SmartLead → `project_blacklist`, прогнали backfill (38 новых доменов, включая обоих виновников), повесили cron на ежедневный инкремент.

---

## Root cause

Существовал Apps Script `sofia/scripts/leads_to_blacklist_sync.gs`, который якобы синкал лидов в blacklist. Но:

1. Скрипт ищет в `OnSocial <> Sally` табы с префиксом `LEADS`. **Таких табов сейчас 0** (есть `Leads booking_Sofia`, `LinkedIn Outreach`, `Weekly replies` — ни один не начинается с `LEADS`). `findLeadsSheets()` возвращает пустой массив.
2. Даже если бы префикс совпадал — скрипт собирает в blacklist *всех, кому писали*, а не *тех, кто отказал*. Это похоронит положительных лидов на ре-таргетинг через 6 месяцев.
3. Источник истины Not Interested / Do Not Contact живёт в SmartLead, а скрипт читает Google Sheets.

В `magnum-opus` автоматики "negative reply → blacklist" тоже **не существовало**. Проверил все писатели в `project_blacklist`:

| Источник | Кол-во | Что делает |
|---|---|---|
| `onsocial_20k` | 10656 | Разовый дамп при запуске проекта |
| `manual` | 272 | Руками |
| `pipeline` | 149 | При загрузке лида в SmartLead домен идёт в blacklist (защита от повторной заливки) |
| `auto_review` | 46 | Rejected в TAM-review flow |
| `pipeline_manual` | 3 | Руками через скрипт |

**Никто не читал SmartLead `lead_category_id`.** Поэтому Hype Lab отказался 2026-03-20 в `EUROPE #C`, никто не записал, мы взяли его снова в `IMAGENCY_FOUNDERS` 2026-04-13. Аналогично Rosas.

---

## Что сделано

### 1. Скрипт `scripts/sofia/blacklist_sync_smartlead.py`

Standalone Python, работает на Hetzner. Логика:

1. `GET /campaigns?include_tags=true` — фильтрует по префиксу `c-OnSocial_` (41 кампания).
2. Для каждой кампании пробит `total_leads` по 5 negative-категориям + unsubscribed sweep.
3. Категории, считающиеся blacklistable:
   - `3` — Not Interested
   - `4` — Do Not Contact
   - `77594` — Negative Reply
   - `77596` — Do Not Contact (custom)
   - `78987` — Not Qualified
   - плюс `is_unsubscribed=true`
4. Извлекает домен из email, нормализует (lowercase, strip protocol/www/trailing slash).
5. Whitelist: free email providers (gmail/outlook/etc) + наши собственные домены (`getsally.io`, `onsocial.io`, etc) — никогда не блеклистим.
6. Upsert в `project_blacklist` (project_id=42) через `INSERT ... ON CONFLICT (project_id, domain) DO NOTHING`. `source='smartlead_negative'`, `reason='smartlead category N (Name)'` или `'smartlead unsubscribed'`.

Режимы:
- `--backfill` — полный sweep всех кампаний, всех времён.
- `--since 24h` — инкремент за окно (для daily cron).
- `--skip-unsubscribed` — для daily, чтобы не делать дорогой sweep без серверного фильтра.
- `--dry-run` — превью без записи.
- `--export-json <path>` — дамп списка новых доменов для аудита.

Rate-limiting: пауза 0.4s между запросами, ретрай на 429 с экспоненциальным backoff до 60 сек, 6 попыток. Полный backfill = ~6-7 минут.

### 2. Backfill результаты

```
OnSocial campaigns scanned:  41
Unique negative domains:     70
Already in project_blacklist: 32
NEW domains inserted:         38
```

**Категория 4 (Do Not Contact) — 14 доменов:**
jabberhaus.com, goldenpill.com.br, phyllislondonpr.com, authenticm.com, **hype-lab.co.uk**, **rosasagency.com**, lv8.co, pixly.tv, kinoba.fr, socialpruf.com, head.com, mcfillmedia.com, acuprojects.com, thanks.co, cinebody.com

**Категория 3 (Not Interested) — 16 доменов:**
intheblackmedia.com, dipaolalatina.com, playerfound.live, scrollstop.com, gmd.digital, thecovenantcreative.com, breakpointsocial.com, dubbinghits.com, thunderlymarketing.com, muhimmaapp.com, new-wave.ai, spaceagencyksa.com, digitalshoutouts.com, archmedia.biz, evolvez.co, thedigitaldept.com, creatororigin.com

**Категория 77594 (Negative Reply) — 1:**
raffiti.com

**Unsubscribed — 6:**
scoop.app, thetimeless.club, fabulate.com.au, iganatech.com, digimag.co.in (плюс ещё 1)

**Whitelist отработал:** `getsally.io` (был среди unsubscribed из-за чьего-то test-forward) исключён.

### 3. Cron на Hetzner

```cron
# Daily SmartLead negative leads -> project_blacklist sync (OnSocial)
0 3 * * * cd /home/leadokol/magnum-opus-project/repo && python3 scripts/sofia/blacklist_sync_smartlead.py --since 48h >> /home/leadokol/logs/blacklist_sync.log 2>&1
```

- 03:00 UTC ежедневно (после `daily_reply_refetch.sh` в 02:00, чтобы свежие категории SmartLead уже подтянулись)
- `--since 48h` даёт overlap на случай сбоя одного запуска
- Лог: `~/logs/blacklist_sync.log`

### 4. Verification

```sql
SELECT domain, source, reason, created_at FROM project_blacklist
WHERE project_id=42 AND domain IN ('hype-lab.co.uk','rosasagency.com');

     domain      |       source       |                reason                 |          created_at
-----------------+--------------------+---------------------------------------+-------------------------------
 hype-lab.co.uk  | smartlead_negative | smartlead category 4 (Do Not Contact) | 2026-04-28 09:36:34.096442+00
 rosasagency.com | smartlead_negative | smartlead category 4 (Do Not Contact) | 2026-04-28 09:36:34.096442+00
```

`onsocial_universal_pipeline.py` → `_filter_project_blacklist()` теперь будет фильтровать оба домена на следующем `--from-step gather` или новом ране.

---

## Scope

**Только OnSocial** (`project_id=42`, кампании `c-OnSocial_*`). Mosta / SquareFi / Palark / другие проекты не затронуты — у них свои pipelines и им нужны свои blacklist-syncs, если такая дыра существует и там.

Whitelist `_OWN_DOMAINS` общий для всех (наши собственные домены, чтобы не самозаблеклистились на test-forward).

---

## Что осталось (не блокирует)

1. **Косметика — sync `project_blacklist` → `OS | Ops | Blacklist` (Exclusion Lists sheet).** БД уже правильная, sheet используется как просмотр. Можно повесить второй cron, который раз в день экспортирует. Полчаса работы.
2. **Удалить дохлый `leads_to_blacklist_sync.gs`** или переименовать в `_deprecated_*` с комментарием. Минута.
3. **Обобщение под все проекты.** Сейчас project_id и префикс зашиты. Если хотим — принимать `--project` argument с маппингом.

---

## Files

- `sofia/scripts/blacklist_sync_smartlead.py` — основной скрипт (на Hetzner: `magnum-opus-project/repo/scripts/sofia/`)
- `sofia/reports/OS_Ops_Blacklist_Sync_Fix_2026-04-28.md` — этот отчёт
- Cron entry: `crontab -l | grep blacklist_sync`
- Лог: `hetzner:~/logs/blacklist_sync.log`
