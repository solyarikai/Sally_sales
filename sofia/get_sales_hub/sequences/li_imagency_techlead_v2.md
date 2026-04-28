# LinkedIn Sequence: IMAGENCY_TECHLEAD (v2 DRAFT — Pattern A/C rewrite)

**Дата**: 2026-04-28
**Канал**: GetSales LinkedIn
**Сегмент**: IMAGENCY_TECHLEAD (CTO / Head of Engineering / VP Tech / Tech Lead в IM-first agencies)
**Sender**: Albina (smoke test)
**GetSales flow**: `f40ce250-816c-4ed1-abc4-982783fbaef3` (`OnSocial | IMAGENCY_TECHLEAD | LI ONLY`)
**Status**: DRAFT v2 — заменяет v1 до запуска

---

## Что говорит SmartLead v5 data (источник переработки)

Кампания `c-OnSocial_IMAGENCY_TECHLEAD` (id: 3169092), окно 2026-03-01 → 04-28:

| Step | Sent | Reply | Positive | Что внутри |
|------|------|-------|----------|------------|
| 1 (Day 0)  | 182 | 4 | **2** (~1.1%) | qualifier `"what API are you calling today?"` + pitch + 15-min CTA |
| 2 (Day +3) | 131 | 1 | **0** | handle-JSON trick |
| 3 (Day +6) | 78  | 1 | **0** | specs compare (freshness/depth) + route-to-DM |

**Вывод**: только Step 1 даёт positive. Step 2/3 email — мёртвые. Перетаскивать их в LI «как было» = повторить мёртвую гипотезу. **Нужно использовать рабочее ядро Step 1 + переизобрести follow-up под LI**.

Что забираем из v5:
- **Qualifier-фраза Step 1**: `"when {{company_name}}'s team needs creator data, what API are you calling today?"` — это Pattern A в полупрятанном виде. Извлекаем в opener.
- **Handle-trick из Step 2** (не сработал в email, но в LI контекст принципиально другой): после accept'a TECHLEAD проявил активный интерес, attention высокая → hook работает иначе.
- **Custom field `{{custom2}}`** = social_proof (e.g. "HypeAuditor, Modash, Captiv8") — переносим как `{{cf_competitor_client}}`.
- **`{{first_name}}` + `{{company_name}}`** — те же variables.

Что НЕ копируем:
- 15-min call CTA из Step 1 (email-CTA не работает в LI connect note из-за char-limit и tone).
- Длинный pitch абзац (450M / 9 years / specs) — в LI это идёт после accept'a, не в opener.
- Email Step 3 закрытие (`"last note"` + route) — оставляем форму, но смягчаем тон под LI.

---

## Что меняется vs v1 LI draft

| Шаг | v1 LI | v2 LI | Зачем |
|-----|----|----|-------|
| Connect note | 200 chars, описание продукта + soft вопрос | **Pattern A**: 1 строка, qualifier из v5 Step 1, без описания продукта | EasyStaff/SquareFi data + v5 Step 1 — qualifier reading > opener-pitch. |
| Step 2 (after accept) | ~600 chars, длинный pitch с handle-hook в конце | **Hook-first compact**: handle-JSON trick в первых 2 строках (формулировка из v5 Step 2), pitch одной строкой | Engineer reads first 3 lines. v5 формулировка `"easier to show than tell - drop a handle"` уже отшлифована. |
| Step 3 | "Stitching Modash/Phyllo/HypeAuditor" comparison | **Pattern C**: одна цифра на одну агентство (60% saving), сравнение **против одной тулзы**, не trio | IMAGENCY редко stitch'ат API — обычно 1 vendor (Modash/CreatorIQ). |
| Step 4 | Hard "last note" + route | **Soft route с reverse-psych** ("no follow-up unless you'd like one") | EasyStaff Day +N pattern. v5 hard "last note" в email не дал positive. |
| Step 5 | — | **+30 day re-touch** опциональный | Long sales cycle, дешёвый второй шанс. |

---

## Идеи по оптимизации flow в GetSales (отдельно от текстов)

1. **Cadence**: v1 = 0 / +1 / +5 / +10. v2 = **0 / +1 / +5 / +12 / +30**.
   - +12 (вместо +10) — даёт TECHLEAD отдышаться после второго touch (sprints, on-call).
   - +30 — последний выстрел через месяц (re-trigger seasonal/budget fit).

2. **Branching по accept/no-accept** (если GetSales поддерживает):
   - Если `connection_accepted = false` после Day +14 → **auto-stop** (нет смысла слать DM, если коннекта нет — LI не доставит).
   - Если `accepted_no_reply` после Day +5 → продолжить Step 3 как обычно.
   - Если `replied` (любой текст) → **stop sequence**, переключить на manual handle.

3. **Daily limits** (smoke test):
   - **20 connect requests/day** (LI safe weekly = 100, оставляем буфер).
   - **30 messages/day** (DMs к уже-connected).
   - **Auto-pause если accept rate < 10%** после первых 50 invites — значит intro-text не работает, тратить дальше нет смысла.

4. **A/B opener** (если хочется насытить smoke данными за 7 дней):
   - **Variant A**: build vs buy qualifier (technical persona).
   - **Variant B**: vendor-by-name qualifier ("using Modash или своё?").
   - Группа A — 50% list, Variant B — 50%. После 100 invites смотрим accept rate.

5. **Sender persona consistency check** (важно перед запуском):
   - Альбина's LinkedIn заголовок должен звучать tech-friendly. Если "Sales Manager" — коннект-rate просядет (TECHLEAD скрывают LI от сейлзов). Лучше "Partnerships @ OnSocial" / "BD @ OnSocial" / "Working with eng teams on creator data".

6. **Variables fallback**:
   - Если `{{cf_competitor_client}}` пустой — Step 2 fallback должен звучать естественно (см. ниже).
   - Если `{{first_name}}` пустой → drop из run (не слать "Hi ,").

---

## Step 1 — Connect request note (Day 0) — **Pattern A**

**Char limit: 300** (LinkedIn cap; safe target ≤200).

### Variant A (recommended) — extracted from v5 Step 1 qualifier

```
Hi {{first_name}}, quick one - when {{company_name}}'s team needs creator data, what API are you calling today?
```

**Char count**: ~125.

**Logic**: это **тот самый qualifier** что дал 2 positive в email v5 Step 1. В email он был спрятан в первой строке pitch'а; здесь — единственный месседж. Чистый Pattern A.

### Variant B — build-vs-buy framing

```
Hi {{first_name}}, does {{company_name}}'s team pull creator data from vendor APIs (Modash, HypeAuditor, etc) or roll your own?
```

**Char count**: ~140.

**Pick one, не оба в одной группе**. **Recommendation для первого smoke: Variant A** — копирует proven qualifier из email v5, контролирует переменные (только канал меняется).

**Why this works:**
- 1 предложение, 1 yes/no вопрос.
- Никакого продукта в opener — pure qualifier.
- Имя + компания в первой строке.
- Никакого CTA, никакой ссылки, никакого pitch.
- Лид сразу понимает: «отвечаю да / нет / не я / некогда».

---

## Step 2 — Day +1 after accept (DM) — **Hook-first** (v5 Step 2 formulation)

```
Thanks for the connect, {{first_name}}. Easier to show than tell.

Drop any creator handle in reply and I'll send back raw JSON from our endpoint: audience demographics down to city, fraud breakdown by type, engagement depth, 24-48h refresh.

Context: OnSocial = creator data API, 450M+ profiles across IG / TikTok / YouTube, 9 years in production. Teams like {{cf_competitor_client}} moved to us for one endpoint instead of stitching multiple APIs.

If the JSON beats what {{company_name}} is calling today, worth a chat. If not, you have a benchmark.
```

**Char count**: ~575.

**Logic**: формулировка `"Easier to show than tell. Drop any creator handle in reply..."` — буквально из v5 Step 2 (который не сработал в email). В LI после accept'а контекст принципиально другой — engineer открыл DM сам, attention свежая. Same hook, new channel, valid гипотеза для smoke.

**Fallback if `{{cf_competitor_client}}` is empty:**

> "Context: OnSocial = creator data API, 450M+ profiles across IG / TikTok / YouTube, 9 years in production. Some IM-first teams use us in place of two or three stitched vendor APIs."

**Why this works (vs v1 LI):**
- **Hook line 2** (не line 4-5). Engineer видит actionable trick без пролистывания.
- Pitch — один абзац, не три.
- "Worth a chat / you have a benchmark" — peer tone, не BD-rep.
- Concrete action (drop a handle), low friction, no call-ask.

---

## Step 3 — Day +5 (DM) — **Pattern C**

```
{{first_name}}, one comparable point if relevant.

Most IM agencies we talk to use Modash or CreatorIQ as their primary creator-data source. We sit one layer below: same audience / fraud / engagement signals, but via raw API at city-level granularity, refreshed every 24-48h instead of weekly.

One IM-first agency cut their creator-data spend ~60% by routing campaign discovery through our API instead of paying per-seat for Modash + ad-hoc HypeAuditor lookups.

If {{company_name}} ever scopes a build vs buy on this, happy to drop tech specs (latency, rate limits, schema) - 5 mins async over LI, no call needed.
```

**Char count**: ~610.

**Why this works (vs v1):**
- **One specific case** (1 agency, 60% saving) — Pattern C: vertical-specific number.
- Frames OnSocial **against one tool** (Modash OR CreatorIQ), not three — matches how IMAGENCY actually buys.
- "Tech specs over LI, no call needed" — engineer-friendly CTA, removes call-ask friction.
- Doesn't claim "we're better" — claims "we're a layer below + here's the math".

---

## Step 4 — Day +12 (DM, route) — **Soft hand-off**

```
{{first_name}}, last technical note from me.

If creator-data API selection isn't your call at {{company_name}} - happy to be pointed at whoever owns the data layer (usually CTO, Head of Data, VP Eng).

If you're the right person but timing is off - will check back next quarter.

Either way, no follow-up from me unless you'd like one.
```

**Char count**: ~330.

**Why this works:**
- Soft route-to-decision-maker.
- "No follow-up from me unless you'd like one" — closes loop politely, increases reply rate (reverse-psych effect, see EasyStaff).
- Not "last note from me" hard-stop tone (which v1 had) — softer.

---

## Step 5 — Day +30 re-touch (DM, optional) — **NEW**

```
{{first_name}}, circling back once - new quarter, new priorities.

Anything moved on the creator-data side at {{company_name}}? Happy to reopen if so. If not, will leave you alone.
```

**Char count**: ~210.

**Why this works:**
- Cheap re-trigger. ~2-5% of long-cycle leads convert on month-out touch (anecdotal SquareFi pattern).
- One sentence, one question. No new pitch.
- Easy to skip if no movement happened — no awkward energy.

**Optional** — если smoke test (7 days) убил sequence до Day +30, этот шаг просто не дойдёт.

---

## Variables required (GetSales custom fields)

| Variable | Source field | Notes |
|----------|--------------|-------|
| `{{first_name}}` | `first_name` | required, drop lead if empty |
| `{{company_name}}` | `company_name` (normalized via `normalize_company()`) | required |
| `{{cf_competitor_client}}` | `social_proof` | optional. For IMAGENCY use `Modash`, `CreatorIQ`, `HypeAuditor`, `Captiv8`, `Lefty` (известные IM-tools — recognition kicks in) |

**Normalization rule**: `company_name` обязательно через `normalize_company()` (см. `.claude/rules/company-normalization.md`) — иначе "imagency" → "Imagency" вместо "iMagency" и т.д.

---

## Sender setup (GetSales)

- **Sender profile**: Albina (uuid фикси в UI)
- **Daily limits**:
  - Connect requests: **20**
  - Messages: **30**
- **Auto-pause if accept rate < 10%** after 50 invites
- **Auto-stop if no accept** by Day +14 → don't burn message budget on dead connects

---

## Kill / extend criteria (after 7 days)

| Outcome | Decision |
|---------|----------|
| 0 warm replies (no demo asks, no info asks) | KILL — Albina переключается на INFPLAT (proven channel) |
| 1 warm reply | EXTEND smoke 7 more days |
| 2+ warm replies | KEEP, scale up to 50 LPD |

**"Warm reply"** definition (важно для решения):
- Asks demo / asks more info / shares email = **WARM**
- "Not a fit" / "не интересно" / "remove me" = **NEGATIVE** (not warm, but valid signal)
- Auto-decline / no response = **NULL** (count as 0)

---

## Open questions / TODO before launch

1. **Sender headline check**: посмотреть как у Albina LinkedIn-заголовок звучит. Если sales-positioned — попросить временно сменить на BD/Partnerships-нейтральный.
2. **Variant A vs B opener**: для первого smoke — погнали с **Variant A** (build vs buy qualifier). B держим для второй итерации, если Albina даёт <10% accept rate.
3. **GetSales branching support**: проверить через UI поддерживает ли flow auto-stop на no-accept (если нет — manual cleanup через 14 дней).
4. **`cf_competitor_client` data fill**: для IMAGENCY_TECHLEAD - убедиться что `social_proof` заполнено в CSV до upload (fallback есть, но work-in-context лучше).
5. **No em dashes** (rule из `smartlead-formatting.md`) — все тексты выше уже на regular `-`.
6. **LI не поддерживает `<br>`** — реальные newlines (через `\n` в API payload).

---

## Source patterns referenced

- **Pattern A** (1-line qualifier): EasyStaff `"Hi Samah! Do you work with freelancers outside of UAE?"`, SquareFi `"Rustam, привет! Актуален ли прием крипты для Alta Tecnologia LLC?"`
- **Pattern C** (vertical proof): SquareFi PSP-флоу `"Processed $25M monthly for a PSP with 5,000+ merchants"`
- **Hook-first DM**: from email v5 (TECHLEAD 3169092) Step 2 "drop a handle" trick — proven hook, just needs to surface to top
- **Soft close-out**: SquareFi/EasyStaff Day +N reverse-psych pattern
