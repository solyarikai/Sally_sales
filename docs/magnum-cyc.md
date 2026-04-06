# Campaign & Sending Worker: полная проверка и стабилизация

**Epic:** `magnum-cyc` | **Приоритет:** P1 | **Статус:** Closed

## Проблема

Sending worker и связанные подсистемы имели ряд критических багов, мешающих запуску кампаний в продакшене:

1. **Alive check ложно помечал живые аккаунты как dead** — `is_user_authorized()` перехватывал ВСЕ `RPCError` (включая `FloodWait`, `ServerError`) и возвращал `False`, что приводило к массовой пометке живых аккаунтов как мёртвых.
2. **Frozen аккаунты не детектились** — SpamBot проверяет только спам-ограничения, но замороженные аккаунты проходят его проверку (говорит "no limits"), хотя не могут отправлять сообщения.
3. **Sending worker не имитировал реального пользователя** — отсутствовали typing indicator, выбор дней недели, человекоподобные паузы.
4. **Inbox: сообщения грузились нестабильно** — каждые 6 секунд poll делал connect → fetch → disconnect, теряя entity cache и вызывая нестабильное разрешение peer.

## Решение

### 1. Alive Check (magnum-cyc.1)

**Коммиты:** `e40054ad`, `ed9ae61e`, `2ce73129`

- Заменили `is_user_authorized()` на `get_me()` с классификацией ошибок — только `AuthKeyUnregistered` / `UserDeactivated` / `UserDeactivatedBan` помечают аккаунт как DEAD.
- Добавлен retry (2 попытки) для `get_me()` при транзиентных ошибках, чтобы сетевые сбои не меняли статус.
- Вторичная детекция frozen: после SpamBot проверки выполняются `UpdateStatusRequest` + `UpdateProfileRequest` — frozen аккаунты не могут выполнить write-операции.
- Дополнительный probe через `contacts.SearchRequest` — frozen аккаунты не могут искать контакты, что ловит `FrozenMethodInvalidError`.

### 2. Sending Worker (magnum-cyc.2)

**Коммит:** `44f91952`, `76494635`

**Тайминги и лимиты:**
- Max 2 cold сообщения в час на аккаунт (`MAX_COLD_PER_HOUR_PER_ACCOUNT = 2`)
- Равномерное распределение по окну Send From → Send To через `_calc_spread_allowance()` с детерминированным jitter (±15 мин, seed = campaign_id + day)
- Дневной лимит `daily_message_limit` на кампанию
- Catch-up cap: максимум 2 сообщения за тик (не burst при позднем старте/рестарте)

**Follow-up приоритет:**
- Follow-up сообщения всегда отправляются первыми (`followup_recipients` собираются до `new_recipients`)
- Follow-up НЕ считаются в cold лимит — лимитируются только первые сообщения новым лидам

**Spamblock:**
- Порог `SPAMBLOCK_THRESHOLD = 5` ошибок → аккаунт пропускается на день
- При достижении порога — каскадное переназначение всех pending получателей на другие аккаунты
- Emergency stop: при N consecutive global spamblocks все активные кампании ставятся на паузу

**Имитация реального пользователя:**
- Typing indicator (`SetTypingRequest`) перед отправкой, длительность пропорциональна длине сообщения (2-8 сек)
- `SendMessageRecordAudioAction` / `SendMessageUploadDocumentAction` для голосовых/файлов
- Человекоподобные задержки через mixture distribution:
  - 65% — gaussian вокруг середины диапазона
  - 23% — "thinking/reading" пауза (1.2x-2.5x base_max)
  - 12% — "distracted/coffee" пауза (2.5x-5x base_max, до 120 сек)
- Модуляция по времени суток: ~1.4x медленнее на краях окна отправки
- Fatigue: +2% за сообщение после 5-го (до +50%)
- Молодые сессии (< 7 дней): x1.8 замедление

**Расписание:**
- Новое поле `send_days` (JSONB) на `TgCampaign` — массив дней недели `[0=Mon..6=Sun]`
- Проверка дня недели в `is_within_send_window()` — пропуск отключённых дней
- UI: pill-кнопки Пн-Вс в настройках кампании + dropdown для выбора часов

### 3. Inbox: стабильная загрузка сообщений (magnum-cyc.3)

**Коммит:** `d39b224e`

**Backend:**
- Telethon-клиент теперь сохраняет соединение между poll-запросами (вместо connect → fetch → disconnect каждые 6 секунд)
- `is_connected()` проверка перед каждым запросом — переподключение только при необходимости
- Retry с паузой при транзиентных ошибках (`ConnectionError`, `OSError`, `TimeoutError`)
- Корректная обработка `FloodWait` — сохранение `peer_username` при retry

**Frontend:**
- Error banner показывается только после 3 подряд неудачных poll-запросов (дебаунс транзиентных сбоев)
- Счётчик ошибок `msgErrorCount` сбрасывается при успешной загрузке
- Кнопка "Retry" для ручного повторного запроса

### 4. E2E тест (magnum-cyc.4)

Полный end-to-end прогон: создание кампании → назначение аккаунтов с Infatica прокси → добавление лидов → запуск → проверка отправки по расписанию и лимитам → follow-up → получение ответов в Inbox.

## Изменённые файлы

- `backend/app/services/sending_worker.py` — тайминги, spread allowance, human delay, follow-up приоритет, spamblock обработка
- `backend/app/services/telegram_engine.py` — alive check (get_me вместо is_user_authorized), frozen detection (contacts.Search, UpdateStatus), typing indicator
- `backend/app/api/telegram_outreach.py` — bulk alive check с retry, inbox messages keep-alive, send_days в API
- `backend/app/models/telegram_outreach.py` — поле `send_days` на `TgCampaign`
- `backend/app/schemas/telegram_outreach.py` — `send_days` в схемах create/update/list
- `frontend/src/pages/InboxV2Page.tsx` — error banner + retry при сбоях загрузки сообщений
- `frontend/src/pages/CampaignDetailPage.tsx` — UI для выбора дней недели и часов отправки
- `frontend/src/api/telegramOutreach.ts` — `send_days` в API типах
- `backend/app/services/telegram_dm_service.py` — keep-alive для inbox connections

## Конфигурация

Настройки кампании (в UI или через API):

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `daily_message_limit` | int | null (без лимита) | Максимум cold сообщений в день |
| `send_from_hour` / `send_to_hour` | int | 9 / 18 | Окно отправки (часы) |
| `send_days` | int[] | [0,1,2,3,4,5,6] | Дни недели (0=Пн, 6=Вс) |
| `timezone` | string | "Europe/Moscow" | Таймзона для расписания |
| `delay_between_sends_min/max` | int | 11 / 25 | Базовый диапазон задержки (сек) |
| `spamblock_errors_to_skip` | int | 5 | Порог spamblock ошибок |

Константы в коде (`sending_worker.py`):

| Константа | Значение | Описание |
|---|---|---|
| `MAX_COLD_PER_HOUR_PER_ACCOUNT` | 2 | Лимит cold сообщений в час на аккаунт |
| `SPAMBLOCK_THRESHOLD` | 5 | Ошибок до пропуска аккаунта |
| `YOUNG_SESSION_DAYS` | 7 | Дней до окончания "молодой" сессии |
| `YOUNG_SESSION_DELAY_MULT` | 1.8 | Множитель задержки для молодых сессий |
