# OnSocial — Секвенсы v2 (3 сегмента × 3 касания)

> Дата: 2026-03-13
> Основа: JTBD-анализ + шаблоны из Outreach Full Guide + данные по ответам

---

## JTBD по сегментам

**INFLUENCER_PLATFORMS (SaaS)**

1. Build and maintain a reliable creator database without spending months on scraping infrastructure
2. Deliver real-time audience demographics and fraud detection to platform users
3. Ship new data features (audience overlap, credibility scoring) faster than competitors
4. Scale data coverage across Instagram, TikTok, and YouTube without growing the engineering team

**DIGITAL_AGENCIES**

1. Find the right creators for client campaigns without hours of manual research
2. Present audience analytics and credibility data to clients under the agency's own brand
3. Run multi-platform campaigns (IG, TikTok, YouTube) from one data source
4. Reduce time-to-proposal by having creator data ready before the pitch

**BRANDS_INHOUSE**

1. Verify that a creator's real audience matches the brand's target buyer before committing budget
2. Compare audience overlap between shortlisted creators to avoid paying for the same eyeballs twice
3. Identify high-credibility creators (real followers, not bots) without relying on vanity metrics
4. Scale creator discovery beyond the usual 50 creators the team already knows

---

## Сегмент 1: INFLUENCER_PLATFORMS

### Email 1 — Первое касание

Subject: {{first_name}}, quick question about your creator data

How are you currently sourcing and maintaining creator data for {{company_name}}'s platform?

Most teams we talk to spend 3-6 months building scrapers — then another engineer just to keep them running. One API change from Instagram and the whole pipeline breaks.

OnSocial gives you a ready data layer: 450M+ profiles across Instagram, TikTok, and YouTube. Audience demographics, credibility scoring, fraud signals, creator overlap — all via one API endpoint, real-time.

Your team ships features. We handle the data.

Would you be open to a 15-minute call to see how this fits into {{company_name}}'s stack?

### Email 2 — Follow-up

Subject: Re: {{first_name}}, quick question about your creator data

Quick note on integration speed.

Most platforms we work with go live in days, not months. One endpoint, real-time data — your UI wraps it, your clients see it as your feature.

Think of it as adding a full data engineering team to your product without a single hire.

Open to a 15-minute walkthrough of the actual API output?

### Email 3 — Финальный follow-up

Subject: Re: {{first_name}}, quick question about your creator data

One last thought on creator data infrastructure.

We solve the 2 problems where most in-house pipelines fail: data freshness (our profiles update in real-time vs. weekly/monthly scrapes) and coverage gaps (450M+ profiles across 3 platforms vs. partial databases).

If either sounds familiar, worth a quick chat?

---

## Сегмент 2: DIGITAL_AGENCIES

### Email 1 — Первое касание

Subject: {{first_name}}, how does {{company_name}} find creators for clients?

How are you currently handling creator research for {{company_name}}'s client campaigns?

Most agencies we talk to spend 5-10 hours per campaign on manual creator sourcing — scrolling hashtags, checking profiles one by one, guessing at audience fit.

OnSocial gives {{company_name}} instant access to 450M+ creator profiles with audience demographics, engagement data, and credibility scores. 27 filters, white-label ready — your clients see it as your tool.

Would you be open to a 15-minute call to see how this fits into {{company_name}}'s workflow?

### Email 2 — Follow-up

Subject: Re: {{first_name}}, how does {{company_name}} find creators for clients?

Quick note on what agencies use most.

Two things we hear from agencies running 10+ campaigns at a time: white-label access (clients see your brand, not ours) and audience overlap analysis (so you don't pitch 3 creators who share 60% of the same followers).

Agencies using OnSocial cut creator research time by 70% and catch audience overlap issues before the brief goes out.

Open to a 15-minute walkthrough with your team?

### Email 3 — Финальный follow-up

Subject: Re: {{first_name}}, how does {{company_name}} find creators for clients?

One last thought on creator sourcing for agencies.

We solve the 2 problems that slow campaigns down: research time (27 filters vs. manual scrolling) and audience guesswork (real demographics by city, age, gender — not just follower count).

If either sounds familiar, worth a quick chat?

---

## Сегмент 3: BRANDS_INHOUSE

### Email 1 — Первое касание

Subject: {{first_name}}, quick question about creator vetting at {{company_name}}

How are you currently verifying that a creator's audience actually matches {{company_name}}'s target buyer?

Most brand teams we talk to pick creators based on follower count and content style — then find out post-campaign that 40% of the audience was in the wrong country or age group.

OnSocial shows the full picture before you spend a dollar: real audience demographics, interests, credibility breakdown, and overlap analysis across Instagram, TikTok, and YouTube. 450M+ profiles, all public creators with 1,000+ followers.

Would you be open to a 15-minute call to see how this works for {{company_name}}'s campaigns?

### Email 2 — Follow-up

Subject: Re: {{first_name}}, quick question about creator vetting at {{company_name}}

Quick note on audience verification.

For every creator, you see: real vs. fake follower breakdown, audience split by country/city/age/gender, brand affinities, and overlap with other creators on your shortlist.

Brands using OnSocial identify the right creators 5x faster and reduce wasted spend on mismatched audiences.

Open to a 15-minute walkthrough with real data from your niche?

### Email 3 — Финальный follow-up

Subject: Re: {{first_name}}, quick question about creator vetting at {{company_name}}

One last thought on creator selection.

We solve the 2 problems where most influencer spend gets wasted: audience mismatch (real demographics vs. assumptions) and creator overlap (paying 3 creators who share 60% of the same followers).

If either sounds familiar, worth a quick chat?

---

## Заметки по A/B-тестированию

Рекомендация: для каждого сегмента создать **вариант B** с другой темой первого письма. Менять только одну вещь (subject line).

**Варианты B тем:**

- INFLUENCER_PLATFORMS: `Creator data API for {{company_name}}`
- DIGITAL_AGENCIES: `White-label creator data for {{company_name}}`
- BRANDS_INHOUSE: `See who really follows your creators, {{first_name}}`

---

## Ключевые отличия от TEST A/B (предыдущая версия)


|                    | TEST A/B                                                | v2                                                      |
| ------------------ | ------------------------------------------------------- | ------------------------------------------------------- |
| Сегменты           | 1 (всё вместе)                                          | 3 отдельных                                             |
| Касания            | 4                                                       | 3                                                       |
| Структура          | Фичи → Фичи → Техника → Breakup                         | JTBD-вопрос → Value + proof → Конкурентное преимущество |
| Первое предложение | "We provide creator and audience data via API" (о себе) | Вопрос о их текущем процессе (о них)                    |
| CTA                | "Who handles product/data partnerships?"                | "15-min call to see how this fits"                      |
| Breakup touch      | Да ("are you the right person?")                        | Нет (3 касания, потом LinkedIn)                         |


