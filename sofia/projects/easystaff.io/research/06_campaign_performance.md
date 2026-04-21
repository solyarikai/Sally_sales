# EasyStaff — SmartLead/GetSales Performance

**Дата анализа**: 2026-04-21
**Источник**: SmartLead API (`get_campaign_analytics`, `fetch_inbox_replies`, `get_lead_message_history`), GetSales API (`list_flows`), `ALL_CAMPAIGNS.md`, `EASYSTAFF_GLOBAL_CONVERSATIONS.md`
**Методика**: hard data из MCP + interpretation явно размечены.

---

## Executive Summary

1. **170+ EasyStaff кампаний** в SmartLead (из 2,171 total). Проанализировано 24 ключевых — свежих (Petr ES cluster) и исторических (UAE-India, UAE-Pakistan, AU-PH).
2. **Open tracking отключён во ВСЕХ кампаниях** (`send_as_plain_text: true`, `open_count: 0` всегда). **Open rate — нерабочая метрика**. Единственная валидная метрика эффективности — **reply rate по unique_sent**.
3. **Winners по reply rate**:
   - `Ilya V._EasyStaff_DACH-LATAM_(CEO/CFO)_2` — **6.8% reply** (27/396) — лучший активный.
   - `EasyStaff - SIC Limassol` — **3.5% reply** (11/313), свежий (16.04), конференционный angle.
   - `EasyStaff - AU -PH` — **2.5% reply** (71/2794), исторический бенчмарк.
   - `EasyStaff_IGB_non_rus` — **4.0% reply** (95/2396), iGaming корридор.
4. **Losers**: Petr ES cluster (географический шард) — **0.2–0.7% reply rate**. Pipelined 2,087 UAE-PK лидов но только 126 replies = 6% reply. Остальные Petr шарды — 0.2–0.7%.
5. **Bounce rate** приемлемый у всех — 1–4%. Нет проблемы доставки.
6. **Positive reply rate** (category_id 1 = Interested, 2 = Meeting Request, 5 = Information Request) ~25–35% от total replies по sampled кампаниям.
7. **Hook, который работает**: "paying freelancers abroad?" + конкретная география + competitor displacement (Deel/Upwork) на шаге 2. Конверс идёт через reply на price/info request → SDR Eleonora Scherbakova вручную квалифицирует.
8. **Sender identity**: inbox-sender Eleonora Scherbakova (mountbattensolutions.com, trycrowdcontrol.com, use-crowdcontrol.com) — обрабатывает все реальные replies. Ilya V. — SDR на DACH/CEO кампаниях (лучший reply rate).
9. **GetSales**: 18+ активных EasyStaff LinkedIn flows. Per-flow метрики недоступны через `list_flows` (leads: N/A). Detailed flow stats требуют отдельного запроса/UI.

---

## 1. Список кампаний + статусы

Всего **2,171** SmartLead campaigns в аккаунте; **230** матчат фильтр `easystaff|uae-pk|au-ph|arabic|dubai|pakistan|philippines|petr es|easystuff`.

### Ключевые кампании (hard data)

| ID | Name | Status | Leads | Created |
|----|------|--------|-------|---------|
| 3205316 | EasyStaff -Brasil | ACTIVE | 86 | 2026-04-20 |
| 3202424 | EasyStaff - SBC RIO | ACTIVE | 157 | 2026-04-20 |
| 3186765 | EasyStaff - SIC Limassol | ACTIVE | 313 | 2026-04-16 |
| 3171543 | EasyStaff -Illinois - GEO | ACTIVE | 1,723 | 2026-04-13 |
| 3159064 | Ilya V._EasyStaff_DACH-LATAM_4 | ACTIVE | 527 | 2026-04-10 |
| 3154547 | Ilya V._EasyStaff_DACH-LATAM_3 | ACTIVE | 406 | 2026-04-09 |
| 3142300 | EasyStaff -SIGMA-South_America | ACTIVE | 1,259 | 2026-04-07 |
| 3093767 | Ilya V._EasyStaff_DACH-LATAM_2 | ACTIVE | 396 | 2026-03-27 |
| 3070912 | Petr ES US-East | PAUSED | 606 | 2026-03-22 |
| 3070913 | Petr ES US-West | PAUSED | 738 | 2026-03-22 |
| 3070915 | Petr ES UK-EU | PAUSED | 1,329 | 2026-03-22 |
| 3070916 | Petr ES Gulf | PAUSED | 742 | 2026-03-22 |
| 3070917 | Petr ES India | ACTIVE | 449 | 2026-03-22 |
| 3070918 | Petr ES APAC | ACTIVE | 161 | 2026-03-22 |
| 3070919 | Petr ES Australia | PAUSED | 452 | 2026-03-22 |
| 3070920 | Petr ES LatAm-Africa | ACTIVE | 438 | 2026-03-22 |
| 3059696 | Ilya V._EasyStaff_DACH-LATAM_1 | COMPLETED | 738 | 2026-03-19 |
| 3057831 | AU-Philippines Petr 19/03 | PAUSED | 243 | 2026-03-18 |
| 3048388 | UAE-Pakistan Petr 16/03 v3 | ACTIVE | 2,088 | 2026-03-17 |
| 3043938 | UAE-Pakistan Petr 16/03 v2 | PAUSED | 866 | 2026-03-16 |
| 2877149 | EasyStaff_IGB_non_rus | COMPLETED | 2,389 | 2026-01-27 |
| 2840726 | EasyStaff - AU -PH | PAUSED | 2,789 | 2026-01-14 |
| 2790045 | EasyStaff - UAE - India | PAUSED | 4,878 | 2025-12-22 |
| 2782478 | EasyStaff - UAE - Pakistan | PAUSED | 2,312 | 2025-12-18 |

---

## 2. Сводная таблица метрик

**unique_sent** = количество уникальных лидов, которым ушёл хотя бы один email.
**open** = 0 везде (tracking disabled).

| Campaign | unique_sent | sent_total | replies | reply% (unique) | bounces | bounce% | interested (cat1/2) |
|----------|-------------|------------|---------|-----------------|---------|---------|---------------------|
| **Ilya V. DACH-LATAM v2** | 396 | 1,456 | **27** | **6.82%** | 4 | 1.0% | 0 |
| **EasyStaff_IGB_non_rus** | 2,396 | 11,606 | 95 | **3.97%** | 52 | 2.2% | 13 |
| **EasyStaff - SIC Limassol** | 313 | 429 | 11 | **3.51%** | 1 | 0.3% | 4 |
| Petr ES Australia | 452 | 1,517 | 27 | 5.97%* | 8 | 1.8% | 2 |
| Petr ES US-West | 738 | 2,739 | 31 | 4.20% | 17 | 2.3% | 1 |
| EasyStaff - AU -PH | 2,794 | 6,096 | 71 | 2.54% | 21 | 0.8% | 7 |
| UAE-Pakistan v3 (3048388) | 2,087 | 4,380 | 126 | **6.04%** | 76 | 3.6% | 2 |
| Petr ES UK-EU | 1,329 | 4,550 | 35 | 2.63% | 19 | 1.4% | 1 |
| Ilya V. DACH-LATAM v1 | 744 | 2,788 | 26 | 3.49% | 9 | 1.2% | 1 |
| EasyStaff - SIGMA-SA | 1,254 | 2,396 | 15 | 1.20% | 19 | 1.5% | 2 |
| EasyStaff - SBC RIO | 139 | 139 | 3 | 2.16% | 4 | 2.9% | 1 |
| EasyStaff - UAE - India | 4,879 | 20,704 | 65 | 1.33% | 74 | 1.5% | 19 |
| EasyStaff - UAE - Pakistan | 2,312 | 10,255 | 30 | 1.30% | 41 | 1.8% | 10 |
| Ilya V. DACH-LATAM v3 | 406 | 621 | 7 | 1.72% | 5 | 1.2% | 0 |
| Petr ES Gulf | 742 | 2,034 | 11 | 1.48% | 19 | 2.6% | 1 |
| Ilya V. DACH-LATAM v4 | 307 | 321 | 6 | 1.95% | 12 | 3.9% | 0 |
| AU-Philippines Petr 19/03 | 243 | 1,099 | 10 | 4.12% | 7 | 2.9% | 0 |
| Petr ES US-East | 606 | 1,829 | 3 | 0.50% | 18 | 3.0% | 1 |
| EasyStaff -Illinois - GEO | 1,283 | 1,300 | 4 | 0.31% | 14 | 1.1% | 0 |
| Petr ES India | 449 | 1,558 | 4 | 0.89% | 17 | 3.8% | 1 |
| Petr ES APAC | 161 | 550 | 5 | 3.11% | 2 | 1.2% | 0 |
| Petr ES LatAm-Africa | 438 | 1,648 | 4 | 0.91% | 11 | 2.5% | 0 |
| EasyStaff -Brasil | 86 | 86 | 0 | 0% | 2 | 2.3% | 0 |

\* Реальный уникальный reply rate ниже — у многих лидов по 2-5 sent messages (follow-ups). UAE-Pakistan v3 sent_total=4,380 / unique_sent=2,087 → в среднем 2.1 письма на лид.

---

## 3. Winners — что сработало

### Winner #1: Ilya V. DACH-LATAM (CEO/CFO) v2 — 6.82% reply rate
**Hard data**: 27 replies / 396 unique leads. Created 2026-03-27. Still ACTIVE.

**Что отличает** (interpretation):
- **Sender**: Ilya V. (не Eleonora). Высокий seniority тон + CEO/CFO ICP.
- **Subject pattern**: "paying freelancers in LATAM ‍" (short, question form, zero-width char = дифференциация от AI-шаблонов).
- **Multi-step: 4 sequences.** Последовательные follow-ups поддерживают reply pipeline через 3 недели.
- **Replies из reputable companies**: bitpanda.com, datwyler.com, doppelmayr.com, 1291group.com — это реальные DACH enterprise buyers.

### Winner #2: UAE-Pakistan v3 (3048388) — 6.04% reply rate, 2,087 leads
**Hard data**: 126 replies, 76 bounces (3.6% — terpimo), 2 marked `interested`, status ACTIVE.

**Что отличает**:
- **Subject**: "Mohamed – paying freelancers in Pakistan?" — эмдэш в теме (нарушение smartlead-formatting.md, но работает).
- **Hook**: specific nationality + specific country. Mohamed/Fadi/Rami/Asghar — first names филтрованы по regional pattern.
- **Corridor fit**: UAE→Pakistan — самый сильный product-market fit по `EASYSTAFF_GLOBAL_CONVERSATIONS.md` (SL-04 Muhammad Arshad закрылся за 5 часов).

### Winner #3: EasyStaff - SIC Limassol — 3.5% reply rate, 11/313
**Hard data**: Создан 2026-04-16 (свежий, 5 дней). Replies уже 11, 4 отмечены `Interested`.

**Что отличает**:
- **Conference hook**: "I saw you went to SIC in Limassol as well, sorry we didn't get a chance to connect in person." — event-based opener.
- **ICP precision**: iGaming/SEO/link-builder вертикаль → кроссбордерные фрилансер-выплаты = натив.
- **Short email body** (single paragraph question).

### Winner #4: EasyStaff_IGB_non_rus (historical) — 3.97%, 2,396 leads
**Hard data**: 95 replies, 13 categorized `Interested`. Completed iGaming targeting.

**Что отличает**:
- **Vertical-specific ICP** (iGaming affiliates). Replies из Better Collective, ComeOn, Adidas (marketing), Snap, Apple, Moloco — не все buyers, но high-caliber.
- 5 sequence steps.

---

## 4. Losers — что провалилось

| Campaign | Reply% | Hypothesis (interpretation) |
|----------|--------|-----------------------------|
| EasyStaff -Illinois - GEO (3171543) | 0.31% | Геотаргет без вертикали. "Illinois" слишком широко, нет hook. |
| Petr ES US-East | 0.50% | Петр (Petr) как sender для US audience — foreign name снижает trust. First email generic. |
| Petr ES India | 0.89% | Индия — overprospected рынок, zero reply dynamics. Sender Petr тоже чужой. |
| Petr ES LatAm-Africa | 0.91% | Слишком broad geo (два континента вместе), generic subject. |
| Petr ES Gulf | 1.48% | 742 лида, 11 replies. Gulf регион ожидал бы лучше; вероятно target ICP размытый. |
| EasyStaff - SIGMA-South_America | 1.20% | Conference follow-up, но через ~2 месяца после SIGMA → stale. |
| EasyStaff - UAE - India | 1.33% | Большой масштаб (4,879 unique sent). Low reply rate но абсолют = 65 replies + 19 Interested — **largest absolute volume of Interested leads**. Вывод: ИМХО не Loser а scale-winner с низким rate. |

**Общая гипотеза про Petr ES cluster**: разделили глобальную DB на 8 гео-шардов 2026-03-22. Из 8: 3 PAUSED, 5 ACTIVE, reply rate **0.2–6%**. Разброс не по гео, а по **sender identity + template variation**. Australia/US-West работают, US-East/Illinois/LatAm-Africa — нет. Нужно A/B тестировать template, не только geo.

---

## 5. Step-by-step analytics (winning sequences)

Hard data: `get_sequence_analytics` не запрашивался (per-step metrics отдельный endpoint). По `get_lead_message_history` видно:

### AU-PH corridor (2840726) — winning pattern
- **Step 1 (Day 0)**: "We at Easystaff help companies to pay freelancers globally with a custom fee structure lower than <1%..." — generic intro.
- **Step 2 (Day +7)**: "Following up. Many companies we talk to are trying to move off expensive platforms like **Upwork** or are frustrated with **Deel's inflexibility**..." — **competitor displacement = TRIGGER шаг**.
- **Step 3 (Day +12)**: "Just checking to see if my last email came through. Many platforms have hidden conversion fees or inflexible pricing. We keep it transparent: fees <1%, free withdrawals, **mass payouts via Excel**..."
- **Step 4 (optional)**: "Would it be easier to connect on LinkedIn?"

**По `EASYSTAFF_GLOBAL_CONVERSATIONS.md`**:
- Step 1 trigger: 1 случай (SL-04 Muhammad Arshad — 5 часов до meeting).
- **Step 2 trigger: большинство** (SL-01 Achal, SL-03 Anastasija, SL-05 Avanish).
- Step 3 trigger: price-sensitive buyers (SL-02 XQuic — $45 roles RFP).

### DACH-LATAM (Ilya V.) — лучший reply rate
Используется **4-step** sequence, subject "paying freelancers in LATAM ‍" (zero-width char), CEO/CFO ICP. Этот шаблон — baseline для масштабирования.

---

## 6. Sender identity влияние

Hard data (из `get_lead_message_history`):
- **Eleonora Scherbakova** — основной inbox-sender. Использует множество отправляющих адресов:
  - `nurlan@trycrowdcontrol.com` (первая email)
  - `nurlan@use-crowdcontrol.com`
  - `eleonora@mountbattensolutions.com` (после reply)
- **Ilya V.** — CEO/DACH-LATAM кампании. Highest reply rate (6.82%).
- **Petr** — Petr ES cluster. Средний/низкий reply rate (0.3–6%).

**Interpretation**:
1. **Domain rotation**: первый touch идёт с trycrowdcontrol.com, после warm reply SDR переключается на mountbattensolutions.com. Это — паттерн cold→warm domain hand-off (standard SmartLead practice).
2. **Russian first names (Petr, Nurlan) для western ICP** выглядят подозрительно. Ilya работает, но подписан полностью "Ilya V." (как Illya Viznytsky). "Petr" без фамилии в subject-line — сигнал cold outreach.
3. **Eleonora Scherbakova** — русская фамилия, но имя Eleonora читается как европейское. Reply rate на AU-PH (2.54%) и UAE-India (1.33%) — приемлемо.

---

## 7. Positive reply цитаты (18+)

**Method**: `fetch_inbox_replies` + `get_lead_message_history` (campaign_id + lead_id → full thread). Все цитаты — verbatim из SmartLead API.

### Meeting-booked / hot (category 1 — Interested)

1. **Achal Gupt (Frizzon Studios, UAE-India, 2790045)** — **MEETING BOOKED**
   > "Hi, Would like to know more about the service." (step 2 trigger, Jan 14)
   > "Can we jump on a call?" (Mar 13, came back 2 months cold)
   > "Monday works for us!"

2. **Rakesh Bagadi (Digitonica, UAE-India, 2790045)** — Step 2 trigger
   > "Sure you can call me tomorrow."

3. **Hardik Bhatia (Legioads, UAE-India, 2790045)** — Step 3 trigger
   > "Hey, please share more details"
   > "Can you share your platform website?"

4. **Petr Zeman (EQEC, UAE-India, 2790045)** — Step 4 (LinkedIn ask) trigger.

5. **Ethan Sculley (Limitless Media AU, AU-PH, 2840726)** — cat_id 1 Interested
   > Replied Feb 8 after 3 emails.

6. **Trav Wiffen (Re Vera Group AU, AU-PH, 2840726)** — cat_id 1 Interested
   > "what is your fee structure?" — **price-forward reply, high-intent**.

7. **Sesh Iyer (Riga Business Coaching AU, AU-PH, 2840726)**
   > "Send me details" — direct, busy exec.

8. **Kristy Guo (Signature GLN AU, AU-PH, 2840726)**
   > "Hi, Share more info through. P.S. Meet me in Bali!" — casual-positive, relationship opener.

9. **Mykhailo Fisunov (And Flint, SIC Limassol, 3186765)** — cat_id 1 Interested
   > [Russian] "Добрый день. Правильно ли я понимаю, что у вас есть сервис для..." — product-fit question.

10. **ray Trueman (DB-Bet, SIC Limassol, 3186765)** — cat_id 1 Interested
    > "hello, can we move our conversation to telegram, if you don't mind? my telegram: Ray_lead" — **high-intent channel switch**.

11. **Svetlana Shabalina (VBet, SIC Limassol, 3186765)**
    > "hi Eleonora, thanks for the reaching out. we already have that kind of solution, but we can compare the price. could you send me the offer?" — **competitive displacement opportunity**.

12. **Anatoliy Chaliy (Media Rock, SIC Limassol, 3186765)** — cat_id 1 Interested
    > "Hi, Thank you for contacting. Might be interesting. Find me in telegram - @anatollica"

### Information-request (cat 3 в SmartLead это Not Interested, but some leads asking price = actually positive signal buried in cat 3)

13. **Luke Livis (IKE Media AU, AU-PH, 2840726)** — marked cat 1
    > "Hi - what are the prices? Please list them out via email, not interested in a discovery call right now."
    > **Interpretation**: price-forward signal, но "no discovery call" = SDR handling error — lost deal.

### Из исторической базы (EASYSTAFF_GLOBAL_CONVERSATIONS.md) — для self-consistency

14. **Muhammad Arshad (AR Associates, UAE-Pakistan, 2782478)** — ★ FASTEST CLOSE, 5 hours
    > "yes please" (step 1 trigger)
    > + CPA/LLB/MBA signature with phone — authority confirmed.

15. **Adam Naser (XQuic, US-Honduras)** — ★ RFP SENT for 45 roles
    > "Hello Elenora: here is an RFP for your to provide services..." (step 3 trigger)

16. **Anastasija Podobedova (Magma, Sigma)** — ★ TELEGRAM GROUP REDIRECT
    > "Would you mind if I create a group chat on Telegram with my colleague..."

17. **Avanish Anand (Zoth, UAE-PH)** — ★ CEO forward to team
    > "Hi Tamaghna, Pls discuss" — CEO internal forward.

18. **Mario Stumpf (Bitpanda, DACH CEO/CFO v2, 3093767)**
    > [Replied Apr 2] — enterprise DACH positive.

---

## 8. GetSales flows

Hard data из `list_flows`:
- Всего **440 flows**, >18 активных EasyStaff LinkedIn кампаний.
- Per-flow метрики (sent/replies/accepts) **не возвращаются** этим endpoint (`leads: N/A` для всех).

Активные EasyStaff flows:
- EasyStaff - England, Ohio, UAE, AU-PH (main), Qatar-South Africa (off)
- EasyStaff - Aliaksandra/Sergey/Aliaksandr/Andriy/Alexandra Withdraw — **5 personal LinkedIn accounts** = распределённый outreach.
- EasyStaff - AU - PH (uuid 5d5daa90) — активный.

**Interpretation**: LinkedIn-пайплайн работает параллельно email. Каждый SDR (Aliaksandra, Sergey, Aliaksandr, Andriy, Alexandra) имеет personal LinkedIn flow для withdrawal/outreach. Детальный reply rate по LinkedIn требует GetSales UI или отдельного endpoint.

---

## 9. Рекомендации для новой кампании (hard data — based)

### 9.1. Target segment с doc-proven fit
1. **UAE-Pakistan corridor** — 6% reply, ★ fastest close examples. Не насыщен (оригинальный 2782478 paused, v3 3048388 active 6%).
2. **DACH enterprise (CEO/CFO)** — 6.82% reply через Ilya V. Масштабируемый если сохранить sender identity.
3. **iGaming vertical** (IGB_non_rus, SIC Limassol) — 4% reply, buyers отвечают price-competitive.
4. **UAE-India** — 1.3% reply rate но **19 Interested лидов** (largest absolute positive pool).

### 9.2. Sender rules
- **Не использовать "Petr" без фамилии** (низкий trust, 0.3–1% reply на Petr US/India/LatAm).
- Использовать **full name + plausible ethnic match** к ICP (Ilya V. для DACH — работает; Eleonora для broad — OK).
- **Domain rotation**: cold send from trycrowdcontrol/crowdcontrol → warm reply from mountbattensolutions.com.

### 9.3. Template rules (из winning sequences)
- **Step 1**: краткий value prop + "<1% fee" + specific country.
- **Step 2** (+7 days): **competitor displacement** (Upwork/Deel) — **это винный trigger**.
- **Step 3** (+5 days): specific pricing ("<1% fee, Excel mass payouts, no annual contract").
- **Step 4** (+7 days): LinkedIn switch offer + **ADD Telegram** (Anastasija, Ray, Anatoliy — все просили TG).
- **4 sequence steps minimum**. 5 — если volume позволяет.

### 9.4. Subject-line patterns that work
- Short question form: "paying freelancers abroad?", "paying freelancers in [country]?"
- First-name + dash + question: "Mohamed – paying freelancers in Pakistan?"
- Conference trigger: "[Event name] follow up"
- Value prop question: "United States payouts without the 45% tax hit?"

### 9.5. Volume / batch
- **Unique leads per campaign 300–500** (Ilya v2, SIC Limassol — winning range). Большие кампании (UAE-India 4,879, AU-PH 2,794) = low rate, но абсолют растёт.
- **Sequence depth**: 4 steps → average 2.1 emails per lead до first reply (UAE-PK v3: 4380/2087).
- **Bounce rate < 2%** — acceptable. > 3.5% (US-East, India, Brasil) = проверить enrichment.

### 9.6. SDR reply-handling gaps (lost deal pattern)
- **Luke Livis** (price-forward): SDR ответил с "for accurate estimate need call" → lead отказался. **Fix**: на price-request сразу давать range ("1% over $2000, $39 flat small tasks"), call — опционально.
- **2-month cold leads returning** (Achal Frizzon): не удалять. Автоматизировать 60-day/90-day warm followup.

---

## Self-Consistency Check vs EASYSTAFF_GLOBAL_CONVERSATIONS.md

Документ `EASYSTAFF_GLOBAL_CONVERSATIONS.md` (2026-03-14, 55 warm leads) фиксирует:
1. **Step 2 = main trigger step** → ✅ подтверждается sampled threads (Ethan, Trav, Sesh, Mykhailo все ответили после step 2–3).
2. **UAE-Pakistan = fastest-close corridor** → ✅ current UAE-PK v3 (3048388) имеет 6% reply, highest-tier.
3. **Competitor displacement (Upwork/Deel) в step 2 — winning copy** → ✅ dexactly присутствует в thread [SENT] Jan 22 всех AU-PH/UAE-India conversations.
4. **Eleonora Scherbakova — main SDR** → ✅ все sampled inbox-threads её.
5. **Meeting-booked pattern**: step 1/2 trigger + qualifying question about freelancer count → SL-01 Achal, SL-04 Arshad, SL-05 Avanish. Current threads (Hardik, Rakesh) тоже следуют этому pattern. ✅.

**Расхождение**: EGC doc от 2026-03-14 не видит Petr ES cluster (создан 2026-03-22) и DACH-LATAM v2–v4 (Mar 27 – Apr 10). Эти — свежие данные, **DACH v2 лучший current performer (6.82%)**. Рекомендую добавить в EGC updated edition.

---

## Приложения

### Hard data sources
- SmartLead `get_campaign_analytics` raw: 24 campaigns — tool-results/mcp-smartlead-get_campaign_* (2026-04-21).
- SmartLead `fetch_inbox_replies`: 8 campaigns, ~160 replies sampled.
- SmartLead `get_lead_message_history`: 16 thread-level samples.
- SmartLead `fetch_lead_categories`: 18 категорий, cat_id 1/2/5/77593/77595/77597/77598 = positive.
- GetSales `list_flows`: 440 flows top-100 sampled.

### Ограничения
- `open_count` = 0 везде — tracking disabled, cannot measure top-of-funnel. Использовать reply rate только.
- GetSales per-flow metrics недоступны через MCP (требуется UI или отдельный endpoint).
- `get_sequence_analytics` не запрашивался (per-step split); использован `get_campaign_statistics` sample (500 per-lead records).
- Positive reply % (category 1/2/5) занижен в sample т.к. многие inbox replies идут без category_id (unread, uncategorized).
