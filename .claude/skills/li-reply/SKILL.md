---
name: li-reply
description: Генерация человечных ответов на LinkedIn-сообщения с самообучением через коррекции. Используй ВСЕГДА когда пользователь говорит "ответь на линкедин", "li-reply", "linkedin reply", "напиши ответ", "ответ на сообщение", "что ответить", "draft reply", "сгенерируй ответ", "reply to lead".
triggers:
  - li-reply
  - linkedin reply
  - ответь на линкедин
  - напиши ответ
  - что ответить
  - draft reply
  - ответ на сообщение
  - сгенерируй ответ
  - reply to lead
---

# LinkedIn Reply Skill

Генерация человечных ответов на входящие LinkedIn/email сообщения от лидов.
Скилл учится на коррекциях пользователя и не повторяет ошибки.

## Input Modes

Пользователь может вызвать скилл тремя способами:

### Mode 1: Вставка сообщения
```
/li-reply
От: {name} ({company})
Сообщение: {текст сообщения}
Отправитель: {sender persona}
```

### Mode 2: GetSales UUID
```
/li-reply {lead_uuid}
```
→ Подтянуть контакт и историю через GetSales MCP

### Mode 3: Интерактивный
```
/li-reply
```
→ Спросить у пользователя: кто написал, что написал, от чьего имени отвечаем

## Execution Steps

### Step 1: Загрузить базу знаний

**ОБЯЗАТЕЛЬНО** прочитать перед генерацией:
1. `Read` файл `.claude/skills/li-reply/knowledge/corrections.md` — выученные паттерны
2. `Read` файл `.claude/skills/li-reply/knowledge/tone_rules.md` — правила тона
3. `Read` файл `.claude/skills/li-reply/knowledge/reply_frameworks.md` — фреймворки ответов
4. `Read` файл `.claude/skills/li-reply/knowledge/anti_patterns.md` — что НЕЛЬЗЯ делать
5. `Read` файл `.claude/skills/li-reply/knowledge/product_context.md` — контекст продукта

### Step 2: Получить контекст сообщения

Если передан lead_uuid:
- `mcp__getsales__get_contact(lead_uuid)` — данные лида
- `mcp__getsales__list_messages(lead_uuid, limit=10)` — история переписки
- Определить: sender persona, сегмент, историю касаний

Если вставлено сообщение:
- Извлечь: имя, компанию, роль (если есть), текст, язык
- Спросить отправителя (sender persona) если не указан

### Step 3: Классификация

Определить тип ответа:
- `interested` — хочет узнать больше, демо, материалы
- `meeting_request` — предлагает время или просит календарь
- `question` — спрашивает про pricing, как работает, API, конкуренты
- `not_interested` — вежливый отказ или "не актуально"
- `out_of_office` — автоответ, отпуск
- `wrong_person` — ушёл из компании или перенаправляет
- `objection` — бюджет, тайминг, уже есть решение
- `referral` — перенаправляет к коллеге

Показать пользователю: `Категория: {category}`

### Step 3.5: Надеть шкуру лида

**ОБЯЗАТЕЛЬНЫЙ шаг перед генерацией.** Остановись и подумай от лица лида:

1. **Кто этот человек?** — роль, компания, размер, рынок, что они строят
2. **Почему он откликнулся?** — что в нашем аутриче зацепило? Какая боль заставила ответить?
3. **О чём у него болит голова?** — конкретная проблема, которую он пытается решить прямо сейчас (не абстрактная, а реальная: "мне нужны данные по креаторам для клиентов", "мы строим платформу и не хотим 6 месяцев пилить data layer")
4. **Как наш продукт решает именно ЕГО проблему?** — не generic value prop, а конкретный мэтч между его болью и нашим решением

Показать пользователю короткий блок:
```
🎯 Почему откликнулся: {гипотеза}
🔥 Боль: {конкретная проблема}
💡 Наш ответ на боль: {как именно мы решаем}
```

Этот анализ определяет содержание ответа - пиши не про "наши фичи", а про решение ЕГО проблемы.

### Step 4: Генерация ответа

**КРИТИЧЕСКИЕ ПРАВИЛА:**

1. **Язык = язык входящего сообщения** (EN/RU/ES/etc.)
2. **Длина 30-125 слов** в зависимости от категории (см. tone_rules.md)
3. **Структура: Name + Acknowledge + Value/Answer + Soft CTA**
4. **Проверить corrections.md** — не повторять исправленные паттерны
5. **Проверить anti_patterns.md** — ни одного запрещённого шаблона
6. **Тон: peer-to-peer** — как коллега пишет коллеге, не как продавец клиенту
7. **Без em dashes (—)** — использовать обычный дефис (-) или переформулировать
8. **Подпись: только имя отправителя** — без титулов, компании, контактов в LinkedIn DM
9. **Без emoji** если лид не использует emoji в своём сообщении

**Self-check перед показом:**
- [ ] Ответ начинается с имени лида, а не с "Hi there" или "Hello"?
- [ ] Первое предложение отвечает на то, что лид реально написал?
- [ ] Есть конкретика (число, кейс, имя клиента) а не общие слова?
- [ ] CTA — один, мягкий, низко-обязывающий?
- [ ] Нет ни одной фразы из anti_patterns.md?
- [ ] Длина не превышает лимит для данной категории?
- [ ] Нет ни одного em dash?

**Humanizer-проверка (29 паттернов из blader/humanizer):**
- [ ] Нет significance inflation ("testament", "pivotal", "vital role")?
- [ ] Нет AI vocabulary ("additionally", "crucial", "delve", "landscape", "showcase", "foster")?
- [ ] Нет copula avoidance ("serves as", "stands as", "boasts")?
- [ ] Нет rule of three (три прилагательных/существительных в ряд)?
- [ ] Нет negative parallelism ("It's not just X, it's Y")?
- [ ] Нет chatbot artifacts ("I hope this helps", "Let me know if")?
- [ ] Нет sycophantic tone ("Great question!", "Absolutely!")?
- [ ] Нет filler phrases ("In order to", "It is important to note")?
- [ ] Нет excessive hedging ("could potentially")?
- [ ] Нет promotional language ("vibrant", "groundbreaking", "seamless")?
- [ ] Нет signposting ("Let's dive in", "Here's what you need to know")?

Если хоть один чекбокс не пройден — переписать до показа пользователю.

### Step 5: Показ драфта

Показать пользователю:

```
📨 Входящее: {краткое содержание}
🏷 Категория: {category}
👤 Отправитель: {sender persona}
🌐 Язык: {language}

--- DRAFT ---
{generated_reply}
--- /DRAFT ---

Отправить как есть, или есть правки?
```

### Step 6: Обработка коррекции

Если пользователь вносит правки:

1. **Записать коррекцию** в `.claude/skills/li-reply/knowledge/corrections.md`:

```markdown
## {YYYY-MM-DD} — {category}
- **Generated:** "{original phrase or pattern}"
- **Corrected to:** "{user's version}"  
- **Pattern:** {обобщённое правило для будущих ответов}
```

2. Сообщить пользователю: `Записал паттерн: {pattern}. Буду учитывать.`

### Step 7: Отправка (опционально)

Если пользователь подтверждает и хочет отправить:
- Спросить sender_profile_uuid (или определить по контексту)
- `mcp__getsales__send_message(sender_profile_uuid, lead_uuid, text)`
- **ВАЖНО:** Не отправлять без явного подтверждения пользователя

## Knowledge Base Files

| File | Purpose |
|------|---------|
| `knowledge/tone_rules.md` | Правила тона, стиля, длины, языка |
| `knowledge/reply_frameworks.md` | Фреймворки по категориям + industry best practices |
| `knowledge/anti_patterns.md` | Запрещённые шаблоны и формулировки |
| `knowledge/corrections.md` | Выученные коррекции (самообучение) |
| `knowledge/product_context.md` | Контекст продуктов, value props, sender personas |

## External References

Для глубокого контекста (читать при необходимости, НЕ каждый раз):
- `sofia/projects/OnSocial/docs/operator_playbook.md` — полный playbook с 36k разговоров
- `sofia/projects/OnSocial/getsales_strategy_2026-04-01.md` — LinkedIn strategy
- `sofia/projects/OnSocial/hub/smartlead_hub/sequences/v5_*.md` — email sequences (стиль)

## GetSales MCP Tools

| Tool | When |
|------|------|
| `mcp__getsales__get_contact(lead_uuid)` | Получить данные лида |
| `mcp__getsales__list_messages(lead_uuid)` | История переписки |
| `mcp__getsales__search_contacts(query)` | Найти лида по имени/LinkedIn |
| `mcp__getsales__send_message(sender_profile_uuid, lead_uuid, text)` | Отправить ответ |
| `mcp__getsales__list_sender_profiles()` | Список отправителей |

## Sender Profiles (cached)

| Name | UUID | Use for |
|------|------|---------|
| Rajat Chauhan | `f4ddb17a-d410-40d2-9130-d7cb00601d73` | OnSocial LinkedIn outreach |
| Albina Yanchanka | `d5c18723-aca1-4ca4-84b8-60fdee894d67` | OnSocial LinkedIn outreach |

## Quality Metrics

Track in corrections.md header (update periodically):
- Total replies generated
- Total corrections received
- Most common correction patterns
- Correction rate trend (should decrease over time)
