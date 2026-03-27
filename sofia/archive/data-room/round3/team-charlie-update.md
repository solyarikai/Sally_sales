# TEAM CHARLIE — Round 3: Data Update

**Дата:** 2026-03-16
**Фокус:** Пересчёт unit economics с РЕАЛЬНЫМИ actionable числами

---

## 1. ЧТО ИЗМЕНИЛОСЬ: ГЛАВНАЯ КОРРЕКТИРОВКА

### Раньше (Round 1): 148 replies, "genuine" ~55, conversion 16.4%
### Сейчас (Round 3): 143 replies, **actionable = 24**, true actionable rate = **0.25%**

Это фундаментальное изменение. Мы в Round 1 считали "genuine replies" как ~55 (исключив OOO/auto). Новые данные показывают:

| Метрика | Round 1 (наша оценка) | Round 3 (реальность) | Разница |
|---------|----------------------|---------------------|---------|
| Total replies | 148 | 143 | ~одинаково |
| OOO | 21 (14.2%) | **91 (63.6%)** | В 4.3 раза больше, чем мы думали |
| Actionable | ~55 | **24** | В 2.3 раза меньше |
| Actionable rate | 0.57% | **0.25%** | В 2.3 раза хуже |
| Reply-to-meeting (of actionable) | 16.4% (9/55) | **37.5% (9/24)** | В 2.3 раза лучше |

**Вывод:** Воронка не "leaks in the middle" (наш Round 1 диагноз). Воронка ГОРАЗДО уже на входе (0.25% actionable), но конверсия actionable -> meeting ГОРАЗДО выше (37.5%). Машина работает, но на микроскопическом количестве реальных лидов.

---

## 2. ПЕРЕСЧЁТ UNIT ECONOMICS ПО КАМПАНИЯМ

### Стоимость за actionable lead

Базовая ставка: $0.15/контакт (lead sourcing + email tool, наша Round 1 оценка).

| Кампания | Контакты* | Actionable | Cost/Actionable | Meetings | Cost/Meeting |
|----------|----------|------------|-----------------|----------|--------------|
| IM agencies & SaaS (flagship) | 1,980** | **20** | **$14.85** | 7*** | **$42.43** |
| IM_PLATFORMS | 649** | **2** | **$48.68** | 1 | **$97.35** |
| 0903_AGENCIES | 469** | **2** | **$35.18** | 1 | **$70.35** |
| MARKETING_AGENCIES | 265** | **0** | **N/A (бесконечность)** | 0 | **N/A** |
| 0903_PLATFORMS | 526** | **0** | **N/A (бесконечность)** | 0 | **N/A** |
| 1103_PR_firms | 17** | **0** | **N/A (бесконечность)** | 0 | **N/A** |
| **ИТОГО** | **3,906** | **24** | **$24.41** | **9** | **$65.10** |

*Step 1 sends как базовый denominator (уникальные контакты, получившие хотя бы 1 email).
**Из sequence-step-performance.md Step 1 sent.
***Большинство meetings из flagship кампании.

### Сравнение с Round 1

| Метрика | Round 1 | Round 3 | Изменение |
|---------|---------|---------|-----------|
| Cost per reply | $9.80 | $9.80 | Без изменений |
| Cost per **actionable** reply | ~$26.40 (55 genuine) | **$24.41** (24 actionable) | Пересчитано на Step 1 base |
| Cost per meeting | $161 (9,677 base) | **$65.10** (Step 1 base) | Снижение в 2.5x |
| Cost per strong fit | $221-$443 (по сегментам) | См. ниже | Пересчитано |

**ВАЖНО:** Разница в cost/meeting ($161 vs $65.10) -- это методологическая. Round 1 считал все 9,677 "contacts loaded" как denominator. Round 3 считает Step 1 sends (3,906) -- фактически отправленные email, а не загруженные контакты. Правильный denominator = Step 1 sends, потому что неотправленные контакты не стоят email tool cost (хотя стоят lead sourcing).

### Полная стоимость (с учётом всех 9,324 отправленных email, все Steps)

| Метрика | Значение |
|---------|---------|
| Всего отправлено email (все Steps) | 9,324 |
| Cost per email sent (email tool only, ~$0.01-0.03) | ~$93-280 |
| Lead sourcing cost (9,677 contacts x ~$0.10-0.12) | ~$968-1,161 |
| **Total estimated campaign cost** | **~$1,061-1,441** |
| **Cost per actionable lead (total cost)** | **$44.21-$60.04** |
| **Cost per meeting (total cost)** | **$117.89-$160.11** |
| **Cost per strong fit (total cost, 5 fits)** | **$212.20-$288.20** |

---

## 3. STEP PERFORMANCE: ЧТО МЕНЯЕТ

### Step 1 = 74% всех ответов в flagship

| Step | Sent | Replies | Reply Rate | % от всех replies |
|------|------|---------|------------|-------------------|
| 1 | 1,980 | 91 | **4.6%** | **74%** |
| 2 | 1,809 | 20 | 1.1% | 16% |
| 3 | 1,229 | 11 | 0.9% | 9% |
| 4 | 680 | 1 | **0.1%** | **1%** |

**Но 91 reply на Step 1 -- это в основном OOO.** Из 143 total replies, 91 = OOO. Значит подавляющее большинство OOO приходят на Step 1 (автоответчик срабатывает на первое письмо).

**Пересчёт actionable по Steps (оценка):**
- Если 91 из 91 Step 1 replies в flagship -- и 91 OOO по всей кампании...
- Значит ~70-75 OOO из 91 Step 1 reply = OOO авто-ответы
- **Actionable из Step 1: ~16-21 лидов** (из 91 replies)
- **Actionable reply rate Step 1: ~0.8-1.1%** (вместо headline 4.6%)

### Step 4 мёртв -- подтверждено данными

680 sends -> 1 reply -> 0 actionable. **ROI Step 4 = ОТРИЦАТЕЛЬНЫЙ.**

Стоимость отправки 680 email на Step 4: ~$6.80-20.40 (email cost only). Не катастрофа в деньгах, но:
1. 680 email = риск для domain reputation от перегрузки
2. 680 email без engagement = сигнал почтовым провайдерам что отправитель спамит
3. Время на создание/поддержку копии Step 4 = waste

**Round 1 мы писали:** "Touch 4 ('Are you the right person...') generates useful redirects (5 redirects logged)." **Корректировка:** Данные показывают 1 reply на Step 4 из 680 sends. 5 redirects в общем -- не доказательство ценности Step 4.

---

## 4. PR FIRMS: ТЕХНИЧЕСКИ СЛОМАНА

Новые данные усиливают наш Round 1 вердикт:

| Факт | Значение | Что это значит |
|------|---------|----------------|
| Step 1 sent | **17** (из ~1,000+ загруженных) | Кампания технически не работает -- 98% лидов НЕ получили Step 1 |
| Step 2 sent | 263 | Лиды пропустили Step 1 и получили сразу Step 2 -- нарушена логика последовательности |
| Step 2 bounce rate | **10.6%** | КРИТИЧНО -- бенчмарк < 3%. Разрушает domain reputation |
| Actionable | **0** | Из 3 ответов: 2 OOO + 1 Wrong Person |

**Round 1 мы писали:** "PR firms at $75 per reply and 0 meetings... burning money."
**Round 3 корректировка:** PR firms НЕ ТОЛЬКО горит деньгами -- она АКТИВНО ВРЕДИТ deliverability через 10.6% bounce rate. Каждый день работы этой кампании ухудшает доставляемость ВСЕХ кампаний с того же домена.

**Новая рекомендация: НЕ ПАУЗИТЬ, А ОСТАНОВИТЬ НЕМЕДЛЕННО.** В Round 1 и FINAL-SYNTHESIS мы рекомендовали "паузу + микро-тест через 2 недели." С 10.6% bounce rate -- это domain damage. Нужно:
1. Остановить кампанию СЕГОДНЯ
2. Провести аудит email list (28 bounces из 263 отправок)
3. Верифицировать ВСЕ оставшиеся emails перед любой новой отправкой
4. Подождать 4+ недели для восстановления domain reputation прежде чем микро-тест

---

## 5. ОБНОВЛЁННЫЙ ТОП-5 ПО ROI

### Пересчёт с actionable rate 0.25%

| Rank | Кампания/Сегмент | Actionable | Step 1 Sent | Actionable Rate | Cost/Actionable* | Meetings | Strong Fits | **ROI Score** |
|------|-----------------|-----------|-------------|-----------------|-----------------|----------|-------------|---------------|
| **1** | **IM agencies & SaaS (flagship)** | **20** | 1,980 | **1.01%** | **$14.85** | 7 | 3-4 | **ЛУЧШИЙ** |
| **2** | **0903_AGENCIES** | **2** | 469 | **0.43%** | **$35.18** | 1 | 1 | **ХОРОШИЙ** |
| **3** | **IM_PLATFORMS** | **2** | 649 | **0.31%** | **$48.68** | 1 | 1 | **СРЕДНИЙ** |
| **4** | **MARKETING_AGENCIES** | **0** | 265 | **0.00%** | **N/A** | 0 | 0 | **НУЛЕВОЙ** |
| **5** | **0903_PLATFORMS** | **0** | 526 | **0.00%** | **N/A** | 0 | 0 | **НУЛЕВОЙ** |
| **6** | **1103_PR_firms** | **0** | 17** | **0.00%** | **N/A** | 0 | 0 | **ОТРИЦАТЕЛЬНЫЙ (domain damage)** |

*При $0.15/контакт на Step 1 sends.
**17 Step 1 sends -- кампания технически сломана, denominator невалиден.

### ЧТО ИЗМЕНИЛОСЬ В ТОП-5 vs. Round 1

| Rank | Round 1 | Round 3 | Изменение |
|------|---------|---------|-----------|
| 1 | IM agencies & SaaS (~$221/strong fit) | IM agencies & SaaS (**$14.85/actionable**) | Подтверждён как лидер. Ещё лучше при правильном расчёте. |
| 2 | Marketing agencies (~$246/strong fit) | **0903_AGENCIES** ($35.18/actionable) | MARKETING_AGENCIES выпал (0 actionable). 0903_AGENCIES заменил. |
| 3 | IM platforms Wk3-4 (~$440/strong fit) | IM_PLATFORMS ($48.68/actionable) | Подтверждён, но дороже flagship в 3.3x. |
| 4 | Agencies + IM combined (~$443/strong fit) | MARKETING_AGENCIES (0 actionable) | **ПРОВАЛ** -- не в топе больше. |
| 5 | PR firms (infinite) | 0903_PLATFORMS (0 actionable) | Оба на нуле. PR firms ещё хуже (domain damage). |

### КЛЮЧЕВОЙ ВЫВОД ДЛЯ ТОП-5:

**Flagship = 83% всех actionable лидов (20 из 24).** Это не "лучший сегмент" -- это ЕДИНСТВЕННЫЙ работающий сегмент.

Все остальные кампании ВМЕСТЕ дали 4 actionable из 1,909 Step 1 sends = 0.21% actionable rate. Flagship дал 20 из 1,980 = 1.01%. Разница в 5x.

---

## 6. КОРРЕКТИРОВКИ К FINAL-SYNTHESIS

### 6.1 Целевые метрики (ОБНОВЛЕНО)

| Метрика | Round 1 (FINAL-SYNTHESIS) | Round 3 (корректировка) | Почему |
|---------|--------------------------|------------------------|--------|
| Email reply rate | 1.53% -> 2.5% (4 нед) | **Actionable rate: 0.25% -> 0.5%** (4 нед) | Reply rate -- vanity metric. 63.6% = OOO. Мерить нужно actionable rate. |
| Reply-to-meeting (genuine) | 16.4% -> 20% | **Actionable-to-meeting: 37.5% -> 40%** | При правильном denominator (24, не 55) -- конверсия уже ОТЛИЧНАЯ. |
| Cost per meeting | $161 -> $100 | **$65-160 (диапазон в зависимости от расчёта) -> $50-80** | Два валидных расчёта, целить на нижнюю границу. |
| Pipeline value/month | ~$250K (5 strong fits x $50K avg) | **Без изменений** -- strong fits считались верно | -- |

### 6.2 91 OOO -- это НЕ потерянные лиды

Round 1 мы писали "21 OOO responses." Реальное число: **91 OOO = 63.6% ВСЕХ ответов.**

Это меняет приоритет OOO follow-up:
- Round 1: #5 приоритет, 21 лид, ~45 мин
- Round 3: **#2-3 приоритет, 91 лид, ~3-4 часа**

При 15% re-engagement rate:
- 91 x 15% = ~14 re-engaged replies
- 14 x 37.5% actionable-to-meeting = ~5 meetings
- 5 meetings -- это БОЛЬШЕ, чем весь текущий pipeline (9 meetings total)

**OOO follow-up = единственный самый крупный source of new meetings.**

### 6.3 Step 4 = убрать из всех кампаний

В FINAL-SYNTHESIS нет явной рекомендации убрать Step 4. Данные:
- Flagship: 680 sends, 1 reply, 0 actionable
- Все остальные: Step 4 sends = 0 (не дошли)

**Рекомендация:** Убрать Step 4 из всех кампаний. Оставить 3 Steps. Перенаправить энергию копирайтера на улучшение Steps 1-3.

---

## 7. ИТОГОВЫЙ ОБНОВЛЁННЫЙ ТОП-5 ДЕЙСТВИЙ ПО ROI

С учётом новых данных (actionable rate, OOO volume, step performance, PR firms bounce):

| Rank | Действие | Изменение vs. Round 1 | Обоснование числами |
|------|----------|----------------------|---------------------|
| **1** | **Отработать 91 OOO (не 21!) -- систематический follow-up** | Был #5 -> стал **#1** | 91 лидов x 15% re-engage = 14 replies x 37.5% = **5 meetings**. Это больше, чем весь текущий pipeline. |
| **2** | **66 незалогированных replies + 24 actionable -- немедленный follow-up** | Был #1 -> остаётся **#2** | 24 actionable лида -- каждый стоит $24-60. Каждый день задержки снижает conversion probability на ~10%. |
| **3** | **9 reply scripts** | Был #2 -> остаётся **#3** | При 37.5% actionable-to-meeting, каждый потерянный из-за плохого скрипта лид = потерянная встреча с вероятностью 1 к 3. |
| **4** | **ОСТАНОВИТЬ (не паузить) PR firms** | Был #4 -> усилен до **STOP** | 10.6% bounce rate = domain damage для ВСЕХ кампаний. Не "потеря денег" -- АКТИВНЫЙ ВРЕД. |
| **5** | **Убрать Step 4, сконцентрироваться на Step 1 flagship** | **НОВЫЙ** | Step 4: 680 sends = 1 reply = 0 actionable. Step 1 flagship: 1.01% actionable rate = 83% всех результатов. Каждый доллар на Step 4 = waste. Каждый доллар на улучшение Step 1 = ROI. |

### Выбывшие из топ-5:
- **WANNA TALK enterprise** (был #3) -- по-прежнему важен, но ROI OOO follow-up (91 лид, доказанная доставка) превосходит ROI enterprise ABM (12-15 лидов, непроверенная конверсия). Enterprise переходит в #6.
- **OOO reminders** (был #5) -- поглощён новым #1 (91 OOO вместо 21).

---

## 8. ФИНАЛЬНАЯ АРИФМЕТИКА

**При текущей unit economics:**
- 1 actionable lead стоит $24-60
- 1 meeting стоит $65-160
- 1 strong fit стоит $212-288
- Средний потенциал strong fit deal: $50K/год

**ROI кампании:**
- Total spend: ~$1,061-1,441
- Strong fits: 5
- Pipeline value: $250K (5 x $50K)
- **ROI: 173x-236x** (pipeline / spend)
- Если 1 deal closes at $50K: **ROI = 35x-47x**
- Если 2 deals close: **ROI = 69x-94x**

**ROI при фиксации 91 OOO (3-4 часа работы):**
- SDR time cost: ~$60-80 (4 часа x $15-20/час)
- Expected meetings: 5
- Expected strong fits: 2-3 (при текущем 100% strong fit rate из held)
- Expected pipeline: $100K-150K
- **ROI: 1,250x-2,500x**

Это самый высокий ROI action во всём анализе.
