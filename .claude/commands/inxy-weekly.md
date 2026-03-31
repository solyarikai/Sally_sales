# INXY Weekly Sales Analytics

You are generating a weekly sales analytics report for the INXY project by reading the Slack channel.

## Slack Configuration
- **Bot Token**: `xoxb-5059703821363-10697452872996-Wo4zO1bQc7h5FlGNBXowiyZ9`
- **Channel ID**: `C08L8J7F0DB` (INXY channel)
- **Workspace**: sally-saas.slack.com

## User ID Mapping
```
U099J0UPYP8 = Agnia (SDR, books meetings, chases feedback)
U07E1JVP95Z = Danila (PM, weekly summaries)
U033R8GFUHH = s.kuznetsov (Sales)
U08V2S8KV2L = p.akchurin / Pavel (Sales)
U08RPQ805AS = a.zakharchuk / Alexey (Sales)
U08MX4T90HK = i.firsov / Ilya (Sales)
U098AH9UGAH = s.kosovanov (Client-side)
U08PAEKBHMH = Eugene (SDR)
U07U930BPQE = d.spichek (Client-side manager)
U09T32VCTEX = a.bakharev (Sales)
U063D20LYB0 = r.batovkin (Sales)
U0AAQGN71M2 = s.dvoretskii (Client-side)
U0AENT1HBG8 = m.ionin (Client-side)
U0ACA2UCTHB = t.granowski (Sales)
U09C17KSB39 = r.romaniuk / Robert (Sales, English/Polish)
U08R0K1BCUU = ak
U09UDAA5N4X = e.chubarova
U0ALHDARNVA = Sally AI (Bot)
```

## Step 1: Ask the user for the period

Propose a default period based on the current date:
- **Booked meetings**: from last Friday 11:00 MSK to now (the user typically runs this on Friday mornings)
- **Conducted meetings (feedback received)**: look at a wider window (~4 weeks back) because meetings booked weeks ago may have feedback this week

Example prompt:
> Собираю статистику INXY. Предлагаю период:
> - **Поставленные встречи**: с [прошлая пятница] 11:00 МСК по сейчас
> - **Проведённые встречи (по дате ОС)**: смотрю за последний месяц
>
> Подходит или скорректировать?

Wait for the user to confirm or adjust before proceeding.

## Step 2: Fetch messages from Slack

Use the Slack API via `curl` or Python with `urllib` to fetch messages.

### Fetch channel history
```
GET https://slack.com/api/conversations.history
  ?channel=C08L8J7F0DB
  &oldest={unix_timestamp_4_weeks_ago}
  &latest={unix_timestamp_now}
  &limit=200
Header: Authorization: Bearer {BOT_TOKEN}
```

Paginate if `has_more` is true using `cursor` from `response_metadata.next_cursor`.

### Identify meeting messages
Meeting bookings contain `:phone:` emoji in the text. Two types:
1. **Scheduled calls**: contain `:spiral_calendar_pad:` or `:calendar:` with `Звонок с @[sales_person] [date] [time]`
2. **Telegram transfers**: contain phrases like "кто может написать лиду в тг", "дам лиду твой тг", "можешь связаться с лидом"

### Fetch threads
For each meeting message with `reply_count > 0`, fetch the thread:
```
GET https://slack.com/api/conversations.replies
  ?channel=C08L8J7F0DB
  &ts={message_ts}
  &limit=100
```

**IMPORTANT**: Handle Windows encoding issues — always write output to files with `encoding='utf-8'` and read from files rather than printing Cyrillic directly to stdout.

## Step 3: Extract structured data

For each meeting, extract:
- **contact_name**: Person's name from the `:phone:` line
- **company**: Company name (usually a link)
- **sales_person**: Who the call is assigned to (from `Звонок с @...` or who was asked to write in TG)
- **meeting_date**: Scheduled date/time
- **hypothesis**: Segment (e.g., Russian DM, PSP, Luma, ICE collegue, Ecom Berlin, ТГ, etc.)
- **post_date**: When the message was posted in Slack

From threads, extract:
- **status**: One of: `квал`, `не квал`, `no-show`, `перенос`, `отменён`, `ожидание`
- **feedback_date**: When the sales person gave feedback
- **feedback_text**: Brief summary of why qualified/not qualified
- **conducted**: Whether the meeting actually happened (true/false)

### Status classification rules (from thread messages by sales team):
- **Квал**: "квал", "хороший лид", "берем", "будем двигаться дальше", explicit confirmation "ставлю квал?" → "Да"
- **Не квал**: "не квал", explanation of why not suitable (wrong jurisdiction, wrong product need, etc.), "не будем работать", "не пропустит наш AML"
- **No-show**: "не пришел", "не подключился", "не вышел на связь"
- **Перенос**: "перенесли", "rescheduled", "postpone"
- **Отменён до звонка**: "нет смысла в звонке", cancelled before the call happened
- **Ожидание**: No feedback yet, or "не ответил", "прочитал, не ответил"

## Step 4: Generate the report

### Format:

```
## Период [дата] — [дата]

### Поставлено встреч: X

**Запланированные звонки (N):**

| # | Дата поста | Контакт | Компания | Сейлз | Дата звонка | Гипотеза |
|---|---|---|---|---|---|---|
| ... |

**Передано в ТГ/мессенджеры (M):**

| # | Дата поста | Контакт | Компания | Сейлз | Статус связи |
|---|---|---|---|---|---|
| ... |

---

### Проведённые встречи с ОС за [период] (по дате фидбека)

**Квал (K):**

| # | Контакт | Компания | Сейлз | Дата ОС | Детали |
|---|---|---|---|---|---|
| ... |

**Не квал (L):**

| # | Контакт | Компания | Сейлз | Дата ОС | Причина |
|---|---|---|---|---|---|
| ... |

**No-show (J):**

| # | Контакт | Компания | Сейлз | Дата | Статус |
|---|---|---|---|---|---|
| ... |

---

### Итого за неделю

| Метрика | Кол-во |
|---|---|
| Поставлено встреч | X (Y звонков + Z ТГ) |
| Проведено встреч (получена ОС) | ... |
| Квал | ... |
| Не квал | ... |
| No-show | ... |
| Ожидание ответа | ... |
```

## Important notes
- Resolve all `<@USERID>` references to human-readable names using the mapping above
- A meeting is "conducted" if there's feedback about the actual call happening (even if the outcome is "не квал")
- The "feedback date" is when the sales person posted their feedback in the thread, NOT the scheduled meeting date
- Meetings booked in the current week but with calls scheduled for next week should appear in "Поставлено" but NOT in "Проведено" unless feedback already exists
- If a meeting was rescheduled and then conducted, count it by the feedback date
- Half-quals (1/2) happen when the outcome is uncertain — note these
- Use the wider time window (4 weeks) for "conducted" because meetings booked weeks ago may have feedback this week
