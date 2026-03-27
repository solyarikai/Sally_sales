# Полное руководство по аутричу — База знаний

> Полная база знаний по B2B-аутричу. Собрана из всех документов для быстрого ориентирования агента.

---

# Оглавление

1. [Сбор базы контактов](#1-сбор-базы-контактов)
   - [Основной источник: Apollo.io](#основной-источник-apolloio)
   - [Гайд по Apollo](#гайд-по-apollo)
   - [Как использовать AI в Apollo](#как-использовать-ai-в-apollo)
   - [Как найти похожие компании в Apollo](#как-найти-похожие-компании-в-apollo-lookalike)
   - [Crona (Сегментация и обогащение)](#crona-сегментация-и-обогащение)
   - [Гайд по Clay](#гайд-по-clay)
   - [Explee](#explee)
   - [Apify](#apify)
   - [Outscraper](#outscraper)
   - [Альтернативные/дополнительные источники](#альтернативныедополнительные-источники)
   - [Поиск русскоязычных контактов](#поиск-русскоязычных-контактов)
   - [Конференции](#конференции)
   - [Источники высокого намерения (ссылки)](#источники-высокого-намерения-ссылки)
   - [Обогащение и валидация email](#обогащение-и-валидация-email)
   - [Мини SOP](#мини-sop)
2. [Написание секвенса](#2-написание-секвенса)
   - [Фаза 1: Сбор информации о клиенте](#фаза-1-сбор-информации-о-клиенте)
   - [Фаза 2: AI-анализ проекта (JTBD)](#фаза-2-ai-анализ-проекта)
   - [Фаза 3: Создание секвенса (промпты Email 1, 2, 3)](#фаза-3-создание-секвенса-с-claude)
3. [Настройка Email-аутрича](#3-настройка-email-аутрича)
   - [Валидация email](#1-валидация-email)
   - [Настройка почтовых ящиков](#2-настройка-почтовых-ящиков)
   - [Запуск кампании в Smartlead](#3-запуск-кампании-в-smartlead)
   - [Управление ответами вне SmartLead](#управление-ответами-вне-smartlead)
4. [Настройка LinkedIn-аутрича](#4-настройка-linkedin-аутрича)
   - [Настройка LinkedIn и SSI](#1-настройка-linkedin)
   - [Настройка Getsales](#2-настройка-getsales)
   - [Автоматизация Getsales → Google Sheets](#автоматизация-getsales--google-sheets)
5. [Настройка Telegram-аутрича](#5-настройка-telegram-аутрича)
   - [Telegram-бот автоматизации](#telegram-бот-автоматизации-spambot)
6. [Лучшие практики](#6-лучшие-практики)
7. [Частые ошибки](#частые-ошибки)

---

# 1. Сбор базы контактов

## Предварительный чек-лист

- **Проверь готовые сегменты**: если твой сегмент уже есть — **скопируй**. → Sally bases (внутренняя ссылка Notion)
- **Определи ICP асинхронно** (звонок не нужен на старте): гео, численность, индустрия, роли, технологии, исключения, обязательные критерии.
- Проверь таблицу конференций
- **Поделись ICP-таблицей** (Google Sheets: `1r_NAFRnAlFRzbrhTUpyTh7416OLR7IhJU3ouiRRpaEI`) с клиентом и дай доступ по email
- **Только после "ICP: Approved"** → собирай компании и контакты.

---

## Основной источник: Apollo.io

Лучший баланс покрытия, контактов, UX и стоимости.

**Экономный расход кредитов:**
1. Экспортируй **компании** (без людей пока).
2. Отфильтруй компании в **Crona** по ICP через web processing.
3. Выгрузи **людей** только из отфильтрованного набора.

---

## Гайд по Apollo

### Видеогайд
- Google Drive: `1FcQAqSShhC10B6DDWqCRVxHnh1HWdMHm`

### Очистка компаний в Apollo

**Шаг 1: Перейди в раздел Companies**
Открой раздел Companies в Apollo.

**Шаг 2: Настрой фильтры списков**
В настройках фильтров списков добавь **все существующие списки компаний** в фильтр исключений.

> ⚠️ Критично: Убедись, что исключены ВСЕ твои списки до начала удаления. Это предотвратит случайное удаление нужных компаний.

**Быстрый способ исключить списки:**
1. Кликни на пустое место в поле Exclude левой кнопкой мыши (ЛКМ)
2. Нажми Enter
3. Повторяй быстро, пока все списки не будут исключены

**Шаг 3: Удали ненужные компании**
1. Выбери все оставшиеся компании, которых нет ни в одном списке
2. **Лимит**: Выбирай не более **50 000 компаний** за раз
3. Нажми меню три точки (...)
4. Выбери Delete

**Важные замечания:**
- **Временная невидимость в поиске**: После удаления компании могут не появляться в результатах поиска до **1 часа**.
- **Восстановление компаний**: Удалённые компании вернутся в поисковый индекс в течение **24 часов** и снова будут доступны для сохранения.
- **Зачем это нужно**: Регулярная очистка неиспользуемых компаний освобождает место для новых записей в базе Apollo.

---

## Как использовать AI в Apollo

1. Чтобы точно понять, какие фильтры выставить в Apollo, я прошу нейросеть найти **20 компаний, идеально подходящих под ICP**. Опираемся на свой сегмент.

> Лучше всего использовать наш Google AI Studio, он уже обучен и запомнил всю информацию по проекту.

2. Эти компании сохраняем в лист и выгружаем. Отправляем файл в нейросеть и просим выделить фильтры, которые встречаются **чаще всего.**
3. Выставляем фильтры в Apollo, опираясь на советы нейросети.

### Как использовать AI-промпт в Apollo

Нажимаем фиолетовую кнопку — **Run custom AI prompt**

**Настройки для промпта:** Select Prompt: Perplexity Sonar

Через нашу нейросеть просим переделать промпт под свой сегмент и вставляем в поле для промпта.

### Пример AI-промпта для Apollo (проверка соответствия ICP)

```
"Is this company a good fit for [Client]'s [product/platform]?"

Evaluate whether the company {{account.name}} fits the Ideal Customer Profile (ICP) for [Client], which provides [description of product]. The platform targets companies involved in [target industry/activity], who can leverage their [asset] to [desired outcome].

The company is a good fit if it matches at least one of the following profiles:

✅ Profile 1: [Profile Name]
Companies that:
- [Criterion 1]
- [Criterion 2]
- [Criterion 3]
- Preferably have [size] employees

✅ Profile 2: [Profile Name]
Companies that:
- [Criterion 1]
- [Criterion 2]

🔍 What to Look For in description/domain/scraped info:
- Mentions of: "[keyword1]", "[keyword2]", "[keyword3]"
- Keywords like: [list of keywords]
- Signs they [behavior indicator]

✍️ Output Format: [Client]-fit: [Yes / No]
Explanation: Clearly state which profile the company aligns with and why.
```

**Воркфлоу после AI-фильтрации:**
1. Вручную, примерно на 20 компаниях, нужно проверить, правильно ли работает промпт. При необходимости поправить сам промпт.
2. Делаем поиск по людям в этих компаниях.
3. Сохраняем людей с проверенными и с непроверенными почтами отдельно.
4. Непроверенные почты загружаем в Clay для обогащения (Find Work Email enrichment).

---

## Как найти похожие компании в Apollo (Lookalike)

### Что делает Lookalike?
В разделе **Company & Lookalikes** ты вводишь 1-3 компании, на которые таргетишься. AI находит похожие бизнесы, которые затем можно дополнительно фильтровать по индустрии, ключевым словам, размеру и т.д.

### Проблема раньше:
- **Слишком общие ключевые слова** приводили к множеству нерелевантных компаний.
- Некоторые компании указывают только **описания**, а не ключевые слова — поиск по описаниям выдавал много мусора.

**Lookalike решает это**: AI фокусируется на конкретных сегментах вместо размазывания поиска.

### Как использовать: пошаговый план
1. Иди в корпоративный **GPT**, опиши свою компанию, ICP и сегмент.
2. Попроси найти **10 компаний**, идеально подходящих под твоё предложение.
3. Выбери топ-3 и загрузи их в Lookalike в Apollo.
4. Добавь фильтры: индустрии, ключевые слова, роли, локации — что лучше подходит.
5. Получи список максимально релевантных компаний.

---

## Crona (Сегментация и обогащение)

> Crona — наш собственный софт. Используй его!

Старое название — Leadokol.

### 1) Web Processing

#### Сегментация

**Пример промпта для сегментации (проект Deliryo):**

```
You are helping [Client] identify companies that could potentially partner with its [product].
[Client description and value proposition].

Your task:
Analyze the company information and suggest the most suitable segment from the list below.
If several categories might apply, choose the one that seems most relevant.
Provide a brief reasoning paragraph explaining your choice.

Segments:
SEGMENT_1 — [Description]
SEGMENT_2 — [Description]
SEGMENT_3 — [Description]
OTHER — Any business that does not clearly fit the above or has limited public information.

Guidelines:
- Focus on what the company mainly does
- Language or geography clues indicate likely relevance
- Be concise, objective, and confident in your reasoning

Output format:
Line 1: One segment name → [SEGMENT_1 / SEGMENT_2 / ... / OTHER]
Line 2: 2–3 sentences explaining your reasoning in plain English.

Input:
Website:
Website text:
```

**Код фильтра (исключить OTHER):**
```
!{{result.<имя_энричера_сегментации>}}.include?("OTHER")
```

#### Создание писем (через Crona)

Crona может генерировать персонализированные тела писем на основе сектора компании. Используй шаблоны по сегментам с переменными:
- `{company name}` — очищенное название бренда (убрать Ltd, Inc, LLC и т.д.)
- `{property type}` / `{location}` / `{business vertical}` — из контента сайта

**Строгие требования к генерации писем:**
- Использовать ТОЛЬКО шаблон, соответствующий сектору
- Заполнять переменные контекстными данными
- Сохранять оригинальную структуру абзацев
- Заканчивать вопросом-призывом к действию
- БЕЗ подписей, должностей, контактной информации
- БЕЗ форматирования текста (жирный, курсив, подчёркивание)
- БЕЗ дополнительного контента сверх шаблона

#### Создание тем писем (через Crona)

Темы писем генерируются по шаблону сектора с переменной `{company name}`.

**Требования:**
- Максимум 50 символов
- Аббревиатуры валют в CAPS (USDT, BTC)
- БЕЗ восклицательных знаков
- БЕЗ слов в ALL CAPS (кроме валют)
- БЕЗ эмодзи и кавычек

#### Поиск email (через Crona)

Ищет email через Findyemail и верифицирует в MillionVerifier. Если email не верифицирован — просто не будет добавлен.

> Используй после фильтрации базы!

### 2) Обработка Sales Navigator

#### Получение ссылки SN

**Способ 1 — Поиск контактов с нуля** (без списка компаний):
- Видеогайд на Google Drive: `1xIzD_thqrBDZH5TZ6ymSMDjdwtPnDq2e`

**Способ 2 — Поиск из списка компаний (CSV-файл):**

> Этот метод пока работает только с аккаунтом 'sales nav for queries'.

### 3) Как запустить 25 строк
Видеогайд доступен.

### 4) Найти LinkedIn человека по имени, затем найти сайт
Видеогайд доступен.

### Энричеры Crona

**Количество сотрудников:**
```
{{stats.employee_count}}
```

**Энричер сегментации (пример INXY):**

```
gpt("You are a company classification analyst for [Client] solutions. Analyze the provided company website and classify it into ONE of the following segments based on their primary business need:

**SEGMENT_1** - [Description]
- [Example company types]

**SEGMENT_2** - [Description]
- [Example company types]

**SEGMENT_3** - [Description]
- [Example company types]

**OTHER** - Companies whose business model doesn't align
- [Examples]

**OUTPUT FORMAT:**
Classification: [SEGMENT_1/SEGMENT_2/SEGMENT_3/OTHER]
Reasoning: [One paragraph]

**GUIDELINES:**
- Choose the PRIMARY need based on their core business model
- Focus on their most critical payment flow challenge
- Consider transaction volume, frequency, and direction
- Use OTHER only when no clear need

---
Input
Website Link: {{company.website}}
Website Content: {{company.website_text}}")
```

**Шаблон промпта для сегментации (универсальный):**

```
gpt("
COMPANY_INFO:
- Company Name: [Название вашей компании]
- Business Description: [Краткое описание]
- Competitive Landscape: [Конкуренты]

TARGET_SEGMENTS:
1. SEGMENT_1_NAME:
   - Description: [Что нужно этому сегменту]
   - Examples: [10-15 типов компаний]

2. SEGMENT_2_NAME:
   - Description: [Что нужно этому сегменту]
   - Examples: [10-15 типов компаний]

3. SEGMENT_3_NAME:
   - Description: [Что нужно этому сегменту]
   - Examples: [10-15 типов компаний]

4. OTHER: Компании, которые не подходят или являются конкурентами

GUIDELINES:
- FIRST CHECK: Это прямой конкурент? Если да → OTHER
- Choose the PRIMARY need based on core business model
- Use OTHER for competitors AND companies with no clear need

INPUT_VARIABLES:
- Website Variable: {{company.website}}
- Content Variable: {{company.website_text}}
")
```

**Энричер генерации сообщений (пример INXY):**

```
gpt("You are writing personalized outreach emails for [Client] solutions. Based on the company's offer type, strictly follow the appropriate template and fill it with relevant industry details. Use the appropriate currency based on the company's country location.

**TEMPLATE_1:**
[Шаблон тела письма с {плейсхолдерами}]

**TEMPLATE_2:**
[Шаблон тела письма с {плейсхолдерами}]

**CURRENCY LOCALIZATION RULES:**
- UK companies → use £ (GBP)
- EU/Eurozone → use € (EUR)
- US/Canada → use $ (USD)
- Switzerland → use CHF
- Default → use $ (USD)

**STRICT INSTRUCTIONS:**
- Use ONLY the template that exactly matches the offer type
- Replace ONLY the bracketed placeholders
- Use realistic amounts in the correct currency
- Do NOT add greetings, signatures, subject lines
- Do NOT add formatting like bold, headers, or labels
- MAINTAIN all empty lines and paragraph spacing

---
Input Company
Offer type: {{result.offertype}}
Website link: {{company.website}}
Website content: {{company.website_text}}")
```

**Энричер генерации темы:**

```
gpt("You are writing personalized email subject lines for [Client] solutions. Based on the company's offer type and business vertical, use the appropriate template.

**SUBJECT TEMPLATE per offer type:**
[Шаблон с плейсхолдерами {country} {business vertical}]

**STRICT INSTRUCTIONS:**
- Use ONLY the template that matches the offer type
- Extract country and business vertical from the email message
- Output only the subject line

---
Input Company
Website link: {{company.website}}
Offer type: {{result.offertype}}
Email message: {{result.message}}")
```

### FAQ по Crona

#### Базовые операции

**Проверить, пустое ли поле:**
```
{{company_website?}}
```
Возвращает true, если поле не пустое.

**Доступ к вложенным полям (после обработки Sales Navigator):**
```
{{<company_linkedin_details_column>.company_website}}
```

**Доступ к простым числовым/текстовым полям:**
```
{{stats.employee_count}}
{{hq.state}}
```

#### Работа с энричерами

**Фильтрация по результатам энричера (true/false):**
```
{{result.callAi6?}}
```
Только строки с true проходят дальше по workflow.

**Исключение определённых сегментов:**
```
!{{result.callAi4}}.include?("OTHER")
```
`!` — инверсия условия (NOT), `.include?()` — проверка вхождения подстроки.

**Замена текста (A/B-тесты):**
```
{{result.polishedFlame}}.sub('старый CTA текст', 'новый CTA текст')
```
Идеально для A/B-тестов с разными CTA. Не нужно создавать отдельный энричер!

#### Типичный Workflow

```
1. Scrape Website → получаем company_website
   Filter: {{company_website?}}

2. Call AI (Segmentation) → получаем сегмент компании
   Filter: !{{result.callAi4}}.include?("OTHER")

3. Call AI (ICP Check) → проверяем соответствие роли
   Filter: {{result.callAi6?}}

4. Add Code → извлекаем доп. данные
   {{stats.employee_count}}
   {{hq.state}}

5. Call AI (Message Generation) → генерируем сообщение
   Result: polishedFlame

6. Add Code (A/B Test) → заменяем CTA
   {{result.polishedFlame}}.sub('old CTA', 'new CTA')
```

#### Извлечение email-адресов с сайта

**Все email-адреса через запятую:**
```
{{company.website_text}}.scan(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b/i).uniq.join(", ")
```

**Первый email-адрес:**
```
{{company.website_text}}[/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b/i]
```

#### Извлечение номеров телефонов с сайта

**Все номера через запятую:**
```
phone_regex = /
  (?:\+?(\d{1,3})[\s\-\.]?)?
  \(?(\d{1,4})\)?[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,9})?
/x

{{company.website_text}}.scan(phone_regex).map do |match|
  match.compact.join
end.uniq.join(", ")
```

**Первый номер телефона:**
```
phone_regex = /
  (?:\+?(\d{1,3})[\s\-\.]?)?
  \(?(\d{1,4})\)?[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,9})?
/x

match = {{company.website_text}}.scan(phone_regex).first
match ? match.compact.join : nil
```

### Crona — Получение данных из LinkedIn URL

**Получить сайт:**
```
{{<company_linkedin_details_column>.company_website}}
```

**Получить название компании:**
```
{{<company_linkedin_details_column>.company_name}}
```

### Примеры и шаблоны Crona

Раздел содержит качественные эталонные примеры, которые можно добавить в ваш аккаунт как проекты по запросу к операционному менеджеру. Шаблоны помогают оптимизировать B2B-аутрич с уже настроенными процессами обогащения и фильтрации.

### Архив Crona

- Старое название: Leadokol
- Архивные ссылки: Notion (sally-saas), Google Drive, Google AI Studio

---

## Гайд по Clay

Мы обычно используем Clay через **триальные аккаунты**, потому что это выгоднее. Вместо одного корпоративного аккаунта мы создаём несколько новых для продления триалов и оптимизации расхода кредитов.

### Как войти в новый аккаунт Clay с того же устройства

1. **Создай отдельный Google-аккаунт в отдельном профиле Chrome** и используй его для входа в Clay.
2. **Используй браузер Dolphin Anty** и регистрируй новый аккаунт **через Google-логин** — этот метод надёжно работает. Установка: https://dolphin-anty.com/ru/

### Хак: как получить больше кредитов на бесплатном плане Clay

1. Напиши в поддержку Clay с просьбой о дополнительных кредитах перед покупкой подписки:

```
Hi,
Could you please provide me with a small amount of credits to try out your service before I purchase a subscription?
I'd really appreciate it, especially since my previous credits were accidentally spent due to the auto-update function.
```

2. Бот спросит, была ли это непредвиденная трата — ответь **Yes**.
3. Укажи сколько кредитов нужно. Некоторые пользователи получали 200 мгновенно и до 1000 после короткого ожидания с оператором.
4. Бот пришлёт гайд как не тратить кредиты зря (например, отключить Auto Update).

### Clay Tech Stack — поиск компаний по технологическому стеку через HG Insights

1. **Создай новый Workbook в Clay** → нажми "New Workbook" → "All Sources."
2. **Выбери источник данных**: Найди и выбери "Companies by Tech Stack with HG Insights."
3. **Настрой фильтры**: По названию продукта/технологии, по вендору/компании.
4. **Экспортируй список** компаний.
5. **Загрузи в Apollo**: Импортируй список компаний в Apollo, используй Apollo для поиска и обогащения контактов.

### Clay — Скрейпинг LinkedIn-постов человека
Видеогайды доступны.

### Clay — Поиск людей из компаний
Видеогайд доступен.

### Clay — обогащение Find Work Email

1. В Clay нажми **New → Workbook → Import from CSV**. Загрузи файл.
2. Создай колонку **Full Name**: `{{First Name}} + " " + {{Last Name}}`
3. Нажми **Add Enrichment → Find Work Email**.
4. Сопоставь все значения в настройках энричмента (Person's Name → Full Name и т.д.).
5. Дождись результатов, затем экспортируй CSV с найденными почтами.

---

## Explee

Explee — продвинутые AI-фильтры для поиска компаний.

### Как использовать

**Видеогайды доступны** (Google Drive: `1hAMAR1uLMJOJCnhXhvsJodZxIzUHVtsq`)

### Фильтры

Ползунок регулирует «строгость» требований и совпадений. Лучше повернуть его вправо, чтобы не собирать неподходящее, или как минимум в середину.

### Консольный скрипт (Explee Auto Parser v2.4)

**Как запустить:**

1. Сначала запусти код настройки (вставь полный код класса ExpleeAutoParser в консоль браузера).
2. Затем вызови:
```javascript
parser.parseAuto(1, 500)
```
`(1, 500)` = диапазон сотрудников для скрейпинга.

**Скрейпь партиями** — запускай функцию несколько раз с непересекающимися диапазонами:
```javascript
parser.parseAuto(1, 500)
parser.parseAuto(501, 1000)
parser.parseAuto(1001, 2000)
```

**Основные команды:**
```javascript
parser.parseAuto(1, 500)                    // базовый запуск
parser.parseAuto(1, 500, 100, 3000, 5000)   // с настройкой задержек
parser.continueFromProgress()               // продолжить с сохранённого прогресса
parser.showProgress()                       // показать прогресс
parser.clearProgress()                      // очистить прогресс
```

**Возможности парсера v2.4:**
- CSV-вывод вместо JSON (UTF-8 BOM для Excel)
- Автозаполнение домена из email (исключает личные почты: gmail, outlook и т.д.)
- Преобразование LinkedIn ID → URL
- Защита от rate limit (429) с авто-retry (3 попытки, экспоненциальный откат: 30с → 60с → 120с)
- Сохранение прогресса в localStorage после каждого диапазона
- Продолжение с любой сохранённой точки
- Умные задержки с jitter (±30% разброс)
- Автосохранение частичных результатов
- Удаление дубликатов по домену

**Crona — получение данных из LinkedIn URL (для данных Explee):**
```
{{<company_linkedin_details_column>.company_website}}
{{<company_linkedin_details_column>.company_name}}
```

---

## Apify

Видеогайд: Loom `0d7bf30def5e4a46bf303c70c3dbe5b8`

### Как скрейпить Glassdoor
- Ссылка на актор: `https://console.apify.com/actors/t2FNNV3J6mvckgV2g/input`
- Видеогайд доступен.

---

## Outscraper

**Outscraper** — мощный инструмент для скрейпинга публичных данных, особенно из **Google Maps**. Позволяет собирать детальную информацию о бизнесе: название, сайт, email, телефон, рейтинг, адрес — массово.

### Для чего можно использовать:
- Сбор списков локальных бизнесов (напр. «Клиники в Берлине», «Маркетинговые агентства в Стокгольме»)
- Извлечение email, сайтов, телефонов из Google Maps
- Скрейпинг приложений из App Store или Google Play
- API для автоматизации сбора данных в масштабе

### Как использовать (3 простых шага):
1. Зайди на outscraper.com и выбери сервис — обычно **Google Maps Data Extractor**.
2. Введи ключевые слова (напр. «real estate agents in Miami») и выбери локацию.
3. Нажми старт — через несколько минут получишь CSV-файл со всеми данными бизнесов.

### Скрейпер Emails & Contacts:
1. **Подготовь входные данные**: Создай список доменов или URL.
2. **Открой сервис**: Перейди в Emails & Contacts Scraper на Outscraper.
3. **Введи данные**: Вставь список или загрузи CSV/XLSX/TXT файл.
4. **Настрой параметры**: Глубина поиска, типы контактов.
5. **Запусти задачу** и дождись.
6. **Скачай результаты**: email, телефоны, ссылки на соцсети.

Видеогайд: `https://youtu.be/TRsQjqVR7m8`

---

## Альтернативные/дополнительные источники

- **Sales Navigator + PhantomBuster** (вкл. ивенты)
- **Waalaxy** (быстрое извлечение из LI; хороший бесплатный тариф)
- **Crunchbase** (сигналы по раундам финансирования)
- **Скрипты** (поиск доменов): Если у тебя **только названия** — сначала запусти **скрипт поиска доменов** для определения домена каждой компании → **затем** добавь в **Apollo** для обогащения (люди, email).

---

## Поиск русскоязычных контактов

> Русскоязычные контакты стабильно показывают **более высокую конверсию**. Мы настоятельно рекомендуем включать эти профили в кампании.

### Способ 1: Использовать существующую базу

У нас уже есть **общая внутренняя база** русскоязычных контактов, собранная по разным проектам. У многих из них есть Telegram.

- Таблица 1: `1UihgB6kMBXNTDlcx28WeihLmyDgrSuh1KaafP7yhQbk`
- Таблица 2: `1f-sFX3jSNmZ7u6iWtF1Ws9-TW06fsKBT-nBLuwL9RjA`

### Способ 2: Поиск через Crunchbase
Гайд доступен в Notion.

### Способ 3: Логика Apollo (поиск по имени)

**Проблема:** Если базово прописать окончания русских фамилий, то Apollo будет искать по точным совпадениям, что не подходит.

**Решение:** Поставить символ `*` перед буквами — это отменяет точный таргетинг и в 70-80% случаев выдаёт релевантные русскоговорящие контакты.

**Список окончаний для поиска:**
```
Name:
*ov OR *ev OR *in OR *yn OR
*ovich OR *evich OR *sky OR
*skiy OR *ova OR *eva OR *ina OR *yna OR *skaya OR *skaia
OR *itsky OR *itskaya OR *enko OR *ko OR *chuk OR *yuk OR *yan OR *ian OR *dze OR *shvili
```

Видеогайд: Google Drive `1-ygjPMIsd5SFvUU4Th7ZZ-bnLQE0p8EX`

### Способ 4: Логика Apollo + Octoparse
Комбинированный подход: поиск по имени в Apollo + Octoparse для скрейпинга.

### Способ 5: Обогащение через Clay
Гайд доступен в Notion.

### Способ 6: Фильтрация по университету (метод Sales Navigator)

Ещё один очень эффективный метод — фильтрация по **истории образования** в **LinkedIn Sales Navigator**.

**Шаги:**
1. Перейди в **Sales Navigator → Lead search**
2. Используй фильтр **"University"**
3. Вставь название университета из списка ниже

Можно комбинировать с фильтрами по локации, должности (напр. CTO, Co-Founder) и индустрии.

**Список университетов (Россия, Беларусь, Украина, Казахстан):**

**Россия:**
- Lomonosov Moscow State University
- Saint Petersburg State University
- Bauman Moscow State Technical University
- Novosibirsk State University
- Moscow Institute of Physics and Technology (MIPT)
- Tomsk State University
- Moscow State Institute of International Relations (MGIMO)
- National Research University Higher School of Economics (HSE)
- Ural Federal University
- Kazan Federal University
- ITMO University
- Russian Presidential Academy of National Economy and Public Administration (RANEPA)
- Peter the Great St. Petersburg Polytechnic University
- Moscow Power Engineering Institute (MPEI)
- National University of Science and Technology MISIS
- Tomsk Polytechnic University
- Southern Federal University
- Far Eastern Federal University
- Siberian Federal University
- Saint Petersburg Electrotechnical University "LETI"
- Moscow Aviation Institute (MAI)
- Samara National Research University
- Perm State University
- Saint Petersburg Mining University
- Moscow State Technical University of Civil Aviation
- Voronezh State University
- Nizhny Novgorod State Technical University
- Moscow Polytechnic University
- Irkutsk State University
- Kazan National Research Technological University
- Omsk State University
- Ufa State Aviation Technical University
- Tyumen State University
- North-Caucasus Federal University
- Volgograd State Technical University
- Bashkir State University
- Saint Petersburg State University of Economics
- Russian State University for the Humanities
- Saint Petersburg State University of Aerospace Instrumentation
- Moscow State University of Economics, Statistics, and Informatics

**Беларусь:**
- Belarusian State University (BSU)
- Belarusian National Technical University (BNTU)
- Brest State Technical University
- Grodno State University
- Minsk State Linguistic University
- Belarusian State University of Informatics and Radioelectronics
- Belarusian State Economic University
- Belarusian State Technological University
- Gomel State University
- Polotsk State University
- Vitebsk State University
- Yanka Kupala State University of Grodno
- Francisk Skorina Gomel State University
- Belarusian-Russian University
- Mogilev State University

**Украина:**
- Taras Shevchenko National University of Kyiv
- National Technical University of Ukraine "Igor Sikorsky Kyiv Polytechnic Institute"
- Lviv Polytechnic National University
- Kharkiv National University
- Odessa National University
- Dnipropetrovsk National University
- National University of Kyiv-Mohyla Academy
- Sumy State University
- Donetsk National University
- Zaporizhzhia National University
- Ivan Franko National University of Lviv
- Chernivtsi National University
- National University of Life and Environmental Sciences of Ukraine
- Kyiv National Economic University
- Odesa National Polytechnic University
- Vinnytsia National Technical University
- Lviv National Medical University
- Poltava National Technical University
- Kharkiv Polytechnic Institute
- Uzhhorod National University
- Mykolaiv National University
- Bukovinian State Medical University
- National Mining University
- Zhytomyr Polytechnic State University
- Chernihiv National University of Technology
- National Aerospace University (KhAI)
- Kyiv National University of Construction and Architecture
- Dnipro Polytechnic University
- Ukrainian State University of Railway Transport
- Kyiv National University of Trade and Economics

**Казахстан:**
- Al-Farabi Kazakh National University
- Nazarbayev University
- Kazakh-British Technical University
- Eurasian National University
- Kazakh National Medical University
- KIMEP University
- Satbayev University
- Kazakh National Agrarian University
- Karaganda State Technical University
- South Kazakhstan State University
- Pavlodar State University
- Aktobe Regional State University
- Astana Medical University
- West Kazakhstan State University
- International Information Technology University (IITU)

---

## Конференции

### Существующая база
Конференции — мощный источник **лидов с высоким намерением** — участники часто активно ищут новые решения.

Существующая база конференций: Google Sheet `1ArNLCkDpiSYQZj5OnYio-QqlQznm0fyPr1oIpJV-YfA`

**Формат:**
- Full Name, Job Title, Company Name, Email, LinkedIn Profile, Country
- Conference Name, Conference URL, Conference Type (offline/online/hybrid), Sector, Country, Conference Date

### Главное решение: Ваш клиент участвует?

#### ✅ Клиент УЧАСТВУЕТ

**Главная цель:** Забронировать личные встречи на мероприятии.

**План действий:**
1. **Фокус на координации встреч** — Предварительное бронирование, общий календарь, управление логистикой
2. **Использование мессенджера приложения конференции** — Автоматические сообщения через платформу
3. **Дополнить онлайн-исследованием** — Запасные списки из LinkedIn и других источников

#### ❌ Клиент НЕ УЧАСТВУЕТ

**Главная цель:** Собрать списки контактов и связаться удалённо.

**План действий:**
1. **Использовать мессенджер приложения конференции** (если есть)
2. **Фокус на онлайн-исследовании и аутриче**

### Раздел 1: Онлайн-исследование и аутрич (удалённая стратегия)

**Шаг 1: Скрейпинг конференции**

*Сценарий A: Прямой скрейпинг людей*

Когда у конференции есть публичная директория участников, LinkedIn-события или приложение с профилями участников.

**Инструменты:** PhantomBuster, Octoparse, Waalaxy, ручное копирование.

**Процесс:**
1. Проверь сайт конференции — разделы «Attendees», «Participants», «Directory»
2. Используй Octoparse для больших списков, копируй вручную если меньше 50 человек
3. Скачай приложение ивента — многие имеют директории участников

*Сценарий B: Скрейпинг сначала компаний*

Когда нет прямого списка участников — только спонсоры/экспоненты/спикеры. Найди компании, затем ищи людей через Apollo.

**Гайд по скрейпингу SBC Summit:** Google Drive `1QL24oZBDtfJI5gI1zLsgAzz0Vj3_LeqF`

### Раздел 2: Сообщения через приложение конференции

**Когда использовать:** Когда у конференции есть своё приложение/сайт, где участники могут переписываться.

**Процесс настройки:**
1. Войди в приложение/сайт конференции
2. Отфильтруй целевых контактов под свой ICP
3. Настрой автоматическую рассылку через Octoparse в Standard Mode
4. Одно короткое сообщение в один абзац (без переносов строк)
5. Защита от дубликатов — чтобы не писать одному человеку дважды
6. Автоматическая отправка с задержками 5 секунд

**Пример шаблона сообщения:**
"Hey [FirstName], saw you're at [Event]. We help [company type] improve [specific benefit]. Quick intro this week to see if there's a fit?"

### Раздел 3: Стратегия для личного присутствия

#### До мероприятия (за 2 недели)
- Определи 50-150 приоритетных компаний-участников
- Составь карту ключевых контактов (CEO, VP, Business Development)
- Начни LinkedIn-аутрич за 2 недели
- Разошли таргетированные письма
- Подготовь одностраничное описание компании и 30-секундный питч
- Создай общий календарь, групповой чат (Telegram/WhatsApp), трекинг-таблицу

**Колонки трекинг-таблицы:** Company | Contact Name | Job Title | Meeting Time | Location | Owner | Status | Next Steps

#### Во время мероприятия (каждый день)
- **Утренняя координация (10 мин):** Кого нужно встретить, подтвердить время/место, заполнить пробелы
- **Управление встречами:** Приглашения в календарь, напоминания за 30/15/5 минут, координация в чате
- **Фиксация информации:** Что им нужно, возражения, обязательства, следующие шаги, кто ведёт follow-up

#### После мероприятия (1-5 дней)
- Follow-up письма в тот же или на следующий день с резюме встречи
- Перевод контактов в регулярные секвенсы аутрича
- Попытка перенести неявившихся (максимум 2 попытки)
- Обновление трекинг-таблицы

---

## Источники высокого намерения (ссылки)

| Источник | Сектор | Комментарий |
|----------|--------|-------------|
| cryptwerk.com | crypto | Онлайн-каталог мерчантов, принимающих крипту |
| playtoearn.com/blockchaingames | igaming | Каталог блокчейн-игр |
| theirstack.com | tech | Поиск технологического стека компаний (аналог BuiltWith) |
| lu.ma | crypto/AI | Побочные конференции + TG-чаты |
| cryptojobslist.com | web3 | Вакансии в web3 |
| web3.career | web3 | Вакансии в web3 |
| cryptocurrencyjobs.co | web3 | Вакансии в web3 |
| hirify.me | найм | Найм русскоговорящих за рубежом, подходит для кейсов 4dev/geomotv |
| t.me/+RQ3-RaMtSwA5YmQy | igaming | Telegram-чат |

---

## Обогащение и валидация email

### Поиск и валидация email (обязательно)

- **Поиск email**: Clay или Findymail
- **Валидация** каждого списка через **MillionVerifier** перед отправкой

**Процесс:** Источник → (Если только имена: Скрипт → Обогащение в Apollo) → Обогащение (Clay/Findymail) → **Верификация (MillionVerifier)** → Отправка.

---

## Проверка базы

### Фильтрация по чёрному списку

**Формула проверки чёрного списка (Google Sheets):**
```
=ARRAYFORMULA(
  IF(C2:C25="", "",
    COUNTIF(
      UNIQUE(
        FILTER(
          REGEXREPLACE(
            LOWER(
              IFERROR(
                REGEXEXTRACT(
                  REGEXREPLACE(
                    REGEXREPLACE(
                      IMPORTRANGE("1_SIp1a8QA4NyAf8bdsU9b1UhNMKI3EMljRbY7BWuBvw","Blacklist!A2:A"),
                      "^https?://", ""
                    ),
                    "^www\.", ""
                  ),
                  "^(?:[^@/]+@)?([^/:?#]+)"
                ), ""
              )
            ),
            "^www\.", ""
          ),
          LOWER(
            IFERROR(
              REGEXEXTRACT(
                REGEXREPLACE(
                  REGEXREPLACE(
                    IMPORTRANGE("1_SIp1a8QA4NyAf8bdsU9b1UhNMKI3EMljRbY7BWuBvw","Blacklist!A2:A"),
                    "^https?://", ""
                  ),
                  "^www\.", ""
                ),
                "^(?:[^@/]+@)?([^/:?#]+)"
              ), ""
            )
          ) <> ""
        )
      ),
      REGEXREPLACE(
        LOWER(
          IFERROR(
            REGEXEXTRACT(
              REGEXREPLACE(
                REGEXREPLACE(C2:C25, "^https?://", ""),
                "^www\.", ""
              ),
              "^(?:[^@/]+@)?([^/:?#]+)"
            ), ""
          )
        ),
        "^www\.", ""
      )
    ) > 0
  )
)
```

### Используй сегментацию Crona

После экспорта базы из любого источника — **не доверяй ей слепо**.

- **Используй фильтры** по ключевым колонкам: `Industry`, `Keywords`, `Headcount`.
- **Проверяй соответствие с оригинальным таргетингом** — фильтруй по ключевым словам, которые использовал в Apollo.
- Используй фильтры **«не содержит»** для удаления нерелевантных компаний (напр. стоп-слова: «Insurance», «Real Estate», «Logistics»).
- Если замечаешь подозрительные кластеры — много пустых полей, несовпадающие индустрии — копай глубже или отмечай.

**Почему это работает лучше:**
- Даёт количественное понимание качества базы
- Помогает очистить от мусора до запуска
- Позволяет скорректировать запрос в Apollo при необходимости

Помимо фильтрации, вручную открой **случайную выборку из ~20 сайтов компаний** из базы.

---

## Мини SOP

1. Проверь **готовые сегменты**.
2. Согласуй **ICP** в общей таблице.
3. **Если только имена**: запусти **скрипт поиска доменов**, затем **обогати в Apollo**.
4. **Apollo** компании → уточни в **Crona** → выгрузи людей.
5. Заполни пробелы через **Sales Nav + PhantomBuster / Waalaxy / Crunchbase**.
6. **Clay/Findymail** для email → **MillionVerifier** для очистки.
7. Передай чистый CSV в аутрич.

---

# 2. Написание секвенса

## Фаза 1: Сбор информации о клиенте

Перед написанием любых секвенсов собери **максимум информации** от клиента. В идеале используй AI-инструмент для генерации исчерпывающего опросника для аутрича в конкретной нише.

### Ключевые вопросы:

- **Кто клиент?** (Профиль компании, индустрия, размер)
- **Кто их идеальный клиент?** (Демография, психография, боли)
- **Кто НЕ подходит?** (Красные флаги, характеристики для исключения)
- **Кто обычно к ним обращается?** (Текущие паттерны клиентов)
- **Кого они хотят привлечь?** (Расширение таргета)
- **Географические данные** (Предпочтения по локации, ограничения)
- **Демография** (Пол, возраст, размер компании и т.д.)
- **Любые другие релевантные данные** для построения базы, описаний секвенсов, предложений и т.д.

---

## Фаза 2: AI-анализ проекта

### Шаг 1: Генерация JTBD и ролей

После сбора всех данных клиента загрузи всё в Claude AI и попроси изучить проект.

**Ключевые позиции и роли:**
- Какие должности отвечают за эти решения?
- На какие роли нужно таргетить?

### Промпт JTBD

```
You are an expert Business Analyst specializing in identifying Jobs-To-Be-Done (JTBD) for B2B decision-makers. Your task is to analyze a company's offering and target customer profile to generate a comprehensive list of specific tasks, goals, and challenges that the target persona faces in their role.

INPUT REQUIRED:

**[PROJECT DESCRIPTION]:** Brief overview of the client's company, their solution/service, and core value proposition. Their website.

**[IDEAL CUSTOMER PROFILE - ICP]:** Specific job title, role, industry, and company characteristics of the target decision-maker.

YOUR TASK:

Generate 5-8 specific JTBD items that this exact ICP faces in their daily work that directly connect to the client's solution. Each JTBD must be:

- **Specific and Actionable** - Not vague pain points, but concrete tasks they need to accomplish
- **Role-Relevant** - Directly tied to their job responsibilities and KPIs
- **Solution-Connected** - Addressable by the client's offering
- **Business-Impact Focused** - Connected to measurable business outcomes
- **Current and Pressing** - Things they're actively dealing with, not hypothetical

OUTPUT FORMAT:

**[APPROVED JOBS-TO-BE-DONE - JTBD]:**

1. [Specific operational task they need to complete]
2. [Goal they're trying to achieve with current limitations]
3. [Process they need to optimize or streamline]
4. [Challenge they're facing in their current workflow]
5. [Metric/KPI they're struggling to improve]
6. [Resource/time constraint they need to overcome]
7. [Compliance/risk management task they must handle]
8. [Strategic initiative they need to execute]

EXAMPLE:

**Project:** Professional moving services with loyalty program for commercial real estate management companies
**ICP:** Property Manager at commercial real estate management companies

**[APPROVED JOBS-TO-BE-DONE - JTBD]:**

1. Earn commission through loyalty program referrals while providing value to tenants
2. Organize tenant relocations with minimal time investment
3. Adapt to changing moving schedules without additional costs or delays
4. Provide high-quality moving services to increase satisfaction and retention rates
5. Streamline tenant move-in/move-out processes to reduce operational complexity
6. Ensure safe handling and transportation of tenant property to avoid damage claims
7. Coordinate furniture/equipment relocations during office renovations without disruption
8. Improve tenant experience during transitions to enhance lease renewal rates
```

### Шаг 2: Утверждение клиентом

Представь JTBD и список позиций клиенту на утверждение. После подтверждения **ответственность переходит** — вся дальнейшая переписка будет основана на предварительно утверждённой информации.

---

## Фаза 3: Создание секвенса с Claude

Запускай промпты последовательно:

### Email 1 — Первое касание

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating the FIRST TOUCH EMAIL that generates responses from busy decision-makers.

**[THE CONTEXT & TASK]** I will provide you with:
1. **[PROJECT DESCRIPTION]:** Brief overview of our client's company and offering
2. **[IDEAL CUSTOMER PROFILE - ICP]:** Specific job title and role we target
3. **[APPROVED JOBS-TO-BE-DONE - JTBD]:** Tasks, goals, challenges this ICP faces that our client solves

**[EMAIL #1 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`How are you currently {specific task from JTBD}?

At {Company Name}, we {specific solution for their JTBD}. {Brief explanation how it works} + {concrete metric/proof}.

Would you be open to a 15-minute call to explore how we can {solve their specific JTBD task}?`

**[FILLING PRINCIPLES]**

* Each sentence under 20 words
* Concrete numbers and metrics mandatory
* Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.
* No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.
```

**Пример результата (крипто):**

```
How are you currently managing royalty payouts to your avatar creators and handling payments from a global user base?

At Inxy, we offer a powerful API to automate mass payouts and a simple Paygate for crypto acceptance, all under our EU/Canadian regulatory licenses.

Would you be open to a 15-minute call to explore how we can streamline this for you?
```

**Пример результата (грузоперевозки):**

```
How are you currently handling tenant relocations at {target company}?

At Royal Moving & Storage, we handle the full process — from packing to delivery — with licensed crews across LA. 98% damage-free track record.

Would you be open to a 15-minute call to explore how we can simplify this for you?
```

### Email 2 — Follow-up

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating a FOLLOW-UP EMAIL that adds value and continues the conversation.

**[EMAIL #2 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`Quick note on {main aspect of the solution}.

{Operational advantage/efficiency benefit}. {Concrete metric/example with specific numbers and timing}.

{Analogy or comparison that makes the advantage clear}.

Open to a 20-minute call next week to {specific action related to JTBD}?`

**[FILLING PRINCIPLES]**
* Focus on operational efficiency/speed/process advantages
* Include concrete timings and numbers
* Show competitive advantage through efficiency
* Brevity and Scannability
* No Fluff
```

**Пример результата (крипто):**

```
Quick note on automated royalty distribution.

Our system processes 10,000+ creator payouts in under 2 minutes, while manual systems typically take 3-5 business days per batch.

Think of it like having a dedicated finance team that never sleeps - handling all your creator payments instantly across 40+ countries.

Open to a 20-minute call next week to walk through your current payout workflow?
```

### Email 3 — Финальный follow-up

```
PROMPT #3: FINAL FOLLOW-UP EMAIL GENERATOR (Email #3)
You are a world-class B2B Outreach Strategist. Your expertise is in creating a FINAL FOLLOW-UP EMAIL that addresses specific competitive advantages.

**[EMAIL #3 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`One last thought on {main solution topic}.

We solve the {number} problems where most {competitors/alternatives} fail: {problem #1} ({concrete result/timing}) and {problem #2} ({specific advantage}).

If either sounds familiar, worth a quick {adjective} chat?`

**[FILLING PRINCIPLES]**
* Maximum short format
* Two concrete problems where you outperform competitors
* Confident, casual tone
* Very low-pressure CTA
* Brevity and Scannability
* No Fluff
```

**Пример результата (крипто):**

```
One last thought on creator payment management.

We solve the 2 problems where most payment solutions fail: cross-border compliance (we handle 40+ jurisdictions automatically) and transaction speed (payouts in 2 minutes vs 3-5 days).

If either sounds familiar, worth a quick informal chat?
```

### Напоминание о персонализации

После генерации шаблонов писем добавь больше персонализации — как минимум используй название компании, на которую таргетишь:

```
How are you currently {specific task from JTBD} at **{target company}?**
```

---

# 3. Настройка Email-аутрича

## 1. Валидация email

- Находи email через **Clay** или **Findymail**.
- **Всегда** прогоняй списки через **MillionVerifier** перед отправкой — даже если они из надёжных инструментов.
- **Зачем:** защищает доставляемость, снижает баунсы, предотвращает проблемы со спамом; инструменты вроде **Smartlead** штрафуют грязные списки.
- **Процесс: Источник → Верификация (MillionVerifier) → Отправка.**

## 2. Настройка почтовых ящиков

Если нужно настроить email-аккаунты — свяжись с нашим **руководителем инфраструктуры** — он всё настроит: создание доменов, ящиков и подключение.

Мы также сразу занимаемся **прогревом доменов**, чтобы потом не было проблем с доставляемостью.

**Важно:**
- При настройке ящиков для аутрича **всегда добавляй подпись** — это часто забывают.
- При необходимости **загрузи фото профиля**, чтобы аккаунт выглядел настоящим и надёжным. Эти мелочи повышают доставляемость и отклик.

## 3. Запуск кампании в Smartlead

### Стандарт именования кампаний

```
{проект} — {сегмент}
```
Пример: "inxy — fintech"

### Чек-лист перед запуском

1. Убедись, что список чистый, а секвенсы письм качественные.
2. Скинь секвенсы в Slack-канал **#review-sequences** для ревью командой.
3. Запускай только после утверждения.

### Обучающие материалы
- YouTube-канал Smartlead: `youtube.com/watch?v=F_BVmCYcQqE`
- Smartlead University: `smartlead.ai/smartlead-university`

### Open Rate = Всегда 0%

Мы **не отслеживаем открытия**. Все письма уходят как **plain text** без **трекинга**. Если видишь 0% открытий — это ожидаемо и задумано. Это улучшает доставляемость и снижает риск спама.

### Настройки кампании

- Таймаут между письмами: **15 минут**
- Макс. дневных первых касаний: увеличен со 100 до **500**
- Соотношение первых касаний/follow-up: **60/40** — приоритет первым касаниям
- До **50 писем с 1 ящика в день**
- Добавь smart server от руководителя инфраструктуры

### A/B-тестирование

Создай 2 варианта первого сообщения с разными темами или немного другим текстом. Smartlead автоматически распределит контакты между вариантами.

**Совет:** Меняй только *одну вещь за раз* (например, тему), чтобы точно знать, что дало разницу.

### Правило остановки

После запуска кампании, если **500 писем** отправлены без **тёплых ответов**, кампанию нужно **немедленно приостановить**.

### Дублирование кампаний

Если работаешь с похожим сегментом или просто меняешь сообщения — используй функцию **«Duplicate»** в Smartlead для экономии времени.

### Теги

Настрой теги для кампаний в Smartlead с самого начала, чтобы ответы сортировались в отдельные папки.

### Субсеквенсы

Видеогайд: `youtube.com/watch?v=s1U_ncY5fWE`

## Удаление старых лидов из Smartlead (каждую пятницу)

1. **Экспортируй лидов** — нажми «Download as CSV», добавь как новый лист в трекер лидов проекта.
2. **Назови лист как кампанию** (точно такое же имя, как в Smartlead).
3. **Удали всех лидов** в представлении кампании.
4. **Удали кампанию** для чистоты дашборда.

## Управление ответами вне SmartLead

SmartLead иногда пропускает ответы от лидов (другие email-адреса, ошибки переадресации).

**Решение:** Используй внешний email-клиент (**Thunderbird** или **Spark**).
- Добавь все рабочие email в клиент.
- Регулярно проверяй ответы вне SmartLead.

**Зачем:** Полная видимость всех ответов, предотвращение пропущенных тёплых ответов.

### Предупреждение об антивирусе

Отключи проверку email антивирусом (особенно Avast), чтобы избежать **рекламной подписки** внизу писем. Зайди в настройки Avast и отключи эту опцию.

---

# 4. Настройка LinkedIn-аутрича

## 1. Настройка LinkedIn

### Согласование с клиентом

Перед началом согласуй с клиентом использование аккаунтов — иногда используешь аккаунт клиента, иногда свой.

**Важно:** Перед запуском любой кампании всегда **проверяй SSI (Social Selling Index)**. При каждом запуске **уведомляй руководителя операций** с текущим SSI. **Добавь SSI в колонку «SSI» в Google Sheet клиента** до создания плана мощностей.

### Аренда LinkedIn-аккаунтов

**Используй только с антидетект-браузерами:** AdsPower, GoLogin, Dolphin Anty.

Стоимость: $135, контакт @a_trif в Telegram.

### Подписка LinkedIn Premium

Обсуди стоимость подписки с клиентом. **Попроси предоставить аккаунты напрямую или договорись о возмещении, если используешь свои.**

### Работа с низким SSI

Если заметил низкий SSI, сообщи клиенту:

> «Я заметил, что ваш Social Selling Index снизился на 2 пункта (с 49 до 47). Это могло произойти из-за большого количества отправленных приглашений, из которых только 20% были приняты.
>
> Поскольку это важный показатель для LinkedIn (влияет на лимиты сообщений и снижает риск блокировки), не могли бы вы запланировать контент-маркетинговые активности на своей странице?
>
> Было бы отлично, если бы вы могли публиковать посты в LinkedIn хотя бы раз в неделю.»

---

## 2. Настройка Getsales

### Настройка прокси

Каждый LinkedIn-аккаунт должен использовать свой выделенный прокси. Покупай один прокси на аккаунт и всегда входи через него — **без исключений**. Регулярно отслеживай SSI.

### Лимит подключений

Никогда не отправляй больше **200 подключений на аккаунт LinkedIn в неделю**. Безопасная зона — 100-200. Если SSI ниже 30 — **ограничь до 100 в неделю**.

### Добавление контактов в Getsales

1. Перейди в Lists → Create a list
2. Перейди в Import → нажми Import accounts → выбери свой список
3. Перейди в Automation → нажми Add contacts
4. Выбери список → нажми Select all

### Как отфильтровать контакты с менее чем 500 подключениями

Видеогайд доступен.

### Автоматизация и инструменты

Для автоматизации LinkedIn-аутрича мы используем **Getsales**. Он помогает управлять запросами на подключение, follow-up'ами и просмотрами профилей с сохранением персонализации.

Гайды: **YouTube-канал Getsales** (`youtube.com/channel/UCE-wJ2-PDodhHls8kVPx0BA`)

**Ключевые замечания:**
- **Очередь отзыва:** Регулярно сокращай количество ожидающих приглашений. Большая очередь → ограничения или баны. Отзывай приглашения, не принятые через 1-2 недели.
- **Коэффициент подключений:** Поддерживай баланс между приглашениями и удалениями.

### Альтернативный инструмент: LinkedHelper

Альтернативный/дополнительный инструмент для автоматизации LinkedIn.

---

## Автоматизация Getsales → Google Sheets

Ответы из автоматизаций Getsales будут добавляться/обновляться в Google Sheet.

### Часть 1 — Настройка n8n

1. **Создай workflow из шаблона:** В n8n найди «Getsales reply example» и дублируй. Увидишь 3 узла: Webhook → Execution Data → Append or update row in sheet.

2. **Настрой узел Google Sheets:**
   - Operation: `Append or Update Row`
   - Document: выбери свою Google Sheet
   - Sheet: выбери нужную вкладку
   - Mapping Column Mode: `Map Each Column Manually`
   - Column to match: уникальный ключ (обычно `Linkedin`)

3. **Маппинг колонок (только Expressions):**
```
Linkedin (match): {{ $('Webhook').item.json.body.contact.linkedin_url }}
first_name:        {{ $('Webhook').item.json.body.contact.first_name }}
last_name:         {{ $('Webhook').item.json.body.contact.last_name }}
reply_text:        {{ $('Webhook').item.json.body.last_message.text }}
reply_datetime:    {{ $('Webhook').item.json.body.last_message.sent_at }}
```

> Как найти нужные ключи: кликни на узел Webhook → Listen for test event, спровоцируй реальный ответ в Getsales и изучи JSON payload.

4. **Скопируй Production Webhook URL** из узла Webhook (не Test URL).

5. **Сохрани и активируй позже.**

### Часть 2 — Webhook в Getsales

1. **Создай webhook в Getsales:**
   - Name: напр. `n8n – Replies to Sheet`
   - Event: `Contact Replied` (или `Contact Replied LinkedIn Message`)
   - Target URL: вставь Production URL из n8n

2. **Добавь фильтры для автоматизаций:**
   - Нажми Add rule (для каждой автоматизации)
   - Установи заголовок в **OR** (синий)
   - Select field: `Automation`, Operator: `==`, Value: твоя автоматизация

3. **Проверка для одной автоматизации:** Убедись, что переключатель «Not» белый (выключен).

4. **Создай** webhook.

### Часть 3 — Запуск и тестирование

1. **Активируй** workflow в n8n.
2. Отправь себе сообщение из одной из выбранных автоматизаций и ответь.
3. Проверь Executions в n8n → должен быть Success.
4. Проверь Google Sheet → убедись, что появилась новая строка.

### Советы по полям и таблицам

- **Match column** должна существовать в таблице и совпадать с отправляемым значением.
- Не меняй названия заголовков (переименование требует перемаппинга в n8n).
- Используй ISO-формат времени для удобства фильтрации/сортировки.

---

# 5. Настройка Telegram-аутрича

Telegram — всё более популярный и эффективный канал аутрича, особенно в сообществах, где LinkedIn или email не дают быстрых ответов.

**Применение:**
- Связь с фаундерами, маркетологами или разработчиками, активными в нишевых Telegram-группах
- Прямые сообщения контактам после нахождения их в LinkedIn (если у них есть Telegram или одинаковый хэндл)

---

## Telegram-бот автоматизации (spambot)

### Быстрая настройка (macOS, VSCode)

```bash
# 1. Установка зависимостей
python3 -m venv .venv && source .venv/bin/activate && python install.py

# 2. Запуск бота (убедись, что в data.csv лежат контакты!)
python3 -m venv .venv && python spambot.py
```

Гайд ChatGPT: `chatgpt.com/share/6836173b-4cb8-800e-b007-affa3c48dfad`

### Как работает бот

Бот написан на Python с использованием **Telethon** (клиентская библиотека Telegram) и **aiogram** (фреймворк Telegram-ботов).

**Архитектура:**
- Использует Telegram API (API_ID: 1373613, API_HASH: 0ac5b3a05a14c3cb46330d974a52fb04)
- Каждый аккаунт использует свой **SOCKS5/HTTP прокси**
- Сессии хранятся в папке `./sessions/`
- Контакты загружаются из `data.csv`
- Настройки из `settings.json`

**Ключевые параметры:**
- `sleep_time`: 30 минут между пачками
- `sleep_randomizer`: 15 минут случайное отклонение
- `max_msg_day`: 15 сообщений на аккаунт в день
- Начальная случайная задержка: 30-300 секунд до старта

**Логика отправки сообщений:**
1. Для контактов с номерами телефонов (`+` в username): импортирует контакт, затем отправляет сообщение
2. Для контактов с username: отправляет напрямую
3. Отслеживает статус `done` в CSV
4. При PeerFloodError: считает ошибки флуда, если >2 — пишет SpamBot и останавливается
5. Случайная пауза между отправками

**Команды бота (через Telegram-бота):**
- `/set_group` — установить чат для логов
- `/send` — начать рассылку
- Все входящие ответы пересылаются в чат логов

### Устранение неполадок TG

Видеогайд доступен.

---

# 6. Лучшие практики

### LinkedIn

- Не превышай дневные лимиты подключений — даже на старых аккаунтах держи до 50/день. Безопасная зона — 30-40.
- Не шли одно и то же сообщение десяткам людей подряд. Добавляй вариативность — меняй вступления, подходы или хотя бы формулировки.
- Не используй сомнительные скрипты или расширения — работай с проверенными инструментами вроде Linked Helper. Непроверенные плагины = высокий риск бана.
- Следи за **SSI (Social Selling Index)** и реакциями на сообщения. Если слишком много отметок «Спам» — LinkedIn быстро ограничит или заблокирует.
- Таргетируй аккуратно: пиши тем, кому это действительно может быть интересно, и будь вежлив. Если LinkedIn флагнул аккаунт — приостанови активность на несколько дней и потом замедлись.

### Email

- Самый частый бан — от почтового провайдера (напр. Google Workspace блокирует исходящую почту за подозрение в спаме).
- Чтобы этого избежать:
  - **Всегда прогревай ящики**
  - **Наращивай постепенно** — не отправляй сотни писем в первый день
  - **Распределяй нагрузку на несколько ящиков/доменов** — 50 писем с 5 аккаунтов безопаснее, чем 250 с одного
  - **Следи за жалобами** — если кто-то просит удалить — сразу выполняй
- Будь уважителен — на той стороне живой человек.

### Репутация домена

- Для массового аутрича используй **вторичный домен**, похожий на основной (напр. `company.co` или `trycompany.com` для холодных писем).
- Это защищает репутацию основного домена.
- Всё равно нужно прогревать и отправлять качественный контент.

### Работа с отказами

- **Короткий отказ («не интересно»):** Будь вежлив и краток. Не дави.
  > «Totally understand — thanks for getting back to me! If you ever need [your service] down the line, happy to reconnect.»

- **«У нас уже есть поставщик/решение»:** Прими позитивно, предложи оставаться на связи. Можно спросить, довольны ли они текущим решением — но сначала оцени тон.
  > «Good to hear you're covered! If you ever need a backup option, happy to stay in touch.»

- **«Пришлите больше информации»:** Это не «да», но и не «нет». Отправь то, что просили + предложи follow-up.
  > «Here's a quick overview attached. Would be happy to discuss — would Friday or early next week work for a quick chat?»

  Если замолчали — напомни через несколько дней.

- **Гневный ответ или явный отказ:** Будь профессионален. Удали из списка.
  > «Sorry for the interruption — won't reach out again. Wishing you all the best!»

- **Нет ответа:** Самый частый исход. Не принимай на свой счёт. 1 основное письмо + 2 follow-up'а. После 3 касаний — попробуй другой канал (LinkedIn, звонок). Можно «оживить» холодных лидов через месяцы с новым предложением.

### Что отличает высокоэффективные кампании

- **Качественная подготовка:** Чистые списки, прогретые домены, продуманные сообщения. Одно агентство потратило 2 недели на персонализацию для 500 контактов → 55% open rate, 15% reply rate.
- **Настоящая персонализация и ценность:** 100 кастомных писем с адаптированными инсайтами → ~30% отклик, половина перешла в звонки.
- **Мультиканальность — это король:** Email + LinkedIn работают отлично вместе. Отправь email, затем LinkedIn follow-up: «Just sent you a quick note — wanted to make sure it didn't get lost.»
- **Обучение на данных:** Постоянно анализируй метрики и корректируй. Тестируй новые подходы. Неформальный тон и видео-интро набирают популярность.

---

# Частые ошибки

- **Отправка без проверки списка** — низкое качество = низкие результаты или попадание в чёрный список.
- **Стена текста в письмах** — никто не читает длинные холодные вступления. Делай коротко и остро.
- **Обман читателя** — фейковые «Re:» цепочки, вводящие в заблуждение темы вроде «Your invoice». Дают открытия, но убивают доверие.
- **Пропуск follow-up'ов** — большинство ответов приходит на 2-3 касании. Не останавливайся после одной попытки.
- **Нежелание учиться** — то, что работало 2 года назад, может не работать сегодня. Читай, тестируй, делись инсайтами, вступай в сейлз-сообщества (Reddit /r/sales, Telegram-группы).

---

# Cursor

Запись встречи 27.01 (Google Drive: `19CSeRgZ6a26Y8ap1rf8voqL-FMTQ6e-3`)

---

> **Прочитать гайд ты должен. Аутрич не пытайся делать — пока не прочитал.**
> Писать, переписывать — должен ты. Только тогда нажимай «отправить».
> Репутацию отправителя это защитит.
> Не подготовишься — в папке «спам» твои письма жить будут. Вечно.
