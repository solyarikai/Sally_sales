# TEAM BRAVO -- ROUND 3: Data Update

**Дата:** 2026-03-16
**Новые данные:** reply-categories-deep-dive.md, sequence-step-performance.md

---

## 1. ЧТО ИЗМЕНИЛОСЬ. ГДЕ МЫ ОШИБЛИСЬ В ROUND 1

### 1.1 Мы завысили число actionable лидов

**Round 1:** "~55 genuine replies producing 9 meetings" -- мы оценивали 55 actionable.
**Реальность:** 24 actionable из 143. Мы ошиблись в 2.3 раза.

Мы считали "genuine" = все кроме OOO и явных отказов. Но новые данные показывают, что 91 из 143 (63.6%) -- OOO-автоответы. Мы оценивали OOO в ~21 штуку. Фактически их в 4.3 раза больше. Это означает, что наш "genuine reply rate" в 16.4% (55/143 -> 9 meetings) был иллюзией. Реальный: 9 meetings / 24 actionable = **37.5% actionable-to-meeting**. Это кардинально меняет диагноз: конверсия из actionable в meetings не "decent but not great" -- она сильная. Проблема не в конверсии, а в том, что actionable реплаев катастрофически мало.

**Пересчёт:** 24 actionable / 9,677 contacted = **0.25% true interest rate**. Один заинтересованный лид на каждые 400 контактов.

### 1.2 Flagship reply rate 6.2% -- иллюзия, а не успех

**Round 1:** "The flagship has a 6.2% reply rate -- which is excellent for cold outreach."
**Реальность:** 74% всех ответов flagship (91 из 123) -- Step 1. Но Step 1 reply rate = 4.6%, а не 6.2%. Цифра 6.2% -- это replies/unique contacts, что смешивает повторные касания. Более того: 91 OOO из 123 replies. Если убрать OOO, flagship генерирует **~32 genuine reply из 1,980 Step 1 sends = 1.6%**. Это не "excellent" -- это средний показатель для cold outreach.

Мы строили стратегию ("Maintain 5%+", "flagship is the best segment") на числе, которое включает 74% автоответов "я в отпуске".

### 1.3 Follow-ups в новых кампаниях = НОЛЬ

**Round 1:** "Each subsequent step has diminishing returns" -- мы обсуждали diminishing returns как gradient.
**Реальность:** В кампаниях 0903_AGENCIES, 0903_PLATFORMS, MARKETING_AGENCIES, 1103_PR_firms -- Step 2 и далее = **0 replies** (кроме PR firms, где 3 reply = 2 OOO + 1 Wrong Person). Это не diminishing returns -- это стена. Follow-ups работают ТОЛЬКО в flagship кампании, и там их эффективность тоже падает на 70%+ с каждым шагом.

**Вывод, которого не было в Round 1:** Follow-up сиквенсы в текущем виде не работают для НОВЫХ кампаний. Либо:
- Flagship follow-ups ловят OOO-возвраты (механический эффект, не messaging)
- Новые кампании ещё не набрали достаточный объём
- Copy follow-ups в новых кампаниях слабее

Наиболее вероятно первое: Step 2-3 flagship ловят людей, вернувшихся из OOO и увидевших первое письмо.

### 1.4 PR firms -- не просто "плохой messaging", а СЛОМАННАЯ кампания

**Round 1:** "PR firms is a waste of resources at current approach" -- мы обсуждали messaging.
**Реальность:** Кампания ТЕХНИЧЕСКИ сломана. Step 1 отправил только 17 писем из 1,000 контактов. Большинство лидов перескочили сразу на Step 2. Step 2 -- **10.6% bounce rate**. Это не "messaging problem" -- это delivery failure, которая активно убивает domain reputation.

Наша рекомендация "micro-test 50 PR firms with new sequence" в Round 1 была недостаточно жёсткой. Правильная рекомендация: **немедленно остановить, исправить техническую проблему ПЕРЕД любым микро-тестом**.

### 1.5 "Not Interested" -- это ICP mismatches, не messaging failures

**Round 1:** Мы не анализировали Not Interested достаточно глубоко.
**Реальность из данных:** 8 отказов:
- "It's not a service we need" (In The Black Media)
- "We are not an enterprise solution" (Creator Origin)
- "We are a media and education company" (Social Media Examiner)
- "We don't have a need for this type of service" (United Influencers)

**Паттерн:** 6 из 8 отказов -- "this isn't relevant to us". Не "too expensive", не "bad timing", не "wrong person" -- а "we don't do this". Social Media Examiner -- это media company. Creator Origin -- не enterprise. Это не провал copy, а провал таргетинга. Люди, которым не нужен creator data API, оказались в списке рассылки.

**Коррекция к нашей рекомендации по ICP:** Наш фреймворк "API Buyers vs Tool Buyers" из Round 1 был правильным, но недостаточным. Нужен negative filter: компании без активного influencer marketing / creator data use case должны быть ИСКЛЮЧЕНЫ до рассылки, а не отфильтрованы по типу ("agencies vs platforms").

---

## 2. НОВЫЕ CONTRARIAN TAKES

### 2.1 Step 4 нужно не "радикально менять" -- его нужно УБИТЬ

**Round 1:** "Step 4 should be eliminated or radically changed."
**Новые данные:** 680 sends, 1 reply (0.15%) в flagship. В остальных кампаниях Step 4 не запущен (0 sends). Step 4 -- это не низкоэффективный шаг, это спам. Каждый Step 4 email снижает domain reputation за ноль полезного отклика. Не "радикально менять" -- убить и использовать эти sends для НОВЫХ контактов на Step 1 (4.6% vs 0.15% = 30x разница в эффективности).

**Арифметика:** 680 Step 4 sends -> 1 reply. 680 Step 1 sends на новых контактов -> ~31 reply (при 4.6%). Разница = 30 дополнительных replies. Это не оптимизация, это переключение направления огня.

### 2.2 OOO -- это не "pipeline", это шум

**Round 1 (все 4 команды):** "21 OOO leads need scheduled re-engagement" (мы думали 21). **Final Synthesis:** "OOO Follow-up система для 21 лида" -- Action #6.
**Реальность:** 91 OOO-автоответ. Это 63.6% всех replies.

Contrarian take: OOO follow-up на 91 лид -- это не "minimal effort, pre-warmed leads". Это 91 человек, которые НЕ читали ваше письмо. Они не "pre-warmed" -- авто-ответ сработал без их участия. OOO follow-up после возврата = фактически ВТОРОЕ холодное письмо. Ожидаемый отклик: 2-5% от 91 = 2-5 replies, из которых actionable будет 25% = 0.5-1.2 actionable. Это стоит 45 минут настройки, но не стоит называть "pre-qualified pipeline".

**Коррекция:** OOO follow-up остаётся в плане (ROI всё ещё положительный), но его приоритет в Final Synthesis (#6) завышен. Реалистичный outcome: ~1 actionable, а не "3-5 re-engaged replies, 1-2 встречи".

### 2.3 True interest rate 0.25% означает, что у нас проблема с PRODUCT-MARKET FIT в messaging, а не с volume

**Round 1:** "The funnel is not broken where you think it is." Мы фокусировались на reply-to-meeting конверсии.
**Реальность:** 0.25% true interest rate (24/9,677). Даже при идеальных scripts и 100% actionable-to-meeting конверсии, нужно контактировать 400 человек чтобы получить ОДНУ встречу. При целевых 4-5 встреч/неделю (из Final Synthesis) нужно контактировать 1,600-2,000 НОВЫХ людей в неделю. Это нереалистично для 1 SDR.

**Либо:**
1. Сужаем ICP до сегмента с 1%+ true interest rate (если он существует -- flagship без OOO даёт ~1.6%, но actionable из 1,980 sends -- ~20, т.е. ~1.0%)
2. Переходим на inbound/content marketing где лиды приходят сами
3. Принимаем, что cold outreach -- это канал для 1-2 встреч/неделю, а не для 4-5, и добавляем другие каналы

Все 4 команды в Round 1 (включая нас) ставили цель "Meetings/week: 3 -> 4-5". При 0.25% interest rate это означает 1,600-2,000 новых контактов в неделю. Финальный Синтез не адресует эту математику.

### 2.4 Step 1 = единственный шаг, который имеет значение

Across all campaigns Step 1 generates 74% replies в flagship и 100% genuine replies в остальных кампаниях. Это означает:
- Step 1 copy определяет 74-100% результата
- Steps 2-4 -- это tax на domain reputation с marginal return
- Оптимальная стратегия: **Step 1 + один short follow-up (Step 2) + stop**. Экономия: 30-40% email volume при потере <10% replies.

Это прямо противоречит индустриальному стандарту "4-step sequence". Данные говорят: для ЭТОГО продукта и ЭТОГО ICP длинные сиквенсы не работают.

### 2.5 Wrong Person rate 11% = мы тратим 1/9 ресурсов на людей, которые ушли из компаний

16 из 143 replies = "wrong person" (left company). Это не "database quality issue" как мы писали в Round 1. Это 11% wasted sends -- ~1,064 email из 9,677 ушли людям, которые больше не работают в целевых компаниях. При $0.01-0.05 за email это $10-53 прямых потерь, но реальная цена -- bounce risk и domain reputation.

**Новая рекомендация:** email verification (NeverBounce, ZeroBounce) ПЕРЕД загрузкой в SmartLead. Стоимость: ~$0.003 за email. Для 2,000 контактов = $6. ROI: предотвращение ~220 wasted sends.

---

## 3. ОБНОВЛЁННЫЙ ТОП-5 ДЕЙСТВИЙ

Изменения по сравнению с Round 1 и Final Synthesis выделены.

### #1. ОСТАНОВИТЬ PR FIRMS + УБИТЬ STEP 4 ВО ВСЕХ КАМПАНИЯХ (НОВОЕ: Step 4 kill)
- **Что изменилось:** В Round 1 мы ставили PR firms kill на #4. Новые данные показывают, что PR firms кампания ТЕХНИЧЕСКИ сломана (17 sends на Step 1, 10.6% bounce на Step 2). Это не просто плохой messaging -- это активное повреждение domain reputation.
- **Step 4 kill -- новое действие:** 680 sends за 1 reply в flagship. Это спам. Перенаправить эти sends на новых контактов = 30x lift.
- **Усилия:** 15 мин (2 изменения в SmartLead)
- **Impact:** Немедленное прекращение domain damage + перераспределение 680+ sends/cycle на Step 1
- **Сделать:** СЕЙЧАС

### #2. НАПИСАТЬ 9 REPLY SCRIPTS (БЕЗ ИЗМЕНЕНИЙ)
- **Почему без изменений:** 24 actionable leads подтверждают необходимость. 12 из 24 -- Information Request (pricing, one-pager, competitive comparison). Скрипты из Final Synthesis ready to deploy.
- **Дополнение на основе новых данных:** Скрипт для pricing (Script 1) -- САМЫЙ важный. 6 из 12 Information Requests = "what's the pricing?". Это 50% всех тёплых вопросов.
- **Сделать:** СЕГОДНЯ

### #3. ПЕРЕСЧИТАТЬ ICP И ДОБАВИТЬ NEGATIVE FILTERS (ИЗМЕНЕНО: было "WANNA TALK ABM")
- **Что изменилось:** WANNA TALK ABM спускается на #4. Данные показывают, что ICP проблема глубже, чем мы думали. 8 "Not Interested" = ICP mismatches. 16 "Wrong Person" = database quality. 91 OOO = 63.6% шума. Прежде чем добавлять новые лиды (WANNA TALK, AFFPERF), нужно исправить КАЧЕСТВО входящего потока.
- **Конкретные negative filters:**
  1. Компании без active influencer/creator marketing program (Social Media Examiner, In The Black Media -- media/education)
  2. Компании, которые "уже имеют решение и не enterprise" (Creator Origin)
  3. Email verification перед загрузкой (NeverBounce/ZeroBounce -- $6 на 2,000 контактов)
  4. Dedup + empty field check (из Round 1, без изменений)
- **Усилия:** 2-3 часа (один раз), потом 15 мин на каждый новый batch
- **Impact:** Сокращение waste sends на 15-20%, повышение true interest rate с 0.25% до 0.35-0.4%
- **Сделать:** ДО СЛЕДУЮЩЕГО BATCH

### #4. WANNA TALK ABM + ТРИАЖ (БЫЛО #3, БЕЗ ИЗМЕНЕНИЙ В СОДЕРЖАНИИ)
- **Почему спустился:** Не потому что менее важен, а потому что новые данные показали: без исправления ICP и negative filters мы загоним WANNA TALK лидов в тот же сломанный процесс. Сначала фильтры -- потом ABM.
- **Содержание:** Без изменений vs Final Synthesis. Delta's триаж + Alpha's tiering.
- **Сделать:** ЭТА НЕДЕЛЯ (после #3)

### #5. СОКРАТИТЬ СИКВЕНС ДО 2 ШАГОВ + ПЕРЕРАСПРЕДЕЛИТЬ ОБЪЁМ НА STEP 1 (НОВОЕ)
- **Что изменилось:** В Round 1 мы рекомендовали "Rewrite Step 1" на Неделе 2. Новые данные показывают, что проблема не только в КАЧЕСТВЕ Steps 2-4, а в их СУЩЕСТВОВАНИИ. Steps 3-4 генерируют <1% от всех replies при потреблении 30-40% email volume.
- **Конкретное действие:**
  1. Оставить Step 1 (4.6% reply rate) + Step 2 (1.1% reply rate) в flagship
  2. Убрать Steps 3-4 из всех кампаний
  3. Освободившийся email volume (1,909 sends в flagship = 1,229 Step 3 + 680 Step 4) перенаправить на новых контактов в Step 1
  4. Ожидаемый lift: 1,909 sends x 4.6% = ~88 additional replies, из которых ~25% actionable = ~22 actionable
- **Это vs текущие Steps 3-4:** 1,909 sends на Steps 3-4 дали 12 replies total (11 Step 3 + 1 Step 4). Перенаправление на Step 1 = **7x improvement**.
- **Усилия:** 30 мин (отключить steps в SmartLead)
- **Сделать:** НЕДЕЛЯ 2 (после деплоя скриптов и ICP фильтров)

---

## 4. ЧТО НЕ ИЗМЕНИЛОСЬ

Консенсусные пункты из Final Synthesis, которые новые данные ПОДТВЕРЖДАЮТ:

1. **Reply scripts -- #1 приоритет.** 24 actionable leads нуждаются в немедленном ответе. 12 Information Request без скрипта = сделки, которые умирают прямо сейчас.
2. **Actionable-to-meeting конверсия сильная (37.5%).** Проблема не в конверсии -- проблема в volume actionable.
3. **Product-market fit подтверждён.** 10 Interested + 2 Meeting Request из разных сегментов. Люди, которым НУЖЕН creator data API, реагируют положительно.
4. **Bravo's "API Buyers vs Tool Buyers" сегментация подтверждена.** 4/5 strong fits = API buyers (platforms/SaaS с engineering team).
5. **Social proof validation -- критический риск.** Без изменений.

---

## 5. КОРРЕКТИРОВКИ К FINAL SYNTHESIS

| Пункт Final Synthesis | Статус | Корректировка |
|------------------------|--------|---------------|
| Action #1 (66 unlogged replies) | **Снижен приоритет** | Новые данные дают полную картину 143 replies из API. 66 unlogged в Google Sheet -- это ops-проблема, но мы теперь знаем полный breakdown. Не "5-8 actionable в лимбе" а 24 known actionable. Задача сводится к sync Google Sheet с API данными. |
| Action #3 (PR firms пауза) | **Усилен** | Не просто "плохой messaging". Кампания ТЕХНИЧЕСКИ сломана: 17/1000 на Step 1, 10.6% bounce Step 2. Domain damage. Немедленная остановка, не "пауза + микро-тест через 2 недели". Микро-тест только ПОСЛЕ починки technical setup. |
| Action #6 (OOO follow-up 21 лид) | **Снижен** | Не 21, а 91 OOO. Но это не "pre-warmed pipeline" -- это авто-ответы от людей, не читавших письмо. Реалистичный outcome: ~1-2 actionable, не "1-2 встречи". |
| Action #8 (Rewrite Step 1) | **Дополнен** | Недостаточно переписать Step 1. Нужно УБРАТЬ Steps 3-4 и перенаправить объём. Данные однозначны: Step 1 = 74-100% результата. |
| Target: Meetings/week 3 -> 4-5 | **Нереалистичен** | При 0.25% true interest rate = 400 контактов на 1 meeting. 4-5 meetings/week = 1,600-2,000 НОВЫХ контактов/week. Реалистичная цель: 2-3 meetings/week при текущем volume. Для 4-5 нужен либо inbound канал, либо 3x рост true interest rate. |

---

*Team Bravo Round 3. Все корректировки основаны на reply-categories-deep-dive.md и sequence-step-performance.md. Ключевой вывод: мы (и все 4 команды) в Round 1 переоценили quality воронки, потому что 63.6% replies = OOO шум. Реальная проблема -- 0.25% true interest rate, а не reply-to-meeting конверсия.*
