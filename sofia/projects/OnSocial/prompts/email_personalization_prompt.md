Для OnSocial я однозначно рекомендую комбинированный подход (зависит от сегмента). Продукт OnSocial — это инфраструктура (data layer), и ценность для каждого сегмента слишком разная, чтобы использовать один универсальный ледокол.

Вот что идеально сработает для этой компании с учетом триггеров из 

README.md
:

1. Для сегмента INFLUENCER_PLATFORMS (SaaS) — сработает Вариант 2 («Повод через фичи/масштабирование») Их триггер: они строят или масштабируют собственный продукт. Ледокол должен бить в токлауд (tech stack) или развитие фич, которые забирают ресурсы инженеров.

Пример генерации: "Saw that you're currently expanding the discovery features for {Company Name}'s marketplace. Most teams doing this spend months building and maintaining their own creator scrapers..."
2. Для сегмента DIGITAL_AGENCIES (Агентства) — сработает Вариант 1 («Наблюдение за нишей клиентов») Их триггер: ведут кампании масштабно, ищут готовую инфраструктуру (white-label). Они продают свою экспертизу клиентам. Повод должен цепляться за типы брендов, с которыми они работают.

Пример генерации: "Noticed {Company Name} handles a lot of influencer campaigns in the FMCG and Beauty space. Scaling campaigns across multiple clients often means wasted hours on manual creator research..."
3. Для сегмента BRANDS_INHOUSE (Бренды) — сработает Вариант 3 («Интеграция в Value Proposition») Их триггер: тратят бюджет вслепую, хотят видеть пересечение аудиторий. Здесь нужна максимальная прямолинейность из письма-эталона.

Пример генерации: "Since {Company Name} is actively targeting Gen Z on TikTok for your new activewear line, picking creators based just on follower count often leads to mismatched audiences..."
Как я предлагаю обновить промпт (добавим этот блок)
Мы изменим инструкцию в 

email_body_prompt.md
. Вместо статичных первых предложений в шаблонах, мы заставим AI-агента каждый раз синтезировать «Personalized Icebreaker» перед основным оффером OnSocial. И также мы добавили персонализацию по имени Hi {{first_name}}, в самое начало каждого шаблона.

Вот как будет выглядеть новое правило и часть шаблона (покажите это компаньону):

markdown
## ICEBREAKER GENERATION (FIRST SENTENCE RULE)
Before inserting the main template, generate ONE highly personalized introductory sentence (icebreaker) based on the exact sector and website context:
- For INFLUENCER_PLATFORMS (SaaS): Acknowledge a specific product feature, tool, or marketplace they are building/scaling. (e.g., "Saw you're expanding the analytics engine for {Company Name}'s platform.")
- For DIGITAL_AGENCIES: Mention the specific industries or types of clients they run campaigns for. (e.g., "Noticed {Company Name} is scaling influencer campaigns for beauty and lifestyle brands.")
- For BRANDS_INHOUSE: Mention their target audience, product category, or recent launch. (e.g., "Since {Company Name} is actively marketing your activewear collection on social...")
This single sentence MUST smoothly transition into the first paragraph of the respective template below, replacing the placeholder [Insert Icebreaker Here].
---
## EMAIL TEMPLATES BY SECTOR
INFLUENCER_PLATFORMS
Hi {{first_name}},
[Insert Icebreaker Here] Most teams doing this spend months building and maintaining their own creator databases — only to end up with stale data and broken scrapers.
OnSocial gives {company name} a ready API: real-time data on all public accounts with 1,000+ followers across Instagram, TikTok, and YouTube — 27 filters, audience analytics, and white-label options included.
We power creator data for platforms processing millions of searches monthly, with pay-per-request pricing that scales with your growth.
Should we schedule 10 minutes to see how OnSocial could replace your data pipeline?
Обратите внимание: [Insert Icebreaker Here] — это плейсхолдер. Промпт удалит его и на его место бесшовно вставит сгенерированное предложение, так что готовое письмо будет читаться как один единый текст от Hi {{first_name}} до призыва к действию.