# SEXY_STATUSES_LOGIC

## Воронка статусов контактов

### Статусы (поле `contacts.status`)

| Статус | Описание | Как попадает |
|--------|----------|--------------|
| `new` | Новый контакт, ещё не писали | Импорт, создание |
| `contacted` | Написали, ждём ответ | После отправки письма |
| `replied` | Ответил | Автоматически при получении ответа |
| `calendly_sent` | Отправили ссылку на Calendly | Вручную оператор |
| `meeting_booked` | Звонок назначен | Вручную оператор |
| `meeting_held` | Звонок состоялся | Вручную оператор |
| `qualified` | Квалифицированный лид | Вручную или `is_qualified=true` |
| `not_qualified` | Не квалифицирован | Вручную или негативный ответ |

### Категории ответов (поле `processed_replies.category`)

Это **интент** ответа — что лид написал. Ставится автоматически AI.

| Категория | Описание |
|-----------|----------|
| `meeting_request` | Просит встречу |
| `interested` | Заинтересован |
| `question` | Задаёт вопрос |
| `not_interested` | Не интересно |
| `wrong_person` | Не тот человек |
| `out_of_office` | Нет на месте |
| `unsubscribe` | Отписка |
| `other` | Другое |

### Разница между Status и Category

- **Status** = где контакт в **процессе** (воронка)
- **Category** = какой **интент** у ответа (что написал)

Они ортогональны:
```
Контакт со статусом "replied" может иметь category:
  - interested (заинтересован)
  - question (задаёт вопрос)
  - not_interested (отказ)
  - и т.д.
```

### Автоматическое обогащение статусов

При наличии данных в `processed_replies` статус обновляется:

```sql
-- 1. Квалифицированные (is_qualified=true)
UPDATE contacts c SET status = 'qualified'
FROM processed_replies pr
WHERE LOWER(pr.lead_email) = LOWER(c.email)
  AND pr.is_qualified = true
  AND c.project_id = :project_id;

-- 2. Не квалифицированные (негативные категории)
UPDATE contacts c SET status = 'not_qualified'
FROM processed_replies pr
WHERE LOWER(pr.lead_email) = LOWER(c.email)
  AND pr.category IN ('not_interested', 'unsubscribe')
  AND c.status NOT IN ('qualified', 'meeting_held', 'meeting_booked')
  AND c.project_id = :project_id;

-- 3. Ответившие (есть запись в processed_replies)
UPDATE contacts c SET status = 'replied'
FROM processed_replies pr
WHERE LOWER(pr.lead_email) = LOWER(c.email)
  AND c.status NOT IN ('qualified', 'not_qualified', 'meeting_held', 'meeting_booked', 'calendly_sent')
  AND c.project_id = :project_id;
```

### Как раскатать на свой проект

1. Замени `project_id = :project_id` на ID своего проекта
2. Запусти SQL запросы по порядку (1 → 2 → 3)
3. Проверь результат в CRM

### Пример

**До обогащения:**
| Email | Status | ProcessedReply.category | is_qualified |
|-------|--------|------------------------|--------------|
| ivan@mail.ru | lead | interested | false |
| petr@mail.ru | lead | not_interested | false |
| anna@mail.ru | lead | meeting_request | true |

**После обогащения:**
| Email | Status |
|-------|--------|
| ivan@mail.ru | replied |
| petr@mail.ru | not_qualified |
| anna@mail.ru | qualified |

### Ручное управление

После автоматического обогащения оператор двигает по воронке вручную:

```
replied → calendly_sent → meeting_booked → meeting_held → qualified
```

В CRM есть фильтр по Status — можно отфильтровать всех с `replied` и обработать.
