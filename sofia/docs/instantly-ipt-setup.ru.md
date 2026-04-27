# Instantly Inbox Placement Tests — гайд по настройке

**Аудитория:** sales engineers Sally  
**Зачем:** настроить inbox placement tests (IPT) в Instantly так, чтобы  
результаты реально показывали deliverability ящиков. Не silent failures, не  
самоподтверждающие warmup-цифры.

---

## TL;DR — что нужно, чтобы тест работал

1. **Тариф Instantly Inbox Placement Growth** (`pid_ip_g`, ~$47/мес) на
  workspace. Без него API возвращает 402 на всё что связано с IPT.
2. **Все sender-ящики активны** (`status=1`) **в момент создания теста**.
  Paused/errored Instantly молча исключает — у них в отчёте будет 0
   записей и непонятно почему.
3. **Используй встроенный seed pool Instantly** (`recipients_labels` с тремя
  ESP: Google Pro, Google Personal, Outlook Pro). Не пиши свои recipients
   списком — теряешь per-provider breakdown.
4. **Реалистичный subject и body** из боевой кампании этого проекта в
  SmartLead. Spam-фильтры скорят содержимое — заглушка даст бесполезные  
   цифры.

---

## Способ 1 (рекомендуемый): через Claude Code

Самый быстрый путь — дать Claude промпт, он сам сходит в Instantly API,
проверит биллинг, активирует paused-ящики, создаст тест с правильными
параметрами и вернёт отчёт.

Два готовых промпта ниже — для постоянного мониторинга через cron и для
разовой проверки.

### Что эти промпты делают

- Проверяют, что Instantly Inbox Placement Growth активен (биллинг).
- Перебирают список твоих ящиков и активируют paused (`resume`), errored
  (`mark-fixed`). Отсутствующие в Instantly помечают и исключают из теста.
- Создают inbox placement test с правильными параметрами:
  `recipients_labels` со всеми 3 ESP (Google Pro/Personal + Outlook Pro),
  без custom recipients — это даёт встроенный seed pool и per-provider
  breakdown.
- Дожидаются завершения теста (status=3) через ScheduleWakeup.
- Парсят analytics, фильтруют по твоему списку senders (отбрасывают
  foreign), считают deliverability per sender, разбивают на бакеты
  Healthy/Problematic/Silent.
- **Промпт 1** дополнительно создаёт два Node-скрипта по образцу
  OnSocial, деплоит на Hetzner, ставит cron Tue/Fri, отправляет отчёты в
  Slack.
- **Промпт 2** показывает результат прямо в чат, без файлов и cron.

### Что эти промпты НЕ делают

- Не добавляют новые ящики в Instantly если их там нет — это руками через
  UI accounts page.
- Не оплачивают тариф — биллинг руками через UI Billing page.
- Не чинят Google domain reputation — IPT покажет ГДЕ проблема, а чинится
  она отдельно через Google Postmaster Tools, прогрев и контент.

### Промпт 1 — настроить cron-мониторинг (Tue/Fri)

Заполни плейсхолдеры в `<...>`

- `<PROJECT>` — кодовое имя (`Onsocial`, `Palark`, `TFP` и т.д.)
- `<SENDERS>` — sender-ящики через запятую
- `<SLACK_WEBHOOK>` — Slack webhook URL для канала проекта
- `<SUBJECT>` — реальный subject из активной кампании в SmartLead
- `<BODY_HTML>` — HTML body из той же кампании (одной строкой)

```text
Настрой автоматический Instantly IPT-мониторинг для проекта <PROJECT>.

Параметры:
- Project name: <PROJECT>
- Sender mailboxes: <SENDERS>
- Slack webhook: <SLACK_WEBHOOK>
- Email subject: <SUBJECT>
- Email body (HTML): <BODY_HTML>

Контекст (всё что нужно знать):

- API base: https://api.instantly.ai/api/v2
- Auth: `Authorization: Bearer $INSTANTLY_API_KEY` (env на Hetzner в
  ~/magnum-opus-project/repo/.env). Если 401 — попробуй другой ключ из
  существующих скриптов в magnum-opus/infra/instantly-spam-report.js.
- Account status коды: 1=active, 2=paused, -1/-2/-3=errored.
- POST /accounts/{email}/resume — body {} (обязательно непустой JSON).
- POST /accounts/{email}/mark-fixed — body {}.
- POST /inbox-placement-tests — body с полями name, type=1,
  delivery_mode=1, sending_method=1, email_subject, email_body, emails,
  recipients_labels (массив из 3 объектов: Google Professional, Google
  Personal, Outlook Professional, regions North America US). Recipients
  НЕ передавай — Instantly авто-сгенерит из labels.
- GET /inbox-placement-tests/{id} — поле status: 1=active, 2=paused,
  3=completed.
- GET /inbox-placement-analytics?test_id=X&limit=100 — paginated через
  next_starting_after. Записи: sender_email, recipient_email, is_spam,
  recipient_esp (1=Google, 2=Outlook), recipient_type (1=Pro, 2=Personal).
- DELETE /inbox-placement-tests/{id} — без Content-Type header (иначе
  400 FST_ERR_CTP_EMPTY_JSON_BODY).
- /workspace-billing/subscription-details — проверка биллинга, ищи
  product_type=inbox_placement и all_subs_cancelled=false.

Логика отчёта:
- Бакеты per sender: Healthy (deliverability ≥ 80%) / Problematic (< 80%)
  / Silent (0 records).
- Deliverability = (1 - spam_count / total_count) * 100.
- Фильтр analytics строго по configured `emails` из теста (Instantly
  иногда подмешивает foreign senders из других тестов).

Шаги:

1. Проверь биллинг. Если product_type=inbox_placement не активен — стоп.

2. Проверь статусы всех ящиков из <SENDERS>. Активируй paused (resume),
   errored (mark-fixed только если уверен что коннекция ок — иначе спроси).
   Отсутствующих в Instantly accounts исключи и скажи мне.

3. Создай два Node-скрипта по образцу OnSocial:
   - magnum-opus/infra/instantly-<project>-start-test.js (creator с
     recipients_labels на 3 ESP, payload как описано выше)
   - magnum-opus/infra/instantly-spam-report-<project>.js (читает
     latest completed test name="<PROJECT>*", аналитику фильтрует по
     configured emails, формирует Slack-сообщение с тремя бакетами
     Healthy/Problematic/Silent + per-recipient breakdown по problematic)

4. Задеплой оба на Hetzner: scp в /home/leadokol/scripts/ (SSH alias
   `hetzner`).

5. Добавь две cron-записи в crontab leadokol:
   - 03:00 Tue/Fri → start-test
   - 06:00 Tue/Fri → spam-report

6. Запусти start-test один раз для валидации, покажи мне test id.

7. ScheduleWakeup на ~2 часа, после wakeup → проверь status. Когда
   status=3 → запусти spam-report.js один раз, покажи финальный отчёт.

8. Закоммить локальные изменения в git submodule magnum-opus.

Если что-то требует деструктивного действия не из этого списка — стоп
и спроси меня.
```

#### Где взять `<SLACK_WEBHOOK>`

- **Существующий проект Sally** — все webhook-и для уже настроенных проектов
  лежат в одном файле: [magnum-opus/infra/instantly-spam-report.js](../../magnum-opus/infra/instantly-spam-report.js)
  → const `WEBHOOKS` (squarefi, easyglobal, palark, easystaff, tfp,
  onsocial, rizzult, inxy, mifort, internal, paybis, gwc). Скопируй URL
  оттуда.
- **Новый проект** — создай incoming webhook в Slack:
  1. В целевом канале: меню канала → **Integrations** → **Add an App**
  2. Найди **Incoming Webhooks** → **Add to Slack**
  3. Выбери канал → **Add Incoming WebHooks integration**
  4. Скопируй **Webhook URL** (`https://hooks.slack.com/services/T.../B.../...`)
  5. Добавь его в `WEBHOOKS` в `instantly-spam-report.js` под ключом
     проекта (для будущей переиспользуемости)

  Если нет прав на интеграции в workspace — попроси админа Slack у Sally.

### Промпт 2 — одноразовый ручной тест

Без cron, без Slack — результат прямо в чат.

```text
Запусти ОДИН разовый Instantly inbox placement test для <PROJECT> и покажи
результат. Никакого cron, никаких файлов, никакого Slack — результат прямо
в чат.

Параметры:
- Project name: <PROJECT>
- Sender mailboxes: <SENDERS>
- Email subject: <SUBJECT>
- Email body (HTML): <BODY_HTML>

Контекст (всё что нужно знать):

- API base: https://api.instantly.ai/api/v2
- Auth: `Authorization: Bearer $INSTANTLY_API_KEY` (env на Hetzner в
  ~/magnum-opus-project/repo/.env). Если 401 на конкретном endpoint —
  попробуй другие ключи из magnum-opus/infra/instantly-spam-report.js.
- Account status коды: 1=active, 2=paused, -1/-2/-3=errored.
- POST /accounts/{email}/resume — body {}.
- POST /accounts/{email}/mark-fixed — body {}.
- POST /inbox-placement-tests — body: name, type=1, delivery_mode=1,
  sending_method=1, email_subject, email_body, emails (массив активных
  senders), recipients_labels — массив из 3 объектов:
    {region:"North America", sub_region:"US", type:"Professional", esp:"Google"}
    {region:"North America", sub_region:"US", type:"Personal",     esp:"Google"}
    {region:"North America", sub_region:"US", type:"Professional", esp:"Outlook"}
  Custom recipients НЕ передавай — Instantly авто-сгенерит из labels.
- GET /inbox-placement-tests/{id} — status: 1=active, 3=completed.
- GET /inbox-placement-analytics?test_id=X&limit=100 — paginated через
  next_starting_after. Поля записи: sender_email, recipient_email, is_spam,
  recipient_esp (1=Google, 2=Outlook), recipient_type (1=Pro, 2=Personal).
- /workspace-billing/subscription-details — проверка биллинга, ищи
  product_type=inbox_placement, all_subs_cancelled=false.
- DELETE /inbox-placement-tests/{id} — без Content-Type header.

Логика отчёта:
- Бакеты per sender: Healthy (deliverability ≥ 80%) / Problematic (< 80%)
  / Silent (0 records).
- Deliverability = (1 - spam_count / total_count) * 100.
- Фильтр analytics строго по configured emails (Instantly подмешивает
  foreign senders из других тестов — отбрось их).
- Records появляются батчами через ~25 мин (IMAP poll cycle Instantly).

Шаги:

1. Проверь биллинг. Если IPT не активен — стоп, скажи мне.

2. Проверь статусы всех <SENDERS>. Активируй paused (resume), errored
   (mark-fixed только если коннекция реально ок — иначе спроси).
   Отсутствующих в Instantly исключи и скажи мне.

3. Создай один тест с recipients_labels на 3 ESP. Покажи test id и
   сколько actual recipient inboxes Instantly авто-сгенерил.

4. ScheduleWakeup на ~30 мин. На пробуждении: если status=3 → шаг 5. Если
   status=1 и records растут → ещё wakeup на 30 мин. Если status=1 и
   records=0 через час — диагностируй (вероятнее всего senders были
   paused в момент создания, либо Instantly подменяет ящик на другого
   sender'а того же домена).

5. Когда status=3: вытащи analytics постранично, отфильтруй по configured
   emails (foreign senders отметь отдельно), покажи мне:
   - Сводку: total / Healthy (≥80%) / Problematic (<80%) / Silent (0 records)
   - Per-sender таблицу с deliverability %
   - Per-recipient breakdown по problematic (sender → recipient → esp /
     type / verdict)

6. Спроси — удалять тест или оставить.
```

---

## Способ 2: через UI (app.instantly.ai)

Если хочется руками или без Claude.

### Шаг 1: Billing

Меню пользователя справа вверху → **Billing** (или **Settings → Billing**).
Должна быть отдельная секция **Inbox Placement** с активной подпиской. Если
видишь только Outreach plan — IPT не работает, надо оплатить.

### Шаг 2: активировать ящики

Сайдбар → **Email Accounts**. Отфильтруй ящики проекта. У каждой строки
смотри бейдж справа:

- Нет бейджа → ящик активен (`status=1`), готов к тесту.
- **Paused** → меню `…` → **Resume**.
- Красный/error бейдж → меню `…` → **Mark as fixed** (только если SMTP/
IMAP реально починен; иначе ящик через несколько минут вернётся в error).

После этого все ящики проекта должны быть без бейджей. Если какого-то
ящика нет в списке вообще — его надо добавить через **+ Add Account** или
исключить из теста.

### Шаг 3: создать тест

Сайдбар → **Inbox Placement** → **Create Test** (вверху справа).

В форме:

- **Test name** — `<ProjectName> manual YYYY-MM-DD` или похоже.
- **Test type** — **One-time test**.
- **Delivery mode** — **One by one**.
- **Sending method** — **Send from Instantly**.
- **Email subject** — точный subject из боевой кампании.
- **Email body** — точный HTML body. Используй HTML source view чтобы
избежать авто-форматирования.
- **Senders** — multi-select ящиков. Все без Paused/error бейджей.
- **Recipients** — это место где обычно ошибаются. Ищи toggle/tab «Use
Instantly seed pool» или «Recipient labels». Выбери все 3 опции:
  - Google · Professional · US
  - Google · Personal · US
  - Outlook · Professional · US
  **Не добавляй** свои custom recipients сверху — потеряешь per-provider
  breakdown.

Жми **Create**. Бейдж статуса показывает **Active**.

### Шаг 4: подождать

Первые записи появляются через ~25 мин (Instantly опрашивает recipient
ящики через IMAP батчами). Полный тест на 20-30 senders с 3 ESP занимает
1-3 часа. Можно закрыть вкладку и вернуться позже.

### Шаг 5: посмотреть результаты

Когда бейдж **Completed** — на странице теста несколько панелей:

- **Overall placement** — общий % inbox vs spam. Sanity check.
- **Per-sender table** — строка на ящик с колонками: emails sent, inbox,
spam, deliverability. Сортируй по возрастанию deliverability — увидишь
худших. Всё <80% это action list.
- **Per-recipient/provider breakdown** — обычно график с колонками Google
Pro / Google Personal / Outlook Pro. Кликаешь problematic ящик — видишь
per-recipient детали.
- **Authentication results** — % проходимости SPF/DKIM/DMARC. Меньше 100% =
DNS misconfiguration где-то.

### Шаг 6: интерпретация

Для каждого problematic sender'а:

- **Spam в Google + inbox в Outlook** → Google domain reputation. Чинится
через Google Postmaster Tools, прогрев, контент. Дни-недели.
- **Spam везде** → SPF/DKIM/DMARC сломан. Проверь auth-панель.
- **Silent** (0 записей) → один из:
  1. Был paused/errored в момент создания теста → resume + пересоздать.
  2. Instantly подменил на другой sender того же домена (видно в per-sender
    table — будет неожиданное имя) → проверь какие ещё ящики на этом
     домене активны.
  3. Все 22 recipient'а отвергли на SMTP → серьёзный deliverability
    failure, домен в крупном blacklist.

---

## Как читать результат

Главные сигналы:


| Метрика                   | Что означает                                                              |
| ------------------------- | ------------------------------------------------------------------------- |
| **Deliverability ≥ 80%**  | Healthy. Mailbox в inbox у большинства провайдеров.                       |
| **Deliverability 50-80%** | Borderline. Один провайдер режет, остальные принимают. Чаще всего Google. |
| **Deliverability < 50%**  | Problematic. Ящик в спаме у >половины recipient'ов.                       |
| **0 records (silent)**    | Не отправил вообще. Либо paused, либо подменён, либо blacklist.           |


Главное правило интерпретации: **смотри per-recipient breakdown**, не общий %.
60% deliverability на одного ящика и 60% на другого могут означать совершенно
разное. Если у первого Google всё в спам, Outlook всё в inbox — проблема
конкретно с Google reputation. Если у второго в каждом провайдере половина
там, половина тут — проблема с контентом или агрессивностью отправки.

**Что НЕ использовать как сигнал deliverability:**

- SmartLead `warmup_reputation` — закрытый цикл, показывает 100% даже когда
Gmail режет ящик 100% времени.
- `open_rate` соло — Apple MPP и corporate firewalls вырезают tracking
pixels. 0% open при ненулевых replies = трекинг сломан, не спам.

---

## OnSocial — конкретный пример

Тест 2026-04-27:

- 27 senders (14 `bhaskar@onsocial-*.com`, 3 без дефиса, 10 `petr@crona-`*)
- recipients_labels (3 ESP) → 22 авто-сгенерированных recipient inbox
- Subject + body из боевой OnSocial-кампании
- Cron 03:00/06:00 UTC Tue/Fri

Результат:

- 24 из 26 senders → 100% inbox
- `eleonora@crona-b2b.com` → 60% (Google → spam, Outlook → inbox)
- `eleonora@cronaaipipeline.com` → 33% (Google → spam, Outlook → inbox)
- 1 ящик (`petr@prospects-crona.com`) — нет в Instantly accounts вообще

Без per-provider breakdown увидели бы просто 60% и 33% и не знали ГДЕ
чинить. С breakdown'ом — Google reputation на двух доменах.

Скрипты-образец: `magnum-opus/infra/instantly-onsocial-start-test.js` +
`instantly-spam-report-onsocial.js`. Деплой на `hetzner:/home/leadokol/scripts/`.

---

## Troubleshooting

### Тест уже час крутится, 0 записей

Чаще всего: senders были paused в момент создания. Они исключаются молча.
Проверь текущий статус всех ящиков — если paused, удали тест и пересоздай
после активации. Если все active — это нормально, IMAP-poll Instantly
работает батчами раз в ~25 мин, первая партия может прийти через 30+ минут.

### Биллинг 402 на всём

Подписка Instantly Inbox Placement отвалилась. Идти в UI Billing, оплатить.
Это не rate limit (тот возвращает 429), а реально неактивный тариф.

### В отчёте ящики которых нет в моём списке

Instantly иногда (а) лекает записи между тестами одного workspace, (б)
подменяет один ящик на другой того же домена (видели petr@→eleonora@). При
любом анализе фильтруй analytics по configured emails из конфига теста и
отбрасывай чужих. Если делаешь руками в UI — просто игнорируй неожиданные
имена.

### Один ящик 0% Google, 100% Outlook

Domain reputation у Google. Не SPF/DKIM/DMARC (их видно в auth-панели,
будут pass), не контент (тогда падал бы и в Outlook). Ящик попал в Google
spam classifier. Лечится через Google Postmaster Tools (проверка
домена/IP), прогрев и работу с контентом. Может занять дни-недели.

### Все ящики 0% — везде в спам

Проверь SPF/DKIM/DMARC в auth-панели. Если не pass — DNS misconfig у
sender-домена. Если pass — контент письма триггерит spam-фильтры (слова,
ссылки, html-структура).

### `warmup_reputation` 100%, но в IPT всё в спам

Так и есть. `warmup_reputation` мерит трафик внутри Superwarm (юзеры
SmartLead → друг другу), где у всех настроены фильтры пропускать. Это
закрытый цикл. Реальный сигнал — IPT и реальный bounce_rate в кампаниях.

---

## API reference (для разработчиков)

Если кто-то пишет свои скрипты вместо Claude-промптов — основные endpoints:

- `POST /api/v2/inbox-placement-tests` — создать тест
- `GET /api/v2/inbox-placement-tests/{id}` — детали теста
- `GET /api/v2/inbox-placement-analytics?test_id={id}` — записи (paginated)
- `DELETE /api/v2/inbox-placement-tests/{id}` — удалить (без Content-Type)
- `POST /api/v2/accounts/{email}/resume` — снять с паузы (body `{}`)
- `POST /api/v2/accounts/{email}/mark-fixed` — сбросить error (body `{}`)
- `GET /api/v2/workspace-billing/subscription-details` — проверить тариф
- `GET /api/v2/inbox-placement-tests/{id}/email-service-provider-options` —
список доступных ESP labels

Rate limit: 100 req/sec, 6000 req/min, при превышении 429 (не 402).