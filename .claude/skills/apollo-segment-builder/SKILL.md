---
name: apollo-segment-builder
description: >-
  Создаёт Apollo-фильтры для нового ICP-сегмента через структурированный диалог.
  Используй ВСЕГДА когда пользователь говорит: "создай фильтры для нового сегмента",
  "build Apollo filters", "нужны фильтры Аполло", "добавить сегмент в пайплайн",
  "собери фильтры для [название сегмента]", "новый сегмент для [проект]".
  Задаёт по одному вопросу с контекстом, вариантами A/B/C и рекомендацией.
  На выходе: filter JSON + обновлённая документация.
---

# Скилл: apollo-segment-builder

Строит Apollo-фильтры для нового сегмента через диалог — по одному вопросу за раз.
Работает для любого проекта и сегмента.

---

## Справочные материалы

Перед началом диалога прочитай:
- `references/filter-decisions.md` — база знаний: обоснование всех решений, данные Sally, правила по каждому параметру, TAM-ориентиры. Используй для формирования рекомендаций и вариантов.

---

## Шаг 0 — Инициализация

Если аргументы не переданы, спроси:
- **Название сегмента** (slug, напр. `SOCIAL_COMMERCE`)
- **Проект** (напр. `OnSocial`, `INXY`)
- **Краткое описание** что делают компании этого сегмента (1-2 предложения)

Если уже есть segment-doc (`sofia/projects/<Project>/docs/segment-*.md`) — прочитай его перед началом.
Прочитай существующие фильтры (`sofia/projects/<Project>/docs/apollo-filters-v4.md`) чтобы понимать контекст соседних сегментов и избежать overlap.

Сохраняй ответы пользователя в памяти по ходу диалога.

---

## Шаг 1-6 — Диалог (по одному вопросу)

Каждый вопрос оформляй так:

```
**Вопрос N: [Название параметра]**

[Контекст — почему этот параметр важен, какие риски, что уже знаем о сегменте]

**Варианты:**
**A. [Название]** — [описание]. Pro: ... Con: ...
**B. [Название]** — [описание]. Pro: ... Con: ...
**C. [Название]** — [описание]. Pro: ... Con: ...

**Мой выбор: [A/B/C].** [Объяснение почему.]

Что выбираешь?
```

Жди ответа перед следующим вопросом.

---

### Вопрос 1: Geography (страны)

**Контекст:** Apollo не принимает "ALL GEO" — нужен явный список стран. TAM сегмента определяет насколько широко бить. Маленький TAM (<500 компаний) → максимальный охват. Большой TAM → можно сузить до приоритетных рынков.

Предлагай варианты на основе характера сегмента:

- **Western Core (12):** United States, United Kingdom, Germany, Netherlands, France, Canada, Australia, Spain, Italy, Sweden, Denmark, Belgium
- **APAC+MENA (5):** India, Singapore, Japan, South Korea, United Arab Emirates
- **LatAm+IL (3):** Brazil, Mexico, Israel
- **Full Global = все 20**

Типичные варианты:
- A. Western Core (12) — проверенные рынки, меньше шума
- B. Western Core + APAC+MENA (17) — добавляем быстрорастущие рынки
- C. Full Global (20) — максимальный охват, важно при маленьком TAM

---

### Вопрос 2: Company Size (# Employees)

**Контекст:** Нижняя граница = минимальный размер для покупки API. Верхняя = где теряется релевантность (enterprise с долгим циклом, или слишком маленькие без бюджета).

Справка по существующим сегментам:
- INFLUENCER_PLATFORMS: 5–5,000 (самый широкий, SaaS разного размера)
- AFFILIATE_PERFORMANCE: 20–5,000
- IM_FIRST_AGENCIES: 10–500 (агентства не бывают огромными)

Типичные варианты:
- A. 20–5,000 — стандарт для SaaS/платформ
- B. 10–500 — для агентств и нишевых игроков
- C. 50–5,000 — если слишком маленькие ещё не могут позволить API

Формат для JSON: `["20,5000"]` или `["10,50", "51,200", "201,500", "501,1000", "1001,5000"]`

---

### Вопрос 3: Industry

**Контекст:** Apollo фильтрует по категориям индустрий из LinkedIn. Слишком узко — пропустим компании. Слишком широко — затянем нерелевантных.

Блоки индустрий:
- **Tech:** Computer Software, Internet, Information Technology
- **Marketing:** Marketing & Advertising, Online Media
- **Commerce:** E-commerce, Retail
- **Agency-only:** Marketing & Advertising (только для агентств)

Типичные варианты (комбинируй блоки):
- A. Tech + Marketing (без Commerce) — для SaaS/платформ
- B. Tech + Marketing + Commerce — если сегмент связан с e-commerce
- C. Только Marketing & Advertising — для агентств (намеренно узко)

---

### Вопрос 4: Company Keywords (keyword_tags)

**Контекст:** Главный фильтр — Apollo ищет компании у которых эти слова есть в описании. Чем точнее keywords, тем меньше шума. Но при маленьком TAM нужны синонимы и смежные термины.

Предложи 3 варианта с разным охватом:
- A. Узкий (8-12 keywords) — только точные термины для этого сегмента
- B. Средний (15-25 keywords) — ядро + синонимы + смежные термины
- C. Широкий (25+ keywords) — максимальный охват, риск overlap с другими сегментами

**Важно:** Проверь overlap с keyword_tags соседних сегментов из apollo-filters-v4.md. Если keyword уже есть в другом сегменте — либо исключи, либо явно обоснуй почему оставить.

Предложи конкретные списки для каждого варианта, а не абстрактные описания.

---

### Вопрос 5: Excluded Company Keywords

**Контекст:** Отсекаем нерелевантные компании, которые попадут по широким keywords.

Стандартный набор (всегда включается автоматически, не спрашивай):
```
recruitment, staffing, accounting, legal, healthcare,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant, SEO only, PPC only, print,
antivirus, cybersecurity, IT infrastructure, ERP, payroll
```

Вопрос только про **сегмент-специфичные** exclusions. Предложи 3 варианта:
- A. Только стандартные — полагаемся на точность keywords
- B. Стандартные + специфичные для этого сегмента (укажи какие и почему)
- C. B + дополнительные (более агрессивная фильтрация)

---

### Вопрос 6: Job Titles (People filters)

**Контекст:** Кто в этих компаниях принимает решение о покупке API/данных? Обычно это technical или product DMs. Некоторые сегменты имеют специфичные роли (Head of Marketplace, VP Commerce и т.д.).

Базовый набор (всегда включается):
```
CTO, VP Engineering, VP of Engineering, Head of Engineering,
VP Product, Head of Product, Chief Product Officer,
Director of Engineering, Director of Product,
Co-Founder, Founder, CEO, COO
```

Варианты:
- A. Только базовый набор — стандартные tech/product DMs
- B. Базовый + специфичные роли для этого сегмента (предложи конкретно)
- C. B + расширение (Head of Growth, VP Data и т.д.) — риск снижения качества

---

## Шаг 7 — Автоматически (не спрашивай)

**Management Level:** `c_suite, vp, director, owner, head, partner, founder` (единый для всех сегментов)

**Excluded Titles (стандартные):**
```
Intern, Junior, Assistant, Student, Freelance,
Marketing Manager, Sales Representative, Account Executive,
Account Manager, Customer Success, Support, HR, Recruiter,
Content Writer, Designer, Social Media Manager
```

Добавь сегмент-специфичные исключения если очевидны (напр. "Affiliate Manager" для affiliate-сегментов).

---

## Шаг 8 — Генерация outputs

После получения всех 6 ответов:

### 8.1 Создай filter JSON

Путь: `magnum-opus/scripts/sofia/filters/<project_lower>_<segment_lower>_v5.json`

Формат строго как в существующих файлах:

```json
{
  "segment": "SEGMENT_NAME",
  "company_filters": {
    "keyword_tags": [...],
    "locations": [...],
    "sizes": ["20,5000"],
    "excluded_keywords": [...],
    "max_pages": 25
  },
  "people_filters": {
    "titles": [...],
    "seniorities": ["c_suite", "vp", "director", "owner", "head", "partner", "founder"],
    "excluded_titles": [...]
  }
}
```

`sizes` — всегда в формате `["min,max"]` или список диапазонов.
`excluded_keywords` — стандартные + сегмент-специфичные из вопроса 5.

### 8.2 Обнови apollo-filters-v4.md

Найди файл в `sofia/projects/<Project>/docs/apollo-filters-v4.md`.
Добавь новый раздел `## Segment N — SEGMENT_NAME (new)` перед секцией `## Cross-segment exclusions`.

Структура раздела:
- Краткое описание сегмента (1 предложение)
- `### Company filters` — Industry, Keywords, Excluded Keywords, Employees, Locations
- `### People filters` — Job Titles, Management Level, Excluded Titles

### 8.3 Обнови segment-doc (если существует)

Найди `sofia/projects/<Project>/docs/segment-*.md` для этого сегмента.
Если есть секция "Phase 1: Filters" с черновыми фильтрами — замени на финальные.
Добавь ссылку: `(validated YYYY-MM-DD, full version in apollo-filters-v4.md → Segment N)`

### 8.4 Обнови базу знаний

После генерации файлов — **обязательно** обнови `references/filter-decisions.md`.
Это главное что делает скилл умнее с каждым новым сегментом.

Добавь запись по каждому разделу:

**Раздел 1 (Geography):** добавь строку в таблицу решений:
`| SEGMENT_NAME | [выбранный вариант] | [причина выбора из диалога] |`

**Раздел 2 (Company Size):** добавь строку в таблицу:
`| SEGMENT_NAME | [диапазон] | [обоснование из диалога] |`

**Раздел 3 (Industry):** добавь строку в таблицу:
`| SEGMENT_NAME | [комбинация] | [почему именно эти] |`

**Раздел 4 (Keywords):** добавь подраздел:
```
**SEGMENT_NAME:** [краткое описание логики выбора keywords].
Ключевой выбор: [что включили и почему]. Что исключили: [overlap с другими сегментами если был].
```

**Раздел 5 (Exclusions):** если добавили сегмент-специфичные exclusions — добавь строку в таблицу.

**Раздел 6 (Job Titles):** если добавили специфичные титулы — добавь строку в таблицу.

**Важно:** записывай не просто "выбрали B", а **почему** — какой аргумент из диалога стал решающим.
Именно это позволит агенту в следующий раз принять решение самостоятельно без вопросов.

---

### 8.5 Сообщи что осталось

После генерации выведи список того что НЕ сделал скилл и что нужно сделать вручную:
- [ ] Filter JSON создан: `путь/к/файлу.json`
- [ ] apollo-filters-v4.md обновлён
- [ ] segment-doc обновлён (или: не найден)
- [ ] filter-decisions.md обновлён
- [ ] **Classify prompt** — нужно добавить сегмент в gathering_prompts (БД)
- [ ] **Сегмент в БД** — добавить в kb_segments для project_id=X
- [ ] **Email sequence** — написать markdown-файл с текстами писем
