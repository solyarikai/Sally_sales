# TEAM ALPHA — Correction Round: Честное сравнение трёх версий

**Дата:** 2026-03-16
**Контекст:** Обнаружено, что Ярик + Соня ПАРАЛЛЕЛЬНО написали сегмент-специфичные sequences (INFPLAT, IMAGENCY, AFFPERF), которые НИКОГДА не деплоились. Sally задеплоила свои generic sequences и PR/IM_PLATFORMS варианты без координации.

---

## 0. САМОКРИТИКА: ЧТО Я ПОЛУЧИЛ НЕПРАВИЛЬНО

**Главная ошибка Round 1: я критиковал "feature-dump messaging" как если бы это была единственная версия.**

В Round 1 я написал:

> "Every sequence opens with 'We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles...' This is a product spec, not a cold email."

> "Subject lines are equally generic ('450M influencer profiles for {{company_name}}') and read like a vendor pitch."

Это было 100% правильно -- но я приписал эту проблему ВСЕЙ команде. На самом деле это проблема ТОЛЬКО Sally's sequences. Ярик + Соня УЖЕ написали problem-first альтернативы с вопросами-хуками -- именно то, что я рекомендовал.

**Я фактически рекомендовал то, что уже было готово, и никто этого не заметил, потому что никто не сравнил версии.**

Вторая ошибка: я предложил свои rewrites как "решение", не проверив, существуют ли уже внутренние альтернативы. Мой "Rewrite for PLATFORMS" очень похож на INFPLAT HYP A Ярика+Сони. Мой "Rewrite for AGENCIES" -- почти копия IMAGENCY HYP A. Я переизобрёл колесо.

---

## 1. PLATFORMS (CTO/VP Eng/Head of Product)

### Три версии бок о бок

| Элемент | Sally (deployed) | Ярик+Соня INFPLAT HYP A | Мой rewrite (Round 1) |
|---------|-----------------|--------------------------|----------------------|
| **Subject** | "{{first_name}}, 450M influencer profiles are ready for your API" | "Creator data API for {{company_name}}" | "question about creator data at {{company_name}}" |
| **Открытие** | "We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles..." | "How are you currently handling creator data infrastructure at {{company_name}}?" | "Quick question -- is {{company_name}} still maintaining its own creator data pipeline, or have you moved to a third-party provider?" |
| **Структура** | Feature list -> benefit claim -> routing CTA | Вопрос -> позиционирование -> soft CTA | Вопрос -> social proof (1 customer) -> soft CTA |
| **CTA** | "Who at {{company_name}} handles product or data partnerships?" | "Would you be open to a 15-minute call to explore how this could work?" | "happy to show you the actual API output in 15 min. If not, no worries" |
| **Тон** | Vendor pitch | Peer conversation | Peer conversation, чуть расслабленнее |

#### Sally IM_PLATFORMS variant (deployed):

| Элемент | IM_PLATFORMS |
|---------|-------------|
| **Открытие** | "We power creator data for platforms like {{company_name}} -- Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API." |
| **Проблема** | Name-dropping + feature list |
| **CTA** | "I can pull a live demo with your required volume, geo, and other filters on a call -- worth a look?" |

### Вердикт: PLATFORMS

**1. Лучшая версия: Ярик+Соня INFPLAT**

Почему:
- **HYP A** ("Stop Building Scrapers") открывает ВОПРОСОМ, который попадает в реальную боль CTO -- in-house scraping pipelines. Это не generic "tell me about your data" -- это конкретная проблема, которую CTO узнает за 3 секунды.
- **HYP B** ("Ship Features Faster") бьёт по Product-боли -- "how long does it take to ship a new analytics feature?" Это вопрос, на который PM/VP Product ответит рефлекторно.
- Обе гипотезы имеют РАЗНЫЕ углы атаки для A/B-теста. Sally's TEST A vs TEST B -- это просто длинная vs. короткая версия ОДНОГО И ТОГО ЖЕ сообщения. Ярик+Соня тестируют РАЗНЫЕ боли.
- Follow-ups (Touch 2, Touch 3) добавляют новый контент, а не повторяют. Touch 2 = скорость интеграции. Touch 3 = конкретные проблемы (data freshness, coverage).

Почему не мой rewrite: Мой вариант по структуре хорош, но у Ярика+Сони есть два преимущества -- (a) они написали 2 гипотезы для тестирования, я написал 1, и (b) их гипотезы точнее бьют в конкретные боли (scrapers, ship speed), а мой вопрос более generic ("still maintaining your own pipeline or moved to third-party?").

Почему НЕ Sally: Feature-dump. Открывает с продукта. Subject line = "450M profiles" (никого не интересует число, пока нет контекста боли). CTA = routing question ("who handles partnerships?"), что сигнализирует "я не знаю кому писать". IM_PLATFORMS variant ещё хуже -- name-drops "Modash, Captiv8..." (если это неправда -- credibility bomb, если правда -- всё равно плохо как opener, потому что лид думает "зачем мне ваш API если у конкурентов он уже есть").

**2. Деплоить первым: INFPLAT HYP A ("Stop Building Scrapers")**

Причины:
- Engineering pain (scrapers) более universal, чем product pain (feature shipping speed)
- CTO/VP Eng это узнает мгновенно -- каждый, кто строил scraping pipeline, знает этот ад
- Менее рискованно как первый тест: вопрос + мягкий CTA = низкий барьер для ответа
- HYP B оставить для второй волны, когда HYP A соберёт baseline

**3. Что украсть из других версий:**

| Откуда | Что забрать | Куда поставить |
|--------|------------|----------------|
| Мой rewrite | "If not, no worries -- just curious how you're handling it" -- soft exit. Снижает давление. | Добавить в конец Touch 1 INFPLAT |
| Мой rewrite | Упоминание конкретного customer name + outcome ("switched from in-house scraping, cut 3 months of backlog") | Touch 2 INFPLAT -- заменить generic "most platforms go live in under a week" на конкретный пример |
| Sally IM_PLATFORMS | "I can pull a live demo with your required volume, geo, and other filters" -- конкретный CTA | Touch 2 или 3 INFPLAT, как альтернативный CTA |
| Мой subject line | "question about creator data at {{company_name}}" -- curiosity-driven | Тестировать как альтернативу INFPLAT subject line |

**4. Что в моих Round 1 рекомендациях было НЕПРАВИЛЬНО:**

- Я рекомендовал "переписать Step 1 для всех сегментов" -- но Step 1 для платформ УЖЕ был переписан Яриком+Соней. Проблема была не в отсутствии хорошего copy, а в том, что ДЕПЛОИЛСЯ copy Sally.
- Мой subject line "question about creator data" -- лучше Sally's "450M profiles", но INFPLAT "Creator data API for {{company_name}}" тоже нормальный (хотя мог бы быть curiosity-driven, а не descriptive).
- Я не заметил, что у Sally есть IM_PLATFORMS variant с name-dropping. Не предупредил о риске этого приёма.

---

## 2. AGENCIES (CEO/Founder/Head of IM)

### Три версии бок о бок

| Элемент | Sally (deployed) | Ярик+Соня IMAGENCY HYP A | Мой rewrite (Round 1) |
|---------|-----------------|---------------------------|----------------------|
| **Subject** | "450M influencer profiles for {{company_name}}" | "Cut creator research time at {{company_name}}" | "creator vetting -- how long per campaign?" |
| **Открытие** | "We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles..." | "How many hours does your team spend sourcing creators per campaign at {{company_name}}?" | "How long does it take {{company_name}}'s team to vet a creator shortlist for a campaign -- the real vetting, not just checking follower counts?" |
| **Value prop** | Feature list (credibility scoring, demographics, fraud, overlap) | "Cut that to under 2 hours -- 27 filters, audience demographics, credibility scores" | "agencies that cut that from 2 days to under 2 hours" |
| **CTA** | "Who handles product or data partnerships?" | "Would you be open to a 15-minute call?" | "show you a sample report on any creator you pick -- takes 15 min" |

#### Ярик+Соня IMAGENCY HYP B ("White-Label Your Data"):

| Элемент | HYP B |
|---------|-------|
| **Открытие** | "When {{company_name}}'s clients ask for audience data on a creator, what do you show them?" |
| **Angle** | Revenue / brand pain: agencies losing clients to in-house, white-label = retention tool |
| **Touch 2** | "Brands are moving creator selection in-house. The agencies keeping clients offer proprietary analytics." |

### Вердикт: AGENCIES

**1. Лучшая версия: НИЧЬЯ между Ярик+Соня IMAGENCY и моим rewrite. Разные сильные стороны.**

IMAGENCY HYP A vs мой rewrite -- почти идентичны по структуре:
- Оба открывают вопросом о времени на sourcing/vetting
- Оба обещают сокращение до 2 часов
- Оба используют мягкий CTA

Разница:
- Мой вариант добавляет уточнение "the real vetting, not just checking follower counts" -- это показывает экспертизу и отсекает поверхностный ответ. Преимущество: мой.
- IMAGENCY конкретнее в value prop: "27 filters, audience demographics, credibility scores, all white-label ready" vs мой более generic "real audience data (city-level demographics, fraud scores, audience overlap)". Паритет.
- IMAGENCY Touch 2 про audience overlap -- СИЛЬНЫЙ follow-up. "Check if they share 60% of the same followers. Catches bad matches before the brief goes out." Конкретный, визуальный, понятный. Преимущество: Ярик+Соня.
- Мой добавляет escape hatch: "If it's already solved, I'll get out of your inbox." Преимущество: мой.

**НО: IMAGENCY HYP B -- это отдельная сильная гипотеза**, которой у меня нет аналога. "When clients ask for audience data, what do you show them?" + "Brands are moving creator selection in-house" -- это strategic fear-based hook, не operational. Для CEO/Founder это может быть мощнее, чем "сколько часов тратите" (operational efficiency -- это боль менеджера, не CEO).

**2. Деплоить первым: IMAGENCY HYP B ("White-Label Your Data")**

Контринтуитивный выбор. Объясняю:
- HYP A (efficiency) и мой rewrite (vetting time) бьют по операционной боли. Это работает для Head of IM, но CEO/Founder думает стратегически.
- HYP B бьёт по СТРАТЕГИЧЕСКОЙ боли: "клиенты уходят in-house, вы теряете revenue". Для founder agency это экзистенциальный страх.
- Touch 2 HYP B = "The agencies keeping clients offer proprietary analytics their clients can't get on their own" -- это positioning insight, не feature pitch.
- Риск: если agency маленькая (< 20 people), белая этикетка им не нужна. Поэтому ФИЛЬТР по размеру (20+ employees) обязателен для HYP B.

Fallback: если HYP B не работает (reply rate < 1% после 100 sends), переключить на HYP A (operational pain) -- это более safe bet.

**3. Что украсть:**

| Откуда | Что забрать | Куда |
|--------|------------|------|
| Мой rewrite | "the real vetting, not just checking follower counts" -- уточнение к вопросу | HYP A Touch 1 -- добавить после вопроса о часах |
| Мой rewrite | "If it's already solved, I'll get out of your inbox" -- escape hatch | HYP A и HYP B Touch 1 -- добавить в конец |
| IMAGENCY HYP A Touch 2 | "Check if they share 60% of the same followers" -- конкретный use case | Добавить в мой rewrite как Touch 2, если бы его деплоили |
| IMAGENCY HYP B Touch 2 | "Brands are moving creator selection in-house" -- strategic fear | Standalone value -- не трогать |
| Sally's deployed | НИЧЕГО. Sally's agency sequence -- тот же generic feature-dump, что и для platforms. Ноль сегмент-специфики. |

**4. Что в моих Round 1 рекомендациях было НЕПРАВИЛЬНО:**

- Я написал ОДИН rewrite для agencies. Ярик+Соня написали ДВА с разными углами (operational vs. strategic). Мой подход беднее.
- Мой rewrite для agencies почти дублирует IMAGENCY HYP A. Я потратил время на изобретение того, что уже существовало.
- Я НЕ предложил white-label angle вообще. Ярик+Соня увидели то, что я пропустил: для agency founder потеря клиентов страшнее, чем неэффективный sourcing.

---

## 3. PR FIRMS

### Три версии бок о бок

| Элемент | Sally (deployed) | Ярик+Соня | Мой rewrite (Round 1) |
|---------|-----------------|-----------|----------------------|
| **Subject** | (нет данных -- не в sequences-all) | НЕТ ВЕРСИИ | (встроен в rewrite) |
| **Открытие** | "We power creator data for PR firms like {{company_name}} -- NeoReach, Buttermilk, Gushcloud, Influencer.com, and Obviously all run on our API." | -- | "When {{company_name}} recommends a creator to a brand client, how confident are you in the audience data behind that recommendation?" |
| **Social proof** | Name-drops 5 компаний | -- | "PR firms we work with kept getting burned -- creator looked great on paper, but 40% of followers were fake" |
| **CTA** | "Pick a creator you're currently considering -- I'll pull the full breakdown on a call" | -- | "I'll pull a live report on any creator you're currently considering" |

### Вердикт: PR FIRMS

**1. Лучшая версия: Мой rewrite -- по умолчанию, потому что Ярик+Соня не писали PR version.**

Но мой rewrite НЕ идеален. Проблемы:
- "PR firms we work with kept getting burned" -- generic social proof без имён. Если есть реальные PR-клиенты, надо назвать хотя бы одного.
- "40% of followers were fake" -- конкретная цифра, но не привязана к конкретному case. Звучит как выдумка.

Sally's PR version ещё хуже:
- Name-dropping "NeoReach, Buttermilk, Gushcloud..." -- КРИТИЧЕСКИЙ РИСК. Если это не реальные клиенты, одно forward к коллеге в индустрии = уничтоженная репутация. В Round 1 я уже предупреждал: "If they are not actual customers, this is a credibility bomb." Этот риск РЕАЛИЗОВАЛСЯ -- кампания задеплоена с этими claims.
- "You'll get more data at a better cost than whatever provider you're using today" -- пустое обещание. У лида нет причин верить.
- Step 2 лучше: "paying too much for incomplete data, or wasting hours validating profiles manually" -- это problem-first, но ПОСЛЕ feature-dump opener. Порядок убивает эффект.

**2. Деплоить первым: Мой rewrite, НО с доработками.**

PR firms кампания СЛОМАНА (17 Step 1 sends, 10.6% bounce -- Round 3 data). Сначала чинить инфраструктуру, потом деплоить messaging. Когда будет готово:
- Использовать мой rewrite как базу
- Адаптировать по модели IMAGENCY: 2 гипотезы (confidence pain vs. efficiency pain)

**3. Что украсть / доработать:**

| Откуда | Что | Куда |
|--------|-----|------|
| Sally Step 2 | "paying too much for incomplete data, or wasting hours validating profiles manually" | Превратить в Touch 1 opener (вопрос), а не оставлять в Step 2 |
| Sally Step 2 | "If {{company_name}} has a fast, accurate sourcing workflow already, I'll leave you alone" -- escape hatch | Добавить в мой rewrite |
| Sally Step 1 | "Pick a creator you're currently considering -- I'll pull the full breakdown" -- хороший CTA | Уже есть в моём rewrite. Сохранить. |
| IMAGENCY HYP B structure | Два угла: operational vs. strategic | Создать PR HYP B: "When clients ask why a creator underperformed, what data do you show them?" (accountability angle) |

**4. Что в моих Round 1 рекомендациях было НЕПРАВИЛЬНО:**

- Я недостаточно жёстко осудил name-dropping. Написал "if they are not actual customers, this is a credibility bomb" -- но не дал прямую рекомендацию УБРАТЬ эти имена из deployed sequence. Sally's PR variant работает прямо сейчас с этими claims.
- Я не предложил 2 гипотезы для PR (как Ярик+Соня сделали для других сегментов). Мой rewrite -- 1 угол. Для тестирования нужны минимум 2.
- Я написал "PR firms -- statistical non-event, don't kill yet" (Round 1). В Round 3 я исправился: "campaign BROKEN". Но если бы я изначально проверил step-by-step data, увидел бы 17 Step 1 sends и 10.6% bounce сразу.

---

## 4. AFFILIATE & PERFORMANCE (AFFPERF)

У Sally НЕТ отдельной AFFPERF кампании. У меня в Round 1 НЕТ отдельного rewrite для AFFPERF. Только Ярик+Соня написали dedicated sequences.

### Оценка Ярик+Соня AFFPERF

**HYP A ("Affiliates Are Becoming Creators"):**
- Opener: "What percentage of {{company_name}}'s partners are also content creators?" -- ОТЛИЧНЫЙ вопрос. Заставляет задуматься. Большинство affiliate-платформ не отслеживают это, но интуитивно знают, что convergence происходит.
- Touch 2: "Later acquired Mavely for $250M" -- конкретный market signal. НО: дата "2026" в контексте может означать, что это уже случилось, и лид может знать этот факт. Проверить актуальность.
- Touch 3: Стандартная "2 problems" формула. Работает.

**HYP B ("Build vs Buy"):**
- Opener: "If {{company_name}} wanted to show clients which partners have real vs. fake followers -- would you build that in-house?" -- ПРОВОКАЦИОННЫЙ вопрос. CTO/VP Product знает ответ: "нет, это слишком дорого". Вопрос создаёт mental framework, в котором OnSocial = очевидный ответ.
- Touch 2: Technical specifics (one endpoint, one handle). Хорошо для CTO аудитории.
- Touch 3: "6+ months to build" -- конкретный time frame. Работает.

**Вердикт: HYP B сильнее.** "Build vs buy" -- это framework, который CTO/VP Product используют ежедневно. Вопрос попадает в существующий mental model. HYP A ("convergence") -- более стратегический, для CEO. Тестировать оба, но начать с HYP B для CTO-аудитории.

**Что в Round 1 было неправильно:** Я рекомендовал "Launch AFFPERF campaign this week" (Стратег R2), но предлагал использовать "AFFPERF HYP A sequence (modified per Copywriter recommendations)". Какие "Copywriter recommendations"? У меня НЕ БЫЛО rewrite для AFFPERF! Я дал рекомендацию без конкретного copy. Ярик+Соня уже написали оба варианта -- их sequences готовы к деплою.

---

## 5. СВОДНАЯ ТАБЛИЦА РЕШЕНИЙ

| Сегмент | Лучший вариант | Деплоить первым | Деплоить AS-IS? | Что доработать |
|---------|---------------|-----------------|-----------------|----------------|
| **Platforms** | Ярик+Соня INFPLAT | HYP A ("Stop Building Scrapers") | Почти AS-IS | +soft exit ("if not, no worries"), +конкретный customer name в Touch 2, тестировать curiosity subject line |
| **Agencies** | Ярик+Соня IMAGENCY | HYP B ("White-Label") | Почти AS-IS | +escape hatch, +фильтр 20+ employees обязателен для HYP B |
| **PR Firms** | Мой rewrite (единственный problem-first) | Мой rewrite + новая HYP B | НЕТ, нужна доработка | Написать 2-ю гипотезу, убрать fake social proof из Sally's, сначала починить инфраструктуру |
| **Affiliate** | Ярик+Соня AFFPERF | HYP B ("Build vs Buy") | Почти AS-IS | Проверить актуальность Mavely/$250M reference в HYP A |

---

## 6. ОБЩИЙ ВЕРДИКТ: ДОЛЖНЫ ЛИ SEQUENCES ЯРИКА+СОНИ ДЕПЛОИТЬСЯ AS-IS?

**Короткий ответ: ДА, с минимальными правками.**

Развёрнутый ответ:

**Сильные стороны sequences Ярика+Сони (vs. Sally и vs. мои):**
1. **Problem-first hooks** -- каждая sequence открывает вопросом, не feature-dump'ом
2. **Два угла на сегмент** (HYP A + HYP B) -- позволяет A/B-тестировать РАЗНЫЕ боли, а не длинный vs. короткий текст
3. **Segment-specific language** -- "scrapers" для CTO, "sourcing creators" для agency CEO, "partners vs creators" для affiliate
4. **Follow-ups добавляют контент** -- каждый Touch несёт новую мысль, а не повторяет

**Что доработать перед деплоем (МИНИМУМ):**

| Доработка | Приоритет | Время |
|-----------|-----------|-------|
| Добавить escape hatch ("if not, no worries" / "I'll leave you alone") в Touch 1 каждой sequence | Высокий | 10 мин |
| Заменить generic social proof на 1 конкретный customer name + outcome (если есть реальный клиент) | Средний | 15 мин |
| Убрать {{calendar_link}} из HYP B sequences, если календарь не настроен | Высокий | 5 мин |
| Проверить, что A/B testing protocol (50 contacts per send, 100 per variant) реалистичен для каждого сегмента | Средний | 30 мин |

**Что НЕ доработывать (оставить AS-IS):**
- Subject lines -- достаточно хороши. Не идеальны, но тестировать нужно с данными, а не с мнениями.
- Touch 2-3 structure -- "2 problems" formula в Touch 3 работает. Не ломать.
- CTA style -- мягкие CTA ("worth a quick chat?") правильный выбор для cold outreach. Не менять на aggressive.

---

## 7. ЧЕСТНЫЙ СПИСОК МОИХ ОШИБОК В ROUND 1

| # | Ошибка | Серьёзность | Что нужно было сделать |
|---|--------|-------------|----------------------|
| 1 | **Критиковал "feature-dump messaging" как проблему ВСЕЙ команды, когда это была проблема ТОЛЬКО Sally's sequences** | ВЫСОКАЯ | Спросить: "кто написал какой sequence?" перед критикой. Атрибуция авторства = first step. |
| 2 | **Написал rewrites, которые дублируют существующие sequences Ярика+Сони** | СРЕДНЯЯ | Проверить ВСЕ версии в data room перед написанием альтернатив. |
| 3 | **Рекомендовал "Launch AFFPERF" без написания copy для AFFPERF** | СРЕДНЯЯ | Copy уже было. Надо было просто сказать: "деплойте то, что есть." |
| 4 | **Не предложил white-label angle для agencies** | СРЕДНЯЯ | Ярик+Соня увидели strategic fear (client loss), я увидел только operational pain (research time). Узкий lens. |
| 5 | **Недостаточно жёстко осудил name-dropping в PR/IM_PLATFORMS** | ВЫСОКАЯ | Надо было написать: "НЕМЕДЛЕННО убрать имена компаний из deployed sequences, если это не подтверждённые клиенты. Credibility risk = existential." |
| 6 | **Не спросил, почему сегмент-специфичные sequences не задеплоены** | ВЫСОКАЯ | Это ОРГАНИЗАЦИОННАЯ проблема, не copywriting. Sally деплоит без координации с Яриком+Соней. Process fix > copy fix. |

---

## 8. РЕКОМЕНДАЦИЯ ПО ПРОЦЕССУ (новая, из Round 1 не было)

Главная находка Correction Round: **проблема не в том, ЧТО написано, а в том, КТО деплоит и ПОЧЕМУ хорошие версии лежат мёртвым грузом.**

1. **Sally деплоит свои generic sequences без согласования** -- результат: feature-dump messaging в production, problem-first sequences Ярика+Сони лежат в доке.
2. **Нет процесса approve перед деплоем** -- Sally создала PR firms и IM_PLATFORMS variants напрямую в SmartLead, "не из шита". Это значит, что sequence tracking разорван.
3. **Нет single source of truth** -- sequences-all.md содержит всё, но Sally деплоит "не из шита". SmartLead = реальность, док = намерение. Они расходятся.

**Действие:** Ввести правило -- ЛЮБОЙ новый sequence или изменение проходит через sequences-all.md + approve Ярика/Сони ПЕРЕД загрузкой в SmartLead. Иначе будет продолжаться ситуация, где лучшие sequences лежат в доке, а в production работает feature-dump.

---

*Correction Round prepared by Team Alpha. Этот документ -- честная ревизия Round 1 с учётом информации об авторстве sequences и существовании незадеплоенных альтернатив.*
