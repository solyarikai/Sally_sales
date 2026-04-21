# EasyStaff — Финальная стратегия outreach (после Red Team)

_Дата: 2026-04-21. Свод 9 агентов (Wave 1-3). Учтены корректировки A9 Red Team._

---

## Executive Summary (TL;DR)

**EasyStaff** — B2B платёжная платформа для международных выплат фрилансерам/remote teams. 3 продукта (Payroll/Invoice/Connect), €150M+ transferred, 4500 клиентов, CIS-origin distributed teams — real ICP.

**Главный инсайт из 500K+ существующих материалов:** real ICP ≠ заявленному. Сайт продаёт founder/CEO-тоном, отвечают Finance Ops / Accountant / Payroll Manager (n=2 named, всё ещё требует валидации). Gulf Service/Agency = 50% warm replies исторически, но на сайте не подсвечен.

**Рабочие сегменты (priority):**
1. **Gulf Service/Agency** — 50% warm replies (history), требует doc-pack. Move к Week-0 gate.
2. **DACH SMB** — 6.82% reply на n=396 (A9 flag: n=1 кампания, не winner-pattern, нужен 2×400 pilot).
3. **iGaming/Affiliate** — highest ACV, conference-triggered.
4. **CIS-origin Distributed** — reverse-engineered из lookalike, kill gate <2%.

**Критический блокер:** pricing message split (`<1%` vs `3-5%/$42`) в одной sequence — **пофиксить до launch**.

---

## 1. ICP (triangulated across 6 sources)

| Dimension | Заявленный (site) | Реальный (replies) | Lookalike (clients) |
|-----------|-------------------|---------------------|----------------------|
| Buyer role | Founder/CEO | Finance Ops/Accountant (n=2 ⚠️) | Finance Manager/COO |
| Size | SMB/mid-market | 11-50 emp (52% warm) | 10-150 FTE |
| Geo | Global "ru-CIS voice" | Gulf dominates (50%) | UAE/CY/EE/NL/PT/US/UK |
| Industry | Agencies, studios, gamedev | Service/digital/creative agency | CIS-origin distributed |

**Real ICP:** service/agency/digital businesses, 11-50 emp, платящие в диверсифицированные страны (не geo-corridor). Buyer — Finance Ops / Accountant / Payroll Manager / COO (DACH — единственное исключение с C-level).

**Anti-ICP** (Apollo exclude): Gusto/ADP users, in-house payroll 200+, EOR employees, РФ/РБ-incorporated, enterprise 500+, government (NEOM), DolarApp LATAM, Web3-native, solo freelancers, highly-regulated EU finance, influencer platforms (semantic OnSocial clash), PR/media, interior design.

---

## 2. Rollout Plan (corrected after Red Team)

### Week 0 (до launch — блокеры)
- [ ] Собрать **Gulf doc-pack**: trade licence EasyStaff UAB, Malta entity, VAT cert, sample B2B contract, case studies (YallaHub/Proxeet/Changer Club), ISO если есть. Без этого Gulf не запускать.
- [ ] **SmartLead deliverability audit**: bounce rate, spam triggers, rotation health на 48 inbox-ах. Check trycrowdcontrol + mountbattensolutions domains.
- [ ] **Pricing alignment**: выбрать ONE frame через всю sequence. Либо "transaction-based €39" либо "3-5% volume-tiered". Не мешать.
- [ ] **Sender identity fix**: все "one-name" Petr → Petr Korolyov (full name). A6 показал +1 fullname = +3-5× reply.

### Week 1-2: Gulf Service/Agency (priority 1)
- Apollo filter: digital/creative/marketing/branding agency, 11-50 emp, UAE/Saudi/Qatar/Limassol HQ, titles Finance Manager/Accountant/Ops/COO
- Volume: 800 leads, 2 batches × 400
- Sender: Eleonora (proven on Gulf) — но проверить bandwidth
- Hook: "one invoice, one contract" + doc-pack triggered reply playbook
- Target: 3-5% reply, 8-10 meetings

### Week 2-3: DACH SMB (priority 2, pilot)
- **A9 correction:** НЕ treat DACH как winner. n=1 кампания, 0 closed meetings. Run 2×400 pilot, measure **meetings-booked**, не replies
- Apollo: DACH SMB hiring EE/LatAm contractors, C-level OK здесь (Ilya V. pattern)
- Sender: Ilya Viznytsky (full name!)
- Target: re-validate 5-7% → если <3% после 2 batch → retune

### Week 3-4: iGaming/Affiliate (priority 3)
- Conference-triggered
- Telegram switch на Step 4
- Highest ACV potential
- Volume: 300 leads

### Week 5+: CIS-origin Distributed (priority 4, pilot)
- **A9 correction:** reverse-engineered, not validated. Pilot 300 leads, kill gate <2%
- Sender: Arina Kozlova

---

## 3. Sequence Architecture (4-step, proven from A6 winners)

| Step | Цель | Hook | Delay |
|------|------|------|-------|
| 1 | Intro + problem framing | "One invoice, one payment" + persona-relevant pain | 0 |
| 2 | **Competitor displacement** (31% warm replies!) | "Alternative to Deel/Payoneer/Upwork for your case" | 3d |
| 3 | Social proof | YallaHub/Proxeet/Changer Club case | 4d |
| 4 | Channel switch | "Sent from iPhone" + Telegram option (31% warm!) | 4d |

**Не делать**: 5+ follow-ups без new value, текстовые слоты вместо calendar, em-dashes в body, missing Telegram.

---

## 4. Top-5 Risks (Red Team)

| # | Риск | Mitigation | Owner |
|---|------|-----------|-------|
| 1 | DACH 6.82% — n=1, not replicable | 2×400 pilot, gate on meetings | SDR |
| 2 | Gulf doc-pack not ready | Week-0 gate, не launch Gulf без pack | Ops |
| 3 | Eleonora bandwidth bottleneck (3 identities) | Split to Marina/Arina на Gulf-LI + CIS | PM |
| 4 | Pricing contradiction `<1%` vs `3-5%` | Pick ONE before launch | Copy |
| 5 | SmartLead infra spam trigger | Week-0 audit 48 inboxes | Deliv |

**Системные gaps A9 подсветил:**
- **Payoneer-refugee pool** = single Trustpilot source, но используется как primary hook. Validate or downgrade.
- **RU-связь EasyStaff** для US/DACH procurement — никто не обсуждал. Legal/sanctions exposure.
- **Survivorship bias**: 2 winners из 170 кампаний — base rate 1.2%. Новая кампания ≠ winner by default.

---

## 5. KPI Framework

**Leading (week 1-2):**
- Bounce rate <2%
- Delivery ≥95%
- Reply rate per segment (target per segment above)

**Lagging (week 4-8):**
- Meetings booked (primary success metric — НЕ replies)
- Positive reply % (Interested / Info / Meeting)
- Revenue per lead (iGaming will win on this)

**Kill gates:**
- Segment reply <2% after 2 batches (×400) → pause & retune
- Bounce >5% → deliverability audit
- Eleonora inbox burnout signal → identity split

---

## 6. Expected ROI (4 weeks, conservative)

При успешном rollout (Red Team пессимизм учтён):
- Sent: ~1900 leads (Gulf 800 + DACH 800 + iGaming 300)
- Replies: ~60-90
- Positive replies: ~12-18
- Meetings booked: **~15 meetings** (down from A8 20 — A9 correction на DACH n=1)
- First deals: 2-3, ACV $5-10K/год

Week 8 at scale: ~4300 sent → ~30-40 meetings → 5-10 deals. iGaming ACV выиграет по revenue-per-lead.

---

## 7. Files

- `01_existing_materials_insights.md` — 500K materials mining (A1)
- `02_site_positioning.md` — site deep-dive, EN vs RU delta (A2)
- `03_competitors_market.md` — competitor map (A3)
- `04_client_cases.md` — YallaHub/Proxeet/Changer Club analysis (A4)
- `05_voice_of_customer.md` — Reddit/HN/Trustpilot VoC (A5)
- `06_campaign_performance.md` — SmartLead hard data (A6)
- `07_icp_pains_journey.md` — triangulated ICP synthesis (A7)
- `08_outreach_strategy.md` — ready-to-execute plan (A8)
- `09_red_team.md` — adversarial review (A9)

---

## 8. Next Actions (конкретно)

1. **Фиксануть блокеры Week 0** (pricing, doc-pack, sender names, deliverability audit)
2. **Gulf launch** Week 1 — 400-lead batch #1
3. **DACH pilot** Week 2-3 — 2×400 с meetings-as-KPI, не replies
4. **Retro Week 4** — решить какие сегменты скейлить, какие kill
5. **Validate gap claims** (Payoneer-refugee pool, RU-sanctions exposure) параллельно
