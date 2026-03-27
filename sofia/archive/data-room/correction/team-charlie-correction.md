# TEAM CHARLIE -- CORRECTION ROUND

**Дата:** 2026-03-16
**Контекст:** Новая информация о авторстве секвенций. Sally (агентство) писала generic sequences (Framework 1: TEST A/B), задеплоенные в SmartLead. Ярик + Соня написали 3 сегментных фреймворка (INFPLAT, IMAGENCY, AFFPERF) -- ни разу не деплоились. Sally также задеплоила PR_FIRMS и IM_PLATFORMS варианты без координации.

---

## 1. ROI СРАВНЕНИЕ: ДЕПЛОЙ СУЩЕСТВУЮЩИХ vs. НАПИСАНИЕ НОВЫХ

### Вариант A: Адаптировать и задеплоить секвенции Ярика+Сони (1-2ч)

**Что есть:**
- **INFPLAT** (HYP A: "Stop Building Scrapers", HYP B: "Ship Features Faster") -- problem-first hooks, открывающие вопросы, 3-touch структура
- **IMAGENCY** (HYP A: "Cut Research Time", HYP B: "White-Label Your Data") -- problem-first hooks, конкретные pain points агентств
- **AFFPERF** (HYP A: "Affiliates -> Creators", HYP B: "Build vs Buy") -- отраслевой контекст (Later/Mavely, Sprout/Tagger), build-vs-buy framing

**Что нужно адаптировать (1-2ч):**
- Проверить/обновить social proof (убедиться что клиенты актуальны)
- Добавить calendar links ({{calendar_link}} уже прописан в HYP B, но не в HYP A)
- Настроить SmartLead кампании (3 кампании x 2 варианта = настройка шедулинга)
- Убрать Step 4 (по выводам Round 3: 680 sends = 1 reply = 0 actionable)

**Ожидаемый результат:**
- Секвенции Ярика+Сони УЖЕ используют problem-first подход -- именно то, что все 4 команды рекомендовали как #8 в FINAL-SYNTHESIS
- INFPLAT HYP A открывается вопросом "How are you currently handling creator data infrastructure?" -- это ровно тот паттерн, который Delta назвала лучшим и который получил 9/10 от трех команд
- IMAGENCY HYP A: "How many hours does your team spend sourcing creators per campaign?" -- прямой вопрос о боли
- AFFPERF HYP A: "What percentage of partners are also content creators?" -- relevance hook

### Вариант B: Написать новые rewrites с нуля (3-4ч)

**Что получим:**
- Возможность интегрировать ВСЕ лучшие находки (Delta's buyer monologue, Bravo's API/Tool Buyer сегментацию, "reverse demo" идею)
- Оптимизированный Step 2 (micro-case study) и Step 3 (contrarian insight) по Delta's framework
- Возможность учесть Round 3 данные (actionable rate 0.25%, OOO 63.6%)

**Что потеряем:**
- 2 дополнительных часа -- при том что 91 OOO лид, 66 незалогированных reply, 24 actionable лида ждут отработки ПРЯМО СЕЙЧАС
- Эти 2 часа при текущей unit economics = потенциально 1-2 потерянных лида (каждый день задержки снижает conversion probability)

### ВЕРДИКТ: Вариант A выигрывает. ROI = 3-5x выше.

**Математика:**

| Параметр | Вариант A (адаптация) | Вариант B (новые rewrites) |
|----------|----------------------|---------------------------|
| Время до деплоя | 1-2 часа | 3-4 часа |
| Качество Step 1 | 85-90% от идеала (problem-first уже есть) | 95-100% от идеала |
| Дельта в качестве | 5-15% | -- |
| Стоимость задержки | Низкая | 2 часа x SDR rate + opportunity cost |
| Время до первых данных | ~3 дня (деплой -> первые ответы) | ~5 дней |
| A/B тестирование | Встроено (HYP A vs HYP B в каждом фреймворке) | Нужно писать варианты отдельно |

**Ключевой аргумент:** Секвенции Ярика+Сони закрывают 80% замечаний из FINAL-SYNTHESIS:
1. Problem-first hooks -- ЕСТЬ (открывающие вопросы)
2. Сегментная специфика -- ЕСТЬ (3 фреймворка для 3 сегментов)
3. A/B варианты -- ЕСТЬ (HYP A / HYP B)
4. Конкретные pain points -- ЕСТЬ ("Stop Building Scrapers", "White-Label Your Data")

Чего НЕ хватает (и можно добавить итеративно через 1-2 недели):
- Delta's "buyer monologue" оптимизация тона
- Micro-case study в Step 2 (у Ярика+Сони Step 2 -- всё ещё feature-oriented)
- Contrarian insight в Step 3 (у них Step 3 -- summary/recap)
- "No call needed" опция

**РЕКОМЕНДАЦИЯ:** Деплоить Ярика+Соню как v1.0 СЕГОДНЯ. Собрать данные за 1-2 недели. Итерировать на основе реальных результатов, а не гипотез.

---

## 2. РЕЙТИНГ ПО СЕГМЕНТАМ: SALLY vs. ЯРИК+СОНЯ vs. НАШИ REWRITES

### 2.1 INFPLAT (Influencer Platforms & SaaS)

| Rank | Автор | Expected Actionable Rate | Обоснование |
|------|-------|-------------------------|-------------|
| **1** | **Наши rewrites (FINAL-SYNTHESIS #8)** | **1.3-1.8%** | Delta's buyer monologue + problem-first + "ignore this" trust signal + 1 proof point. Максимально оптимизировано под CTO mindset. |
| **2** | **Ярик+Соня INFPLAT** | **0.9-1.4%** | Problem-first ("How are you handling creator data infrastructure?"), но Step 1 всё ещё содержит mini-pitch ("we replace in-house scraping pipelines with a single API endpoint"). Вопрос хороший, но ответ на него дан сразу -- не оставляет пространства для диалога. HYP B ("Ship Features Faster") более агрессивна но менее persona-specific. |
| **3** | **Sally (Framework 1 TEST B -- flagship)** | **0.8-1.0%** (текущие 1.01% actionable) | Feature-dump, но работает за счёт social proof ("Modash, Captiv8...") и чистой формулировки. TEST B (shorter/punchier) доказанно лучше TEST A. Проблема: не дифференцирует по сегментам -- один messaging для всех. |
| **4** | **Sally (IM_PLATFORMS variant)** | **0.3-0.5%** (текущие данные: 2 actionable из 649) | Тот же social proof + feature-dump, но задеплоена без координации. Step 2 ("paying too much or wasting hours") -- первый намек на problem-first, но слишком generic. |

**Вывод по INFPLAT:** Ярик+Соня дают ~30-40% lift vs. Sally flagship. Наши rewrites дают ещё ~30-40% поверх. Но разница между Яриком+Соней и нашими rewrites (~0.4% actionable rate) при 500 контактов = 2 дополнительных лида. За 2 лида мы "платим" 2 дополнительных часа работы. ROI адаптации Ярика+Сони выше.

### 2.2 IMAGENCY (IM-First Agencies)

| Rank | Автор | Expected Actionable Rate | Обоснование |
|------|-------|-------------------------|-------------|
| **1** | **Наши rewrites (FINAL-SYNTHESIS)** | **1.0-1.5%** | Fear-of-loss ("агентство потеряло клиента из-за 60% overlap") -- сильнейший эмоциональный триггер для CEO агентства. "Tool" вместо "API". Конкретный сценарий. |
| **2** | **Ярик+Соня IMAGENCY** | **0.7-1.2%** | HYP A ("Cut Research Time") -- хороший efficiency angle, но "сэкономьте 6 часов" слабее чем "потеряйте клиента". HYP B ("White-Label Your Data") -- отличный revenue angle ("brands are moving creator selection in-house, agencies keeping clients offer proprietary analytics"). Это сильнее, чем Delta's fear-of-loss для определённой подсегмента. |
| **3** | **Sally (Framework 1)** | **0.3-0.5%** | Вообще не различает агентства от платформ. "API endpoint", "data pipeline" -- язык для CTO, не для CEO агентства. Работает только за счёт брутфорс-объёмов. |

**Вывод по IMAGENCY:** HYP B Ярика+Сони ("White-Label") -- неожиданно сильная для sub-сегмента агентств, теряющих клиентов из-за in-house movement. Может оказаться ЛУЧШЕ наших rewrites для этого конкретного pain point. Рекомендация: деплоить обе гипотезы, не выбирать одну.

### 2.3 AFFPERF (Affiliate & Performance)

| Rank | Автор | Expected Actionable Rate | Обоснование |
|------|-------|-------------------------|-------------|
| **1** | **Ярик+Соня AFFPERF** | **0.6-1.0%** | HYP A ("Affiliates -> Creators") -- с отраслевым контекстом (Later/Mavely $250M, Sprout/Tagger). Это ЕДИНСТВЕННАЯ секвенция, которая объясняет ЗАЧЕМ affiliate платформе creator data. HYP B ("Build vs Buy") -- классический technical framing ("6+ months to build, days to integrate"). impact.com = доказанный strong fit из этого сегмента. |
| **2** | **Наши rewrites** | **Не написаны** | В FINAL-SYNTHESIS нет dedicated AFFPERF rewrite. Мы рекомендовали "микро-тест 200 лидов на неделе 3" но не написали копию. Ярик+Соня -- ЕДИНСТВЕННАЯ готовая опция. |
| **3** | **Sally** | **Не существует для AFFPERF** | Generic Framework 1 не адресует affiliate/performance вообще. |

**Вывод по AFFPERF:** Здесь нет выбора. Ярик+Соня = единственный готовый вариант. И он ХОРОШИЙ: отраслевой контекст, M&A references, build-vs-buy -- всё это работает для CTO/VP Product affiliate платформы. impact.com (strong fit) валидирует сегмент.

### 2.4 PR FIRMS

| Rank | Автор | Expected Actionable Rate | Обоснование |
|------|-------|-------------------------|-------------|
| **1** | **Наши rewrites (FINAL-SYNTHESIS)** | **0.5-1.0%** | "Earned media" framing, "vetting and credibility" (PR-язык), конкретный output example ("87% real, 62% female"). Единственная версия, которая говорит с PR-фирмой на ЕЁ языке. |
| **2** | **Sally (PR_FIRMS variant)** | **0.00%** (0 actionable из 17+263 sends) | NeoReach, Buttermilk, Gushcloud -- это НЕ PR-фирмы. Social proof нерелевантен. 10.6% bounce rate. Кампания технически сломана. |

**Вывод по PR FIRMS:** Ярик+Соня не писали PR-секвенцию. Sally's версия разрушает domain reputation. Наш rewrite -- единственный вариант. Но Round 3 данные (10.6% bounce) означают: сначала 4+ недели паузы для восстановления domain, потом микро-тест 200 контактов.

---

## 3. ЧТО МЫ ОШИБЛИСЬ В ROUND 1

### Ошибка 1: АВТОРСТВО И АТРИБУЦИЯ

**Round 1:** "Все сиквенсы начинаются с фич продукта, а не с проблемы покупателя ('feature-dumping')" -- сказано как ОБЩИЙ вердикт на ВСЕ секвенции.

**Реальность:** Feature-dumping -- это Sally's Framework 1 (TEST A/B), PR_FIRMS, и IM_PLATFORMS. Секвенции Ярика+Сони (INFPLAT, IMAGENCY, AFFPERF) НЕ feature-dump -- они используют problem-first hooks с открывающими вопросами. Мы мазали всех одной краской, потому что не знали кто что писал.

**Последствия ошибки:**
- Мы рекомендовали "Переписать Step 1 ВСЕХ сиквенсов" (#8 в FINAL-SYNTHESIS, 3-4 часа) -- когда 3 из 6 фреймворков УЖЕ переписаны и ждут деплоя
- Мы оценили задачу как "WRITE" (создать с нуля), когда задача = "DEPLOY" (адаптировать и запустить готовое)
- Реальная трудоёмкость: 1-2 часа вместо 3-4

### Ошибка 2: COST ESTIMATES

**Round 1:** "#8. ПЕРЕПИСАТЬ STEP 1 ВСЕХ СИКВЕНСОВ. Усилия: 3-4 часа."

**Реальность:**
- Для INFPLAT, IMAGENCY, AFFPERF: Step 1 уже переписан. Адаптация = 1 час (проверка social proof + calendar links + настройка SmartLead). Экономия: 2-3 часа.
- Для PR FIRMS: rewrite нужен, но деплой заблокирован 4+ недельной паузой. Значит 0 часов сейчас.
- Для Generic (Sally's flagship): оставить как есть -- это ЕДИНСТВЕННЫЙ сиквенс с 1.01% actionable rate и реальными данными. Не ломать то, что работает.

**Суммарная ошибка в оценке:** Мы насчитали 3-4 часа на задачу, которая реально стоит ~1 час сейчас + 1 час через месяц. Завышение в 2-4x.

### Ошибка 3: OOO = "21 ЛИДОВ"

**Round 1:** "#6. Настроить OOO follow-up для 21 лидов. Усилия: 45 мин."

**Round 3:** OOO = 91 лид (63.6% ВСЕХ ответов). Нужно 3-4 часа.

Мы занизили объём работы в 4.3 раза, потому что полагались на Google Sheet данные (77 залогированных ответов, из них 21 OOO), а не на SmartLead (143 ответа, из них 91 OOO). Ирония: мы сами в Round 1 написали "66 unlogged replies" -- но не задали вопрос "а сколько из этих 66 -- OOO?"

### Ошибка 4: FLAGSHIP SEQUENCE = "FEATURE-DUMP, НУЖНО ПЕРЕПИСАТЬ"

**Round 1:** "Все сиквенсы feature-dump. Переписать."

**Реальность:** Flagship (Sally's TEST B) даёт 1.01% actionable rate -- это ЛУЧШИЙ результат по всем кампаниям. Да, это feature-dump. Но он РАБОТАЕТ. Вероятная причина: social proof ("Modash, Captiv8, Kolsquare...") перевешивает слабость копирайтинга. В B2B enterprise social proof может быть важнее, чем тон письма.

**Правильная рекомендация (которую мы должны были дать):** Не трогать flagship. Деплоить Ярика+Соню параллельно как challenger. Сравнить результаты через 2 недели. Только потом решать, что заменять.

### Ошибка 5: "НАПИСАТЬ НОВЫЕ" vs. "ЗАДЕПЛОИТЬ ГОТОВЫЕ"

**Round 1:** Мы предложили 4 полных rewrite (Platforms, Agencies, PR Firms, follow-up framework). Total: 3-4 часа.

**Реальность:** У Ярика+Сони готовы 3 из 4 фреймворков. Мы написали то, что уже было написано. Причина: мы не знали об авторстве. Но мы должны были СПРОСИТЬ: "Есть ли неиспользованные драфты секвенций?" Мы не задали этот вопрос -- и потратили свои ресурсы (и время читателя) на rewriting того, что уже существует.

---

## 4. ОБНОВЛЁННАЯ PRIORITY MATRIX

### Принцип: это DEPLOY задача, не WRITE задача

Новая приоритизация учитывает:
- 3 готовых фреймворка Ярика+Сони (INFPLAT, IMAGENCY, AFFPERF)
- 91 OOO (а не 21)
- Actionable rate 0.25% (а не "genuine" 0.57%)
- PR firms = domain damage (не просто "пауза")
- Flagship Sally = оставить (работает, не ломать)

| Rank | Действие | Тип задачи | Усилия | Ожидаемый результат | ROI |
|------|----------|-----------|--------|---------------------|-----|
| **1** | **Отработать 91 OOO -- систематический follow-up** | DEPLOY (Script 9 уже написан) | 3-4ч | 14 re-engaged replies -> 5 meetings | **ЭКСТРЕМАЛЬНЫЙ** -- $60-80 за 5 meetings стоимостью $325-800 каждая |
| **2** | **66 незалогированных replies + 24 actionable -- немедленный follow-up** | OPERATIONS (ручная работа + скрипты) | 3ч | 5-10 тёплых лидов -> 2-3 meetings | **ЭКСТРЕМАЛЬНЫЙ** -- чистое восстановление потерянного |
| **3** | **Задеплоить INFPLAT + IMAGENCY секвенции Ярика+Сони** | **DEPLOY, НЕ WRITE** | **1-1.5ч** | Problem-first copy в SmartLead для 2 ключевых сегментов. Expected lift: +30-50% actionable rate vs Sally generic | **ОЧЕНЬ ВЫСОКИЙ** -- 1 час дает 2 сегментных кампании |
| **4** | **ОСТАНОВИТЬ PR firms (не паузить)** | OPERATIONS (1 клик) | 5 мин | Прекращение domain damage. 10.6% bounce rate снижает deliverability ВСЕХ кампаний | **КРИТИЧЕСКИЙ** -- каждый час задержки = ущерб |
| **5** | **Задеплоить AFFPERF секвенцию Ярика+Сони (микро-тест 200 лидов)** | **DEPLOY** | **30 мин** | impact.com = доказанный strong fit. Сотни нетронутых affiliate платформ. | **ВЫСОКИЙ** -- единственная готовая копия для доказанного сегмента |
| **6** | **9 reply scripts (уже написаны в FINAL-SYNTHESIS)** | DEPLOY (скопировать в рабочий документ + обучить Настю) | 1ч | Стандартизация ответов. 37.5% actionable-to-meeting сохраняется | **ВЫСОКИЙ** |
| **7** | **Убрать Step 4 из всех кампаний** | OPERATIONS | 15 мин | 680 sends/цикл не уходят в пустоту. Снижение domain risk | **СРЕДНИЙ** |
| **8** | **Flagship Sally -- НЕ ТРОГАТЬ, оставить как control** | НЕ-ДЕЙСТВИЕ | 0 мин | Сохраняем единственный сиквенс с доказанными данными. Ярик+Соня = challenger | **ВЫСОКИЙ** (ценность бездействия) |

### Сравнение с Round 1 priority matrix:

| Round 1 Priority | Round 1 Задача | Correction Priority | Correction Задача | Изменение |
|-----------------|----------------|--------------------|--------------------|-----------|
| #1 | Восстановить 66 replies | #1 + #2 | 91 OOO + 66 replies (объединены, масштаб x4) | Масштаб вырос, приоритет подтверждён |
| #2 | Написать 9 reply scripts | #6 | ЗАДЕПЛОИТЬ reply scripts (уже написаны) | WRITE -> DEPLOY, снижение приоритета (скрипты написаны, деплой проще) |
| #3 | WANNA TALK enterprise | Выбыл из топ-8 | Перенесён на неделю 3 | OOO и deploy важнее |
| #4 | Паузить PR firms | #4 | ОСТАНОВИТЬ (не паузить) | Усилен до STOP |
| #5 | OOO reminders (21 лид) | #1 | OOO follow-up (91 лид) | Поглощён #1, масштаб x4.3 |
| Не было | Задеплоить Ярика+Соню | **#3 + #5** | **НОВЫЙ. Самый важный новый пункт** | -- |
| #8 (FINAL-SYNTHESIS) | Переписать Step 1 всех сиквенсов | #8 (НЕ-ДЕЙСТВИЕ) | НЕ переписывать flagship. Деплоить Ярика+Соню как challenger | WRITE -> НЕ-ДЕЙСТВИЕ + DEPLOY |

---

## 5. ИТОГОВОЕ РАСПИСАНИЕ (обновлённое)

### День 1 (СЕГОДНЯ)
1. **STOP PR firms** -- 5 минут, 1 клик в SmartLead (priority #4)
2. **Убрать Step 4** из всех кампаний -- 15 минут (priority #7)
3. **Начать отработку 91 OOO** -- систематически, по Script 9 (priority #1)
4. **Начать логирование 66 пропущенных replies** из SmartLead (priority #2)

### День 2
1. **Продолжить OOO + replies отработку**
2. **Задеплоить INFPLAT и IMAGENCY** секвенции Ярика+Сони (priority #3) -- адаптировать social proof, добавить calendar links, настроить кампании в SmartLead
3. **Задеплоить reply scripts** в рабочий документ Насти (priority #6)

### День 3-5
1. **Задеплоить AFFPERF** микро-тест 200 лидов (priority #5)
2. **Завершить отработку OOO и пропущенных replies**
3. **Flagship Sally = оставить без изменений**, мониторить данные

### Неделя 2-3
1. Сравнить результаты: Ярик+Соня (INFPLAT, IMAGENCY) vs Sally flagship
2. Если Ярик+Соня > Sally: постепенно переводить объёмы
3. Если Sally > Ярик+Соня: оставить flagship, итерировать секвенции Ярика+Сони
4. Запустить WANNA TALK enterprise ABM (сдвинулся с недели 1 на неделю 2-3)
5. Итерировать Step 2/Step 3 на основе Delta's framework (micro-case study, contrarian insight)

### Неделя 4+
1. PR firms -- микро-тест 200 контактов с нашим rewrite (ТОЛЬКО после восстановления domain reputation)
2. Принять data-driven решение по всем сегментам

---

## 6. КЛЮЧЕВОЙ ВЫВОД

**Мы потратили значительные ресурсы на рекомендации "переписать всё с нуля", не зная что 3 из 4 фреймворков уже переписаны и ждут деплоя.**

Это системная ошибка: мы анализировали OUTPUT (задеплоенные Sally's sequences) и не проверили INVENTORY (готовые, но не задеплоенные секвенции Ярика+Сони).

Правило на будущее: **перед тем как рекомендовать "написать", всегда спрашивать "что уже написано?"**

Стоимость ошибки:
- 2-3 часа потенциально потрачены на rewrites, которые не нужны (если бы мы начали их делать)
- #8 в FINAL-SYNTHESIS ("Переписать Step 1 всех сиквенсов, 3-4 часа") -- задача-фантом, реальный scope = 1 час адаптации
- Приоритизация "WRITE" задач выше "DEPLOY" задач задерживала бы time-to-market на 2-3 дня

**Экономия от коррекции:** ~3-4 часа работы + 2-3 дня до первых данных = при текущей unit economics ($65-160/meeting) эквивалентно 1-2 дополнительным meetings за тот же период.
