# Распределённый Enrichment — 2 машины × 15 кампаний

Инструкция для агента в чистом контексте. Запускаешь на одной из двух машин, координируешься через GitHub.

---

## Контекст

30 SmartLead кампаний нужно обогатить полностью автономно:
1. Записать `cf_business_observation` через Claude Code WebSearch (Tier 1 + опционально Tier 2)
2. Написать и загрузить 3-step sequence на каждую кампанию

Запуск распараллелен на **2 машины**: Machine A и Machine B. Каждая берёт половину кампаний.

---

## Окружение (одинаково на обеих машинах)

- **Repo:** `/Users/sofia/code/Sally_sales` (git remote: `https://github.com/solyarikai/Sally_sales`)
- **Python:** `python3.11`
- **Env (берётся из `.mcp.json`):**
  - `SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5`
  - `EXA_API_KEY=9c2d6eb0-66d8-4163-b244-6b4e78525aa0`
- **MCP servers:** `mcp__smartlead__*` доступен через `.claude/mcp/smartlead-mcp/server.py`
- **Базовая инструкция (читать обязательно):** `sofia/projects/OnSocial/docs/ENRICHMENT_AGENT_INSTRUCTIONS.md`

---

## Распределение кампаний

### Machine A — Tier T1 + T2 (16 кампаний)

```
3215181  [T1] AFFPERF_FOUNDERS_SMB_AMERICAS
3215180  [T1] AFFPERF_FOUNDERS_SMB_EMEA
3215186  [T1] AFFPERF_TECHLEAD_SMB
3215178  [T1] IMAGENCY_FOUNDERS_SMB_AMERICAS
3215177  [T1] IMAGENCY_FOUNDERS_SMB_EMEA
3215179  [T1] IMAGENCY_FOUNDERS_SMB_INDIA_APAC
3215185  [T1] IMAGENCY_TECHLEAD_SMB
3215312  [T1-NY] INFPLAT_TECHLEAD_SMB
3215316  [T2-NY] INFPLAT_ACCOUNT_OPS_SMB
3215188  [T2] AFFPERF_ACCOUNT_OPS_SMB
3215187  [T2] AFFPERF_HEAD_SMB
3215183  [T2] IMAGENCY_ACCOUNT_OPS_SMB
3215182  [T2] IMAGENCY_HEAD_SMB
3215314  [T2] INFPLAT_HEAD_SMB
3241493  [T2-BER] INFPLAT_FOUNDERS_SMB_EMEA
3215189  [T2-NY] INFPLAT_FOUNDERS_SMB_AMERICAS
```

### Machine B — Tier T3 (14 кампаний)

```
3215317  [T3-NY] INFPLAT_ACCOUNT_OPS_MidMarket
3215354  [T3] AFFPERF_ACCOUNT_OPS_MidMarket
3215198  [T3] AFFPERF_FOUNDERS_MidMarket
3215353  [T3] AFFPERF_HEAD_MidMarket
3215352  [T3] AFFPERF_TECHLEAD_MidMarket
3215196  [T3] IMAGENCY_ACCOUNT_OPS_MidMarket
3207897  [T3] IMAGENCY_CREATIVE_LATAM
3207895  [T3] IMAGENCY_CREATIVE_US_CA
3215193  [T3] IMAGENCY_FOUNDERS_MidMarket
3215194  [T3] IMAGENCY_HEAD_MidMarket
3215197  [T3] IMAGENCY_TECHLEAD_MidMarket
3215315  [T3] INFPLAT_HEAD_MidMarket
3215199  [T3-NY] INFPLAT_FOUNDERS_MidMarket
3215313  [T3-NY] INFPLAT_TECHLEAD_MidMarket
```

**Принцип распределения:** разделение по тиру (T1/T2 на Machine A, T3 на Machine B) — машины пишут в разные SmartLead кампании, нет конфликтов.

---

## Координация через GitHub

### До старта

Обе машины:
```bash
cd /Users/sofia/code/Sally_sales
git pull origin main
```

### Конвенция файлов (чтобы не было merge-конфликтов)

| Файл | Machine A | Machine B |
|---|---|---|
| Основной лог | `sofia/reports/exa_enrichment_<DATE>_machine_a.jsonl` | `sofia/reports/exa_enrichment_<DATE>_machine_b.jsonl` |
| OTHER-файлы | `sofia/projects/OnSocial/data/other/other_<segment>_a.json` | `sofia/projects/OnSocial/data/other/other_<segment>_b.json` |
| Heartbeat | `sofia/reports/_status_machine_a.json` | `sofia/reports/_status_machine_b.json` |
| Финальный отчёт | `sofia/reports/ENRICHMENT_REPORT_<DATE>_machine_a.md` | `sofia/reports/ENRICHMENT_REPORT_<DATE>_machine_b.md` |

`<DATE>` = текущая дата формата `2026-04-30`.

### Heartbeat файл — обновлять каждые 5 минут

```json
{
  "machine": "a",
  "started_at": "2026-04-30T22:00:00Z",
  "current_campaign": 3215178,
  "campaigns_done": 3,
  "campaigns_total": 16,
  "leads_processed": 87,
  "ok": 12,
  "tier_1": 5,
  "other": 38,
  "fail": 32,
  "last_update": "2026-04-30T22:35:00Z"
}
```

### Git commit правила

- Машина коммитит **только свои файлы** (с суффиксом `_a` или `_b`)
- Pull → commit → push после каждой завершённой кампании
- Если push отклонён → `git pull --rebase origin main && git push`
- Никогда не трогать файлы другой машины

---

## Алгоритм работы (на каждой машине одинаковый)

### Шаг 0 — Подготовка (1 раз)

1. `cd /Users/sofia/code/Sally_sales && git pull origin main`
2. Прочитать **базовую инструкцию полностью**: `sofia/projects/OnSocial/docs/ENRICHMENT_AGENT_INSTRUCTIONS.md`
3. Прочитать промпты сегментов из `sofia/projects/OnSocial/prompts/classify_*.md`
4. Создать heartbeat файл с `started_at`, `campaigns_total = <твой список>`

### Шаг 1 — Цикл по своим кампаниям

Для каждой `campaign_id` из своего списка (последовательно):

#### 1.1 Получить лиды
```python
mcp__smartlead__list_campaign_leads(campaign_id=<id>, offset=0, limit=100)
```
Пагинация до конца. Извлечь `id`, `email`, `company_name`, `website`, `custom_fields`.

#### 1.2 Сгруппировать по домену
- Домен = после `@` в email (или поле `website`)
- Skip free-mail: gmail/yahoo/hotmail/outlook/icloud/aol/proton/mail.com/live/msn
- Skip если у первого лида домена `cf_business_observation` уже непустой → лог `already_enriched`

#### 1.3 Для каждого домена — Research (параллельно через Task subagents)

Запустить **8 параллельных subagents** (Task tool, `subagent_type: "general-purpose"`), каждый берёт ~10 доменов.

Промпт каждому subagent:

```
You are a research agent. For each domain in your list, do the following:

TIER 1 — Company research:
1. WebSearch: "{company_name}" interview OR raised OR growth site:linkedin.com OR site:crunchbase.com OR site:techcrunch.com
2. WebSearch: "{company_name}" creator influencer affiliate
3. If both empty → fallback Exa scrape:
   POST https://api.exa.ai/contents { "ids": ["https://{domain}"], "text": {"maxCharacters": 1600} }

Score Tier 1 quality 0-3 based on:
- 3: explicit funding/growth metric + public quote + scale number
- 2: any 2 of (vertical, scale, named clients)
- 1: only generic mentions
- 0: nothing found

TIER 2 — Person research (only if at least one contact has full name):
For each contact:
1. WebSearch: "{first_name} {last_name}" "{company_name}" {title}
2. If thin: WebSearch: "{first_name} {last_name}" {company_domain} interview OR podcast

Score Tier 2 0-3.

Build cf_business_observation per domain following formula:
[what company does specifically] + [operational pain with creator/influencer data] + [economic or time cost]

Use the strongest hook from this rank order:
1. concrete_number (specific scale: "3000+ creators", "$12M Series A")
2. math_on_their_data (derived: "50% × 6 months = 600 hours")
3. career_path (person's prior company connection)
4. scaling_pain (named in their own quote)
5. role_daily_pain (generic but role-specific)
6. fallback (segment-level pain)

Output for each domain (JSON):
{
  "domain": "...",
  "tier_1_quality": 0-3,
  "tier_2_quality": 0-3,
  "hook_used": "concrete_number",
  "facts_cited": ["..."],
  "sources": ["url1", "url2"],
  "cf_business_observation": "<one sentence following formula>",
  "tier": "TIER_0" | "TIER_1" | "OTHER",
  "evidence": "<short reason for tier>"
}

If no signal at all anywhere → tier = "OTHER", cf_business_observation = "".

Save results in your message back. Do not write to files yet.
```

Собери результаты от всех subagents.

#### 1.4 Запись в SmartLead

Для каждого домена с `tier == TIER_0`:
```python
for lead in domain_leads:
    mcp__smartlead__update_lead(
        campaign_id=<id>,
        lead_id=lead["id"],
        custom_fields={"cf_business_observation": result["cf_business_observation"]}
    )
```

`TIER_1` → не пишем, логируем.
`OTHER` → не пишем, добавляем в `other_<segment>_<machine>.json`.

#### 1.5 Запись лога

Append в `sofia/reports/exa_enrichment_<DATE>_machine_<a|b>.jsonl`:
```json
{"domain":"...","campaign_id":...,"segment":"...","tier":"TIER_0","tier_1_quality":3,"tier_2_quality":2,"hook_used":"concrete_number","cf_business_observation":"...","sources":[...],"status":"ok","processed_at":"..."}
```

#### 1.6 Sequence для кампании

После завершения всех доменов кампании:

```python
existing = mcp__smartlead__get_campaign_sequences(campaign_id=<id>)
```
Если в ответе `0 sequence steps` → пишем. Если есть steps → лог `sequence_exists`, пропускаем.

**Написать 3 шага** строго по правилам из `ENRICHMENT_AGENT_INSTRUCTIONS.md` (раздел Sequence):
- Step 1 (Day 0): начинается с `{{cf_business_observation}}` дословно + одна строка про OnSocial + soft CTA
- Step 2 (Day +3): берёт один элемент из observation (число/канал/потери) и раскрывает механизм. Пустой subject.
- Step 3 (Day +6): soft exit или переадресация. Пустой subject.

**Особый случай:** если у кампании 0 лидов получили `cf_business_observation` — использовать generic opener по сегменту (см. таблицу в базовой инструкции).

```python
mcp__smartlead__save_campaign_sequence(
    campaign_id=<id>,
    sequences=[
        {"seq_number": 1, "seq_delay_details": {"delay_in_days": 0}, "subject": "{{first_name}}, creator data — {{company_name}}", "email_body": "<step 1>"},
        {"seq_number": 2, "seq_delay_details": {"delay_in_days": 3}, "subject": "", "email_body": "<step 2>"},
        {"seq_number": 3, "seq_delay_details": {"delay_in_days": 3}, "subject": "", "email_body": "<step 3>"}
    ]
)
```

#### 1.7 Heartbeat update + git push

Обновить `_status_machine_<a|b>.json`, увеличить `campaigns_done`.
```bash
git pull --rebase origin main
git add sofia/reports/exa_enrichment_<DATE>_machine_<a|b>.jsonl \
        sofia/reports/_status_machine_<a|b>.json \
        sofia/projects/OnSocial/data/other/other_*_<a|b>.json
git commit -m "enrich: campaign <id> done (machine <a|b>)"
git push origin main
```

### Шаг 2 — После всех кампаний: финальный отчёт

`sofia/reports/ENRICHMENT_REPORT_<DATE>_machine_<a|b>.md`:

```markdown
# Enrichment Report — Machine <A|B>
Дата: <DATE>
Кампаний обработано: N

## По сегментам
| Segment | OK | TIER_1 | OTHER | Fail |
|---|---|---|---|---|
| INFPLAT | ... | ... | ... | ... |
| IMAGENCY | ... | ... | ... | ... |
| AFFPERF | ... | ... | ... | ... |
| SOCCOM | ... | ... | ... | ... |

## Tier breakdown (только OK)
- person tier: N (X%)
- company tier: N (X%)
- company_light: N (X%)

## Hook usage
- concrete_number: N
- math_on_their_data: N
- career_path: N
- scaling_pain: N
- ...

## Sequences
✅ Загружено: N
↩️ Уже было: N
✗ Ошибка: N

## Файлы
- Log: sofia/reports/exa_enrichment_<DATE>_machine_<a|b>.jsonl
- OTHER: sofia/projects/OnSocial/data/other/other_*_<a|b>.json
```

Закоммитить, запушить.

---

## Обработка ошибок (одинаково на обеих машинах)

| Ошибка | Действие |
|---|---|
| WebSearch quota exhausted | Перейти к следующему домену с tier_1=0, не падать |
| WebSearch не вернул ничего | Fallback на Exa contents → дальше Haiku |
| Exa 402 Payment Required | **СТОП весь ран**, сообщить через heartbeat |
| SmartLead 429 | Backoff 5/15/30s, 3 retry |
| SmartLead 5xx | `update_fail`, следующий лид |
| LinkedIn URL 999/403 (rate limit) | Skip этот URL, использовать что нашёл |
| Subagent упал/timeout | Перезапустить только этот chunk доменов, не всю кампанию |
| Git push отклонён | `git pull --rebase && git push` |
| Любое другое исключение | Поймать, лог `unknown_fail`, продолжить |

---

## Параллельность (внутри одной машины)

- 8 параллельных subagents через Task tool
- Каждый subagent = ~10 доменов = ~25-50 лидов
- Кампании внутри машины — последовательно (одна за раз)

---

## Что НЕ делать

- Не трогать кампании другой машины (даже если она упала)
- Не писать в файлы без суффикса `_a` или `_b`
- Не активировать кампании в SmartLead (только sequences и custom_fields)
- Не перезаписывать существующий `cf_business_observation`
- Не перезаписывать существующие sequences
- Не использовать `git push --force`
- Не сообщать пользователю промежуточный прогресс — работать молча, отчёт в конце

---

## Старт

```
1. Прочитай этот файл целиком
2. Прочитай sofia/projects/OnSocial/docs/ENRICHMENT_AGENT_INSTRUCTIONS.md целиком
3. Прочитай 4 промпта classify_*.md
4. Подтверди какая ты машина: A или B
5. Создай heartbeat файл
6. Стартуй цикл по своим кампаниям
7. По завершении — финальный отчёт + git push
```
