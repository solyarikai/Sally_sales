# Instantly Inbox Placement Tests — гайд по настройке

**Аудитория:** sales engineers Sally
**Зачем:** правильно настроить inbox placement tests (IPT) в Instantly так,
чтобы результаты реально отражали deliverability ящиков — не silent failures,
не самоподтверждающие warmup-цифры.

Гайд собран по итогам отладки OnSocial-мониторинга 2026-04-23..27, когда мы
прошли путь от «0 records, 27 ящиков silent» до рабочего отчёта с
per-provider deliverability.

---

## TL;DR

Правильно настроенный IPT требует четырёх вещей:
1. Workspace на тарифе **Inbox Placement Growth** (`pid_ip_g`, ~$47/мес)
2. Все sender-ящики в `status=1` (active) **в момент создания теста**
3. `recipients_labels` заполнен всеми тремя доступными ESP-опциями (Google Pro,
   Google Personal, Outlook Pro) — это даёт встроенный seed pool Instantly
4. Реалистичные subject/body, совпадающие с боевыми кампаниями (spam-фильтры
   оценивают контент)

Если что-то из этого пропущено — получишь один из failure-сценариев из
[Troubleshooting](#troubleshooting).

---

## Два способа запустить тест

| Подход | Когда использовать |
|---|---|
| **API / Claude Code** | Регулярный автоматический мониторинг (cron), большие списки ящиков, программные алерты в Slack |
| **UI (app.instantly.ai)** | Разовая проверка, ручное расследование, когда нет смысла писать скрипты |

Оба пути дают одинаковый тест и одинаковые данные — выбирай по удобству
рабочего процесса.

---

## Prerequisites (для обоих путей)

### 1. Убедиться что биллинг активен

Inbox Placement продаётся отдельно от Outreach. У workspace должна быть
подписка с `product_type: inbox_placement`. Без неё **все** API endpoints
относящиеся к IPT возвращают `402 Payment Required: Workspace does not have
an active paid plan` — включая read-only.

**Проверить через API:**

```bash
curl -s https://api.instantly.ai/api/v2/workspace-billing/subscription-details \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" | jq .
```

Ожидается:
```json
{
  "subscriptions": [
    {
      "product_id": "pid_ip_g",
      "product_type": "inbox_placement",
      "plan_type": "plt_primary",
      "current_period_end": 1779735707,
      "price_in_dollars": 47,
      "all_subs_cancelled": false
    }
  ]
}
```

Если `subscriptions: []` или `all_subs_cancelled: true` — IPT работать не
будет, сначала чини биллинг через UI billing page.

**Проверить через UI:** открой `https://app.instantly.ai`, в правом верхнем
углу меню пользователя → **Billing** (или **Settings → Billing**). Ищи
секцию «Inbox Placement» с активной подпиской. Если виден только Outreach
plan и нет отдельной записи Inbox Placement — значит не оплачено.

### 2. Активировать все sender-ящики

**Это самая частая причина провала.** При создании теста Instantly фиксирует
список активных senders. Если ящик в `status=2` (paused) или `status=-1/-2/-3`
(error) ровно в этот момент — он молча исключается, тест проходит без него,
никаких analytics-записей по этому sender'у не появится. Когда ты потом
заметишь и активируешь ящик — для текущего теста уже поздно.

Для нашего 27-mailbox теста OnSocial, созданного когда все 27 были paused:
0 записей по всему тесту. После активации всех 27 и пересоздания: 100%
senders отдали данные в первой же batch.

**Коды статусов аккаунтов:**
- `1` = active (будет слать)
- `2` = paused (исключён)
- `-1` = connection error (исключён)
- `-2` = soft bounce error (исключён)
- `-3` = sending error (исключён)

#### Через API

Список всех OnSocial-ящиков и их статус:

```bash
curl -s "https://api.instantly.ai/api/v2/accounts?limit=100" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  | jq '.items[] | select(.email | test("onsocial|crona")) | {email, status, warmup_status}'
```

Resume каждого paused-ящика:

```bash
curl -X POST "https://api.instantly.ai/api/v2/accounts/$EMAIL/resume" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Mark-fixed каждого errored (только после того как починил underlying
проблему):

```bash
curl -X POST "https://api.instantly.ai/api/v2/accounts/$EMAIL/mark-fixed" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Важные нюансы:
- Оба endpoint **требуют пустой JSON-body `{}`**. Без body вернут
  `400 FST_ERR_CTP_EMPTY_JSON_BODY`.
- Email в path должен быть URL-encoded (`@` → `%40`).
- У разных API-ключей разные scope. Reader-ключ
  (`...:RIBVujbQqgXU` для нашего workspace) умеет и list, и account-write.
  Writer-ключ (`...:sykqgmaZLtul`) нужен для создания тестов, но возвращает
  401 на `GET /accounts`. Если что-то ломается с 401 — попробуй другой ключ.

Готовый скрипт лежит в `magnum-opus/infra/` (см. секцию OnSocial-пример
ниже).

#### Через UI

1. Открой `https://app.instantly.ai/app/accounts`
2. Отфильтруй ящики, которые планируешь поставить в тест
3. Для каждой строки с бейджем **Paused**: меню `…` справа → **Resume**
4. Для каждой строки в error (красный бейдж): меню `…` → **Mark as fixed**
   (только после того как починил SMTP/IMAP — иначе вернётся в error через
   несколько минут)
5. После действия бейдж Paused/error должен исчезнуть — это значит
   `status=1`. Сверь количество активных строк по проекту.

### 3. Подготовить реалистичный subject и body

Принимающие ESP (Gmail/Outlook) скорят содержимое тестового письма как если
бы это был настоящий cold email. Если протестируешь с заглушкой или
содержимым другого проекта — померяешь deliverability **этого контента**, а
не своих ящиков. Возьми свежий subject и body из боевой кампании в SmartLead
и вставь.

---

## Вариант 1 — API / Claude Code

### Шаг 1: создание теста

`POST /api/v2/inbox-placement-tests` со следующим payload:

```javascript
{
  "name": "ProjectName auto " + new Date().toISOString().slice(0, 10),
  "type": 1,                    // one-time test (не automated/recurring)
  "delivery_mode": 1,           // one by one (не all-together)
  "sending_method": 1,          // send from Instantly (не external)
  "email_subject": "<реальный subject из боевой кампании>",
  "email_body": "<HTML body из боевой кампании>",
  "emails": [
    "sender1@yourdomain.com",
    "sender2@yourdomain.com",
    // ... все senders которые тестим
  ],
  "recipients_labels": [
    {"region": "North America", "sub_region": "US", "type": "Professional", "esp": "Google"},
    {"region": "North America", "sub_region": "US", "type": "Personal",     "esp": "Google"},
    {"region": "North America", "sub_region": "US", "type": "Professional", "esp": "Outlook"}
  ]
}
```

Что делает каждый параметр:

- **`type`** — `1` для разового теста, `2` для автоматического повторяющегося,
  управляемого Instantly. Используй `1` и крути cron самостоятельно.
- **`delivery_mode`** — `1` шлёт по одному письму, `2` все параллельно.
  `1` для органичного вида.
- **`sending_method`** — `1` использует Instantly relay через твои
  authenticated ящики (это что нужно), `2` для «отправлю сам и расскажу что
  сделал». Всегда `1`.
- **`emails`** — sender-ящики. Каждый должен быть `status=1` в `/accounts`
  ровно в этот момент (см. Prerequisites #2).
- **`recipients_labels`** — встроенный seed pool Instantly. 3 entry выше — это
  всё что доступно на тарифе `pid_ip_g`; используй все три чтобы получить
  per-provider distribution.
- **`recipients`** — не передавай. Когда отправляешь `recipients_labels`,
  Instantly сам генерирует 22 actual recipient inboxes покрывающие labels
  (10× Google Pro на Sally seed-доменах, 2× Google Personal на free Gmail,
  10× Outlook Pro на Sally seed-доменах). Они появятся в response.

**Response** содержит `id` теста (UUID) и `status: 1` (active). Сохрани ID —
он нужен для запроса analytics.

### Шаг 2: подождать

Тест проходит несколько фаз:
1. Отправка писем (~1–10 мин в зависимости от размера)
2. Recipient-ящики получают сообщения
3. Instantly опрашивает каждый recipient через IMAP примерно раз в 25 мин и
   маркирует каждое сообщение inbox vs spam

Записи появляются в `/inbox-placement-analytics` только после IMAP-poll.
Не жди данных в первые 20 мин даже для маленького теста.

Для нашего 26-sender × 22-recipient = 572-pair OnSocial теста записи
приходили батчами по ~26 каждые ~25 мин, полное покрытие заняло ~2.5 часа.
Probe из 1 sender × 1 recipient тоже занял ~25 мин до первой записи.

### Шаг 3: вытащить analytics

Постранично:

```bash
curl -s "https://api.instantly.ai/api/v2/inbox-placement-analytics?test_id=$TID&limit=100" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY"
```

Каждая запись выглядит так:

```json
{
  "test_id": "...",
  "sender_email": "bhaskar@onsocial-platform.com",
  "recipient_email": "avery@gofynor.com",
  "is_spam": false,
  "spf_pass": true,
  "dkim_pass": true,
  "dmarc_pass": true,
  "recipient_esp": 1,             // 1=Google, 2=Outlook
  "recipient_type": 1,            // 1=Professional, 2=Personal
  "recipient_geo": 1,
  "authentication_failure_results": null,
  "record_type": 2
}
```

### Шаг 4: агрегировать и репортить

Сгруппировать по `sender_email`, посчитать total vs spam, посчитать
deliverability:

```javascript
deliverability(sender) = (1 - spam_count / total_count) * 100
```

**Фильтровать строго по configured `emails` из конфига теста** — Instantly
иногда лекает записи из других тестов того же workspace в твою аналитику, и
иногда подменяет один ящик на другой на том же домене (наш тест указывал
`petr@crona-force.com`, а Instantly вернул данные от `eleonora@crona-force.com`).
Всегда сверяй с массивом `detail.emails` теста, отбрасывай чужих senders.

Бакеты для отчёта:

- **Healthy** — у sender'а есть записи и deliverability ≥ 80%
- **Problematic** — записи есть, но deliverability < 80%
- **Silent** — sender в конфиге теста, но записей нет (значит не отправил:
  paused при создании, ИЛИ подменён, ИЛИ реально заблокирован)

Для каждого problematic sender'а делай per-recipient breakdown по
`recipient_esp` + `recipient_type` чтобы понять какой провайдер режет.
Domain-reputation проблема у Google выглядит так: 6 Google rcpts → все spam,
4 Outlook rcpts → все inbox.

### Шаг 5: расписать cron

Паттерн который мы используем для OnSocial на основном Hetzner-сервере:

```cron
# Создать тест (~3h до отчёта чтобы IMAP-polling успел собрать данные)
0 3 * * 2,5 cd /home/leadokol/scripts && node instantly-onsocial-start-test.js \
    >> /home/leadokol/logs/instantly-onsocial-start.log 2>&1

# Прочитать analytics, отправить в Slack
0 6 * * 2,5 cd /home/leadokol/scripts && node instantly-spam-report-onsocial.js \
    >> /home/leadokol/logs/instantly-spam-report-onsocial.log 2>&1
```

Выбираем Tue/Fri чтобы совпадало со стандартным outreach-расписанием. Чаще
чем раз на (Tue/Fri) не запускай — IPT credits не безлимитные, а мелкие
дневные колебания не несут сигнала.

---

## Вариант 2 — UI (app.instantly.ai)

### Шаг 1: открыть creator теста

Сайдбар → **Inbox Placement** (иконка похожая на inbox tray). На странице
inbox placement жми **Create Test** (вверху справа).

### Шаг 2: заполнить форму

- **Test name** — `<ProjectName> auto YYYY-MM-DD`. Префикс `auto` важен если
  планируешь дёргать «последний тест по имени» из скриптов.
- **Test type** — выбираем **One-time test** (соответствует API `type=1`).
- **Delivery mode** — **One by one** (соответствует `delivery_mode=1`).
- **Sending method** — **Send from Instantly** (соответствует
  `sending_method=1`).
- **Email subject** — вставь точный subject который используешь в боевой
  кампании этого проекта.
- **Email body** — вставь точный HTML body. UI-редактор поддерживает rich-text
  и HTML source view; используй HTML чтобы избежать авто-форматирования.
- **Senders** — multi-select ящиков проекта. У каждого должно быть active в
  dropdown (никаких Paused/error бейджей). Если видишь Paused в dropdown —
  стоп, иди фикси на странице Email Accounts, потом возвращайся.
- **Recipients section** — здесь чаще всего настраивают неправильно.
  - Ищи tab/toggle с лейблом **Use Instantly seed pool** или
    **Recipient labels** (в разных билдах UI называется по-разному).
  - Выбираем все 3 доступные labels:
    - **Google · Professional · US**
    - **Google · Personal · US**
    - **Outlook · Professional · US**
  - **Не добавляй** свои custom recipient emails сверху — они не дают
    per-provider visibility и усложняют фильтрацию analytics.

Жмём **Create**. Бейдж статуса показывает **Active** пока тест идёт.

### Шаг 3: подождать

Те же тайминги что в API: ~25 мин до первых записей, ~1–3h до полных
результатов в зависимости от размера. UI показывает progress bar; обнови
страницу или закрой вкладку и вернись позже.

### Шаг 4: посмотреть результаты

Когда тест закончился (бейдж **Completed**), на странице detail видны
несколько панелей:

- **Overall placement** — единое число: % inbox vs % spam усреднённо по всем
  парам (sender, recipient). Sanity check.
- **Per-sender table** — одна строка на sender-ящик, колонки: emails sent,
  inbox, spam, deliverability %. Сортируй по возрастанию deliverability чтобы
  увидеть худших. Всё < 80% — твой action list.
- **Per-recipient/provider breakdown** — обычно график с колонками Google
  Pro / Google Personal / Outlook Pro. Для каждого problematic sender'а
  кликаешь — видишь per-recipient детали. Sender который весь spam в Google,
  но inbox в Outlook — это Google domain-reputation проблема, не контент и
  не auth.
- **Authentication results** — % проходимости SPF/DKIM/DMARC. Что-либо
  кроме 100% — DNS misconfiguration где-то.

### Шаг 5: действовать по результатам

Для каждого problematic sender'а:
- **Spam в Google + inbox в Outlook** → проверяй Google Postmaster Tools для
  этого домена (https://postmaster.google.com), смотри панели IP/Domain
  reputation. Починка может занять дни.
- **Spam везде** → скорее всего SPF/DKIM/DMARC. Сверяй с панелью
  authentication.
- **Silent** (у sender'а 0 данных в тесте) → один из:
  1. Был paused при создании теста → resume + пересоздать тест
  2. Instantly подменил на другой sender того же домена (видно в per-sender
     table — будет неожиданное имя) → проверь какие ещё аккаунты есть на
     этом домене
  3. SMTP-level reject у всех 22 recipients → серьёзный deliverability
     failure, домен в крупном blacklist

---

## OnSocial — конкретный пример

Наш референсный тест (2026-04-27):
- Senders: 27 ящиков (14 `bhaskar@onsocial-*.com`, 3 `bhaskar@onsocial*.com`
  без дефиса, 10 `petr@crona-*.com`)
- Recipients: встроенный seed pool через `recipients_labels` (3 ESP) → 22
  actual recipient inboxes автогенерируются
- Subject: скопирован из активной OnSocial cold-кампании в SmartLead
- Cron: 03:00 UTC создание, 06:00 UTC отчёт (Tue/Fri)

Скрипты лежат в `magnum-opus/infra/` (source of truth, в git) и задеплоены
на `/home/leadokol/scripts/` основного Hetzner (`hetzner` SSH alias):

- `instantly-onsocial-start-test.js` — создаёт тест
- `instantly-spam-report-onsocial.js` — читает последний completed тест,
  кидает bucketed-отчёт в Slack (`#onsocial` webhook)

Находки этого теста:
- 24 из 26 senders → **100% inbox** на каждом Google/Outlook recipient'е
- `eleonora@crona-b2b.com` → 60% (Google → spam, Outlook → inbox)
- `eleonora@cronaaipipeline.com` → 33% (Google → spam, Outlook → inbox)
- 1 ящик (`petr@prospects-crona.com`) → нет в Instantly accounts вообще,
  надо добавить перед следующим тестом

Эти два `eleonora@*` результата вычислили Google-only domain-reputation
проблемы. Без per-provider breakdown (который требует `recipients_labels`,
который требует paid plan) увидели бы «60%» и «33%», но не ГДЕ чинить.

---

## Troubleshooting

### `402 Payment Required: Workspace does not have an active paid plan`
Подписка Inbox Placement отсутствует или истекла. Проверь
`/workspace-billing/subscription-details`. Чини в UI Billing page, потом
ретрай. Важно: этот 402 ловит и READ, и WRITE — даже листинг существующих
тестов падает. Не путать с rate-limit (тот возвращает 429).

### `400 FST_ERR_CTP_EMPTY_JSON_BODY`
Дёрнул `POST /accounts/{email}/resume` (или похожий) без body. Отправь `{}`.
Если используешь `curl`, добавь `-d '{}'`.

### Тест в `status=1` уже 30+ мин, 0 записей в analytics
Самая вероятная причина: senders были paused когда тест создавался. Проверь
текущий статус каждого sender'а из конфига — если хоть один в `status≠1`,
тест не восстановится. Удали его (`DELETE /inbox-placement-tests/{id}` —
обязательно убрать Content-Type header чтобы избежать empty-body issue),
активируй senders, пересоздай.

### В записях видны senders, которых нет в моём конфиге (foreign senders)
Instantly лекает записи между тестами одного workspace, плюс подменяет
ящики на одном домене. Всегда пересекай analytics со списком configured
`emails` перед расчётом deliverability. Используй этот фильтр консистентно
во всех инструментах.

### `warmup_reputation` показывает 100%, а ящики явно в спаме
SmartLead `warmup_reputation` мерит трафик внутри Superwarm (юзеры
SmartLead шлют друг другу), где у всех настроены фильтры чтобы эти письма
не попадали в спам. Закрытый цикл — показывает ~100% даже когда внешний
Gmail блочит того же sender'а 100% времени. **Никогда не используй
`warmup_reputation` как сигнал deliverability** — используй IPT.

### `open_rate` = 0%, но replies не нулевые
Apple Mail Privacy Protection, корпоративные firewall и современные email
clients вырезают или префетчат tracking-пиксели. 0% open rate с ненулевыми
reply означает что open tracking сломан, а не что письма ушли в спам. Не
действуй по `open_rate` в одиночку.

### Coverage высокий у одних проектов, silent у других (один workspace)
Чаще всего: senders silent-проекта paused. Иногда: список конфига теста
неправильный (опечатка, ящик переименован, или его никогда не было в
Instantly accounts — видно по флагу `MISSING` в нашем activation-скрипте).
Сверь каждый sender листингом `/accounts` и пересечением с конфигом теста.

---

## API reference quick links

- `POST /api/v2/inbox-placement-tests` — создать тест
- `GET /api/v2/inbox-placement-tests/{id}` — детали теста (status,
  configured emails, recipients, recipients_labels)
- `GET /api/v2/inbox-placement-tests/{id}/email-service-provider-options` —
  доступные ESP labels для твоего тарифа
- `GET /api/v2/inbox-placement-analytics?test_id={id}` — постраничные записи
- `DELETE /api/v2/inbox-placement-tests/{id}` — отмена/удаление (убирай
  Content-Type header)
- `POST /api/v2/accounts/{email}/resume` — снять с паузы (body: `{}`)
- `POST /api/v2/accounts/{email}/mark-fixed` — сбросить error state (body: `{}`)
- `GET /api/v2/workspace-billing/subscription-details` — проверить активность
  IP plan
- `GET /api/v2/workspaces/current` — workspace plan IDs

Rate limit: 100 req/sec, 6000 req/min, возвращает 429 (не 402) при
превышении.
