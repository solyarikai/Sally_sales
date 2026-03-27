# TEAM DELTA -- Correction Round

**Дата:** 2026-03-16
**Задача:** Честный разбор собственных ошибок. Метод "buyer's internal monologue" применён к сиквенсам Ярика+Сони. Сравнение Sally vs. Yarik+Sonya vs. наших реврайтов.

---

## 1. BUYER'S INTERNAL MONOLOGUE -- сиквенсы Ярика+Сони

Читаю каждый Touch от имени покупателя, как если бы это письмо пришло мне в 9:14 утра вторника.

---

### INFPLAT HYP A -- "Stop Building Scrapers"

**Touch 1:**
> How are you currently handling creator data infrastructure at {{company_name}}?
> At OnSocial, we replace in-house scraping pipelines with a single API endpoint — 450M+ profiles across IG, TikTok, and YouTube, real-time updates.
> Would you be open to a 15-minute call to explore how this could work for {{company_name}}?

**Внутренний голос CTO:**
"О, кто-то спрашивает про мой стек, а не сразу пичит. Ок, читаю дальше... 'replace in-house scraping pipelines' -- допустим, у нас свои скраперы, это релевантно. 450M -- конкретная цифра. Но 'would you be open to a 15-minute call' -- стандартный cold email CTA. Звучит как шаблон. Ладно, посмотрим."

**Оценка:** Вступительный вопрос -- ПРАВИЛЬНЫЙ ход. CTO чувствует, что к нему обращаются как к эксперту, а не как к кошельку. Но переход от вопроса к продукту слишком резкий: "How are you handling X? We replace X." -- вопрос риторический, а не настоящий. Покупатель это чувствует. Это лучше, чем у Sally ("We provide creator data via API..."), но всё ещё ощущается как вопрос-ловушка, а не как искренний интерес.

**Touch 2:**
> Quick note on integration speed. Most platforms go live with our API in under a week. Your clients see creator demographics, fraud signals, and overlap data as your native feature.
> Think of it as adding a full data engineering team — without the headcount.
> Open to a 20-minute call next week to walk through how this fits your stack?

**Внутренний голос CTO:**
"'Under a week' -- слишком хорошо, чтобы быть правдой. Любой CTO знает, что интеграция API в продакшен -- это не 'под ключ за неделю'. Тестирование, edge cases, ошибки, миграция данных... 'Adding a full data engineering team without the headcount' -- метафора хорошая, но я слышал её от каждого второго data vendor. Ничего нового."

**Оценка:** Touch 2 добавляет новую информацию (скорость интеграции, аналогия с headcount) -- это ЛУЧШЕ, чем Sally, где Step 2 перефразирует Step 1. Но claim "under a week" вызывает скептицизм у технического покупателя. Лучше было бы: "Most platforms start pulling data within days; full production rollout depends on your architecture."

**Touch 3:**
> One last thought on creator data infrastructure.
> We solve the 2 problems where most in-house pipelines fail: data freshness (real-time vs. weekly scrapes) and coverage (3 platforms vs. partial databases).
> If either sounds familiar, worth a quick informal chat?

**Внутренний голос CTO:**
"'One last thought' -- ок, этот человек уважает мое время, это последнее письмо. 'Data freshness и coverage' -- да, это две реальные проблемы. Наши скраперы ломаются каждую неделю и покрывают только Instagram хорошо. 'If either sounds familiar' -- мягко, не давит. Может, отвечу."

**Оценка:** Это ЛУЧШИЙ Touch в серии. Конкретный, сфокусированный, мягкий CTA. "If either sounds familiar" -- это уважение, а не давление. Покупатель чувствует, что может ответить без обязательств.

---

### INFPLAT HYP B -- "Ship Features Faster"

**Touch 1:**
> How long does it take {{company_name}} to ship a new analytics feature — audience demographics, fraud detection, creator overlap?
> At OnSocial, we provide that entire data layer via API. Teams ship the same features in days, not months.
> Worth a 15-min walkthrough? Here's my calendar: {{calendar_link}}

**Внутренний голос VP Product:**
"Вопрос попал в точку. Мы 4 месяца пилим audience demographics, и до сих пор не закончили. 'Days, not months' -- хочется верить, но... это sales-язык. Тем не менее, вопрос заставил меня ЗАДУМАТЬСЯ о нашем time-to-ship. Это уже больше, чем 95% холодных писем."

**Оценка:** Сильный opener. Вопрос касается БОЛИ, а не функционала. VP Product не думает "мне нужны 450M profiles" -- он думает "почему мы 4 месяца не можем закрыть тикет по fraud detection". Этот Touch попадает в эту мысль. Calendar link в первом письме -- рискованно (слишком прямой), но для технического сегмента, где люди ценят прямоту, может сработать.

**Touch 2:**
> Quick note on what the API output looks like.
> One endpoint returns credibility scoring, audience demographics by city, fraud signals, brand affinities, and creator overlap. All real-time, all white-label ready.
> Easiest to show live — here's my calendar: {{calendar_link}}

**Внутренний голос VP Product:**
"Это ответ на мой follow-up вопрос, даже если я его не задавал. 'What does the output look like?' -- именно это я бы спросил. 'One endpoint' -- звучит чисто. Но 'easiest to show live' -- я ещё не решил, хочу ли я звонок. Пришлите мне документацию API, я сам посмотрю."

**Оценка:** Хороший ход -- предвосхитить технический вопрос. Но CTA повторяется (calendar link снова). Для технического покупателя здесь уместнее: "Here's the API documentation: [link]. If you want to see it live, I'm around this week."

**Touch 3:**
> One last thought on data features.
> We solve the 2 problems slowing platform teams: build time (days vs. months per feature) and data coverage (3 platforms, 450M+ profiles, real-time).
> 15 min is all it takes to see if this fits. {{calendar_link}}

**Внутренний голос VP Product:**
"Опять '2 problems'. Паттерн. Все три письма закончились calendar link. Это campaign, не разговор. Проигнорирую."

**Оценка:** Touch 3 слабее Touch 3 из HYP A. "One last thought" + calendar link в третий раз = ощущение автоматизации. "If either sounds familiar" из HYP A значительно мягче, чем "15 min is all it takes".

---

### IMAGENCY HYP A -- "Cut Research Time"

**Touch 1:**
> How many hours does your team spend sourcing creators per campaign at {{company_name}}?
> At OnSocial, we cut that to under 2 hours — 27 filters, audience demographics, credibility scores, all white-label ready. 450M+ profiles across IG, TikTok, YouTube.
> Would you be open to a 15-minute call to walk through how this works?

**Внутренний голос CEO агентства:**
"Sourcing creators? Мы используем [Modash/HypeAuditor/CreatorIQ]. Уже работает нормально. 'Under 2 hours' -- ну, у нас уходит час, мы не понимаем, зачем менять. '27 filters' -- это описание функционала, мне не интересно сколько у вас фильтров, мне интересно находят ли они правильных creators."

**Оценка:** Вопрос правильный по форме, но НЕ попадает в реальную боль. Боль CEO агентства -- НЕ "sourcing takes too long". Боль -- "мы порекомендовали клиенту инфлюенсера с фейковыми подписчиками, кампания провалилась, клиент ушёл". Время поиска -- efficiency pain, а не fear pain. Fear конвертирует лучше. Мы ЭТО ПРАВИЛЬНО отметили в Round 1.

**Touch 2:**
> Quick note on audience overlap.
> Before pitching 3 creators to a client, you can check if they share 60% of the same followers. Catches bad matches before the brief goes out.
> Think of it as due diligence for every creator recommendation — in seconds, not hours.
> Open to a 20-minute call next week to see a sample report?

**Внутренний голос CEO агентства:**
"О, overlap. Это реальная проблема. Мы действительно иногда питчим 5 инфлюенсеров, а потом выясняется, что у них одна и та же аудитория. Клиент тогда спрашивает: зачем мы платим за трёх, если охват как у одного? 'Due diligence for every creator recommendation' -- хорошая фраза. Может, посмотрю."

**Оценка:** Touch 2 -- ЛУЧШИЙ email во всей серии IMAGENCY. Конкретный сценарий (3 creators, 60% overlap), конкретное последствие (bad matches), конкретная метафора (due diligence). Это ДОЛЖЕН БЫТЬ Touch 1, а не Touch 2. Человек, проигнорировавший Touch 1 (generic efficiency pitch), может никогда не увидеть этот гениальный Touch 2.

**Touch 3:**
> One last thought on creator sourcing.
> We solve the 2 problems slowing agency campaigns: research time (27 filters vs. manual scrolling) and audience guesswork (real demographics, not follower counts).
> If either sounds familiar, worth a quick informal chat?

**Внутренний голос CEO агентства:**
"Слышал 'manual scrolling' -- мы не скроллим вручную, у нас есть инструменты. Это описание проблемы 2020 года, не 2026. 'Audience guesswork' -- ближе к делу, но слишком абстрактно."

**Оценка:** Touch 3 слабее Touch 2. Паттерн "we solve 2 problems" повторяется из INFPLAT -- это шаблон, покупатель это чувствует.

---

### IMAGENCY HYP B -- "White-Label Your Data"

**Touch 1:**
> When {{company_name}}'s clients ask for audience data on a creator, what do you show them?
> At OnSocial, agencies show branded reports under their own logo — powered by our data. 450M+ profiles, real-time, your brand.
> Worth a 15-min demo? Here's my calendar: {{calendar_link}}

**Внутренний голос CEO агентства:**
"Хороший вопрос. Если честно, мы показываем скриншоты из HypeAuditor с замазанным логотипом. Или пересобираем данные в Google Slides вручную. 'Branded reports under their own logo' -- это то, что мне нужно. Это экономит моему менеджеру 2 часа на каждый отчёт."

**Оценка:** СИЛЬНЫЙ opener. Вопрос попадает в ежедневную СТЫДНУЮ ситуацию агентства: клиент просит данные, а агентство показывает скриншоты чужого инструмента. Это ощущение "мы несерьёзны" -- болезненное. White-label решает эту боль напрямую.

**Touch 2:**
> Quick note on client retention.
> Brands are moving creator selection in-house. The agencies keeping clients offer proprietary analytics their clients can't get on their own. White-label data is how you stay indispensable.
> Easier to show live — 15 min, I'll walk you through a sample branded report. {{calendar_link}}

**Внутренний голос CEO агентства:**
"'Brands are moving creator selection in-house' -- это ПРАВДА, и это моя главная тревога. У меня клиент Unilever уже нанял in-house team. 'Proprietary analytics their clients can't get on their own' -- логика рабочая: если я даю клиенту то, что он не может сделать сам, он не уйдёт. Это стратегический аргумент, не функциональный. Мне это нравится."

**Оценка:** Touch 2 поднимает ставки от тактики (white-label reports) до стратегии (client retention vs. in-housing). Это ПРАВИЛЬНАЯ эскалация. Покупатель, которого не зацепил "branded report", может зацепиться на "you'll lose clients if you don't have proprietary data". Это страх, и страх работает.

**Touch 3:**
> One last thought on agency positioning.
> We solve the 2 problems agencies face: clients wanting self-serve data (white-label keeps them dependent on you) and research bottlenecks (27 filters vs. manual scrolling).
> Let's jump on a quick call — 15 min, no pitch. {{calendar_link}}

**Внутренний голос CEO агентства:**
"'Keeps them dependent on you' -- формулировка неудачная. Я не хочу делать клиентов 'dependent', я хочу быть ЦЕННЫМ. 'No pitch' -- все говорят 'no pitch'. Это пустое обещание."

**Оценка:** Touch 3 ослабляет Touch 2. "Dependent on you" звучит манипулятивно. И снова паттерн "2 problems" -- к этому моменту покупатель, видевший INFPLAT HYP A Touch 3, уже встречал этот формат.

---

### AFFPERF HYP A -- "Affiliates Becoming Creators"

**Touch 1:**
> What percentage of {{company_name}}'s partners are also content creators on Instagram, TikTok, or YouTube?
> At OnSocial, we provide a creator data layer via API — audience demographics, credibility scoring, reach overlap. 450M+ profiles, plugs into your existing product.
> Would you be open to a 15-minute call to explore how this fits {{company_name}}'s platform?

**Внутренний голос VP Partnerships:**
"Интересный вопрос. Мы действительно видим, что 30-40% наших affiliate-партнёров ведут YouTube или TikTok. Но мы не знаем, что с этим делать. 'Creator data layer' -- а зачем мне это? Письмо не объясняет, какую проблему это решает для affiliate платформы."

**Оценка:** Вопрос УМНЫЙ -- он ставит покупателя в позицию "а правда, какой процент?" Это curiosity trigger. Но второй абзац не закрывает curiosity -- он перечисляет фичи вместо того, чтобы объяснить ЗАЧЕМ affiliate-платформе нужны creator demographics. Gap между вопросом и продуктом слишком большой.

**Touch 2:**
> Quick note on the affiliate-creator convergence.
> Later acquired Mavely for $250M to merge creator and affiliate data. Sprout Social bought Tagger for the same reason. The platforms winning in 2026 combine performance tracking with creator intelligence.
> Open to a 20-minute call next week to discuss how our API adds that layer?

**Внутренний голос VP Partnerships:**
"Later купил Mavely -- это я знаю, это было в новостях. Sprout + Tagger -- тоже слышал. 'The platforms winning in 2026 combine performance tracking with creator intelligence' -- окей, это рыночный тренд, и вы говорите, что я отстаю. Это немного обидно, но... заставляет задуматься. Может, мы и правда отстаём."

**Оценка:** Touch 2 -- СИЛЬНЫЙ. Конкретные примеры ($250M deal), trend framing ("platforms winning in 2026"), implicit pressure ("if you're not doing this, you're falling behind"). Это fear-of-missing-out, и для VP-level это работает. Лучший Touch 2 во всех сиквенсах.

**Touch 3:**
> One last thought on creator data for affiliate platforms.
> We solve the 2 problems where most affiliate platforms hit a wall: creator audience visibility (real demographics, not follower counts) and fraud detection (credibility scoring on every profile).
> If either sounds familiar, worth a quick informal chat?

**Внутренний голос VP Partnerships:**
"Опять 'we solve 2 problems'. Я видел этот формат уже в трёх письмах (если получаю параллельно из разных кампаний). Это шаблон. Но 'hit a wall' -- хорошее выражение. И fraud detection для affiliate -- это реально: мы тратим кучу денег на партнёров, которые генерят fake traffic."

**Оценка:** Средне. Шаблон "2 problems" ослабляет, но содержание верное.

---

### AFFPERF HYP B -- "Build vs Buy"

**Touch 1:**
> If {{company_name}} wanted to show clients which partners have real vs. fake followers — would you build that in-house?
> At OnSocial, our API delivers audience demographics, credibility scoring, and overlap data. Most platforms estimate 6+ months to build this. We deliver it in days.
> Worth a 15-min look? Here's my calendar: {{calendar_link}}

**Внутренний голос CTO:**
"Хороший вопрос. Если бы мне поставили такую задачу -- я бы сказал 'это займёт 6 месяцев минимум, нанимайте 2 ML-инженеров'. '6+ months vs. days' -- если это правда, это сильный аргумент. Но 'days' звучит нереально для production-ready интеграции. Тем не менее, вопрос попал: build vs. buy -- это дискуссия, которую я веду с CEO каждый квартал."

**Оценка:** СИЛЬНЫЙ opener. Вопрос резонирует с внутренним конфликтом CTO (build vs. buy -- вечная дилемма). "6+ months" -- конкретный, проверяемый claim. Calendar link в первом письме -- опять рискованно, но для CTO/технических ролей это ок: они ценят прямоту и не любят мягкие CTA.

**Touch 2:**
> Quick note on what the integration looks like.
> One endpoint, one creator handle. You get back: follower credibility, audience split by country/city/age/gender, brand affinities, and overlap. Real-time. Your team wraps it in your UI.
> Easiest to show live — here's my calendar: {{calendar_link}}

**Внутренний голос CTO:**
"'One endpoint, one creator handle' -- это я понимаю. Чистая архитектура. 'You get back: ...' -- список полей, как в API docs. Это нормально для технического письма. Но дайте мне ДОКУМЕНТАЦИЮ, а не ещё один calendar link."

**Оценка:** Для CTO это нормальный email. Технически конкретный. Но CTA повторяется -- нужна ссылка на API docs или sandbox, а не третий calendar link.

**Touch 3:**
> One last thought on build vs. buy for creator data.
> We solve the 2 problems where building in-house fails: maintenance cost (one API change breaks your pipeline) and time to market (days vs. 6+ months).
> 15 min — I'll walk you through pricing + live demo. {{calendar_link}}

**Внутренний голос CTO:**
"'One API change breaks your pipeline' -- это НАСТОЯЩАЯ боль. Instagram API меняется каждые 3 месяца, и каждый раз мои инженеры тратят неделю на починку. Это аргумент, который я понимаю. Но 'pricing + live demo' -- это sales pitch, не 'quick informal chat'. Разница в тоне."

**Оценка:** Maintenance cost argument -- СИЛЬНЫЙ, конкретный, резонирующий. Но CTA ("pricing + live demo") слишком прямой для третьего письма, на которое человек уже дважды не ответил.

---

## 2. ТРОЙНОЕ СРАВНЕНИЕ: Sally vs. Yarik+Sonya vs. Delta (наши реврайты)

### Для INFPLAT (IM Platforms & SaaS)

| Критерий | Sally (TEST A/B) | Yarik+Sonya (HYP A/B) | Delta (реврайт Round 1) |
|----------|-----------------|------------------------|------------------------|
| **Opener** | Feature dump: "We provide creator data via API..." | Вопрос: "How are you handling creator data infrastructure?" / "How long does it take to ship a new feature?" | Вопрос: "Is {{company_name}} maintaining its own pipeline, or licensing?" |
| **Что думает покупатель** | "Очередной vendor. Delete." | "Кто-то интересуется моей ситуацией. Прочитаю дальше." | "Конкретный вопрос, на который у меня есть ответ. Читаю." |
| **Proof** | Список фич (credibility, demographics, fraud, overlap) | "450M+ profiles, real-time" | "Platform doing 2B+ monthly lookups" |
| **CTA** | "Who handles product or data partnerships?" | "Would you be open to a 15-minute call?" | "If that's not your situation, ignore this." |
| **Что думает покупатель о CTA** | "Вы просите МЕНЯ маршрутизировать ваш sales email? Нет." | "Стандартный cold email CTA. Норм." | "Этот человек допускает, что мне это не нужно. Уважает. Может, отвечу." |

**Кто побеждает с точки зрения покупателя:**

1. Sally -- ПРОИГРЫВАЕТ однозначно. Feature-first, "who handles X" CTA -- худший вариант. Покупатель не дочитывает до второго абзаца.

2. Yarik+Sonya vs. Delta -- БЛИЗКО, но по-разному.

   Yarik+Sonya: вопрос-opener ПРАВИЛЬНЫЙ, но переход к продукту резкий ("How are you handling X? We replace X."). Вопрос ощущается риторическим.

   Delta: вопрос КОНКРЕТНЕЕ ("maintaining own pipeline OR licensing?") -- это binary choice, на который CTO мысленно отвечает. Плюс "If that's not your situation, ignore this" -- permission to say no, что увеличивает trust.

   **Победитель для INFPLAT: Delta, но с малым отрывом.** Yarik+Sonya уже были на 80% пути. Наш реврайт -- polish, а не revolution.

---

### Для IMAGENCY (IM-First Agencies)

| Критерий | Sally (TEST A/B) | Yarik+Sonya (HYP A/B) | Delta (реврайт Round 1) |
|----------|-----------------|------------------------|------------------------|
| **Opener** | Feature dump | "How many hours sourcing creators?" / "When clients ask for data, what do you show them?" | "How do you validate that audiences don't overlap by 50%+?" |
| **Что думает покупатель** | "Delete." | HYP A: "Не моя боль." / HYP B: "Это моя стыдная ситуация!" | "Overlap -- проблема, о которой я знаю, но не решаю." |
| **Strongest Touch** | Нет сильных | HYP A Touch 2 (overlap scenario) + HYP B Touch 2 (client retention) | Overlap story + fear of losing client |
| **Слабость** | Всё | HYP A Touch 1 (efficiency, не fear) | Немного длинный (4 абзаца) |

**Кто побеждает:**

Здесь интересно.

**Yarik+Sonya HYP B Touch 1** ("When clients ask for audience data, what do you show them?") -- это ЛУЧШИЙ opener для agency segment во всех трёх версиях. Он попадает в стыд. CEO агентства, который показывает клиентам скриншоты из HypeAuditor -- это человек, который знает, что так нельзя, но не знает, как сделать лучше. Этот вопрос зеркалит его внутренний дискомфорт.

**Delta реврайт** фокусируется на overlap -- это тоже боль, но не СТЫД. Overlap -- это операционная проблема ("мы потратили бюджет зря"). White-label -- это идентитетная проблема ("мы выглядим несерьёзно перед клиентом"). Для CEO агентства идентитет > операция.

**Победитель для IMAGENCY: Yarik+Sonya HYP B.** Наш реврайт -- хорош, но HYP B попадает в более глубокую эмоцию.

Однако у Yarik+Sonya HYP A Touch 2 (overlap scenario) -- ЛУЧШИЙ отдельный email для agency. Проблема в том, что он стоит на позиции Touch 2, а не Touch 1. С учётом данных Round 3 (74% replies на Step 1), этот блестящий email видят единицы.

---

### Для AFFPERF (Affiliate & Performance)

| Критерий | Sally (TEST A/B) | Yarik+Sonya (HYP A/B) | Delta (реврайт Round 1) |
|----------|-----------------|------------------------|------------------------|
| **Opener** | Feature dump (одинаковый для всех сегментов) | "What % of partners are creators?" / "Would you build real-vs-fake detection in-house?" | Не было отдельного реврайта для AFFPERF |
| **Unique angle** | Нет | Affiliate-creator convergence (Mavely $250M deal) + Build vs. Buy | N/A |

**Кто побеждает:** Yarik+Sonya -- безоговорочно. Sally даже не адресует affiliate сегмент (generic для всех). Delta не написал отдельный реврайт (в Round 1 мы не дошли до AFFPERF).

Yarik+Sonya HYP A Touch 2 (Mavely + Sprout acquisitions) -- самый сильный trend-based email во всех сиквенсах. Он переводит разговор из "нам пытаются продать data tool" в "рынок трансформируется, и мы можем отстать". Это fear-of-missing-out на стратегическом уровне.

Yarik+Sonya HYP B ("build vs. buy") -- попадает в вечный CTO-конфликт и является самостоятельно сильным.

---

## 3. ХИРУРГИЧЕСКИЕ ПРАВКИ к сиквенсам Ярика+Сони

Не полные реврайты. Конкретные изменения, которые усилят то, что уже работает.

---

### INFPLAT HYP A

**Правка 1: Touch 1 -- убрать риторический привкус вопроса.**

Сейчас:
> How are you currently handling creator data infrastructure at {{company_name}}?
> At OnSocial, we replace in-house scraping pipelines...

Проблема: вопрос + немедленный ответ = вопрос-ловушка.

Исправить:
> How are you currently handling creator data infrastructure at {{company_name}} — own pipeline, third-party vendor, or a mix?
>
> Asking because we work with platforms that switched from in-house scraping to our API (450M+ profiles, real-time, IG/TikTok/YT) and the main trigger was usually maintenance cost, not missing features.
>
> If that resonates, worth a 15-min look. If not — genuinely curious what's working for you.

Что изменилось: (a) вопрос стал real question (три варианта ответа), (b) "At OnSocial, we replace..." заменено на "we work with platforms that switched..." (third-person framing = less salesy), (c) CTA включает "if not -- genuinely curious" (permission + curiosity).

**Правка 2: Touch 2 -- уточнить "under a week".**

Сейчас: "Most platforms go live with our API in under a week."

Исправить: "Most platforms start pulling data from our API within days. Production rollout timeline depends on your stack — simplest case is a week, typical is 2-3 weeks."

Что изменилось: честность > overclaiming. CTO доверяет тому, кто говорит "depends on your stack", а не "under a week guaranteed".

**Правка 3: Touch 3 -- оставить как есть.** Touch 3 сильный. "If either sounds familiar" -- лучший CTA во всех сиквенсах. Не трогать.

---

### INFPLAT HYP B

**Правка 1: Touch 2 -- добавить ссылку на API docs вместо второго calendar link.**

Сейчас: "Easiest to show live — here's my calendar: {{calendar_link}}"

Исправить: "Here's what the API response looks like for a single creator: [link to sample output or docs]. If you want to see it with YOUR creators — here's my calendar: {{calendar_link}}"

Что изменилось: технический покупатель хочет ПОТРОГАТЬ данные сам, прежде чем согласиться на звонок. Дать ему это.

**Правка 2: Touch 3 -- смягчить CTA.**

Сейчас: "15 min is all it takes to see if this fits."

Исправить: "If build time or coverage is a bottleneck for your team, happy to do a quick comparison with your current setup."

Что изменилось: "15 min is all it takes" звучит как infomercial. "Happy to do a quick comparison" -- collaborative, не pushful.

---

### IMAGENCY HYP A

**Правка 1 (КРИТИЧЕСКАЯ): Поменять Touch 1 и Touch 2 местами.**

Текущий Touch 2 (overlap scenario: "Before pitching 3 creators to a client, you can check if they share 60% of the same followers") -- это ЛУЧШИЙ email в серии. Он стоит на позиции, которую 74% людей никогда не увидят. Сделать его Touch 1.

Новый Touch 1 (бывший Touch 2):
> Hi {{first_name}},
>
> Before pitching 3 creators to a client, how does {{company_name}} check if they share 60% of the same followers?
>
> We had an agency pitch 3 creators for a DTC brand — turned out they shared most of the same audience. The campaign underperformed, and the agency lost the retainer.
>
> We built a tool that catches this in seconds — before the brief goes out.
>
> Worth a 15-min look at a sample overlap report?

Новый Touch 2 (бывший Touch 1, сокращённый):
> Quick note on research time.
>
> Beyond overlap, we cover sourcing: 27 filters, audience demographics, credibility scores — most teams cut research from days to hours.
>
> Open to a 20-min walkthrough?

Что изменилось: лучший контент стоит на позиции, где его увидят.

**Правка 2: Touch 3 -- убрать "manual scrolling".**

Сейчас: "27 filters vs. manual scrolling"

Исправить: "27 filters vs. platform-hopping across 3 tools"

Что изменилось: в 2026 году никто не "scrolls manually". Но "platform-hopping" (переключение между HypeAuditor + Instagram + TikTok Creator Portal) -- реальная боль.

---

### IMAGENCY HYP B

**Правка 1: Touch 3 -- убрать "dependent on you".**

Сейчас: "white-label keeps them dependent on you"

Исправить: "white-label makes your data part of their workflow — they can't replicate it without you"

Что изменилось: "dependent" звучит манипулятивно. "Part of their workflow" -- позитивная формулировка той же идеи (lock-in через value, а не через зависимость).

**Правка 2: Touch 3 -- убрать "no pitch".**

Сейчас: "Let's jump on a quick call — 15 min, no pitch."

Исправить: "15 min — I'll show you a sample branded report for a creator your team is currently evaluating."

Что изменилось: "no pitch" -- пустое обещание, все так говорят. "Sample branded report for YOUR creator" -- конкретный deliverable.

---

### AFFPERF HYP A

**Правка 1: Touch 1 -- связать вопрос с ответом.**

Сейчас: "What percentage of {{company_name}}'s partners are also content creators?" (вопрос) -> "At OnSocial, we provide a creator data layer via API" (несвязанный ответ).

Исправить:
> What percentage of {{company_name}}'s partners are also content creators on Instagram, TikTok, or YouTube?
>
> The platforms figuring this out are adding a creator intelligence layer — audience demographics, credibility scoring, overlap data — to understand not just who converts, but who influences.
>
> We provide that layer via API. 450M+ profiles, plugs into your existing product.
>
> Worth exploring how this fits {{company_name}}? 15 min.

Что изменилось: добавлен МОСТ между вопросом и продуктом ("The platforms figuring this out are adding..."). Покупатель понимает ЗАЧЕМ ему нужны creator data в контексте его affiliate бизнеса.

**Правка 2: Touch 2 -- оставить как есть.** Mavely/Sprout touch -- идеальный. Не трогать.

---

### AFFPERF HYP B

**Правка 1: Touch 3 -- заменить CTA.**

Сейчас: "15 min — I'll walk you through pricing + live demo."

Исправить: "15 min — I'll pull real vs. fake follower data on a few of your top partners. You'll see the output before the call ends."

Что изменилось: "pricing + live demo" = sales pitch. "Real data on YOUR partners" = proof of value. CTO хочет увидеть СВОИ данные, а не ваш sales deck.

---

### ОБЩАЯ ПРАВКА ДЛЯ ВСЕХ СИКВЕНСОВ

**Убрать паттерн "We solve the 2 problems..."**

Этот формат встречается в Touch 3 КАЖДОГО сегмента (6 из 6 сиквенсов). Если один покупатель получает emails из двух кампаний (а дедупликация не работает -- см. Round 1), он увидит ОДИНАКОВУЮ структуру дважды. Это моментальный "шаблон" сигнал.

Заменить разнообразными формулировками:
- INFPLAT HYP A Touch 3 -- ОСТАВИТЬ КАК ЕСТЬ (самый сильный вариант)
- Остальные пять -- переписать каждый уникально. Варианты:
  - "One question that keeps coming up from [segment] teams: [question]. We solve it by [answer]."
  - "Most [segment] companies hit the same wall at scale: [problem]. Here's how we help: [solution]."
  - Просто два коротких абзаца без нумерации.

---

## 4. ЧТО НАША ROUND 1 АНАЛИТИКА ПОЛУЧИЛА НЕПРАВИЛЬНО

Честный список ошибок.

### Ошибка 1: Мы приписали ВСЮ копию Sally, когда Sally написала только Framework 1.

Наш Round 1 анализ начинается с:
> "I read every sequence and reply from the perspective of a CTO..."

И далее критикует "every email leads with the product, not the buyer's problem", "no social proof is believable", "CTA is weak and generic". Всё это ВЕРНО для Sally (Framework 1, TEST A/B, PR firms, IM_PLATFORMS). Но мы применили ТУ ЖЕ КРИТИКУ ко ВСЕМ сиквенсам, как будто все написаны одним человеком.

Frameworks 2-4 (Yarik+Sonya) УЖЕ содержат problem-first hooks, question-based openers, segment-specific angles. Наша главная рекомендация ("Rewrite Step 1 to lead with the buyer's situation, not the product") -- это ИМЕННО ТО, что Yarik+Sonya уже сделали. Мы рекомендовали то, что уже существовало.

**Почему мы ошиблись:** Мы читали все 4 frameworks как единый corpus и критиковали средний уровень. Но средний уровень тянула вниз Sally. Yarik+Sonya были значительно выше среднего, но мы этого не разделили.

### Ошибка 2: Мы переоценили unlogged replies.

Round 1: "66 unlogged replies could contain ~15-20 interested leads and ~8-10 additional meetings."
Round 3 correction: "3-5 actionable из 66."

Мы были правы, что Alpha переоценивает (10-15), но мы САМИ переоценивали. 16.8% actionable rate из всех ответов = ~11 actionable из 66. Но те 66, которые Настя не залогировала -- скорее всего, были OOO/noise (именно поэтому она их не залогировала). Реалистичная оценка: 5-7 actionable, а не 15-20.

К чести Round 3 -- мы уже скорректировали это до 3-5. Но первоначальная оценка в Round 1 была dangerously optimistic.

### Ошибка 3: Наш реврайт для IMAGENCY не бьёт HYP B Ярика+Сони.

Наш реврайт в Round 1 для IM Agencies фокусируется на overlap (3 creators share 60% followers -> agency lost a client). Это хороший email. Но Yarik+Sonya HYP B Touch 1 ("When clients ask for audience data, what do you show them?") попадает в СТЫД, а не в СТРАХ ПОТЕРИ. Стыд -- более глубокая эмоция.

Мы писали в Round 1: "The emotional trigger is FEAR OF LOOKING INCOMPETENT IN FRONT OF A CLIENT." Мы ПРАВИЛЬНО диагностировали эмоцию. Но наш собственный реврайт использовал fear of loss (lost retainer), а не fear of looking incompetent. Yarik+Sonya HYP B использует именно incompetence trigger ("what do you show them?" = "мы знаем, что вы показываете скриншоты из чужого инструмента").

Мы диагностировали правильно, но прописали неправильно.

### Ошибка 4: Мы критиковали "27 filters" как "feature list, not a benefit" -- но не предложили лучшей конкретики.

Round 1: "27 filters sounds like a feature list, not a benefit."

Это верно. Но наш собственный реврайт для IMAGENCY не содержит НИКАКОЙ конкретики уровня "27 filters". Мы убрали "feature dump" и заменили его на story (overlap scenario) -- это лучше по формату, но покупатель, который хочет ПОНЯТЬ продукт, получает story без substance.

Правильный подход: story + ONE concrete detail. "We catch overlap in seconds — you select the creators, we show you exactly how much audience they share, down to the city level." Это и story (overlap catching), и конкретика (down to city level), но не список фич.

### Ошибка 5: Мы не заметили AFFPERF сиквенсы вообще.

В Round 1 нет отдельного анализа AFFPERF. Мы упомянули "Affiliate & Performance (no data yet)" в стратегических рекомендациях и предложили убить этот сегмент. Но сами сиквенсы для AFFPERF (HYP A и HYP B) -- одни из самых сильных в portfolio. Мы их просто проигнорировали.

AFFPERF HYP A Touch 2 (Mavely/Sprout acquisitions) -- лучший trend-based email во всех сиквенсах. AFFPERF HYP B Touch 1 (build vs. buy) -- лучший technical opener. Мы это пропустили.

---

## 5. ЧЕСТНАЯ ОЦЕНКА: НАШИ РЕВРАЙТЫ VS. YARIK+SONYA

### Где наши реврайты ЛУЧШЕ:

1. **CTA quality.** Наши CTA ("If that's not your situation, ignore this", "send me 2-3 creator handles, I'll pull the breakdown") -- конкретнее и мягче, чем "Would you be open to a 15-minute call?" Это реальное улучшение. У Ярика+Сони CTA стандартные (calendar link, 15-min call). Наши -- дифференцированные.

2. **Permission to say no.** "If not — no worries" / "If that's not your situation, ignore this." Ярик+Соня этого не делают. Покупатель чувствует уважение, когда ему дают explicit permission to ignore. Это counterintuitive (кажется, что ты ослабляешь CTA), но в реальности увеличивает trust и response rate.

3. **Reply scripts.** Ярик+Соня написали outbound sequences, но не написали reply scripts. Наши 9 скриптов (pricing, send info, how are you different, we have a partner, etc.) -- это полностью наш вклад. Это покрывает самый высокоценностный момент в воронке (человек уже ответил).

4. **Structural recommendations.** Kill Step 4, differentiate each step, break-up email -- это meta-level рекомендации, которые Ярик+Соня не формулировали (они писали контент, не framework).

### Где Yarik+Sonya ЛУЧШЕ:

1. **IMAGENCY HYP B opener.** "When clients ask for audience data, what do you show them?" -- бьёт наш overlap-based opener по глубине эмоции (стыд > страх потери). Мы диагностировали правильную эмоцию (fear of looking incompetent) и прописали неправильное лекарство (fear of losing client).

2. **AFFPERF HYP A Touch 2 (Mavely/Sprout).** Trend-based argument с конкретными M&A deals -- это sophistication, которую наши реврайты не достигают. Мы фокусируемся на immediate pain; Yarik+Sonya фокусируются на strategic trend. Для VP-level покупателя strategic trend > immediate pain.

3. **AFFPERF HYP B (build vs. buy framework).** Вся гипотеза -- сильная. Мы не предложили альтернативу.

4. **Segment-specific thinking.** Yarik+Sonya написали РАЗНЫЕ сиквенсы для РАЗНЫХ сегментов с РАЗНЫМИ гипотезами (A/B на уровне angle, не на уровне subject line). Наш Round 1 критиковал "ICP too broad, 5 segments is too many" -- но при этом наши реврайты были для 2 сегментов (Platforms + Agencies), не для 3. Мы пропустили AFFPERF целиком.

### Где мы ПРОСТО РАЗНЫЕ (не лучше и не хуже):

1. **Tone.** Наши реврайты -- warmer, more conversational, more "permission-based". Yarik+Sonya -- more direct, more assertive, more "here's what we do". Какой тон конвертирует лучше -- зависит от сегмента и персоны. Для CTO -- direct может работать лучше. Для agency CEO -- warm/permission может работать лучше. Без A/B теста это гипотеза, а не факт.

2. **Proof points.** Мы используем "one named customer" и social proof через behavior ("a platform doing 2B+ monthly lookups"). Yarik+Sonya используют product specifics (450M, 27 filters) и market proof (Mavely, Sprout). Оба подхода валидны.

3. **Structure.** Наш framework (problem-first hook -> micro case study -> contrarian insight -> graceful close) vs. Yarik+Sonya (question -> product -> CTA в каждом Touch, с "2 problems" Touch 3). Наш framework теоретически лучше (каждый step добавляет новое), но мы его НЕ ВОПЛОТИЛИ в полные 3-step sequences. Мы написали реврайты только для Touch 1. Yarik+Sonya написали ПОЛНЫЕ 3-step sequences для каждой гипотезы.

---

## ИТОГОВЫЙ ВЕРДИКТ

**Наш Round 1 анализ был полезен, но грешил слепым пятном: мы критиковали "copy" как монолит, не разделяя авторов.**

Самая ценная часть нашего вклада -- НЕ реврайты Step 1 (Yarik+Sonya уже были на 80% пути). Самая ценная часть:

1. **Reply scripts** -- Yarik+Sonya этого не писали, а это самое высокоценностное звено в воронке.
2. **Structural fixes** -- kill Step 4, differentiate each step, break-up email с конкретным примером.
3. **Операционные рекомендации** -- OOO pipeline, show rate fix, pre-qualification, dedup.
4. **CTA philosophy** -- permission to say no, reverse demo (send data before asking for call).

Yarik+Sonya превосходят нас в:

1. **Segment depth** -- три полных sequence x 2 гипотезы x 3 touches = 18 emails. Мы написали 2 реврайта Touch 1.
2. **Emotional precision** -- HYP B IMAGENCY (стыд) и HYP A AFFPERF (FOMO через M&A data) бьют наши реврайты по глубине.
3. **Technical credibility** -- AFFPERF HYP B (build vs. buy) и INFPLAT HYP B (ship features faster) говорят на языке CTO, а не на языке copywriter.

**Честный ответ на вопрос "наши реврайты лучше?":**

Для Sally (Framework 1) -- ДА, однозначно лучше. Sally написала generic feature-dump, мы написали problem-first hooks. Значительное улучшение.

Для Yarik+Sonya (Frameworks 2-4) -- НЕТ, не лучше в целом. Наши CTA и permission-based tone -- улучшение. Наши Reply Scripts -- уникальный вклад. Но наши Step 1 реврайты -- это polish того, что Yarik+Sonya уже сделали, а не принципиально другой подход. А в IMAGENCY HYP B и AFFPERF -- Yarik+Sonya бьют нас.

**Правильная стратегия -- не "заменить Yarik+Sonya нашими реврайтами", а:**

1. Взять Yarik+Sonya Frameworks 2-4 как БАЗУ.
2. Применить хирургические правки из раздела 3 (риторические вопросы -> real questions, "under a week" -> honest timeline, swap Touch 1/2 в IMAGENCY HYP A, убрать "2 problems" паттерн, добавить permission-based CTAs).
3. Добавить Reply Scripts (наш уникальный вклад).
4. Применить structural fixes (kill Step 4, break-up email, differentiate steps).
5. ЗАДЕПЛОИТЬ наконец. Сиквенсы Ярика+Сони НИКОГДА не деплоились. Лучший email в мире = 0 meetings, если он не отправлен.

---

*Correction Round подготовлен Team Delta. Если мы не готовы признать, что ошиблись -- мы не готовы давать советы.*
