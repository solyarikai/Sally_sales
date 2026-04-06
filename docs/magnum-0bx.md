# Anti-Ban & Telegram Safety — предотвращение блокировок аккаунтов

## Проблема

13 аккаунтов заблокировано за один день. Корневые причины:
- Все аккаунты отправляли с одинаковыми device fingerprints (один device_model/system_version)
- Прокси не enforcement'ились — Telethon подключался напрямую при recheck
- Задержки между отправками слишком агрессивные (11–25 сек)
- Spam? check через @SpamBot не определял замороженные/забаненные аккаунты
- Отсутствовал warm-up для новых сессий
- Не было emergency stop при массовых спамблоках
- Warmup worker использовал Android fingerprint, а sending worker — Desktop, что создавало мгновенный бан-триггер

## Решение

Полный аудит и рефакторинг системы безопасности рассылки. 10 подзадач, все закрыты.

### 1. Исследование TeleRaptor (0bx.1)
Декомпозиция антибан-механизмов TeleRaptor: задержки (11–25 сек, Beta distribution), device fingerprints, ротация аккаунтов (max 10 sends), warm-up (7 дней), прокси (SOCKS5), spamblock tolerance, emergency stop. Результат — `docs/teleraptor-analysis.md`.

### 2. Исследование веб-аналогов (0bx.2)
Изучены WaDesk, Enreach.ai, CRMChat, TGForge, гайды по безопасности. Результат — gap analysis: поднять задержки до 45–90 сек, добавить hourly rate limit, растянуть warmup до 14 дней.

### 3. Аудит прокси (0bx.3)
- `telegram_engine.py`: трекинг прокси через `_client_proxies` dict
- `connect()` детектит proxy mismatch и переподключается с правильным прокси
- `_recheck_spamblocked_accounts()` загружает и передаёт прокси аккаунта (раньше подключался напрямую)
- Аудит подтвердил: все 27 активных аккаунтов имеют уникальные прокси (Infatica pool)

### 4. Аудит device fingerprints (0bx.4)
- Пулы устройств: 34 Android, 12 Desktop, 10 iOS
- Миграция всех 28 аккаунтов — 100% уникальные кортежи (device_model, system_version, app_version)
- Новые аккаунты автоматически получают fingerprint при создании
- Bulk-обновление через `POST /accounts/bulk-update-params` с пресетами (100+ устройств)
- **Критический фикс**: все fingerprints выровнены на Desktop params (PC 64bit / Windows 10) для соответствия api_id=2040 (TDesktop). Warmup worker ранее использовал Android-профиль (Samsung SM-G998B / SDK 33), что создавало переключение Android↔Desktop на одном аккаунте — прямой бан-триггер.

### 5. Fix Spam? check (0bx.5)
- Парсер @SpamBot дополнен ключевыми словами: `frozen`, `banned`, `blocked`, `disabled`, `deactivat`, `restrict`
- Дефолт для нераспознанных ответов: `unknown` + логирование
- API ставит `status=FROZEN` вместо ложного `ACTIVE`

### 6. Ротация задержек и hardcoded sending logic (0bx.6)
Удалены пользовательские настройки задержек из UI кампании (Priority slider, Delay Between Sends, Delay Randomness, Spamblock Errors). Вместо них — захардкоженная логика:
- Follow-ups всегда первые в очереди
- Max 2 cold msgs/hr/account
- Spamblock threshold = 5
- Base delay 11–25 сек с human-like jitter

Human-like паттерны в `sending_worker.py` — функция `_human_delay()`:
- **Mixture distribution**: 65% нормальное, 23% medium thinking pause, 12% long distracted pause
- **Time-of-day variation**: ~1.4× медленнее на границах рабочего окна
- **Account fatigue**: +2% за каждое сообщение после пятого (cap +50%)
- **Young session multiplier**: ×1.8 для аккаунтов < 7 дней
- **Micro-jitter**: ±0.1–0.9 сек к каждой задержке (избегаем round seconds)

### 7. Warm-up логика (0bx.7)
Два уровня warm-up:

**Пассивный warm-up** — лимиты на холодные отправки:
- `get_effective_daily_limit()` использует `session_created_at`
- Day 1: 2 msgs → Day 2: 4 → Day 3: 6 → ... → Day 7+: полный лимит
- Young sessions (< 7 дней): hard cap 5 msgs + delay multiplier ×1.8

**Активный warm-up** — `WarmupWorker` (14 дней):
- Day 1–8: подписки на каналы (1–2/день) из курируемого списка `TgWarmupChannel`
- Day 2+: реакции на сообщения в каналах (2–3/день)
- Day 3+: multi-turn conversations с warm buddies (5 старейших аккаунтов)
- Банк сообщений: 120 вопросов + 105 ответов в 8 категориях (RU+EN mix)
- Рабочие часы: 9–22 МСК, human-like задержки 2–5 сек между действиями
- Авто-стоп после 14 дней
- `skip_warmup` toggle — позволяет пропустить warmup для конкретных аккаунтов (с подтверждением)

### 8. Проверка session age (0bx.8)
- Аккаунты < 7 дней получают сниженные лимиты (п.7)
- В UI — AlertTriangle иконка на молодых аккаунтах с tooltip "Аккаунт слишком новый (X дн.), включён Warm-up"
- Confirmation dialog при деактивации warmup для молодых аккаунтов
- Fix: `session_created_at` enrichment обновляет даже когда поле уже установлено, если estimated date старше

### 9. Интеграционные тесты (0bx.9)
`test_sending_safety.py` — 5 проверок:
1. Каждый аккаунт подключается через свой уникальный прокси
2. Device fingerprints уникальны
3. Задержки в безопасных пределах
4. Дневные лимиты не превышаются (warm-up + young session caps)
5. Spamblock detection + emergency stop работают

Критический баг найден: 27 аккаунтов не имели прокси — автоматически назначены 1:1.

### 10. Детекция перманентного бана (0bx.10)
Разделение статусов:
- `SPAMBLOCKED` — временный, автоматический recheck каждые 30 мин
- `BANNED` — перманентный (Abuse Notifications), аккаунт = dead
- `FROZEN` — ограниченный, мониторится

Проверка включает:
- Поиск сообщений от "Abuse Notifications" в диалогах
- Тестовая отправка сообщения самому себе (ловит silent bans)
- Парсинг @SpamBot с EN/RU ключевыми словами и извлечением дат

### Anti-ban hardening (дополнительно)
- Официальные TDesktop api_id/api_hash константы (2040) — все аккаунты переключены
- Задержка 3–7 сек перед удалением диалога (анти-автоматизация fingerprint)
- Задержка 2–5 сек перед cleanup SpamBot диалога
- `/accounts/bulk-audit-sessions` endpoint: детекция concurrent Desktop sessions, fingerprint↔api_id mismatch
- `/accounts/bulk-switch-to-tdesktop` endpoint: массовое переключение на официальный api_id
- Cascade reassign: при спамблоке ВСЕ pending recipients переназначаются на другие аккаунты через round-robin

## Изменённые файлы

### Backend
- `backend/app/services/sending_worker.py` — human-like задержки (`_human_delay()`), warm-up лимиты (`get_effective_daily_limit()`), counter sync на рестарте, emergency stop (30 consecutive spamblocks), spamblock cascade (`_cascade_reassign_all`), batch limit per tick, skip_warmup support
- `backend/app/services/telegram_engine.py` — proxy enforcement (`_client_proxies`, mismatch reconnect), SpamBot парсер (frozen/banned/abuse), `check_account()` с Abuse Notifications + self-message test, dialog deletion delays
- `backend/app/services/warmup_worker.py` — активный warm-up: подписки на каналы, реакции, multi-turn conversations с warm buddies, 14-дневный цикл, Desktop fingerprints
- `backend/app/services/warmup_messages.py` — банк сообщений: 120 вопросов + 105 ответов в 8 категориях
- `backend/app/models/telegram_outreach.py` — enum-значения `BANNED`, `FROZEN`, `PROXY_ISSUE`; модели `TgWarmupChannel`, `TgWarmupLog`, `TgWarmupActionType`; `skip_warmup` field
- `backend/app/schemas/telegram_outreach.py` — warmup schemas, skip_warmup; удалены user-configurable delay fields
- `backend/app/api/telegram_outreach.py` — endpoints: warmup start/stop/status, bulk-warmup, warmup channels CRUD, bulk-update-params, bulk-audit-sessions, bulk-switch-to-tdesktop
- `backend/app/main.py` — регистрация WarmupWorker в startup

### Frontend
- `frontend/src/pages/TelegramOutreachPage.tsx` — UI: статусы (ACTIVE/SPAMBLOCKED/BANNED/FROZEN/DEAD), warmup progress (day/14), session age warnings (AlertTriangle), device fingerprint, bulk warmup operations, warmup channels panel, skip warmup toggle + confirmation
- `frontend/src/pages/CampaignDetailPage.tsx` — удалены настройки: Priority, Delay Between Sends, Delay Randomness, Spamblock Errors
- `frontend/src/api/telegramOutreach.ts` — типы и API-клиент: warmup endpoints, check endpoints, bulk operations

### Миграции
- `backend/alembic/versions/202604020100_add_active_warmup.py` — поля `warmup_active`, `warmup_started_at`, `warmup_actions_done`; таблица `tg_warmup_log`
- `backend/alembic/versions/202604020200_add_tg_warmup_channels.py` — таблица `tg_warmup_channels`

### Скрипты и документация
- `backend/tests/test_services/test_sending_safety.py` — интеграционные тесты безопасности
- `scripts/assign_proxies.py` — автоназначение уникальных прокси
- `scripts/fix_android_fingerprints.py` — миграция существующих аккаунтов на Desktop fingerprints
- `docs/teleraptor-analysis.md` — reverse-engineering анализ TeleRaptor

## Использование

### Warm-up новых аккаунтов
**Пассивный** (автоматический): при добавлении аккаунта с `session_created_at` — лимиты нарастают сами (2 → 4 → 6 → ... → full).

**Активный** (через UI или API):
```
POST /telegram-outreach/accounts/{id}/warmup/start
POST /telegram-outreach/accounts/{id}/warmup/stop
GET  /telegram-outreach/accounts/{id}/warmup/status
POST /telegram-outreach/accounts/bulk-warmup  {account_ids, action: "start"|"stop"}
```

### Управление каналами для warm-up
```
GET    /telegram-outreach/warmup/channels
POST   /telegram-outreach/warmup/channels         {url, title}
DELETE /telegram-outreach/warmup/channels/{id}
PATCH  /telegram-outreach/warmup/channels/{id}     {is_active}
POST   /telegram-outreach/warmup/channels/seed     # 6 дефолтных каналов
```

### Аудит безопасности аккаунтов
```
POST /telegram-outreach/accounts/bulk-audit-sessions    # проверка concurrent sessions, fingerprint mismatch
POST /telegram-outreach/accounts/bulk-switch-to-tdesktop # переключение на api_id=2040
```

### Emergency stop
Автоматически при 30 consecutive spamblocks — все активные кампании → `PAUSED`.

### Проверка аккаунтов
Через UI (кнопки "Alive?" / "Spam?") или API:
- Проверяет @SpamBot + Abuse Notifications + self-message test
- Результат: `none` / `temporary` / `permanent` / `frozen` / `unknown`
- Frozen/banned аккаунты автоматически исключаются из рассылки
- Recheck каждые 30 мин для SPAMBLOCKED и FROZEN аккаунтов

### Cascade reassign при спамблоке
При достижении spamblock threshold аккаунтом, `_cascade_reassign_all` находит все PENDING/IN_SEQUENCE recipients и переназначает на другие аккаунты через round-robin. Если альтернатив нет — assignment очищается для pickup при восстановлении.
