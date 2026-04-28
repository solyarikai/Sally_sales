# Instantly Inbox Placement Tests — гайд по настройке

**Аудитория:** sales engineers Sally  
**Зачем:** настроить inbox placement tests (IPT) в Instantly так, чтобы  
результаты реально показывали deliverability ящиков. Не silent failures, не  
самоподтверждающие warmup-цифры.

---

## TL;DR

**Какой путь выбрать:**

| Хочу | Бери |
|---|---|
| Постоянный мониторинг с нуля, минимум возни, кастомный формат отчёта | [Способ 1 — Промпт 1](#промпт-1--настроить-cron-мониторинг-tuefri). Одна команда Claude → cron + скрипты + Slack развёрнуты автоматически. Бакеты Healthy/Problematic/Silent, фильтр foreign senders. **Если senders >10 — Промпт 1 разобьёт их на параллельные батчи** (иначе семпл будет шумовой). |
| Поправить уже существующий cron (добавить/убрать ящики, сменить webhook, обновить subject/body, сменить расписание) | [Способ 1 — Промпт 3](#промпт-3--обновить-существующий-cron-мониторинг). |
| Один разовый тест прямо сейчас | [Способ 1 — Промпт 2](#промпт-2--одноразовый-ручной-тест). Claude создаёт тест и показывает результат прямо в чат. |
| Без Claude Code / без доступа к Hetzner | [Способ 2 — UI](#способ-2-через-ui-appinstantlyai). Для разового теста — Шаги 1–6 (форма каждый раз заново). Для рекуррентного — [Шаг 7 (Automated test + Slack)](#шаг-7-альтернатива-automated-test--slack-вместо-cron-скриптов): форма заполняется **один раз**, Instantly дальше гоняет тест по расписанию сам. Trade-off против Промпта 1: формат отчёта стандартный (что Instantly выдаёт), своих бакетов и фильтров нет. UI не умеет в параллельные батчи — для проектов с >10 senders используй Промпт 1. |

**Что должно быть прежде чем запускать (любой путь):**

1. **Тариф Instantly Inbox Placement Growth** (`pid_ip_g`, ~$47/мес) на
   workspace. Без него API/UI на IPT отдают 402.
2. **Все sender-ящики активны** (`status=1`) **в момент создания теста**.
   Paused/errored Instantly молча исключает — в отчёте будет 0 записей и
   непонятно почему.
3. **Встроенный seed pool Instantly** (`recipients_labels` с тремя ESP:
   Google Pro, Google Personal, Outlook Pro). Не пиши свои recipients
   списком — теряешь per-provider breakdown.
4. **Реалистичный subject и body** из боевой кампании этого проекта в
   SmartLead. Spam-фильтры скорят содержимое — заглушка даст бесполезные
   цифры.
5. **Если senders > 10 — разбей на параллельные батчи.** Размер seed-пула
   Instantly фиксирован (~90 писем на тест), пул делится между всеми
   senders. На 17 senders каждый получит ~5 писем — статистический шум.
   См. [Размер пула и параллельные батчи](#размер-пула-и-параллельные-батчи).

---

## Размер пула и параллельные батчи

**Открытие, которое меняет всё (узнали 2026-04-28):** на Growth-тарифе пул
seed-инбоксов Instantly **фиксирован**. Эндпоинт
`/inbox-placement-tests/email-service-provider-options` отдаёт ровно 3 ESP
(Google Pro US, Google Personal US, Outlook Pro US) и за ними стоит ~30
seed-инбоксов на ESP — итого **~90 seeds на тест**.

Каждый seed получает **1 письмо**, и эти 90 писем **распределяются между
всеми senders в одном тесте**:

| Senders в тесте | Писем/sender | Статистика |
|---|---|---|
| 5  | ~18 | ✅ отлично |
| 9  | ~10 | ✅ норм |
| 17 | ~5  | ⚠️ слабо (один спам = 20% deliv) |
| 27 | ~3  | ❌ шум, цифрам нельзя верить |

### Когда нужны параллельные батчи

Если у проекта **больше 10 senders** — разбивай на 2 (или больше)
параллельных тестов в одно окно cron'а. Каждый тест получает **свой
независимый пул ~90 seeds**, поэтому per-sender семпл удваивается.

OnSocial monitor (`magnum-opus/infra/instantly-onsocial-monitor.js`) уже
работает в этом режиме — 17 ящиков bhaskar разбиты на:

- **Batch A** — `bhaskar.v@*` (9 senders) → ~10 писем/sender
- **Batch B** — `bhaskar@*` (8 senders) → ~11 писем/sender

Оба теста стартуют одновременно через `Promise.all`, polling независимый,
итоговый Slack-отчёт **один** с двумя секциями.

### Как разбивать senders

Два разумных варианта:

1. **По user-prefix** (как у OnSocial): batch A = `bhaskar.v@*`, batch B =
   `bhaskar@*`. **Diagnostic value:** один и тот же домен попадает в оба
   батча с разными local-parts. Если **оба ящика** домена просели → проблема
   доменная (DKIM/DMARC/репутация). Если только один → проблема user/ящика.

2. **По домену пополам:** batch A = первая половина доменов целиком, batch
   B = вторая. **Diagnostic value:** в каждом батче domain pair (bhaskar +
   bhaskar.v) отвечают за один домен → быстрее видишь репутационные issues
   на конкретном домене, но не сравнить два user-аккаунта на одном.

Для большинства проектов первый вариант информативнее.

### Идемпотентность и батчи

Каждый батч — отдельный Instantly-тест с уникальным name-prefix. Например:

- `Onsocial monitor batch A 2026-04-28`
- `Onsocial monitor batch B 2026-04-28`

`findActiveTest()` в monitor.js проверяет конфликты **per batch** — зависший
batch A не блокирует свежий batch B и наоборот.

### Известный баг — status=1 не закрывается

Тесты с `recipients_labels` у Instantly **не переходят в status=3**
(completed). Status остаётся на 1 (active) даже после того, как все письма
зарезолвлены. Так и должно быть в monitor.js — он ждёт TIMEOUT_MS (8h) и
после этого пулит analytics всё равно (partial-отчёт с пометкой).

По индустриальной норме (Validify, Warmy, Inboxy) тест должен резолвиться
за минуты-часы. К 1-2 часам данные плато и больше не растут. То есть
TIMEOUT 8h — **запас на всякий**, не реальное время сбора. Если хочешь
сэкономить — можно срезать до 3-4h, ничего не потеряешь.

### Когда апгрейдить план

Hypergrowth ($97/мо) даёт расширенный seed-пул (вероятно +Yahoo, +Apple,
+другие регионы EU/Asia → 150-200 seeds на тест). Имеет смысл если:

- Senders >25 даже после батчинга → батчей нужно слишком много
- Нужно тестить deliverability в EU/Asia/Yahoo (наш Growth — только US
  Google + Outlook)
- Проект критичный, цена цифр в отчёте превышает $50/мес

Для большинства Sally-проектов Growth + батчинг хватает.

---

## Способ 1 (рекомендуемый): через Claude Code

Самый быстрый путь — дать Claude промпт, он сам сходит в Instantly API,
проверит биллинг, активирует paused-ящики, создаст тест с правильными
параметрами и вернёт отчёт.

Три готовых промпта ниже:
- **Промпт 1** — настроить cron-мониторинг с нуля
- **Промпт 2** — разовый тест с результатом в чат
- **Промпт 3** — поправить уже существующий cron

### Что эти промпты делают

Общее для **Промпт 1 и Промпт 2** (создают новый тест):

- Проверяют, что Instantly Inbox Placement Growth активен (биллинг).
- Перебирают список твоих ящиков и активируют paused (`resume`), errored
  (`mark-fixed`). Отсутствующие в Instantly помечают и исключают из теста.
- Создают inbox placement test с правильными параметрами:
  `recipients_labels` со всеми 3 ESP (Google Pro/Personal + Outlook Pro),
  без custom recipients — это даёт встроенный seed pool и per-provider
  breakdown.
- Дожидаются завершения теста (status=3) через ScheduleWakeup.
- Парсят analytics, фильтруют по твоему списку senders (отбрасывают
  foreign), считают deliverability per sender, разбивают на бакеты:
  Healthy / Problematic (<80% по `is_spam`) / Categorized (≥1 запись с
  `has_category=true` — попало в Gmail Promotions/Social/Updates вкладки)
  / Silent (0 записей).

Различия:

- **Промпт 1** дополнительно создаёт один Node-скрипт по образцу
  OnSocial (`instantly-<project>-monitor.js` — unified create+wait+report
  в одном цикле), деплоит на Hetzner, ставит один cron Mon/Thu 22:00 UTC.
  Скрипт сам создаёт тест, ждёт завершения (poll каждые 15 мин, timeout
  8h), потом шлёт отчёт в Slack. К утру Tue/Fri отчёт уже в канале.
- **Промпт 2** показывает результат прямо в чат, без файлов и cron.
- **Промпт 3** не создаёт новый тест — читает текущие скрипты + cron,
  делает минимальный diff (новый ящик / webhook / subject / расписание /
  порог), деплоит правку на Hetzner, коммитит в git. Валидирует только
  если меняли senders или контент.

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
- Бакеты per sender:
  - Healthy: deliverability ≥ 80% (по `is_spam`)
  - Problematic: deliverability < 80%
  - Categorized: ≥1 запись с `has_category=true` (письмо попало в
    Gmail-вкладки Promotions/Social/Updates — отдельный warning, даже
    если по spam-rate ящик Healthy)
  - Silent: 0 records (paused/blocked/substituted при создании теста)
- Deliverability = (1 - spam_count / total_count) * 100.
- Фильтр analytics строго по configured `emails` из теста (Instantly
  иногда подмешивает foreign senders из других тестов).
- `has_category` бинарный — Instantly не различает какая именно вкладка
  (Promotions vs Social vs Updates). Если bucket Categorized непустой —
  скорее всего Promotions, нужно проверить контент письма.

Шаги:

1. Проверь биллинг. Если product_type=inbox_placement не активен — стоп.

2. Проверь статусы всех ящиков из <SENDERS>. Активируй paused (resume),
   errored (mark-fixed только если уверен что коннекция ок — иначе спроси).
   Отсутствующих в Instantly accounts исключи и скажи мне.

3. **Архитектура: один тест или параллельные батчи?**

   Размер seed-пула Instantly фиксирован (~90 seeds на тест, делится между
   всеми senders). Если в `<SENDERS>` **больше 10 ящиков** — раздели на 2
   параллельных батча (см. секцию [Размер пула и параллельные батчи]
   (#размер-пула-и-параллельные-батчи)). Каждый батч получает свой
   независимый пул ~90 seeds → per-sender семпл удваивается.

   Образец single-test и параллельных батчей — в OnSocial monitor:
   `magnum-opus/infra/instantly-onsocial-monitor.js`. Сейчас он работает
   в режиме батчей (Batch A bhaskar.v + Batch B bhaskar).

   Создай unified Node-скрипт по этому образцу. Скрипт делает (для каждого
   батча параллельно через `Promise.all`):
   - magnum-opus/infra/instantly-<project>-monitor.js должен:
     a) Создать тест с recipients_labels на 3 ESP (payload как описано
        выше). Если батчей несколько — отдельный тест на каждый батч,
        name-prefix включает batch key (`<Project> monitor batch A`).
     b) Polls статус каждые 15 мин до status=3 или timeout 8h.
        ⚠️ Тесты с recipients_labels часто **зависают в status=1** даже
        после полного резолва — это баг Instantly, не наш. Поэтому
        timeout обязателен.
     c) Когда тест завершился (или timeout) — вытащить analytics,
        отфильтровать по configured emails (для каждого батча — свой
        configuredSet), разбить на Healthy/Problematic/Silent
        (+ foreign), сформировать Slack-сообщение с per-recipient
        breakdown по problematic.
     d) Финальный Slack — **один объединённый** с шапкой-сводкой и
        секциями per batch (как в OnSocial). Не плодить отдельные
        сообщения на каждый батч.
     e) При timeout — partial-отчёт с пометкой (часть данных есть, статус
        не дошёл до 3).
     f) При любой ошибке создания/чтения — отдельное сообщение в Slack
        «monitor error» (best-effort, чтобы тихо не молчать).

   Идемпотентность: `findActiveTest()` проверяет конфликты per batch
   prefix — зависший batch A не блокирует свежий batch B.

4. Задеплой на Hetzner: scp в /home/leadokol/scripts/ (SSH alias
   `hetzner`). Проверь синтаксис: `node -c path/to/script.js`.

5. Добавь ОДНУ cron-запись в crontab leadokol:
   `0 22 * * 1,4 cd /home/leadokol/scripts && node instantly-<project>-monitor.js >> /home/leadokol/logs/instantly-<project>-monitor.log 2>&1`
   (Mon/Thu 22:00 UTC — тест крутится ночью, отчёт в Slack утром Tue/Fri.)

6. Запусти monitor один раз ВРУЧНУЮ для end-to-end валидации (займёт
   ~3-6 часов из-за wait-loop'а — лучше делать в выходной/в фон). Если
   надо быстрее — запусти только createTest()+первый getStatus() для
   sanity check, polling прервёшь Ctrl-C.

7. Закоммить локальные изменения в git submodule magnum-opus.

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
- Бакеты per sender:
  - Healthy: deliverability ≥ 80% (по `is_spam`)
  - Problematic: < 80%
  - Categorized: ≥1 запись с `has_category=true` — письмо попало в
    Gmail-вкладки (Promotions/Social/Updates), отдельный warning
  - Silent: 0 records
- Deliverability = (1 - spam_count / total_count) * 100.
- Фильтр analytics строго по configured emails (Instantly подмешивает
  foreign senders из других тестов — отбрось их).
- `has_category` бинарный — без указания вкладки. Если непустой —
  скорее всего Promotions.
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
   - Сводку: total / Healthy (≥80%) / Problematic (<80%) / Categorized
     (has_category=true) / Silent (0 records)
   - Per-sender таблицу с deliverability % + кол-вом categorized записей
   - Per-recipient breakdown по problematic (sender → recipient → esp /
     type / verdict)

6. Спроси — удалять тест или оставить.
```

### Промпт 3 — обновить существующий cron-мониторинг

Используй когда у проекта уже настроен мониторинг на Hetzner и нужно
поправить: добавить/убрать ящики, сменить Slack-канал, обновить
subject/body под новую кампанию, изменить расписание, поменять порог
deliverability.

```text
Обнови существующий Instantly IPT cron-мониторинг для проекта <PROJECT>.
Изменение: <ОПИСАНИЕ ИЗМЕНЕНИЯ>.

Возможные изменения (примеры):
- "Добавить sender newuser@domain.com в список ящиков"
- "Убрать sender olduser@domain.com из списка"
- "Сменить Slack webhook на <URL>"
- "Обновить subject/body под текущую кампанию SmartLead <campaign_id>"
- "Сменить расписание с Mon/Thu 22:00 UTC на Mon/Wed/Fri 22:00 UTC"
- "Сменить порог deliverability с 80% на 75%"
- "Сменить ESP labels (например добавить Yahoo если появился в плане)"

Контекст:
- Source of truth (NEW unified стиль): magnum-opus/infra/instantly-<project>-monitor.js
  (GitLab sally-saas/magnum-opus). Один скрипт create+wait+report.
- Source of truth (LEGACY двухскриптовый стиль, может ещё остаться у
  старых проектов): magnum-opus/infra/instantly-<project>-start-test.js
  + instantly-spam-report-<project>.js. Сначала проверь какой стиль —
  смотри что лежит в /home/leadokol/scripts/ и какие cron-записи есть.
- Деплой на Hetzner (SSH alias `hetzner`): /home/leadokol/scripts/.
- Cron: пользовательский crontab leadokol на Hetzner, ищи строки
  `instantly-<project>`.
- API endpoints, status коды, body форматы — как в Промпт 1.

Шаги:

1. Покажи мне:
   - Текущие скрипт(ы) из /home/leadokol/scripts/ на Hetzner.
     Определи стиль (unified monitor.js или legacy start-test+spam-report).
   - Текущие cron-записи: `crontab -l | grep <project>`.
   - git log -3 этих файлов в magnum-opus (когда последний раз менялись
     и кем).

2. Если изменение касается senders — проверь статусы новых ящиков через
   GET /accounts. Активируй paused (resume), errored (mark-fixed только
   если коннекция реально ок). Отсутствующих в Instantly скажи.

3. Внеси минимальное изменение в magnum-opus/infra/<file>.js локально.
   Покажи мне diff (только то что меняешь — без лишних правок).

4. Деплой обновлённый файл(ы) на Hetzner в /home/leadokol/scripts/.

5. Валидация только если меняли senders, subject/body или
   recipients_labels:
   - Для unified monitor.js: запусти тест через прямой POST
     /inbox-placement-tests (теми же полями что в скрипте), получи test
     id, покажи мне. Не запускай весь monitor через node — он будет
     ждать 3-6 часов в polling-loop.
   - Для legacy start-test.js: запусти просто `node start-test.js`,
     покажи test id.
   Для смены webhook, расписания, порога — этот шаг пропускай, новое
   значение применится в следующий cron-tick.

6. Если меняли расписание — отредактируй crontab leadokol на Hetzner,
   покажи мне `crontab -l | grep <project>` после.

7. Закоммить изменение в magnum-opus (push на GitLab) и bump submodule
   pointer в sales_engineer (push на GitHub).

Не трогай чужие проекты. Не делай "пока я тут — давай ещё что-нибудь
обновлю". Если в изменении сомнение — спроси меня, не угадывай.
```

---

## Способ 2: через UI (app.instantly.ai)

Если хочется руками или без Claude.

> **Caveat:** точные названия полей и кнопок UI ниже — best-effort. Мы
> работали в основном через API, UI-лейблы могут немного отличаться от
> описанных. Ищи аналог по смыслу. Если у тебя UI-screen отличается —
> поправь этот раздел.

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
- **Test type** — два варианта:
  - **One-time test** — разовый тест прямо сейчас (для разовой проверки).
  - **Automated test** — рекуррентный по расписанию (для постоянного
    мониторинга, заменяет наш cron-сетап). См. [Шаг 7](#шаг-7-альтернатива-automated-test--slack-вместо-cron-скриптов) ниже.
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
  3. Все recipient'ы (22 на pid_ip_g тарифе) отвергли на SMTP →
     серьёзный deliverability failure, домен в крупном blacklist.

### Шаг 7 (альтернатива): Automated test + Slack вместо cron-скриптов

Если нужен **постоянный мониторинг** — Instantly умеет всё сам через UI,
без нашего cron-сетапа на Hetzner. На шаге 3 при создании теста выбери
**Automated test** вместо One-time, тогда появятся дополнительные поля:

- **Schedule** — дни недели (отметь Tue + Fri) + время запуска + timezone
  (под API это `schedule.days[0..6]`, `schedule.timing`, `schedule.timezone`).
- **Automations / Actions on completion** — условие + действие. По API
  (`automations`) известно: action может быть webhook, pause campaign,
  add/remove tag. В UI ищи аналог по смыслу. Полезные пресеты:
  - When `placement < threshold` → **Webhook URL**, в URL подставь Slack
    incoming webhook канала проекта. Slack принимает `{"text": "..."}`
    payload — Instantly должен его сформировать (если шлёт другой формат,
    нужен middleware). Если в UI есть готовый «Send to Slack» preset —
    используй его, он чище.
  - When `mailbox went to spam` → **Pause campaign** или **Add tag**.

Сохраняешь — Instantly сам гоняет тест по расписанию и шлёт уведомление
по сконфигурированному automation. **Это альтернатива Промпту 1** (cron +
скрипты на Hetzner). Trade-offs описаны в TL;DR-табличке в начале гайда.

---

## Как читать результат

Главные сигналы:


| Метрика                   | Что означает                                                              |
| ------------------------- | ------------------------------------------------------------------------- |
| **Deliverability ≥ 80%**  | Healthy. Mailbox в inbox у большинства провайдеров.                       |
| **Deliverability 50-80%** | Borderline. Один провайдер режет, остальные принимают. Чаще всего Google. |
| **Deliverability < 50%**  | Problematic. Ящик в спаме у >половины recipient'ов.                       |
| **`has_category: true`**  | Categorized. Письмо в Gmail-вкладке (Promotions/Social/Updates), не Primary. Не spam, но почти как — почти никто не открывает. Чинится переработкой контента (картинки, ссылки, unsubscribe-блок, продвиженческие фразы). |
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

### Эволюция мониторинга

**Текущая версия (с 2026-04-28):** 2 параллельных батча на 17 bhaskar-ящиков.

- **Batch A** — 9 ящиков `bhaskar.v@*` → ~10 писем/sender
- **Batch B** — 8 ящиков `bhaskar@*` → ~11 писем/sender
- Каждый домен (`onsocial-analytics`, `onsocial-data`, ..., `onsocialmetrics`)
  попадает в оба батча с разными local-parts → cross-batch comparison
  быстро отделяет user-issues от domain-issues.
- 10 `petr@crona-*` ящиков **выкинуты из мониторинга**: Instantly постоянно
  подменяет их на `eleonora@*` (sender-side redirect, не лечится).
- recipients_labels (3 ESP: Google Pro/Personal + Outlook Pro)
- Subject + body из боевой OnSocial-кампании (SmartLead campaign 3169118
  c-OnSocial_IMAGENCY_FOUNDERS, step 1, шаблонные переменные подменены
  на realistic placeholders: Jordan/Atlas Creative/Dentsu)
- Cron 22:00 UTC Mon/Thu — оба батча стартуют одновременно через
  `Promise.all`, итоговый Slack-отчёт один с двумя секциями.

### Что узнали по дороге (журнал)

**2026-04-08:** Запустили single-test на 27 senders (17 bhaskar + 10 petr).
Получили 93 записи всего → ~3 письма/sender → шум. Показалось, что план
Growth даёт мало семпла на каждый ящик.

**2026-04-28:** Дёрнули `/inbox-placement-tests/email-service-provider-options`
— узнали что **пул фиксированный** (~90 seeds на тест, делится между всеми
senders). Сравнили с другими Sally-проектами: их тесты «завершались» (status=3)
просто потому что отправляли 0-2 письма (silent senders), наш с 93
записями реально работал. Решили — split на 2 параллельных батча.

**2026-04-28 (тот же день):** Раскрыли баг Instantly — тесты с
`recipients_labels` не переходят в status=3 даже после полного резолва.
Monitor.js ждёт TIMEOUT_MS (8h) и берёт partial-analytics — это
по дизайну, а не bug в нашем коде.

### Скрипт и файлы

- Source of truth: `magnum-opus/infra/instantly-onsocial-monitor.js`
  (unified create+wait+report для обоих батчей)
- Деплой: `hetzner:/home/leadokol/scripts/instantly-onsocial-monitor.js`
- Логи cron: `/home/leadokol/logs/instantly-onsocial-monitor.log`
- Per-run JSON dumps: `/home/leadokol/logs/runs/onsocial-<timestamp>.json`

Старая legacy-версия двумя скриптами (`instantly-onsocial-start-test.js`
+ `instantly-spam-report-onsocial.js`) больше из cron не запускается —
файлы остались в репо и на Hetzner для истории, но cron указывает на
unified monitor. Если у других проектов ещё legacy-стиль — Промпт 3
поддерживает оба.

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

### Bucket Categorized — что делать

`has_category=true` значит письмо попало в Gmail-вкладку
(Promotions/Social/Updates), не в Primary. **Не spam, но почти как** —
recipients редко проверяют эти вкладки, open-rate сравнимо плохой.

Что переключает Gmail в категоризацию (по убыванию вероятности):
1. Картинки / inline-картинки в HTML — основной триггер Promotions
2. Несколько ссылок (особенно tracking-параметры в URL)
3. Большой HTML-блок vs plain-text-подобный контент
4. Слова из «маркетинг-словаря»: discount, offer, exclusive, limited, %
5. Unsubscribe-блок с явной CTA (в IPT не должно быть, в проде — да)

Чинится **переписыванием контента**: убрать картинки, сократить ссылки до
1-2, plain-text-стиль. Тестировать снова. Это про контент, не про домен.

Instantly через API не показывает в какую конкретно вкладку
(Promotions/Social/Updates). Если хочешь это видеть — внешние сервисы
(GlockApps premium) разделяют.

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