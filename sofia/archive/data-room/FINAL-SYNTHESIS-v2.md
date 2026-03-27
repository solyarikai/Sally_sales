# ФИНАЛЬНЫЙ СИНТЕЗ v2 — OnSocial Outreach Analysis

**Дата:** 2026-03-16
**Источники:** 4 командных отчёта Round 1 + 4 перекрёстных рецензии Round 2 + 4 обновления Round 3 + reply-categories-deep-dive.md + sequence-step-performance.md
**Арбитр:** Claude Opus 4.6

---

## 1. КЛЮЧЕВЫЕ КОРРЕКЦИИ (что изменилось после новых данных)

Все 4 команды в Round 1 построили анализ на иллюзорных числах. Round 3 вскрыл масштаб ошибок.

### 1.1 "143 replies" -- иллюзия. Реальных actionable = 24

| Что мы думали (Round 1) | Что оказалось (Round 3) | Масштаб ошибки |
|--------------------------|------------------------|----------------|
| ~55 genuine replies | **24 actionable** | Завышено в 2.3 раза |
| ~21 OOO-ответов | **91 OOO (63.6% всех)** | Занижено в 4.3 раза |
| Reply rate flagship 6.2% | **2.2% (все шаги) / 4.6% (Step 1)** | Headline-метрика включала OOO |
| Actionable rate ~0.57% | **0.25%** | Завышено в 2.3 раза |
| Reply-to-meeting 16.4% | **37.5% (9/24)** | Занижено -- конверсия ЛУЧШЕ, база МЕНЬШЕ |
| 66 unlogged = 10-15 warm leads | **4-6 warm leads (оценка)** | Большинство unlogged = OOO |
| PR firms "too early, 1.2%" | **СЛОМАНА: 17 Step 1 sends, 10.6% bounce** | Неверная интерпретация |
| "Воронка leaks in the middle" | **Воронка пуста на входе** | Фундаментально другой диагноз |

### 1.2 Что конкретно каждая команда поправила

**Alpha:** Главная ошибка -- хвалили flagship за "6.2% reply rate, well above benchmark". Реальность: 74% ответов = OOO-автоответчики. Actionable rate flagship = 1.01%, не 6.2%. Также переоценили recovery из 66 unlogged (ожидали 10-15 warm, реально 4-6).

**Bravo:** Главная ошибка -- "The funnel is not broken where you think it is" (фокус на reply-to-meeting). Реальность: проблема на самом верху воронки. 0.25% true interest rate означает 400 контактов на 1 встречу. Цель "4-5 meetings/week" нереалистична при текущих объёмах.

**Charlie:** Главная ошибка -- unit economics считались от 9,677 "contacted" (загруженных контактов). Правильный denominator = 3,906 Step 1 sends (фактически отправленные). Это меняет cost/meeting с $161 до $65-160 (диапазон в зависимости от метода). Также OOO поднят с #5 приоритета до топ-3.

**Delta:** Главная ошибка -- "~88 real engaged replies". Реальность: 24 человека ДЕЙСТВИТЕЛЬНО прочитали письмо и решили ответить. Также пересмотрена оценка OOO follow-up: это не "pre-warmed pipeline", а второе холодное письмо людям, вернувшимся из отпуска.

### 1.3 Ключевой сдвиг диагноза

**Round 1:** "Хорошая воронка с операционными дырами (tracking, scripts, logging)."
**Round 3:** "Воронка генерирует 24 actionable leads из 9,324 emails (0.25%). Конверсия actionable->meeting = 37.5% (отлично). Проблема -- на самом верху: горлышко 'actionable reply' пропускает микроскопически мало лидов."

**Порядок приоритетов изменился:** infrastructure fix > reallocation > re-engagement > messaging optimization.

---

## 2. РЕАЛЬНАЯ ВОРОНКА (скорректированные числа)

### 2.1 Полная воронка

```
9,677 контактов загружено
  |
  v
3,906 получили Step 1 (40.4% от загруженных)
  |
  v
9,324 emails отправлено всего (все Steps)
  |
  v
143 ответа (1.53% reply rate -- VANITY METRIC)
  |
  ├── 91 OOO (63.6%) -- автоответчики, не читали письмо
  ├── 16 Wrong Person (11.2%) -- ушли из компании
  ├── 8 Not Interested (5.6%) -- ICP mismatches, НЕ ценовые возражения
  ├── 3 Do Not Contact (2.1%)
  ├── 1 Bounce (0.7%)
  |
  └── 24 ACTIONABLE (16.8% от replies, 0.25% от contacted)
       ├── 12 Information Request (pricing, one-pager, comparison)
       ├── 10 Interested (хотят тест/демо)
       └── 2 Meeting Request (готовы к звонку)
            |
            v
          9 ВСТРЕЧ проведено (37.5% от actionable)
            |
            v
          5 STRONG FITS (55.6% от встреч, 100% show rate-to-fit)
```

### 2.2 Воронка по кампаниям

| Кампания | Step 1 Sends | Total Sends | Actionable | Actionable Rate | Meetings | Strong Fits |
|----------|-------------|-------------|-----------|-----------------|----------|-------------|
| **IM agencies & SaaS (flagship)** | 1,980 | 5,698 | **20** (83%) | **1.01%** | 7 | 3-4 |
| IM_PLATFORMS | 649 | 1,326 | 2 | 0.31% | 1 | 1 |
| 0903_AGENCIES | 469 | 764 | 2 | 0.43% | 1 | 1 |
| MARKETING_AGENCIES | 265 | 458 | **0** | 0.00% | 0 | 0 |
| 0903_PLATFORMS | 526 | 723 | **0** | 0.00% | 0 | 0 |
| 1103_PR_firms | 17 (!) | 355 | **0** | 0.00% | 0 | 0 |
| **ИТОГО** | **3,906** | **9,324** | **24** | **0.25%** | **9** | **5** |

**Вывод:** Flagship = 83% всех actionable. Остальные 5 кампаний ВМЕСТЕ = 4 actionable из 1,926 Step 1 sends (0.21%). Flagship -- единственный работающий сегмент в масштабе.

### 2.3 Unit Economics (скорректированные)

| Метрика | Round 1 | Round 3 |
|---------|---------|---------|
| Cost per actionable lead | ~$26 (от 55 genuine) | **$24-60** (от 24 actionable, метод расчёта) |
| Cost per meeting | $161 | **$65-160** (диапазон) |
| Cost per strong fit | $221-443 | **$212-288** |
| Emails per meeting | ~1,075 | **1,036** (все steps) / **444** (unique contacts) |
| ROI кампании (pipeline) | -- | **173x-236x** ($250K pipeline / $1,061-1,441 spend) |

### 2.4 Step Performance (flagship)

| Step | Sent | Replies | Reply Rate | % от всех replies | Статус |
|------|------|---------|------------|-------------------|--------|
| **1** | 1,980 | 91 | **4.6%** | **74%** | Единственный значимый шаг |
| 2 | 1,809 | 20 | 1.1% | 16% | Работает как напоминание |
| 3 | 1,229 | 11 | 0.9% | 9% | Diminishing returns |
| **4** | **680** | **1** | **0.15%** | **1%** | **МЁРТВ -- убрать** |

---

## 3. КОНСЕНСУС v2 (обновлённый)

Что все 4 команды подтвердили/скорректировали после Round 3. Ранжировано по срочности.

### :red_circle: СЕГОДНЯ

| # | Консенсус | Round 1 vs Round 3 |
|---|-----------|---------------------|
| 1 | **НЕМЕДЛЕННО остановить PR firms** -- 10.6% bounce rate на Step 2 АКТИВНО убивает domain reputation для ВСЕХ кампаний. Step 1 отправил только 17 из ~1,000 лидов -- кампания технически сломана. | Round 1: "паузить + микро-тест через 2 нед". Round 3: **СТОП СЕЙЧАС, починка 4+ недели** |
| 2 | **Написать и задеплоить 9 reply scripts** -- 12 из 24 actionable = запрос цены/инфо. Каждый день без скрипта = умирающая сделка. | Без изменений -- подтверждено данными |
| 3 | **Отработать 24 actionable leads + синхронизировать 66 unlogged** -- при 37.5% conversion каждый потерянный actionable = $65-160 | Скорректировано: 66 unlogged содержат 3-5 actionable (не 5-8 как в Round 1) |
| 4 | **Убрать Step 4 из ВСЕХ кампаний** -- 680 sends, 1 reply (0.15%). Чистый ущерб domain reputation без ROI. | НОВЫЙ приоритет (не было в Round 1) |

### :yellow_circle: ЭТА НЕДЕЛЯ

| # | Консенсус | Round 1 vs Round 3 |
|---|-----------|---------------------|
| 5 | **OOO follow-up для 91 лида (не 21!)** -- крупнейший пул confirmed deliveries. Экспорт -> парсинг дат -> queue -> Script 9. Усилия: 3-4 часа. | Масштаб вырос в 4.3 раза. Приоритет поднят. |
| 6 | **Сконцентрировать 80%+ объёмов на flagship** -- 20 из 24 actionable оттуда. Перенаправить sends с мёртвых кампаний. | Усилено: было "flagship лучший", стало "flagship ЕДИНСТВЕННЫЙ" |
| 7 | **Поставить на паузу 0903_PLATFORMS** (526 sends, 1 reply = Do Not Contact, 0 actionable). | Было "monitor", стало "pause" |
| 8 | **Создать one-pager PDF** -- Georg и Roland ждут. Разблокирует все будущие "send more info". | Без изменений |
| 9 | **Починить LinkedIn** -- добавить CTA + calendar link. 18.8% accept rate, 3.5% reply rate, 0 meetings = сломан process. | Без изменений |
| 10 | **Дедупликация + email verification + validate social proof** | Усилено: 16 Wrong Person (11%) = database quality issue |

### :green_circle: СЛЕДУЮЩАЯ НЕДЕЛЯ

| # | Консенсус | Round 1 vs Round 3 |
|---|-----------|---------------------|
| 11 | **Сократить sequence до 2-3 шагов, перенаправить sends на Step 1 новых контактов** | НОВЫЙ -- данные по steps однозначны |
| 12 | **Переписать Step 1 всех сиквенсов** -- problem-first hook вместо feature-dump. 70% копирайтерских усилий на Step 1. | Скорректировано: Step 1 = 74% результата, инвестиция в Steps 2-4 минимальна |
| 13 | **Триаж WANNA TALK enterprise лидов** -- research 15 мин/компания, исключить нерелевантные, ABM для 10-12 | Без изменений |
| 14 | **Добавить negative ICP filters** -- исключить media/education companies, competitors, компании без IM use case | НОВЫЙ -- 8 Not Interested = ICP mismatches |
| 15 | **AFFPERF микро-тест 200 лидов** -- impact.com = strong fit из этого сегмента | Отложен: сначала починить ops |

---

## 4. НОВЫЙ КОНСЕНСУС (появился только в Round 3)

Эти пункты НЕ были консенсусом в Round 1, но стали после новых данных.

### 4.1 Step 4 надо УБИТЬ, а не "оптимизировать"
**Кто согласен:** 4/4 команд (Alpha, Bravo, Charlie, Delta)
**Данные:** 680 sends -> 1 reply -> 0 actionable в flagship. В остальных кампаниях Step 4 даже не запущен.
**Round 1 позиция:** "radically change" (Step 4 analysis) или вообще не упоминался.
**Round 3 консенсус:** Убить. Перенаправить 680+ sends на Step 1 новых контактов = 30x lift в эффективности.

### 4.2 Actionable rate (0.25%), а не reply rate (1.53%) -- правильная метрика
**Кто согласен:** 4/4 команд
**Round 1:** Все оперировали reply rate. Flagship "6.2%" подавался как success.
**Round 3:** 63.6% replies = OOO. Reply rate -- vanity metric. Правильный KPI = actionable rate.

### 4.3 "Not Interested" -- это ICP mismatches, не messaging failures
**Кто согласен:** 4/4 команд (Alpha, Bravo, Charlie, Delta)
**Данные:** 8 отказов. 0 ценовых возражений. Все -- "нам это не нужно" (media companies, education, уже есть provider).
**Следствие:** Нужны negative ICP filters ДО рассылки. Messaging не поможет -- контакты НЕПРАВИЛЬНЫЕ.

### 4.4 PR firms -- не "плохой messaging", а ТЕХНИЧЕСКАЯ ПОЛОМКА
**Кто согласен:** 4/4 команд
**Данные:** Step 1 отправил только 17 emails из ~1,000 лидов. Step 2: 10.6% bounce rate.
**Round 1:** "messaging сломан, микро-тест через 2 нед".
**Round 3:** Кампания ТЕХНИЧЕСКИ сломана + активно вредит domain reputation. Починка 4+ недели.

### 4.5 Sequence length: 2-3 шага, не 4
**Кто согласен:** 4/4 команд
**Данные:** Step 1 = 74% ответов. Step 2 = 16%. Step 3 = 9%. Step 4 = 1%. Follow-ups в новых кампаниях = 0 ответов.
**Вывод:** Step 1 + 1 short follow-up + (опционально) break-up email. Длинные сиквенсы -- tax на domain reputation.

### 4.6 91 OOO -- крупнейший пул, который мы проглядели
**Кто согласен:** 4/4 команд
**Расхождение в оценке конверсии:**
- Charlie (оптимист): 15% re-engagement = 14 replies = 5 meetings
- Delta/Bravo (реалист): 2-4% re-engagement = 2-4 replies = 1-2 meetings
**Решение арбитра:** Реалистичная оценка 3-5% re-engagement = 3-5 actionable replies = 1-2 meetings. Charlie's 15% слишком оптимистична (OOO =/= warm lead, это второе холодное письмо).

---

## 5. СПОРНЫЕ ВОПРОСЫ (обновлённые)

### 5.1 OOO follow-up: "pre-warmed pipeline" или "второе холодное письмо"?

| Позиция | Команды | Аргумент |
|---------|---------|----------|
| **Pre-warmed, приоритет #1** | Alpha, Charlie | 91 лид с подтверждённой доставкой. Email дошёл, авто-ответ сработал. Они не отказывались -- просто не видели. Charlie: 15% re-engage = 5 meetings. |
| **Второе холодное, приоритет #3** | Bravo, Delta | OOO авто-ответ НЕ = engagement. Человек возвращается к 200+ emails. Наше -- одно из них. Bravo: "~1 actionable, не 3-5". Delta: 2-4% conversion = 2-4 ответа. |

**Решение арбитра:** Bravo и Delta ближе к истине. OOO follow-up = приоритет #3-4 (не #1). Реалистичная конверсия: 3-5% = 3-5 ответов, из которых 50% actionable = 1-2 meetings. Это НЕ "pre-warmed pipeline", но ROI всё ещё положительный при 3-4 часах работы.

### 5.2 Целевые meetings/week: 4-5 или 2-3?

| Позиция | Команды | Аргумент |
|---------|---------|----------|
| **4-5 meetings/week достижимы** | Alpha, Charlie | При перераспределении sends + OOO follow-up + AFFPERF = достаточно volume |
| **2-3 meetings/week -- реалистичный потолок** | Bravo | 0.25% true interest rate = 400 контактов / meeting. 4-5/week = 1,600-2,000 НОВЫХ контактов/week. Нереалистично для 1 SDR. Нужен inbound или 3x рост interest rate. |

**Решение арбитра:** Bravo математически прав. При текущем 0.25% interest rate и 1 SDR реалистичная цель -- **2-3 meetings/week**. Для 4-5 нужны: (а) рост actionable rate до 0.5%+ через ICP фильтры и rewrites, (б) OOO re-engagement, (в) LinkedIn конверсия. Ставим цель 2-3 на 4 недели, пересматриваем при улучшении actionable rate.

### 5.3 PR firms: микро-тест или полный kill?

| Позиция | Команды | Аргумент |
|---------|---------|----------|
| **Полный kill** | Bravo | Объём контактов конечен. Каждый сожжённый PR-контакт невозвратен. 0 actionable. |
| **Микро-тест ПОСЛЕ починки** | Alpha, Charlie, Delta | Messaging НИКОГДА не тестировался правильно. Social proof нерелевантен (IM-платформы для PR-фирм). |

**Решение арбитра (обновлено):** Немедленная ОСТАНОВКА (не пауза). Починка infrastructure. Верификация email list. Ожидание 4+ недели для восстановления domain reputation. ЗАТЕМ микро-тест 200 контактов с полностью новым messaging (Charlie's "earned media" framing). Если actionable rate < 0.3% через 2 недели после микро-теста -- закрыть сегмент навсегда.

### 5.4 Сократить до 2 шагов или оставить 3?

| Позиция | Команды | Аргумент |
|---------|---------|----------|
| **2 шага (Step 1 + Step 2 + stop)** | Bravo | Step 1 = 74%, Step 2 = 16% = 90% coverage. Steps 3-4 = tax на reputation. Экономия 30-40% email volume при потере <10% replies. |
| **3 шага (Step 1 + Step 2 + break-up)** | Alpha, Delta | Step 3 ещё даёт 9% replies (11 штук в flagship). Break-up email с конкретным fear-of-loss value hook может зацепить. |

**Решение арбитра:** 3 шага. Step 1 (problem hook) + Step 2 (micro-case study / reminder) + Step 3 (break-up с конкретным примером). Step 4 убить. Step 3 оставить как "последний шанс" с fear-of-loss hook. Разница между 2 и 3 шагами -- 9% replies (11 в flagship), это не ноль.

---

## 6. ФИНАЛЬНЫЙ ACTION PLAN -- TOP 10

### #1. ОСТАНОВИТЬ PR FIRMS + УБИТЬ STEP 4 ВО ВСЕХ КАМПАНИЯХ
- **Действие:** (а) Немедленно остановить 1103_PR_firms в SmartLead. (б) Убрать Step 4 из всех кампаний.
- **Почему:** PR firms: 10.6% bounce rate на Step 2 = прямой ущерб sender domain для ВСЕХ кампаний. Step 1 отправил 17 из ~1,000 = техническая поломка. Step 4: 680 sends -> 1 reply -> 0 actionable = чистый спам.
- **Ожидаемый результат:** Прекращение domain damage. Высвобождение 680+ sends/цикл для Step 1 новых контактов.
- **Кто делает:** Настя (SmartLead)
- **Усилия:** 15 мин
- **Confidence:** HIGH (4/4 команд)
- **Срок:** :red_circle: СЕГОДНЯ

### #2. ЗАДЕПЛОИТЬ 9 REPLY SCRIPTS ДЛЯ ONSOCIAL
- **Действие:** Заменить скрипты The Fashion People на OnSocial-специфичные (см. раздел Скрипты ниже). Обучить Настю. Добавить в accessible doc.
- **Почему:** 12 из 24 actionable = запрос цены/инфо. 50% всех actionable покрываются Scripts 1+2 (pricing + send info). Каждый день без скрипта снижает conversion probability на ~10%.
- **Ожидаемый результат:** Стандартизация ответов. Улучшение actionable-to-meeting с 37.5% до 40-45%.
- **Кто делает:** Соня (написание), Настя (деплой)
- **Усилия:** 3ч написание + 1ч обучение
- **Confidence:** HIGH (4/4 команд)
- **Срок:** :red_circle: СЕГОДНЯ-ЗАВТРА

### #3. СИНХРОНИЗИРОВАТЬ 66 UNLOGGED + ОТРАБОТАТЬ 24 ACTIONABLE
- **Действие:** (а) Экспорт всех 143 ответов из SmartLead API. (б) Сравнение с Google Sheet. (в) Классификация незалогированных. (г) Немедленный follow-up на все тёплые.
- **Почему:** 24 actionable leads стоят $24-60 каждый. 5 misclassified (Norbert/PFR, Jacob/KJ Marketing, Melker/BrandNation, Georg/GameInfluencer, Bronson/Luxe Latam). Из 66 unlogged ожидаем 3-5 дополнительных actionable.
- **Ожидаемый результат:** 3-5 дополнительных actionable leads, 1-2 дополнительные встречи.
- **Кто делает:** Настя (экспорт + sync), Соня (классификация + follow-up)
- **Усилия:** 3-4 часа (one-time)
- **Confidence:** HIGH (4/4 команд, скорректированная оценка)
- **Срок:** :red_circle: СЕГОДНЯ

### #4. ПОСТАВИТЬ НА ПАУЗУ 0903_PLATFORMS + MARKETING_AGENCIES (WATCH)
- **Действие:** (а) Pause 0903_PLATFORMS (526 sends, 1 reply = Do Not Contact, 0 actionable). (б) MARKETING_AGENCIES: дать ещё 2 недели, но если 0 actionable после 1,000 total sends -- закрыть.
- **Почему:** 0903_PLATFORMS = мёртвая кампания. Каждый send -- сожжённый контакт. MARKETING_AGENCIES: 458 sends, 0 actionable, но ещё не набрала объём для окончательного вердикта.
- **Ожидаемый результат:** Высвобождение sends для flagship. Прекращение waste.
- **Кто делает:** Настя (SmartLead)
- **Усилия:** 15 мин
- **Confidence:** HIGH (3/4 за pause 0903, 4/4 за мониторинг MARKETING)
- **Срок:** :yellow_circle: ЭТА НЕДЕЛЯ

### #5. OOO FOLLOW-UP ДЛЯ 91 ЛИДА
- **Действие:** (а) Экспорт 91 OOO из SmartLead с текстами авто-ответов. (б) Парсинг дат возврата. (в) Создание queue в Google Sheet с reminder. (г) Follow-up через return_date + 2 рабочих дня. (д) Использовать Script 9.
- **Почему:** 91 лид с подтверждённой доставкой. Самый большой пул confirmed contacts в воронке. Реалистичная конверсия: 3-5% = 3-5 ответов, 1-2 meetings.
- **Ожидаемый результат:** 3-5 re-engaged replies, 1-2 дополнительные встречи
- **Кто делает:** Настя (экспорт + парсинг), Соня (follow-up)
- **Усилия:** 3-4 часа
- **Confidence:** MEDIUM-HIGH (консенсус 4/4, расхождение в оценке конверсии: 2-15%)
- **Срок:** :yellow_circle: ЭТА НЕДЕЛЯ

### #6. СКОНЦЕНТРИРОВАТЬ 80%+ ОБЪЁМОВ НА FLAGSHIP
- **Действие:** Перенаправить все sends с мёртвых кампаний (PR firms, 0903_PLATFORMS) + высвобожденные от Step 4 на IM agencies & SaaS. Целевое распределение: 80% flagship, 20% IM_PLATFORMS + 0903_AGENCIES.
- **Почему:** Flagship = 83% всех actionable (20 из 24). Actionable rate flagship = 1.01% vs. 0.21% у остальных = 5x разница.
- **Ожидаемый результат:** Рост actionable volume на 30-40% при тех же ресурсах.
- **Кто делает:** Ярик (стратегия), Настя (операции)
- **Усилия:** 1-2 часа
- **Confidence:** HIGH (4/4 команд)
- **Срок:** :yellow_circle: ЭТА НЕДЕЛЯ

### #7. СОЗДАТЬ ONE-PAGER PDF
- **Действие:** 1-страничный PDF: что OnSocial делает (3 предложения), coverage (450M+, 3 платформы), ключевые фичи (credibility, demographics, fraud, overlap), интеграция (API, white-label, < 1 нед), social proof (ТОЛЬКО подтверждённые клиенты), контакт.
- **Почему:** Georg и Roland уже попросили. Разблокирует ВСЕ будущие "send more info" ответы (50% от Information Request).
- **Ожидаемый результат:** Разблокировать 2+ ожидающих лидов. Ускорить обработку ВСЕХ future info requests.
- **Кто делает:** Соня (контент), дизайнер (верстка)
- **Усилия:** 2-3 часа
- **Confidence:** HIGH (3/4 команд)
- **Срок:** :yellow_circle: ЭТА НЕДЕЛЯ

### #8. ДЕДУПЛИКАЦИЯ + EMAIL VERIFICATION + NEGATIVE ICP FILTERS
- **Действие:** (а) Dedup emails между всеми кампаниями. (б) Email verification (NeverBounce/ZeroBounce) ПЕРЕД загрузкой -- ~$6/2,000 контактов. (в) Добавить fallback "Hi there" для пустых {{first_name}}. (г) Negative filters: исключить media/education companies, data providers/competitors, компании без active IM use case. (д) Создать "No list" (influData, HypeAuditor, конкуренты). (е) Validate social proof: Modash, Captiv8, Kolsquare -- реальные paying customers?
- **Почему:** 16 Wrong Person (11%) = database freshness problem. 8 Not Interested = ICP mismatches. 10.6% bounce PR firms = email verification failure. Social proof risk: если заявленные клиенты не платят -- бомба для репутации.
- **Ожидаемый результат:** Сокращение waste sends на 15-20%. Рост actionable rate с 0.25% до 0.35-0.4%. Защита domain reputation.
- **Кто делает:** Настя (dedup + verification), Ярик (ICP filters + social proof validation)
- **Усилия:** 3-4 часа (один раз), потом 15 мин/batch
- **Confidence:** HIGH (4/4 команд)
- **Срок:** :yellow_circle: ЭТА НЕДЕЛЯ (до следующего batch)

### #9. ЗАДЕПЛОИТЬ ВАШИ СЕКВЕНЦИИ (INFPLAT / IMAGENCY / AFFPERF) + СОКРАТИТЬ ДО 3 ШАГОВ
- **Действие:** (а) Ярик и Соня уже написали сегментные секвенции с A/B гипотезами (INFPLAT: "Stop Building Scrapers" vs "Ship Features Faster", IMAGENCY: "Cut Research Time" vs "White-Label Your Data", AFFPERF: "Affiliates→Creators" vs "Build vs Buy") — они НИ РАЗУ не были задеплоены в SmartLead. Все кампании работали на generic sequence от Sally. (б) Задеплоить INFPLAT и IMAGENCY в соответствующие кампании. (в) Сократить до 3 шагов (убрать Step 4). (г) Сравнить результат с Sally's generic — если ваши гипотезы дают выше actionable rate, масштабировать. (д) Рерайты от агентов (Delta/Alpha) использовать как дополнительные варианты для A/B, не как замену ваших.
- **Почему:** Step 1 = 74% всех ответов. Текущий Step 1 = feature-dump от Sally. Ваши гипотезы (problem-first: "How are you currently handling creator data?", "How many hours sourcing creators per campaign?") уже ближе к problem-first подходу, который рекомендуют все 4 команды. Но данных по ним ноль — ни одна не была протестирована.
- **Ожидаемый результат:** Рост actionable rate Step 1 с 1.01% до 1.5-2.0% = +10-20 actionable / 2,000 sends.
- **Кто делает:** Ярик + Соня (адаптация под 3-step формат), Настя (деплой в SmartLead)
- **Усилия:** 2-3 часа (секвенции уже написаны, нужна адаптация)
- **Confidence:** MEDIUM-HIGH
- **Срок:** :green_circle: СЛЕДУЮЩАЯ НЕДЕЛЯ
- **ВАЖНО:** Все 4 аналитические команды критиковали и предлагали рерайты для Sally's копи. Ваши секвенции (INFPLAT/IMAGENCY/AFFPERF) НЕ анализировались, потому что не были задеплоены. При этом ваши гипотезы по духу совпадают с рекомендациями агентов (problem-first, pain-based hooks). Нужно сравнение: ваши vs Sally's vs рерайты агентов.

### #10. ТРИАЖ WANNA TALK + ENTERPRISE ABM
- **Действие:** (а) Research каждой из 19 компаний (15 мин/компания). (б) Исключить подтверждённо нерелевантные (inDrive, Dovetail, возможно Patreon). (в) Для 10-12 валидных: Tier 1 (decision-makers) = персонализированный email + LinkedIn от CEO. Tier 2 (assistants) = точки входа. (г) ABM sequence, не mass cold email.
- **Почему:** WANNA TALK = 19 enterprise лидов, запущены и забыты. 1 закрытая сделка = $50K-200K+. Но сначала -- ICP фильтры (#8) и скрипты (#2), чтобы не загнать enterprise лидов в сломанный процесс.
- **Ожидаемый результат:** 2-3 enterprise встречи за 3 недели. 1 сделка = $50K-200K+.
- **Кто делает:** Ярик (research + strategy), Настя (execution)
- **Усилия:** 4-6 часов
- **Confidence:** MEDIUM-HIGH
- **Срок:** :green_circle: СЛЕДУЮЩАЯ НЕДЕЛЯ

---

## 7. СКРИПТЫ ОТВЕТОВ -- ЛУЧШИЕ ВЕРСИИ

### Script 1: "What's the pricing?" (6 лидов: Atul, Daniel, Eduardo, Urban, Arnab, Melker)

**Источник:** Delta + Bravo

> Hi {{first_name}},
>
> Good question -- pricing depends on volume and which data points you need, so I want to make sure I give you the right number rather than a range that's not useful.
>
> Quick context: most teams at our scale pay between $X-Y/month depending on whether they need full audience demographics or just credibility + basic stats. Our smallest customers do ~500K lookups/month, largest do 2B+.
>
> Two options:
> 1. I can send you the pricing grid right now if you tell me your approximate monthly volume and which platforms (IG/TikTok/YT) you need.
> 2. Or we do 15 min on a call -- I'll pull a live demo with your volume, and you'll have exact pricing before the call ends.
>
> What works better?

**Ключевое:** Не уклоняется от цены. Даёт диапазон. 2 опции (async + call). 50% всех actionable = pricing-вопросы -- это САМЫЙ важный скрипт.

---

### Script 2: "Send more info / one pager" (Georg, Roland)

**Источник:** Delta

> Hi {{first_name}},
>
> Attached is a one-pager covering how the API works, what data points you get, and which platforms we cover.
>
> [ATTACH ONE-PAGER PDF]
>
> One thing the doc won't show you: what the actual API output looks like for a creator YOUR team is working with. If you send me 2-3 creator handles, I'll pull the full breakdown -- credibility score, audience demographics, overlap -- and send it back. No call needed.
>
> That usually answers more questions than a PDF.

**Зависимость:** Требуется one-pager PDF (Action #7).

---

### Script 3: "How are you different from HypeAuditor / SocialData / X?" (Norbert @ PFR Group)

**Источник:** Delta

> Hi {{first_name}},
>
> Fair question. Three honest differences:
>
> 1. **Coverage:** HypeAuditor has ~80M profiles. We have 450M+ with truly global coverage -- especially strong in LATAM, SEA, and MENA where HA thins out.
> 2. **Data freshness:** SocialData batch-processes weekly. Our data updates in real-time -- you get the audience snapshot as of today, not last Tuesday.
> 3. **API-first pricing:** HA and SocialData are SaaS-first (dashboards, seats, per-user pricing). We're API-first -- you pay per call, no seat licenses. If you're integrating into your own product, this is typically 40-60% cheaper at scale.
>
> Easiest way to compare: send me a creator handle you've recently analyzed in HA. I'll pull the same profile in our system and you can compare side-by-side. No call needed.

**ВАЖНО:** Проверить все числа конкурентов перед использованием.

---

### Script 4: "We already have a partner/system" (Roland, Louis)

**Источник:** Delta

> Hi {{first_name}},
>
> Understood -- makes sense to stick with what's working. Quick question: is your current provider covering all three platforms (IG, TikTok, YouTube) with real-time updates, or are you supplementing with manual checks on any of them?
>
> Not trying to replace anything that works. But most teams we talk to have at least one gap -- usually TikTok depth or audience geo accuracy in emerging markets.
>
> If that resonates, happy to do a blind comparison. If not, no hard feelings.

---

### Script 5: "Do you cover [region/platform]?" (Salvador -- SEA/China)

**Источник:** Alpha + Charlie

> Hi {{first_name}},
>
> Great question. Our current coverage:
> - **Platforms:** Instagram, TikTok, YouTube -- 450M+ profiles combined
> - **Geographies:** Truly global, including Southeast Asia (strong coverage in Indonesia, Philippines, Thailand, Vietnam)
>
> For China-specific platforms (Douyin, Xiaohongshu): we currently don't cover Chinese platforms. We focus on IG, TikTok, and YouTube globally. If China is a dealbreaker, I want to be upfront about it.
>
> For SEA -- happy to pull sample data for creators in your target markets. Send me a few handles and I'll have the breakdown back within 24 hours. No call needed.

**Ключевое:** Честный ответ о China. Конкретные страны SEA. Async опция.

---

### Script 6: "Let's schedule a call" (Colby, Gordon, Johan)

**Источник:** Delta

> Great -- looking forward to it.
>
> Here's my calendar: {{calendar_link}}
>
> To make the 15 min as useful as possible, could you send me 2-3 creator handles your team is currently evaluating? I'll pull the full data breakdown before the call so we're looking at YOUR use case, not a generic demo.

**Ключевое:** Максимально коротко. Запрос хендлов = commitment = выше show rate.

---

### Script 7: "I'm interested, adding colleagues" (Atul -- добавил Pavel, Akira)

**Источник:** Delta

> Hi Atul, Pavel, Akira --
>
> Great to have everyone in the loop. To make sure this is worth your time, here's what I'll cover in our walkthrough:
>
> 1. Live API demo using creator profiles relevant to {{company_name}}
> 2. Data coverage + freshness vs. what you're currently using
> 3. Pricing based on your volume
>
> Here's my calendar: {{calendar_link}} -- feel free to pick a slot that works for the group. 30 min should be enough with three of you.
>
> If it's easier, I can also send a 5-min Loom walkthrough first so you can evaluate asynchronously.

---

### Script 8: "Wrong person, try X" (Sebastian -> Robin, Alexander -> Hannes)

**Источник:** Delta + Alpha

> Hi {{first_name}},
>
> Thank you -- really appreciate the redirect.
>
> {{redirect_name}}, I was speaking with {{first_name}} who suggested you'd be the right person for this.
>
> Short version: we provide creator and audience data via API for platforms like {{company_name}} -- 450M+ profiles, credibility scoring, demographics, audience overlap. Your team integrates it in days.
>
> Happy to send a quick overview or jump on a 15-min call -- whatever's easier. {{calendar_link}}

---

### Script 9: OOO auto-reply (91 лид)

**Источник:** Alpha + Delta

> Hi {{first_name}},
>
> Hope you had a good [trip/break]. Circling back on my earlier note about creator data for {{company_name}}.
>
> Short version: we provide audience demographics, credibility scoring, and creator overlap via API -- 450M+ profiles across IG, TikTok, YouTube. Most integrations go live in days.
>
> Worth a 15-min look now that you're back? {{calendar_link}}

**Timing:** return_date + 2 рабочих дня. Настроить queue для 91 лида.

---

## 8. РЕРАЙТЫ СЕКВЕНЦИЙ -- ЛУЧШИЕ ВЕРСИИ

> **ВАЖНОЕ ПРИМЕЧАНИЕ:** Все рерайты ниже — это предложения 4 аналитических команд как замена **Sally's generic sequence** (TEST A/B), которая сейчас задеплоена в SmartLead. Однако Ярик и Соня уже написали сегментные секвенции (INFPLAT, IMAGENCY, AFFPERF) с problem-first гипотезами, которые **ни разу не были задеплоены**. Их подход ("Stop Building Scrapers", "Cut Research Time", "White-Label Your Data") по духу совпадает с рекомендациями агентов. **Перед деплоем нужно сравнить:** ваши секвенции vs рерайты ниже — и выбрать лучший вариант или скомбинировать.

### Step 1 для PLATFORMS (CTO/VP Eng) -- API Buyers

**Источник:** Delta + Alpha
**Для сравнения:** см. лист "Sequences | INFPLAT" в Google Sheet — ваша HYP A ("Stop Building Scrapers") и HYP B ("Ship Features Faster")

**Subject:** question about creator data at {{company_name}}

> Hi {{first_name}},
>
> Quick question -- is {{company_name}} maintaining its own creator data pipeline, or licensing from a third party?
>
> Asking because we power the data layer for [1 named real customer -- e.g., "a platform doing 2B+ monthly lookups"] and the pattern is always the same: internal scraping works until it doesn't, then it becomes the eng team's biggest maintenance headache.
>
> If that's not your situation, ignore this. But if your team is spending cycles on data infrastructure instead of product -- happy to show what the alternative looks like. 15 min.
>
> {{sender_name}}

**Что изменено:** Убран feature-dump. Убран CTA "Who handles X?". Открывается вопросом об ИХ ситуации. 1 proof point. "Ignore this" = уважение.

---

### Step 1 для AGENCIES (CEO/Founder) -- Tool Buyers

**Источник:** Delta (fear-of-loss)
**Для сравнения:** см. лист "Sequences | IMAGENCY" в Google Sheet — ваша HYP A ("Cut Research Time") и HYP B ("White-Label Your Data")

**Subject:** creator vetting -- how long per campaign?

> Hi {{first_name}},
>
> I noticed {{company_name}} is running influencer campaigns for [industry -- e.g., "DTC beauty brands"]. When your team pitches 3-4 creators to a client, how do you validate that their audiences don't overlap by 50%+?
>
> We had an agency lose a major client because they recommended 3 creators who shared 60% of the same followers. The campaign underperformed, and the client blamed the agency.
>
> We built a tool that catches this in seconds -- before the brief goes out. Used by [1 named agency].
>
> Worth 15 min to see the overlap report for creators {{company_name}} is currently working with?
>
> {{sender_name}}

**Что изменено:** Fear-of-loss вместо efficiency angle. "Tool" вместо "API". Конкретный сценарий.

---

### Step 1 для PR FIRMS (полностью новый)

**Источник:** Charlie (earned media framing) + Delta

**Subject:** Creator vetting for {{company_name}}'s earned media campaigns

> Hi {{first_name}},
>
> When {{company_name}} recommends a creator for a brand partnership, how do you verify their audience is real?
>
> Most PR firms we talk to either eyeball it (risky) or pay per-report fees that add up fast when you're vetting 20+ creators per campaign.
>
> We provide audience credibility scoring, demographics (country, city, age, gender), and fraud signals for 450M+ creators. The pitch to your client becomes "we checked -- this creator's audience is 87% real, 62% female, 45% US-based" instead of "they have 500K followers."
>
> Worth a 15-min look at a sample report for a creator your team is evaluating right now?
>
> {{sender_name}}

**Что изменено:** Убран social proof от IM-платформ. "Vetting" и "credibility" (PR-язык). Фокус на client trust. Конкретный пример output.

**ПРИМЕЧАНИЕ:** Этот реврайт использовать ТОЛЬКО после починки PR firms кампании (Action #1) и 4+ недель восстановления domain reputation.

---

### Структура follow-up (Steps 2-3 для всех сегментов)

**Round 3 обновление:** Sequence сокращена с 4 до 3 шагов.

| Step | Цель | Формат | Пример для Platforms |
|------|------|--------|---------------------|
| **Step 1** | Problem-first hook + 1 proof point + конкретный CTA | Вопрос -> сценарий -> предложение | "Is {{company_name}} maintaining its own scraping pipeline?" |
| **Step 2** | Micro-case study (1 клиент, 1 результат, 2 предложения) | История -> конкретный outcome | "One platform cut 3 months of eng backlog by switching from in-house scraping to our API. They shipped audience demographics as a native feature within a week." |
| **Step 3** | Break-up email + fear-of-loss value hook | Конкретный пример -> уважительное закрытие | "Last note from me. I recently pulled data on a few creators popular in [niche] -- one had 340K followers but 43% fake audience. If that's the kind of risk {{company_name}} wants to catch -- {{calendar_link}}. If not, no worries." |

**Step 4 УБРАН** -- 680 sends, 1 reply, 0 actionable. Нет данных, оправдывающих 4-й шаг.

---

## 9. МЕТРИКИ ДЛЯ ОТСЛЕЖИВАНИЯ

### 9.1 Primary KPIs (еженедельно)

| Метрика | Текущее | Цель (4 недели) | Цель (8 недель) | Почему важно |
|---------|---------|-----------------|-----------------|-------------- |
| **Actionable rate** (actionable / Step 1 sends) | **0.25%** (24/9,677) | **0.5%** | **0.75%** | Главная метрика. Reply rate -- vanity metric. |
| **Actionable-to-meeting** | **37.5%** (9/24) | **40%** | **40-45%** | Уже отличный. Улучшение через скрипты. |
| **Meeting show rate** | **55.6%** | **70%** | **75%** | 3-touch confirmation sequence. |
| **Meetings/week** | **~1.5** | **2-3** | **3** | Реалистичная цель при 0.25-0.5% actionable rate |
| **Strong fit rate (of held)** | **100%** (5/5) | **Maintain** | **Maintain** | Product-market fit подтверждён |

### 9.2 Operational KPIs (еженедельно)

| Метрика | Текущее | Цель | Как мерить |
|---------|---------|------|-----------|
| **Bounce rate по кампаниям** | 2.9% flagship, **10.6% PR firms** | **< 3% на всех шагах** | SmartLead API / dashboard |
| **Step 1 sends / week** (flagship) | ~300-400 | **500-600** (после перераспределения) | SmartLead |
| **OOO follow-up coverage** | 0% (не настроено) | **100%** (все 91 в queue) | Google Sheet "OOO Queue" |
| **Response time на actionable** | Неизвестно | **< 4 часа** | Google Sheet timestamp |
| **Wrong Person rate** | 11.2% (16/143) | **< 5%** | Email verification pre-send |
| **Email campaigns active** | 6 (3 мёртвые) | **3** (flagship + IM_PLATFORMS + 0903_AGENCIES) | SmartLead |

### 9.3 Quality KPIs (ежемесячно)

| Метрика | Текущее | Цель | Как мерить |
|---------|---------|------|-----------|
| **Actionable / кампания** | Flagship=20, остальные=0-2 | >5 на активную кампанию | Reply categories deep dive |
| **ICP match rate** (1 - Not Interested%) | 94.4% | **97%+** | After negative filters |
| **Cost per meeting (total)** | $65-160 | **$50-80** | Spend / meetings |
| **Pipeline value / month** | ~$250K (5 strong fits x $50K) | **$300K+** | CRM |
| **LinkedIn meeting conversion** | 0% | **5% of warm replies** | LinkedIn tracking |

### 9.4 Что НЕ мерить (vanity metrics)

| Метрика | Почему НЕ мерить |
|---------|------------------|
| Reply rate (total) | 63.6% = OOO. Бесполезно без разбивки по категориям. |
| "Contacts loaded" | 9,677 загружено, 3,906 получили Step 1 -- разница в 2.5x. |
| A/B test reply rate | При 100-200 контактов на вариант -- 1-3 ответа. Не статистика. Мерить QUALITY replies вместо rate. |
| "Emails sent" (total) | Включает Steps 2-4 на тех же людей. Не показывает reach. |

### 9.5 Формула успеха (как считать)

```
Meetings/week = (Step 1 sends/week) x (Actionable rate) x (Actionable-to-meeting) x (Show rate)

Текущее: 400/week x 0.25% x 37.5% x 55.6% = 0.21 meetings/week (!)

С учётом всех Actions: 600/week x 0.5% x 40% x 70% = 0.84 meetings/week (от cold email)
+ OOO pipeline: ~0.5 meetings/week (первые 4 недели)
+ WANNA TALK ABM: ~0.5 meetings/week
+ LinkedIn: ~0.25 meetings/week
= ~2.0-2.1 meetings/week

Для 3 meetings/week нужно: actionable rate 0.75% ИЛИ Step 1 sends 800/week ИЛИ добавить inbound канал.
```

---

*Финальный синтез v2 подготовлен на основе 12 документов: 4 командных отчёта Round 1, 4 перекрёстных рецензии Round 2, 4 обновления Round 3, reply-categories-deep-dive.md и sequence-step-performance.md. Все рекомендации скорректированы на реальные данные: 24 actionable из 9,324 emails, 0.25% true interest rate, 37.5% actionable-to-meeting. Скрипты и рерайты готовы к немедленному деплою.*
