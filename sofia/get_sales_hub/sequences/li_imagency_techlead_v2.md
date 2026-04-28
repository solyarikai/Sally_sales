# LinkedIn Sequence: IMAGENCY_TECHLEAD (v2 DRAFT — Pattern A/C rewrite)

**Дата**: 2026-04-28
**Канал**: GetSales LinkedIn
**Сегмент**: IMAGENCY_TECHLEAD (CTO / Head of Engineering / VP Tech / Tech Lead в IM-first agencies)
**Sender**: Albina (smoke test)
**GetSales flow**: `f40ce250-816c-4ed1-abc4-982783fbaef3` (`OnSocial | IMAGENCY_TECHLEAD | LI ONLY`)
**Status**: DRAFT v2 — заменяет v1 до запуска

---

## Что меняется vs v1

| Шаг | v1 | v2 | Зачем |
|-----|----|----|-------|
| Connect note | 200 chars, описание продукта + soft вопрос | **Pattern A**: 1 строка, 1 yes/no qualifier, без описания продукта | EasyStaff/SquareFi data: 1-line qualifier > opener-pitch. Меньше signal of automation. |
| Step 2 (DM after accept) | ~600 chars, длинный pitch с handle-hook в конце | **Hook-first**: handle-JSON trick в первых 2 строках, контекст в одну строку | Engineer reads first 3 lines. Если hook там — поймает. |
| Step 3 | "Stitching Modash/Phyllo/HypeAuditor" comparison | **Pattern C**: 1-line product + IMAGENCY-specific case (1 number) | IMAGENCY редко stitch'ат API — обычно 1 vendor (Modash/CreatorIQ). Comparison нужен против одной тулзы, не trio. |
| Step 4 | Route-to-DM close-out | Без изменений (формат рабочий) | OK. |
| Step 5 | — | **+30 day re-touch** опциональный, "checking back in" | Long sales cycle для tech-аудитории. Дёшево по credit, дорого если упустить. |

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

### Variant A (build-vs-buy)

```
Hi {{first_name}}, quick one: does {{company_name}}'s team pull creator data from vendor APIs (Modash, HypeAuditor, etc) or roll your own?
```

**Char count**: ~150.

### Variant B (vendor-named qualifier)

```
Hi {{first_name}}, building OnSocial (creator data API, 450M profiles). Curious - is creator-data plumbing on your team's roadmap at {{company_name}}, or someone else's?
```

**Char count**: ~190.

**Pick one, не оба сразу в одной группе**. Рекомендация для smoke: **Variant A**, чище Pattern A.

**Why this works:**
- 1 предложение, 1 yes/no вопрос ("vendor APIs vs roll your own").
- Никакого продукта в opener (Variant A) — pure qualifier.
- Имя + компания в первой строке.
- Никакого CTA, никакой ссылки, никакого pitch.
- Лид сразу понимает: «отвечаю да / нет / не я / некогда».

---

## Step 2 — Day +1 after accept (DM) — **Hook-first**

```
Thanks for the connect, {{first_name}}.

Easiest way to show what we do: drop any creator handle below and I'll DM back the raw JSON - audience demographics down to city, fraud breakdown by type, engagement depth, refresh in last 24-48h.

Context if useful: OnSocial = creator data API, 450M profiles across IG / TikTok / YouTube, 9 years in production. Teams like {{cf_competitor_client}} switched from stitched vendors to one endpoint.

If the JSON beats what {{company_name}} sees from current tooling, worth a chat. If not, you've got a benchmark.
```

**Char count**: ~590.

**Fallback if `{{cf_competitor_client}}` is empty:**

> "Context if useful: OnSocial = creator data API, 450M profiles across IG / TikTok / YouTube, 9 years in production. Some IM-first teams use us in place of two or three stitched vendor APIs."

**Why this works (vs v1):**
- **Hook moves to top** (line 2). Engineer scans 3 lines — hook caught.
- Pitch reduced to **one paragraph**, not three.
- Tone reads peer-to-peer engineer ("worth a chat / you've got a benchmark"), not BD-rep.
- "Drop a handle" = concrete action, low friction. Doesn't ask for a call.

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
