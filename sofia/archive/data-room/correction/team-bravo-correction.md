# TEAM BRAVO -- CORRECTION ROUND

**Дата:** 2026-03-16
**Контекст:** Сравнение трёх версий сиквенсов (Sally vs Ярик+Соня vs Bravo-переписка) по каждому сегменту. Самокоррекция ошибок Round 1.

---

## 0. КЛЮЧЕВОЙ ФАКТ, КОТОРЫЙ МЫ ПРОПУСТИЛИ

В Round 1 мы написали: "The sequences are good -- but they are solving the wrong problem for half the audience." И предложили problem-first rewrites для PR firms и IM_PLATFORMS.

**Мы не знали, что Ярик и Соня УЖЕ написали три сегмент-специфичных фреймворка (INFPLAT, IMAGENCY, AFFPERF) с problem-first хуками.** Эти сиквенсы НИКОГДА не деплоились. Вместо них Sally задеплоила свои generic TEST A/B и дополнительные PR firms / IM_PLATFORMS варианты -- напрямую в SmartLead, без координации.

Это означает: наша главная рекомендация ("перейти от feature-dump к problem-first") уже была реализована на бумаге. Проблема была не в отсутствии правильного copy -- а в том, что правильное copy лежало в шите, а в SmartLead работало неправильное.

---

## 1. СРАВНЕНИЕ ТРЁХ ВЕРСИЙ ПО СЕГМЕНТАМ

### 1.1 INFPLAT (Influencer Platforms & SaaS)

#### Sally (задеплоено):

**IM_PLATFORMS variant:**
- Открывает с name-dropping: "Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API"
- Фокус на credentials и feature-список
- Step 2: "stitching together patchy data sources that break under scale"

**Generic TEST A/B (задеплоено):**
- "450M influencer profiles are ready for your API"
- Образовательный подход: объясняет, что такое OnSocial
- Универсальный, не адаптирован к платформам

#### Ярик+Соня (НЕ деплоились):

**HYP A -- "Stop Building Scrapers":**
- Хук: "How are you currently handling creator data infrastructure at {{company_name}}?"
- Problem-first: обращается к инженерной боли (scraping pipelines, data freshness)
- Touch 2: "Adding a full data engineering team -- without the headcount"
- Touch 3: "data freshness (real-time vs. weekly scrapes) and coverage (3 platforms vs. partial databases)"

**HYP B -- "Ship Features Faster":**
- Хук: "How long does it take {{company_name}} to ship a new analytics feature?"
- Product/competitive pain: time-to-market, feature velocity
- Конкретный: "Teams ship the same features in days, not months"

#### Bravo-переписка (Round 1):

- "Quick question: how many of the creator profiles in {{company_name}}'s database have verified audience demographics vs. estimated?"
- Фокус на data quality challenge
- Убирает name-dropping, заменяет на вопрос

#### ВЕРДИКТ: ЛУЧШИЙ -- Ярик+Соня HYP A "Stop Building Scrapers"

**Почему:**

1. **Ярик+Соня попадают в правильную боль.** CTO/VP Engineering платформы просыпается утром и думает: "мой pipeline опять упал", "скрейпер сломался", "нам нужно ещё 2 инженера на data infra". Вопрос "How are you currently handling creator data infrastructure?" -- это зеркало их повседневной реальности.

2. **Наш Bravo-вариант слишком умный.** "How many profiles have verified vs. estimated demographics?" -- это хороший вопрос, но он не адресует БОЛЬ. Он адресует КАЧЕСТВО ДАННЫХ, что является следствием боли, а не самой болью. CTO не лежит ночью без сна думая о "verified vs estimated" -- он думает о "pipeline maintenance costs" и "feature delivery speed".

3. **Sally name-dropping вызывает conflict of interest.** Мы это правильно диагностировали в Round 1: "Modash, Captiv8, Kolsquare" -- это конкуренты потенциального клиента. Сигнал: "мы работаем с вашими врагами".

4. **HYP B ("Ship Features Faster") -- сильный второй вариант** для A/B теста. Попадает в другую грань той же боли: не infrastructure maintenance, а competitive speed.

**Деплоить: Ярик+Соня HYP A as-is.** Без адаптации. Copy зрелое и готовое. A/B тест HYP A vs HYP B.

---

### 1.2 IMAGENCY (IM-First Agencies)

#### Sally (задеплоено):

**Generic TEST A/B:**
- Тот же текст, что и для платформ. "We provide creator and audience data via API for influencer marketing platforms"
- Говорит "API" агентству без технической команды
- "Your clients see it as your feature" -- это API framing, который не резонирует с CEO agency

#### Ярик+Соня (НЕ деплоились):

**HYP A -- "Cut Research Time":**
- Хук: "How many hours does your team spend sourcing creators per campaign?"
- Efficiency pain: "cut that to under 2 hours -- 27 filters"
- Touch 2: audience overlap как due diligence tool -- конкретный use case
- Touch 3: "research time (27 filters vs. manual scrolling) and audience guesswork"

**HYP B -- "White-Label Your Data":**
- Хук: "When {{company_name}}'s clients ask for audience data on a creator, what do you show them?"
- Revenue/brand pain: competitive positioning через proprietary analytics
- Touch 2: "Brands are moving creator selection in-house. The agencies keeping clients offer proprietary analytics"
- Стратегический fear appeal: "if you don't have exclusive data, clients will leave"

#### Bravo-переписка (Round 1):

Мы НЕ писали отдельный вариант для агентств. Мы предложили общие принципы: problem-first hooks, убрать feature-dump, добавить reply scripts. Наш фокус был на PR firms и IM_PLATFORMS.

#### ВЕРДИКТ: ЛУЧШИЙ -- Ярик+Соня HYP B "White-Label Your Data"

**Почему:**

1. **HYP B бьёт в страх потери клиентов.** CEO агентства боится одного: что бренд заберёт influencer marketing in-house. "Brands are moving creator selection in-house" -- это экзистенциальная угроза. "White-label data is how you stay indispensable" -- это решение экзистенциальной угрозы.

2. **HYP A хорош, но решает операционную проблему.** "Сколько часов тратите на research?" -- экономия времени. Это важно, но не заставит CEO агентства ответить на cold email. CEO думают о P&L и client retention, не о часах на research.

3. **Sally generic просто не работает для агентств.** Говорить "API" и "white-label ready" в одном предложении с "your clients see it as your feature" -- это mixed messaging. Агентство без dev team не знает, что делать с API.

**Деплоить: Ярик+Соня HYP B as-is.** A/B тест HYP A vs HYP B. Если у агентства есть dev team -- попадут в INFPLAT сегмент через negative filter.

**Одна корректировка:** Touch 1 упоминает "450M+ profiles, real-time, your brand" -- это feature tail, который ослабляет problem-first хук. Рекомендую вырезать эту строку и оставить хук + CTA чистыми. Но это minor -- можно деплоить и так.

---

### 1.3 AFFPERF (Affiliate & Performance)

#### Sally (задеплоено):

**Generic TEST A/B:**
- Тот же текст. "We provide creator and audience data via API for influencer marketing platforms"
- Affiliate platforms -- это НЕ "influencer marketing platforms". Они -- performance/partnership platforms. Messaging вообще не релевантен.

#### Ярик+Соня (НЕ деплоились):

**HYP A -- "Your Affiliates Are Becoming Creators":**
- Хук: "What percentage of {{company_name}}'s partners are also content creators?"
- Convergence narrative: Later + Mavely ($250M), Sprout Social + Tagger
- Стратегический: "The platforms winning in 2026 combine performance tracking with creator intelligence"

**HYP B -- "Build vs Buy":**
- Хук: "If {{company_name}} wanted to show clients which partners have real vs. fake followers -- would you build that in-house?"
- Technical pain: 6+ months to build vs. days via API
- Touch 2: конкретный API output -- one endpoint, one handle, what you get back

#### Bravo-переписка (Round 1):

Мы НЕ писали для AFFPERF. Мы рекомендовали запуск, но не предлагали переписать copy.

#### ВЕРДИКТ: ЛУЧШИЙ -- Ярик+Соня HYP A "Affiliates Are Becoming Creators"

**Почему:**

1. **HYP A -- это стратегический insight, не product pitch.** "Later acquired Mavely for $250M to merge creator and affiliate data" -- это рыночный сигнал. CEO affiliate-платформы увидит это и подумает: "мы тоже должны это делать". Это consultative selling, не cold pitching.

2. **HYP B хорош для CTO, но слабее для CEO.** "Build vs buy" -- это engineering conversation. CEO affiliate-платформы может не думать в этих терминах. HYP A говорит на языке стратегии и рынка.

3. **Convergence narrative уникальна.** Ни один конкурент OnSocial (HypeAuditor, Modash, Phyllo) не позиционирует себя через affiliate-creator convergence. Это differentiator в messaging.

**Деплоить: Ярик+Соня HYP A с одной корректировкой.** Touch 1 заканчивается "Would you be open to a 15-minute call to explore how this fits {{company_name}}'s platform?" -- это generic CTA. Учитывая стратегический хук, CTA должен быть тоже стратегическим: "Worth a 15-min conversation about how {{company_name}} could add a creator intelligence layer?" A/B тест HYP A vs HYP B.

---

### 1.4 PR Firms

#### Sally (задеплоена, СЛОМАНА):

- Name-dropping: "NeoReach, Buttermilk, Gushcloud, Influencer.com, and Obviously all run on our API"
- Технически сломана: 17/1000 на Step 1, 10.6% bounce на Step 2
- 0.2% reply rate, 0 meetings
- Активно повреждает domain reputation

#### Ярик+Соня:

Не писали отдельный вариант для PR firms. Этот сегмент был добавлен Sally напрямую.

#### Bravo-переписка (Round 1):

- "When {{company_name}} recommends a creator for a PR campaign, how do you validate their audience is real and in the right market?"
- Problem-first: "Most PR firms either eyeball it (risky) or pay per-report fees"
- CTA: "Pick a creator you're vetting right now -- I'll pull the full breakdown"

#### ВЕРДИКТ: НИ ОДИН. СЕГМЕНТ НУЖНО УБИТЬ (подтверждаем Round 1 + Round 3)

**Почему:**

1. **Round 3 данные подтверждают:** кампания технически сломана, domain damage активен.
2. **8 из 8 "Not Interested" -- ICP mismatches:** PR firms не покупают API, они покупают tools/reports.
3. **Наш Bravo-вариант из Round 1 -- теоретически лучше Sally**, но это не имеет значения: сегмент не конвертируется, потому что PR firms -- не ICP.
4. **Рекомендация:** полная остановка. Если через 3-6 месяцев появятся 2-3 ручные wins с PR firms -- вернуться к вопросу. Не раньше.

---

## 2. ГДЕ МЫ ОШИБЛИСЬ В ROUND 1

### Ошибка 1: Мы не знали, что problem-first copy уже существует

Главная рекомендация Round 1 ("kill the PR firms name-dropping", "swap name-dropping for a challenge", "problem-first hooks") -- всё это Ярик и Соня уже сделали в Frameworks 2-4. Мы потратили значительную часть анализа на изобретение велосипеда.

**Причина ошибки:** Нам дали только задеплоенные сиквенсы Sally, без контекста о том, что существуют альтернативные версии. Мы анализировали то, что было в SmartLead, а не то, что было в шите.

**Урок:** Прежде чем переписывать -- спросить: "кто-то уже писал альтернативные варианты?"

### Ошибка 2: Мы недостаточно оценили качество work Ярика+Сони

Посмотрев на все три фреймворка (INFPLAT, IMAGENCY, AFFPERF), видно:
- Каждый сегмент имеет ДВЕ гипотезы (HYP A и HYP B) -- A/B тест заложен в структуру
- Хуки problem-first и segment-specific
- Touch 2-3 deepens the problem, не повторяет Touch 1
- CTA варьируется: soft ("worth a chat?") vs direct (calendar link)
- Timing protocol для A/B тестирования прописан

Это зрелая outreach architecture. Наши rewrites в Round 1 были слабее по нескольким параметрам:
- У нас был один вариант на сегмент, у них -- два
- У нас не было Touch 2-3 progression, у них -- есть
- Их хуки точнее попадают в buyer persona (наш "verified vs estimated" -- слишком абстрактный)

### Ошибка 3: Мы атрибутировали результаты Sally к messaging, а не к deployment

"8 out of 12 interested replies came from the Generic/TEST B campaign" -- мы интерпретировали это как "generic messaging works better than segment-specific." Но реальность: Generic/TEST B -- единственное, что массово деплоилось (1,980 sends на Step 1). Сегмент-специфичные варианты Ярика+Сони НИКОГДА не деплоились. Мы сравнивали deployed vs non-deployed и делали вывод о качестве messaging. Это классическая survivorship bias.

### Ошибка 4: Мы переоценили OOO pipeline

Round 1: "21 OOO leads need scheduled re-engagement."
Round 3: 91 OOO-автоответов, и это не "pre-warmed pipeline" -- это шум.
Мы уже скорректировали это в Round 3, но сама ошибка Round 1 была серьёзной: мы построили Action #6 в Final Synthesis на иллюзии "21 pre-warmed leads", когда реальность -- 91 автоответов от людей, которые не читали письмо.

### Ошибка 5: "Stop A/B testing" -- НЕПРАВИЛЬНО

В Round 1 Contrarian Take #1 мы написали: "Stop A/B testing. You don't have the volume for statistical significance."

Это было ошибкой, и вот почему: Ярик+Соня ЗАЛОЖИЛИ A/B тестирование правильно. Каждый сегмент имеет HYP A и HYP B с принципиально разными angles (engineering pain vs product pain, efficiency vs revenue). Это не A/B тест на длину subject line -- это тест на гипотезу о том, КАКАЯ БОЛЬ резонирует с сегментом. Такой тест можно проводить при малых объёмах, потому что signal = quality of replies, не statistical significance open rates.

Мы смешали "A/B testing subject lines at low volume" (бессмысленно) с "A/B testing fundamental value propositions" (необходимо). Ярик+Соня делали второе.

---

## 3. CONTRARIAN TAKE: МОЖЕТ ЛИ SALLY GENERIC РАБОТАТЬ ЛУЧШЕ?

Обязаны рассмотреть: есть ли аргументы в пользу того, что Sally generic TEST A/B может работать ЛУЧШЕ, чем сегмент-специфичные варианты Ярика+Сони?

### Аргументы ЗА generic:

**3.1 Simplicity scales.** Один текст на все сегменты = одна переменная для оптимизации. Три сегмента x 2 гипотезы = 6 вариантов. При 1 SDR и ограниченном volume (2,000 контактов/неделю максимум) 6 вариантов означают ~330 контактов на вариант. При 0.25% true interest rate это менее 1 actionable reply на вариант. Невозможно понять, что работает. Sally generic даёт 2,000 контактов на один вариант = ~5 actionable replies = хоть какой-то signal.

**3.2 "450M profiles" -- это фильтр, а не pitch.** Sally generic фильтрует: если человеку НЕ нужен creator data API, он не ответит. Если нужен -- числа "450M", "API", "audience demographics" достаточно для квалификации. Problem-first хуки Ярика+Сони могут получить больше replies от людей, которые ОТКЛИКНУТСЯ на вопрос, но НЕ нуждаются в продукте. "How many hours does your team spend sourcing creators?" -- может получить ответ "12 hours" от agency без бюджета. Generic отсеивает таких: если ты не API buyer, ты не ответишь.

**3.3 Единая data pipeline для оптимизации.** С одним generic текстом вы можете быстрее итерировать: subject line week 1 -> CTA week 2 -> opening line week 3. С 6 вариантами итерация займёт 6x дольше.

**3.4 Data evidence:** Generic TEST B -- единственный вариант, который РЕАЛЬНО генерировал meetings. 8 из 12 interested, 5 из 5 held meetings. Да, это потому что он единственный массово деплоился, но факт остаётся: он РАБОТАЛ. Не отлично (0.25% true interest rate), но работал.

### Аргументы ПРОТИВ generic (почему segment-specific всё-таки лучше):

**3.5 Generic работает ТОЛЬКО на API buyers.** 4 из 5 strong fits -- Platforms & SaaS. Generic text говорит "API", "your clients", "white-label" -- это язык платформ. Для агентств без dev team это чужой язык. Generic не "universal" -- он segment-specific для платформ, просто замаскированный под generic.

**3.6 0.25% true interest rate -- это НЕ "работает".** При generic messaging 1 actionable на 400 контактов. Если segment-specific даст 1 на 200 (что реалистично для INFPLAT, учитывая что flagship без OOO даёт ~1.0% actionable rate) -- это 2x improvement. При ограниченном TAM (несколько тысяч целевых компаний) 2x -- это разница между выработкой TAM за 6 месяцев и за 12.

**3.7 Problem-first хуки отвечают на вопрос "зачем мне открывать это письмо?"** Generic Sally отвечает на "что вы продаёте?" -- это слабее. CTO получает 50 cold emails в неделю от data vendors. "450M profiles, API" -- noise. "How are you currently handling creator data infrastructure?" -- это его вопрос, заданный ему обратно.

**3.8 A/B тест гипотез (не subject lines) даёт strategic insight.** Если HYP A "Stop Building Scrapers" даёт 3x reply rate vs HYP B "Ship Features Faster" -- вы узнали, что инженерная боль резонирует сильнее product боли. Это information asset, который влияет на positioning, website copy, demo script, pricing framing. Generic testing даёт только "long vs short works better" -- тактический insight.

### ФИНАЛЬНЫЙ ВЕРДИКТ:

**Sally generic -- это acceptable baseline, но не оптимум.**

Segment-specific Ярика+Сони лучше по двум причинам:
1. Они адресуют конкретную боль, а не описывают продукт
2. Они дают strategic signal через HYP A/B тестирование

Но: аргумент 3.1 (simplicity scales) реален. При 1 SDR и текущем volume нужен компромисс.

**Рекомендация: поэтапный деплой.**

1. **Неделя 1:** Деплоить Ярик+Соня INFPLAT HYP A (самый сильный сегмент, 6.2% raw reply rate). Оставить Sally generic как контроль для сравнения.
2. **Неделя 2:** Если INFPLAT HYP A > generic по actionable reply rate -- деплоить INFPLAT HYP B. Деплоить IMAGENCY HYP B.
3. **Неделя 3:** Деплоить AFFPERF HYP A. Первый A/B comparison: HYP A vs HYP B в INFPLAT.
4. **Неделя 4:** Оценка. Какой сегмент x гипотеза даёт highest actionable rate? Scale winner.

Это даёт segment-specific advantage без потери control signal.

---

## 4. ИТОГОВАЯ ТАБЛИЦА

| Сегмент | Sally (задеплоено) | Ярик+Соня (не деплоено) | Bravo Round 1 | Лучший | Действие |
|---------|-------------------|------------------------|---------------|--------|----------|
| **INFPLAT** | Name-dropping, feature-dump | HYP A "Stop Building Scrapers" / HYP B "Ship Features Faster" | "Verified vs estimated" challenge | **Ярик+Соня HYP A** | Деплоить as-is, A/B с HYP B |
| **IMAGENCY** | Generic API pitch (не для агентств) | HYP A "Cut Research Time" / HYP B "White-Label Your Data" | Не писали | **Ярик+Соня HYP B** | Деплоить as-is, minor edit в Touch 1 опционально |
| **AFFPERF** | Generic (вообще нерелевантен) | HYP A "Affiliates→Creators" / HYP B "Build vs Buy" | Не писали | **Ярик+Соня HYP A** | Деплоить с minor CTA tweak, A/B с HYP B |
| **PR Firms** | Name-dropping, технически сломана | Нет | Problem-first rewrite | **Никто** | УБИТЬ сегмент |

---

## 5. ЧТО BRAVO СДЕЛАЛ ПРАВИЛЬНО В ROUND 1

Чтобы не впасть в overcorrection -- вот что из Round 1 подтверждается:

1. **Диагноз name-dropping = conflict of interest.** Абсолютно верно для PR firms и IM_PLATFORMS. Sally деплоила оба с name-dropping, и оба провалились.
2. **"Kill PR firms" -- правильно.** Round 3 data подтвердила и усилила: не просто messaging problem, а technical failure + ICP mismatch.
3. **Reply scripts -- правильный #1 приоритет.** 24 actionable leads без скриптов = сделки, умирающие прямо сейчас. Это подтверждено Round 3.
4. **"API Buyers vs Tool Buyers" сегментация.** 4/5 strong fits = API buyers. Подтверждено. Ярик+Соня INFPLAT -- это именно сиквенс для API buyers.
5. **Competitive positioning gap.** "How are you different from HypeAuditor?" -- скрипта нет до сих пор. Правильно идентифицировано.
6. **Step 4 kill.** Round 3 подтвердил: 680 sends, 1 reply. Перенаправление на Step 1 = 30x lift.
7. **Meeting show rate improvement.** Reminder 24h before -- простое действие, правильная рекомендация.

---

## 6. ОБНОВЛЁННЫЙ ПРИОРИТЕТ ДЕЙСТВИЙ (POST-CORRECTION)

### #1. ОСТАНОВИТЬ PR FIRMS + УБИТЬ STEP 4 (без изменений vs Round 3)
15 мин. Domain damage прекращается немедленно.

### #2. ДЕПЛОИТЬ REPLY SCRIPTS (без изменений vs Round 1)
2-3 часа. 24 actionable leads ждут.

### #3. ДЕПЛОИТЬ Ярик+Соня INFPLAT HYP A (НОВОЕ)
30 мин. Заменяет Sally IM_PLATFORMS variant в SmartLead. Problem-first хук вместо name-dropping.

### #4. NEGATIVE FILTERS + EMAIL VERIFICATION (без изменений vs Round 3)
2-3 часа. Убирает 11% wrong person + ICP mismatches до загрузки.

### #5. ДЕПЛОИТЬ Ярик+Соня IMAGENCY HYP B + AFFPERF HYP A (НОВОЕ)
1 час. Два новых сегмента с problem-first messaging.

### #6. WANNA TALK ABM (понижен vs Round 1, без изменений vs Round 3)
10 часов research. Только после #3-4.

### #7. СОКРАТИТЬ СИКВЕНС ДО 2 ШАГОВ (без изменений vs Round 3)
30 мин. Steps 3-4 -> new contacts на Step 1 = 7x improvement.

---

## 7. ГЛАВНЫЙ ВЫВОД

**Проблема OnSocial outreach -- не в отсутствии правильного copy. Правильное copy существует. Проблема -- в coordination gap между теми, кто пишет copy (Ярик+Соня) и теми, кто его деплоит (Sally).**

Sally задеплоила свои generic варианты и name-dropping sequences напрямую в SmartLead. Ярик+Соня написали сегмент-специфичные problem-first сиквенсы, которые лежат в шите без движения. Bravo в Round 1 потратил время на рекомендации, которые дублировали уже существующую работу.

Самое ценное действие прямо сейчас -- не переписывать copy (оно есть), а ЗАДЕПЛОИТЬ то, что уже написано. Ярик+Соня INFPLAT HYP A, IMAGENCY HYP B, AFFPERF HYP A -- три готовых сиквенса, протестированных на бумаге, с A/B парами. Деплой займёт 1-2 часа. Expected impact при 2x improvement vs generic: +5-10 actionable replies в месяц = +2-4 meetings.

---

*Team Bravo Correction Round. Все оценки основаны на: sequences-all.md (все версии copy), team-bravo.md (Round 1 analysis), team-bravo-update.md (Round 3 data). Ключевая коррекция: мы изобретали велосипед в Round 1, не зная что Ярик+Соня уже написали лучшие варианты.*
