# LinkedIn Sequence: IMAGENCY_TECHLEAD (v1 DRAFT)

**Дата**: 2026-04-27
**Канал**: GetSales LinkedIn
**Сегмент**: IMAGENCY_TECHLEAD (CTO / Head of Engineering / VP Tech / Tech Lead в IM-first agencies)
**Источник**: адаптировано из SmartLead email v5 (TECHLEAD 3169092)
**Sender**: Albina
**Status**: DRAFT — на ревью

---

## Logic / why this differs from email

| Принцип | Email | LI |
|---------|-------|-----|
| Subject | yes | none (connect req + DM) |
| Length step 1 | ~600 chars | <300 chars (connect note limit) |
| Signature | "Bhaskar from OnSocial" | none — profile = signature |
| CTA | "15-min call" hard | "curious if useful" soft |
| Cadence | day 0, +3, +6 | accept → +1 → +5 → +10 |
| Tone | direct B2B | peer-to-peer engineer |

LI penalizes overt sales pitch in connect notes. First message after accept = real value drop, not pitch.

---

## Step 1 — Connect request note (Day 0)

**Char limit: 300** (LinkedIn cap is 300 for free, ~200 to be safe across plans)

```
Hi {{first_name}}, building creator data infra for IM agencies — API with 450M profiles across IG/TikTok/YouTube. Curious how {{company_name}}'s team handles it today. Open to connect?
```

**Char count**: ~200 — safe.

**Why this works:**
- No "I'd love to connect" generic — signals automation
- States what we do in 1 line (hook = creator data infra)
- Question respects their expertise (asks how *they* do it)
- No CTA, no link, no pitch

---

## Step 2 — Day +1 after accept (DM)

```
Thanks for connecting, {{first_name}}.

Quick context: we run a creator data API — 450M profiles across IG, TikTok, YouTube. Fraud breakdown by type, audience demographics down to city level, raw real-time access. 9 years in production, teams as {{cf_competitor_client}} moved to us for one endpoint instead of stitching multiple APIs.

Easier to show than tell — drop any creator handle in reply and I'll send back raw JSON: demographics, audience quality, fraud breakdown, engagement depth. If coverage or freshness beats what {{company_name}} is calling today, worth a chat. If not, you have a benchmark.
```

**Char count**: ~600 — fits comfortably in LI DM (8000 char limit).

**Hook**: "drop a handle, get JSON" — proven strongest part of email v5 Step 2. Engineers respond to concrete demos better than calls.

---

## Step 3 — Day +5 (DM)

```
{{first_name}}, two things tech teams usually compare on:

- Data freshness — we refresh every 24-48h
- Depth — 450M+ profiles across IG, TikTok, YouTube in 50+ countries at city level

If {{company_name}} is currently stitching Modash, Phyllo, HypeAuditor or similar — happy to show side-by-side on any creator you pick.
```

**Char count**: ~370.

**Why**: Tech-comparable specs, not marketing-speak. Engineer-to-engineer tone. Concrete competitor names = positions vendor space.

---

## Step 4 — Day +10 (DM, close-out)

```
{{first_name}}, last note from me.

If API vendor selection isn't your call at {{company_name}}, no worries — happy to be pointed at whoever owns it (usually CTO, Head of Data, or VP Eng).

If timing's off — will check back next quarter.
```

**Char count**: ~270.

**Why**: Soft route-to-decision-maker. No pitch. Final.

---

## Variables required (GetSales custom fields)

| Variable | Source | Notes |
|----------|--------|-------|
| `{{first_name}}` | first_name | required |
| `{{company_name}}` | company_name (normalized) | required |
| `{{cf_competitor_client}}` | social_proof | optional but recommended for Step 2; e.g. "Modash, Captiv8, Lefty" |

If `{{cf_competitor_client}}` empty, fallback Step 2 phrasing:
> "9 years in production, teams across the IM space moved to us for one endpoint instead of stitching multiple APIs."

---

## Sender setup

- Sender profile: **Albina** (uuid TBD — ты указываешь в GetSales UI)
- Daily limit: **30 LPD** (smoke test cap)
- Daily connect requests: **20** (LinkedIn safe weekly is ~100)
- Auto-pause if accept rate < 10% после 50 invites

---

## Kill / extend criteria (after 7 days)

| Outcome | Decision |
|---------|----------|
| 0 warm replies (asks demo / asks more info) | KILL — switch Albina to INFPLAT_TECHLEAD |
| 1 warm reply | EXTEND smoke 7 more days |
| 2+ warm replies | KEEP, scale up to 50 LPD |

---

## Notes / open questions

1. Albina's LI profile должен совпадать tech-tone (engineer vs sales rep) — если её профиль больше sales-positioned, может потребоваться tweak intro в Step 2.
2. `{{cf_competitor_client}}` для IMAGENCY_TECHLEAD — какие social proofs использовать? Email v5 использует `{{custom2}}`. Для агентств это могут быть HypeAuditor / Modash / Captiv8 как тулзы которые они стопроцентно знают.
3. Не использую em dashes (rule из smartlead-formatting.md), только regular `-`.
4. LI не поддерживает `<br>` — используем real newlines (через `\n` в API payload).
