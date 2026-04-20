# OnSocial — Classify Prompt: Tier 1 Candidate Segments

Назначение: **тестовая классификация** компаний против 5 новых гипотез-сегментов, выявленных в «other» списке project 42 (OnSocial). Запускать на изолированном gathering_run, не на основном.

Tier 1 сегменты (5 штук): SOCIAL_LISTENING, REVIEW_UGC, LOYALTY_COMMUNITY, AI_CONTENT_MARKETING, CREATOR_PLATFORM.

---

## Promt text (paste as `prompt_text` in analysis_run)

```
You classify companies as potential customers of OnSocial — a B2B API that provides creator/influencer data for Instagram, TikTok, and YouTube (audience demographics, engagement analytics, fake follower detection, creator search, credibility scoring).

This prompt tests FIVE CANDIDATE SEGMENTS — companies whose core product is adjacent to creator economy and might need creator data even though they are not traditional influencer platforms / agencies / affiliate networks.

Companies that qualify here have a SaaS product, platform, or scaled service where creator/audience data would directly improve what they sell to their own customers.

== STEP 1: INSTANT DISQUALIFIERS ==
- website_content is EMPTY and no description -> OTHER | No website data
- Domain is parked / for sale / dead / holding page -> OTHER | Domain inactive
- <5 employees -> OTHER | Too small
- Individual creator / personal brand / coach / freelancer (the company IS the creator, not a tool for creators) -> OTHER | Individual creator
- Pure services firm without a product (dev shop, design studio, consulting, PR agency) -> OTHER | Services, no product

If none triggered -> continue to Step 2.

== STEP 2: SEGMENTS ==

SOCIAL_LISTENING
  Platforms that monitor, measure, and analyze social media conversations, sentiment, brand mentions, earned media, or audience discussions at scale. Typically sold to brands, PR teams, or market researchers.
  KEY TEST: the core product ingests public social data (posts, comments, mentions) and produces analytics/insights/reports for brands. Creator attribution, influencer-of-mention tracking, and UGC monitoring are common use cases.
  NOT THIS: generic web analytics, CRM analytics, or customer support tools that happen to read social inbox.
  Why they need OnSocial: enrich mention data with creator-level signals (audience quality, reach, credibility) to go from "who said it" to "does their audience matter".

REVIEW_UGC
  Platforms that collect, display, manage, or syndicate customer reviews, ratings, Q&A, photos/videos from buyers, or any user-generated content for ecommerce/brands. Includes reviews widgets, reputation management SaaS, UGC galleries, product Q&A, testimonial platforms.
  KEY TEST: the core product is a pipeline for UGC — brands use it to collect/moderate/display content from their customers or fans.
  NOT THIS: generic survey tools, NPS trackers, or helpdesk products where reviews are a side feature.
  Why they need OnSocial: identify which reviewers/UGC creators have real audiences vs bots; prioritize high-reach UGC; detect fake reviews via creator authenticity signals.

LOYALTY_COMMUNITY
  Platforms running loyalty programs, brand ambassador programs, referral/rewards programs, creator affiliate programs for brands, branded community platforms, or advocacy/engagement platforms that reward members for content or referrals.
  KEY TEST: the core product enables brands to reward / activate / retain customers-as-advocates, often including creator/ambassador tiers or UGC incentives.
  NOT THIS: generic punch-card loyalty (coffee shop apps), B2B partner portals without creator element, pure rewards marketplaces for consumers.
  Why they need OnSocial: qualify applicants to ambassador programs (real reach vs fake), match members to campaigns by audience fit, detect gaming / fraud.

AI_CONTENT_MARKETING
  AI-first SaaS products for content creation, social content generation, brand intelligence, creator style cloning, marketing copy/image/video AI, AI-driven personalization or market research for marketers.
  KEY TEST: the product is an AI/ML platform sold to marketing teams or creators, where creator data (style, audience reaction, engagement patterns) would materially improve output quality or personalization.
  NOT THIS: generic AI dev tools (vector DBs, LLM APIs), AI chatbots for customer support, computer vision for manufacturing, AI agencies without a product.
  Why they need OnSocial: ground-truth creator data for style/audience modeling, fine-tuning datasets, attribution of AI-generated content performance, fraud detection on AI-amplified engagement.

CREATOR_PLATFORM
  Platforms built FOR creators as end-users: newsletter growth tools, podcast hosting & analytics, monetization platforms for creators (subscriptions, tips, paid communities), creator CMS/workflow tools, creator education platforms at scale, creator IP/rights management.
  KEY TEST: the product's main users ARE creators themselves, and the business model depends on creator success (they pay, churn, or grow based on audience).
  NOT THIS: individual creator websites, Patreon-alternative for a single creator, agency booking platforms (those are IM_FIRST adjacent, not CREATOR_PLATFORM), pure social networks without creator monetization focus.
  Why they need OnSocial: help their creators understand / grow audience, verify audience quality to unlock higher monetization tiers, cross-platform analytics for creators who publish everywhere.

OTHER
  Everything that does not fit the five candidate segments above. Includes: consumer brands / DTC, generic SaaS, adtech without creator relevance, web3/crypto platforms without creator focus, gambling / betting / esports betting, event organizers, media publishers selling ads (not creator data), generic digital agencies, staffing, consulting, education for non-creators, HR tech, fintech, logistics, offline businesses.

== CONFLICT RESOLUTION ==

If a company could fit two candidate segments:
- SOCIAL_LISTENING vs REVIEW_UGC -> if the product is primarily ECOMMERCE reviews on a brand's own site, choose REVIEW_UGC. If it monitors social media OFF-site (Twitter/Reddit/TikTok), choose SOCIAL_LISTENING.
- LOYALTY_COMMUNITY vs REVIEW_UGC -> if customers GET REWARDED for content/referrals, choose LOYALTY_COMMUNITY. If the core is review collection without reward mechanics, REVIEW_UGC.
- AI_CONTENT_MARKETING vs CREATOR_PLATFORM -> if end user is a MARKETER at a brand, AI_CONTENT_MARKETING. If end user is a CREATOR themselves, CREATOR_PLATFORM.
- CREATOR_PLATFORM vs INFLUENCER_PLATFORMS (legacy) -> this prompt does not classify to INFLUENCER_PLATFORMS. If a company is a creator discovery tool sold to BRANDS, mark OTHER (already covered by existing ICP).

If a company fits one of the legacy ICP segments (SOCIAL_COMMERCE / INFLUENCER_PLATFORMS / AFFILIATE_PERFORMANCE / IM_FIRST_AGENCIES) — classify as OTHER and note the legacy segment in reasoning. This prompt's job is to test NEW hypotheses, not re-classify the known ICP.

== CALIBRATION ==

Be STRICT, not inclusive. Default to OTHER when in doubt — we are validating hypotheses, so we want high precision on small matched lists rather than large noisy buckets.

Examples of clear fits:
- Neticle, Canvs.ai, Brandwatch -> SOCIAL_LISTENING
- Judge.me, Stamped.io, Yotpo, Bazaarvoice -> REVIEW_UGC
- SparkLoop (newsletter growth), Buzzsprout (podcast host), Podia (creator courses) -> CREATOR_PLATFORM
- Rediem, Rewardchain, Social Snowball (ambassador/affiliate for creators) -> LOYALTY_COMMUNITY
- Jasper, Copy.ai when they pivot to creator-style content, Novaview.ai (brand intelligence) -> AI_CONTENT_MARKETING
```

---

## Как запускать

1. Создать новый `gathering_run` на Hetzner через backend API (или pipeline `gather` step) — **не** переклассифицировать существующие runs, это затрёт текущие verdicts.
2. Прогнать через `/runs/{id}/analyze` с этим `prompt_text`.
3. После классификации — выгрузить таргеты по каждому новому сегменту отдельно и вручную провалидировать 10-20 компаний на каждый сегмент (ICP sanity check).
4. Если precision >= 70% на сегменте → идти в `/apollo-segment-builder` для него.
5. Если precision < 50% → уточнить определение сегмента или выкинуть гипотезу.

## Примечания

- Backend сам оборачивает промт JSON-инструкцией (см. `.claude/rules/classify-prompt-format.md`) — здесь её НЕ прописывал.
- В промте дублируется часть дисквалификаторов из основного OnSocial prompt — это ОК, они нужны и для тестовой классификации.
- `OTHER` здесь шире, чем в основном prompt: включает legacy ICP сегменты, чтобы не пересекаться с ними.
