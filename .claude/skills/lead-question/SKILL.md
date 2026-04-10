---
name: lead-question
description: >-
  Оформление входящих вопросов от лидов в структурированную карточку #question.
  Ресёрч лида, определение сегмента, форматирование, драфт ответа.
  Используй когда: "вопрос от лида", "lead question", "оформи вопрос",
  "пришёл вопрос", "ответь лиду", "#question", "вопрос от", "лид спрашивает",
  "reply to lead", "draft reply", "incoming question".
---

# /lead-question - оформление входящих вопросов от лидов

## Цель

Превратить сырой вопрос от лида в структурированную карточку `#question` с полным контекстом и драфтом ответа.

---

## Ввод от пользователя

Обязательные:
1. **Имя лида** (или компания, или email - любой идентификатор)
2. **Канал** (Email, LinkedIn, Twitter, Website, другое)
3. **Сообщение** - сырой текст вопроса от лида

Опционально:
- Email, LinkedIn URL, компания (если пользователь уже знает)
- Контекст вопроса (из какой кампании пришёл, что обсуждали ранее)

Если чего-то не хватает - спроси у пользователя, НЕ додумывай.

---

## Шаг 1 - Ресёрч лида

**СКОРОСТЬ КРИТИЧНА.** Все поиски делай ПАРАЛЛЕЛЬНО в одном сообщении.

### 1a. Параллельный поиск (ВСЕ ЗАПРОСЫ ОДНОВРЕМЕННО)

Запусти ВСЕ эти запросы в одном tool call batch:
- WebSearch: `"{имя}" "{компания}" LinkedIn` (найдёт профиль + должность + локацию)
- WebSearch: `"{компания}" influencer marketing platform features` (найдёт что делает компания)
- WebSearch: `"{конкурент/продукт из вопроса}" features pricing` (если лид спрашивает про конкурента)

НЕ делай последовательных поисков. НЕ жди результат одного поиска перед следующим.

### 1b. Опционально (только если 1a не дал достаточно)
- Поищи лида в `OS | Leads | All` (sheet ID: `1Jia8Sor5V2cby3sORXZxuaSvM_vgWB-uMdazK6RZ5wA`) через `sheets_search`
- Поищи в SmartLead через `/smartlead` если есть email

### 1c. Заполни карточку лида
Собери все поля:
- **Имя** (full name)
- **Должность** (title/role)
- **Email**
- **LinkedIn URL**
- **Компания** (name + domain)
- **Описание** (что делает компания, 1 строка)
- **Локация** (город, страна)

Если какое-то поле не найдено - поставь `[не найдено]` и сообщи пользователю.

---

## Шаг 2 - Определи гипотезу/сегмент

На основе профиля компании определи к какому сегменту OnSocial относится лид:

| Сегмент | Описание | Маркер |
|---------|----------|--------|
| `OnSocial \| Platforms (SaaS / Data)` | IM-платформы, SaaS, social listening, analytics | Компания - платформа/SaaS с API или dashboard для маркетологов |
| `OnSocial \| Agencies (IM-Tool / SaaS)` | IM-агентства 10-200 чел с выделенной IM-практикой | Агентство, фокус на influencer marketing |
| `OnSocial \| Affiliate & Performance` | Affiliate платформы, performance marketing | Трекинг партнёрок, performance, ROI attribution |
| `OnSocial \| E-commerce / D2C` | Бренды с in-house IM | Бренд продаёт напрямую, использует инфлюенсеров |
| `OnSocial \| Other` | Не подходит ни к одному | Не IM-индустрия, но интересуется данными |

Если не уверен - поставь `[уточнить]`.

---

## Шаг 3 - Напиши драфт ответа

### Правила для ответов (ОБЯЗАТЕЛЬНО):

1. **Сначала ответь на конкретный вопрос лида** - не начинай с pitch'а OnSocial
2. **Тон**: дружелюбный, экспертный, не шаблонный. Как будто пишет senior sales engineer, а не бот
3. **Длина**: 50-120 слов. Не больше
4. **Структура**: ответ на вопрос -> 3-5 буллетов про OnSocial (только релевантные к вопросу) -> мягкий CTA
5. **CTA формулировка**: мягкая. "Could walk you through", "happy to show", "see if it fits". НЕ "book a demo", НЕ "schedule a call"
6. **НЕ угадывай нишу клиента** - не говори "your mamá influencers" если не уверен на 100%
7. **НЕ обещай конкретный результат** - "could", "see if", а не "will", "guaranteed"
8. **Em dashes** (`-`): используй обычный дефис, не длинное тире

### Контекст OnSocial для ответов:

- 450M+ public creator profiles (Instagram, TikTok, YouTube)
- No creator consent/OAuth required - works on any public profile
- 35+ API endpoints, high RPS, 24/7 uptime
- Creator search with 27+ filters
- Audience demographics, engagement rates, credibility scores
- Data refreshed every 24-48h
- Built for product teams (API-first)

---

## Шаг 4 - Выведи карточку

Формат вывода (ТОЧНО такой):

```
#question

📩 Channel: {Email | LinkedIn | Twitter | Website | Other}
🧩 Hypothesis: {сегмент из Шага 2}

👤 {Full Name} - @ {Company Name}
✉️ Email: {email или [не найдено]}
🔗 LinkedIn: {URL или [не найдено]}
🏢 {Company Name} ({domain})
🧩 Description: {должность} at {Company} - {что делает компания, 1 строка}
🌍 Location: {City, Country}

Message:
"{оригинальный текст сообщения от лида - дословно}"

💬 Draft Reply:

{текст ответа}
```

---

## Шаг 5 - Запиши в Leads booking_Sofia (ОБЯЗАТЕЛЬНО, автоматически)

После вывода карточки **всегда** добавляй лида в таблицу `OnSocial <> Sally` в блок **pending** наверх списка.

### Параметры таблицы:
- Sheet ID: `1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E`
- Tab: `Leads booking_Sofia`

### Алгоритм:

**5a. Прочитай структуру листа:**
```
sheets_read_range(
  spreadsheet_id="1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E",
  range="Leads booking_Sofia!A1:Z50"
)
```

**5b. Найди блок pending и строку с датой недели:**

Структура листа:
```
... (другие блоки) ...
[строка] pending          ← заголовок блока
[строка] 06.04-10.04     ← срез недели (дата-диапазон)
[строка] лид 1           ← первый лид
[строка] лид 2
...
```

- Найди строку с текстом "pending" (регистр не важен)
- Следующая строка после pending — это строка с датой недели (например `06.04-10.04`) — её НЕ трогай
- Новый лид вставляется ПОСЛЕ строки с датой, т.е. на позицию pending+2

**5c. Сдвинь существующие строки вниз и вставь новую запись:**
- Прочитай существующие данные начиная с pending+2 до конца блока (до следующего заголовка блока)
- Запиши их на строку ниже (сдвинь на 1 вниз через `sheets_write_range`)
- Запиши нового лида в строку pending+2

**5d. Данные для записи (маппинг по заголовкам колонок):**
Сначала прочитай row 1 (заголовки) чтобы понять колонки. Стандартные маппинги:
- `Name` / `Full Name` → `{Full Name}`
- `Company` → `{Company Name}`
- `Email` → `{email}`
- `LinkedIn` / `LinkedIn URL` → `{LinkedIn URL}`
- `Segment` / `Hypothesis` → `{сегмент из Шага 2}`
- `Channel` → `{Email | LinkedIn | ...}`
- `Date` → сегодняшняя дата (YYYY-MM-DD)
- `Status` → `pending`
- `Message` / `Question` → первые 100 символов оригинального сообщения
- `AE` / `Owner` → `Sofia`

Если колонка не найдена — пропусти (не ломай форматирование строки).

**5e. Подтверди:**
После записи выведи: `✅ Added to Leads booking_Sofia — row {N}`

---

## Примеры

### Пример 1: Вопрос про конкурента

**Ввод:** "Kyle Roach из SocialPruf спрашивает по email как мы отличаемся от Phyllo"

**Вывод:**
```
#question

📩 Channel: Email
🧩 Hypothesis: OnSocial | Platforms (SaaS / Data)

👤 Kyle Roach - @ SocialPruf
✉️ Email: kyle@socialpruf.com
🔗 LinkedIn: https://www.linkedin.com/in/kyle-roach--
🏢 SocialPruf (socialpruf.com)
🧩 Description: COO & Co-Founder at SocialPruf - social analytics platform for organic social performance
🌍 Location: Toronto, Canada

Message:
"Hi there, how do you compare to getphyllo? https://www.getphyllo.com/ We use their api in our product for influencer demographics and search tool"

💬 Draft Reply:

Hey Kyle,

The core difference: Phyllo is consent-based - it only pulls data from creators who've authenticated via OAuth. That limits your searchable pool to whoever has connected their account.

OnSocial works the opposite way:

- 450M+ public profiles - no creator sign-up required
- Audience demographics, engagement rates, credibility scores
- Creator search with 27+ filters across Instagram, TikTok & YouTube
- 35+ endpoints, high RPS, 24/7 uptime - built for product teams
- Data refreshed every 24-48h

So your search tool works on any creator your users look up - not just the ones in Phyllo's consented pool.

Happy to walk you through the docs if useful - takes 15 min.
```

### Пример 2: Вопрос про цены

**Ввод:** "Maria из InfluencerDB спрашивает в LinkedIn сколько стоит API"

**Вывод:** карточка с ресёрчем + ответ НЕ с прайсом, а с предложением обсудить на звонке (цены не публичные - обсуждаются после квалификации)

### Пример 3: Лид согласился получить данные ("yeah, send me")

**Ввод:** "paul.adewumi@viralget.io" (только email — лид в SmartLead, история в inbox)

**Контекст:** Bhaskar предложил прогнать локальных creators через API и показать реальный output. Лид ответил: "Yeah, that would be great. You can share the result with me."

**Алгоритм:**
1. Поиск по email в SmartLead (`fetch_lead_by_email`) → получаем campaign_id + lead_id
2. `get_lead_message_history` → видим последний ответ лида
3. Если SmartLead обрезает HTML-тело — сообщи пользователю что видно, попроси полный текст

**Вывод:**
```
#question

📩 Channel: Email
🧩 Hypothesis: OnSocial | Agencies (IM-Tool / SaaS)

👤 [Founder Name] - @ [Company Name]
✉️ Email: [email]
🔗 LinkedIn: [url]
🏢 [Company] ([domain])
🧩 Description: Founder & COO at [Company] - data-driven end-to-end IM platform for brands
🌍 Location: [City, Country]

Message:
"Yeah, that would be great. You can share the result with me."

💬 Draft Reply:

Hey [Name],

Pulling a few [geo] creators through now - you'll see audience breakdown by city/state, engagement rate, fraud score, and credibility index. Public data, no creator sign-up needed.

Any specific handles you want included? Otherwise I'll pick a mix across Instagram and TikTok relevant for [their market].

Best,
[Sender]
```

**Паттерн "yeah send me"**: лид согласился на data demo. Ответ короткий — подтверди что делаем, спроси handles или скажи что выберем сами. Не питчи заново.

---

## AI Red Flags — обязательная проверка перед отправкой

Каждый драфт ДОЛЖЕН пройти этот фильтр. Если нашёл хоть один флаг - перепиши.

### Слова-маркеры (ЗАПРЕЩЕНЫ)

**Глаголы-пустышки:** leverage, streamline, utilize, optimize, facilitate, foster, bolster, spearhead, navigate, harness, empower, elevate, cultivate, delve, dive in, unlock

**Прилагательные-буллшит:** robust, comprehensive, cutting-edge, game-changing, groundbreaking, innovative, transformative, seamless, holistic, dynamic, scalable, world-class, best-in-class, state-of-the-art, tailored, specifically

**Существительные-вода:** landscape, ecosystem, synergy, paradigm, framework, alignment, bandwidth, cadence, deep dive, low-hanging fruit, value proposition, pain point

**Связки-костыли:** Moreover, Furthermore, Additionally, In today's fast-paced, It's worth noting, That said, At the end of the day, In this regard

**Чатбот-фразы:** "Great question!", "Absolutely!", "I'd be happy to help", "Let me break this down", "Here's the thing", "Let's dive in", "I hope this email finds you well", "I completely understand", "That's a great point"

### Структурные паттерны (ЗАПРЕЩЕНЫ)

- Начинать с комплимента или пересказа слов лида ("Love what you're building", "Thanks for sharing")
- Ровно 3 буллета (AI почти всегда делает именно 3)
- Шаблон intro → bullets → CTA в каждом письме
- Все параграфы одинаковой длины
- Все предложения грамматически идеальные - ни одного фрагмента
- "Let me know if you have any questions!" или "Looking forward to hearing from you" в конце
- Subject line как заголовок блог-поста

### Тон (ЗАПРЕЩЕНО)

- Безудержный позитив без единого сомнения или оговорки
- Слишком отполировано: 0 разговорных оборотов, 0 характера
- Фейковая эмпатия: "I understand how challenging X can be"
- "We" и "our" через слово, но ничего конкретного
- Восклицательные знаки где не надо
- "Best regards" или "Warm regards" (люди пишут "Best," или "Thanks," или вообще ничего)

### Sales-специфичные флаги (ЗАПРЕЩЕНЫ)

- "{Name}, I noticed your company recently..." (мердж-тег + generic наблюдение)
- Комплимент который подходит любой компании на свете
- "Would love to hop on a quick 15-minute call"
- 3-5 преимуществ продукта без связи с конкретной ситуацией лида
- "Companies like X, Y are already seeing results" (без контекста)

### Как писать по-человечески (ОБЯЗАТЕЛЬНО)

1. **Ритм**: короткое предложение. Потом длинное. Потом среднее. Не одинаковые
2. **Одно несовершенство**: дефис посреди мысли, фрагмент, скобки как в разговоре
3. **Конкретика про лида**: упомянуть что-то специфичное - их пост, их продукт, их рынок
4. **Своё мнение**: "I think X is overhyped, but Y actually works" - не бояться позиции
5. **Разговорный тон**: сокращения (we're, don't), "honestly", начать с "And" или "But"
6. **Минимум буллетов**: если можно написать абзацем - пиши абзацем
7. **Разные концовки**: вопрос, P.S., одна строка, ничего - не одно и то же каждый раз
8. **Тест вслух**: прочитай вслух. Если звучит как пресс-релиз - переписывай
9. **Убей каждое слово которое существует только чтобы звучать умно**

---

## Чеклист перед выводом

- [ ] Все поля карточки заполнены (или помечены `[не найдено]`)
- [ ] Гипотеза/сегмент определена
- [ ] Ответ отвечает на КОНКРЕТНЫЙ вопрос лида (не generic pitch)
- [ ] Длина ответа 50-120 слов
- [ ] CTA мягкий ("could", "happy to", "see if")
- [ ] Нет em dashes (только `-`)
- [ ] Нет угадывания ниши клиента
- [ ] Нет обещаний конкретного результата
- [ ] **Прошёл AI Red Flags проверку (секция выше)**
