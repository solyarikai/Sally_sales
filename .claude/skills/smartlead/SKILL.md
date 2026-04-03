---
name: smartlead
description: >-
  Универсальный SmartLead API скилл - кампании, лиды, секвенции, аккаунты, аналитика, вебхуки, инбокс.
  Используй ВСЕГДА когда пользователь упоминает SmartLead, кампании рассылок, cold email,
  выгрузку лидов, экспорт из кампании, создание кампании, секвенции писем, email accounts,
  аналитику кампании, replies inbox, вебхуки SmartLead.
  Триггеры: "smartlead", "смартлид", "кампания", "выгрузи лиды", "экспорт лидов",
  "leads export", "создай кампанию", "секвенция", "sequence", "email accounts",
  "аналитика кампании", "campaign stats", "inbox replies", "вебхук", "webhook",
  "добавь лиды", "add leads", "поставь на паузу", "pause campaign",
  "покажи кампании", "list campaigns", "message history", "история переписки".
---

# SmartLead — Universal API Tool

Единый скрипт `smartlead.py` для всех операций с SmartLead API.

**Скрипт**: `python3 $(pwd)/.claude/skills/smartlead/smartlead.py <command> [args]`

## Важные правила

1. **НИКОГДА не активируй кампании через API** (START/ACTIVE запрещены). Только PAUSED и STOPPED. Активация - только вручную в SmartLead UI.
2. **RTK фильтрует curl** - если нужен raw curl, используй `rtk proxy curl`. Но скрипт работает через urllib напрямую, RTK его не трогает.
3. **Пагинация**: макс 100 лидов за запрос. Скрипт автоматически проходит все страницы.
4. **CSV экспорт включает ВСЕ поля** - стандартные + все custom_fields динамически.

---

## Команды

### Кампании

```bash
# Список всех кампаний
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaigns
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaigns --search "OnSocial"
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaigns --status ACTIVE
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaigns --json  # полный JSON

# Детали кампании
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaign-get 3064335

# Создать кампанию (статус DRAFTED)
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaign-create "c-OnSocial_NEW SEGMENT #C"

# Поставить на паузу / остановить (START запрещён!)
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaign-status 3064335 PAUSED

# Обновить настройки
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaign-settings 3064335 '{"send_as_plain_text": true, "follow_up_percentage": 100}'

# Установить расписание
python3 $(pwd)/.claude/skills/smartlead/smartlead.py campaign-schedule 3064335 '{"tz": "Europe/London", "days": [1,2,3,4,5], "startHour": "09:00", "endHour": "18:00"}'
```

### Лиды

```bash
# Список лидов (JSON)
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads 3064335
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads 3064335 --status COMPLETED
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads 3064335 --email-status is_replied

# Экспорт в CSV (все поля + все custom_fields)
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-export 3064335
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-export 3064335 --status COMPLETED -o completed_leads.csv
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-export 3064335 --require-job-title

# Добавить лиды из JSON файла (макс 400 за батч, автосплит)
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-add 3064335 leads.json
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-add 3064335 leads.json --skip-blocklist --allow-duplicates

# Поиск лида по email
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-search john@example.com

# Обновить лида
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-update 3064335 123456 '{"first_name": "John"}'

# Пауза / возобновление лида
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-pause 3064335 123456
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-resume 3064335 123456

# Отписать лида глобально
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-unsubscribe 123456

# Категории лидов
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-categories
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-set-category 3064335 123456 5

# История переписки
python3 $(pwd)/.claude/skills/smartlead/smartlead.py leads-history 3064335 123456
```

### Секвенции

```bash
# Получить секвенции кампании
python3 $(pwd)/.claude/skills/smartlead/smartlead.py sequences 3064335

# Создать/обновить секвенции из JSON файла
python3 $(pwd)/.claude/skills/smartlead/smartlead.py sequences-set 3064335 sequences.json
```

Формат JSON для секвенций:
```json
[
  {
    "id": null,
    "seq_number": 1,
    "subject": "Hello {{first_name}}",
    "email_body": "<p>Hi {{first_name}},</p>",
    "seq_delay_details": {"delay_in_days": 0}
  },
  {
    "id": null,
    "seq_number": 2,
    "subject": "",
    "email_body": "<p>Following up...</p>",
    "seq_delay_details": {"delay_in_days": 3}
  }
]
```

### Email-аккаунты

```bash
# Все аккаунты
python3 $(pwd)/.claude/skills/smartlead/smartlead.py accounts
python3 $(pwd)/.claude/skills/smartlead/smartlead.py accounts --warmup-status ACTIVE --json

# Аккаунты кампании
python3 $(pwd)/.claude/skills/smartlead/smartlead.py accounts-campaign 3064335

# Добавить аккаунты к кампании
python3 $(pwd)/.claude/skills/smartlead/smartlead.py accounts-add 3064335 "101,102,103"
```

### Аналитика

```bash
# Статистика кампании (sent, opened, clicked, replied, bounced)
python3 $(pwd)/.claude/skills/smartlead/smartlead.py analytics 3064335

# Аналитика по шагам секвенции
python3 $(pwd)/.claude/skills/smartlead/smartlead.py analytics-sequences 3064335

# Аналитика по датам
python3 $(pwd)/.claude/skills/smartlead/smartlead.py analytics-dates 3064335 --start-date 2026-03-01 --end-date 2026-04-01
```

### Вебхуки

```bash
# Список вебхуков
python3 $(pwd)/.claude/skills/smartlead/smartlead.py webhooks

# Создать вебхук
python3 $(pwd)/.claude/skills/smartlead/smartlead.py webhook-create '{"name": "Replies", "webhook_url": "https://example.com/hook", "association_type": 3, "email_campaign_id": 3064335, "event_type_map": {"REPLIED": true}}'

# Обновить / удалить
python3 $(pwd)/.claude/skills/smartlead/smartlead.py webhook-update 456 '{"name": "Updated"}'
python3 $(pwd)/.claude/skills/smartlead/smartlead.py webhook-delete 456
```

### Master Inbox

```bash
# Ответы из инбокса
python3 $(pwd)/.claude/skills/smartlead/smartlead.py inbox-replies
python3 $(pwd)/.claude/skills/smartlead/smartlead.py inbox-replies --campaign-id 3064335

# Ответить лиду
python3 $(pwd)/.claude/skills/smartlead/smartlead.py inbox-reply 3064335 123456 "Thanks for your reply!"

# Заметка к лиду
python3 $(pwd)/.claude/skills/smartlead/smartlead.py inbox-note 123456 "Interested, follow up next week"

# Обновить категорию в инбоксе
python3 $(pwd)/.claude/skills/smartlead/smartlead.py inbox-category 123456 5
```

---

## Поиск кампании по названию

Если пользователь даёт название кампании вместо ID:

1. Запусти `campaigns --search "часть названия"` чтобы найти ID
2. Используй найденный ID в остальных командах

---

## Формат leads-add JSON

Файл с лидами для добавления:
```json
[
  {
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "Acme Corp",
    "linkedin_profile": "https://linkedin.com/in/johndoe",
    "custom_fields": {
      "job_title": "CEO",
      "industry": "SaaS"
    }
  }
]
```

---

## SmartLead Email Formatting Rules

При работе с секвенциями (email_body):
- Используй `<br>` вместо `\n` для переносов строк
- Используй `-` вместо `—` (em dash ломает некоторые email клиенты)
- A/B варианты не поддерживаются API - добавляй вручную в SmartLead UI
