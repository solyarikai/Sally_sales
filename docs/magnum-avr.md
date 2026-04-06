# magnum-avr: Data Integrity & Counting Fixes

## Проблема

Три связанных проблемы в модуле Telegram Outreach:

1. **Счётчик `sent_today` показывал некорректные данные** (P1). Аккаунт `79828204955` показывал `sent_today=5`, хотя в Activity Log только 5 ошибок (Account not connected, User not found) и ни одного реального отправленного сообщения. Счётчики инкрементировались независимо от фактического статуса доставки, что приводило к дрейфу при перезапусках, крешах и ошибках отправки.

2. **Proxy dropdown в bulk actions выезжал за экран** (P2). В нижней floating-панели массового редактора выпадающий список Proxy Group раскрывался вниз, выходя за край экрана.

3. **Bulk upload аватарок работал некорректно** (P2). При массовой загрузке фото они не распределялись на все выбранные аккаунты, а при смене фото старое не удалялось из Telegram. Дополнительно — замороженные (frozen) аккаунты вызывали необработанные исключения, а устаревшие соединения приводили к сбоям загрузки.

## Решение

### 1. Точный подсчёт `sent_today`

Два механизма для гарантии корректности счётчиков:

**Инкремент только при `status == "sent"`** (`sending_worker.py`):
```python
if status == "sent":
    account.messages_sent_today += 1
    account.total_messages_sent += 1
    campaign.messages_sent_today += 1
    campaign.total_messages_sent += 1
```

Сообщения со статусом `failed`, `spamblocked` или `bounced` не увеличивают счётчик.

**Пересчёт из реальных данных при запуске воркера** (`sending_worker.py`, метод `_sync_daily_counters()`):

Вызывается при каждом старте `SendingWorker`. Выполняет SQL-запрос к таблице `tg_outreach_messages`, считая только записи с `status='sent'` и `sent_at >= today`, и перезаписывает `messages_sent_today` у каждого аккаунта и кампании:

```python
async def _sync_daily_counters(self):
    """Recalculate messages_sent_today from actual TgOutreachMessage records."""
    today_start = datetime.combine(today, datetime.min.time())
    real_account = await session.execute(
        select(TgOutreachMessage.account_id, func.count().label("cnt"))
        .where(TgOutreachMessage.status == TgMessageStatus.SENT,
               TgOutreachMessage.sent_at >= today_start)
        .group_by(TgOutreachMessage.account_id)
    )
    # Сравнить с текущим значением и исправить при расхождении
```

Также реализован авто-сброс счётчиков в полночь UTC.

### 2. Proxy dropdown — два исправления

Проблема решена двумя дополняющими подходами:

**A) `StyledSelect` — авто-определение направления раскрытия** (`TelegramOutreachPage.tsx`):

Компонент `StyledSelect` измеряет позицию кнопки при открытии и автоматически раскрывается вверх, если dropdown не помещается в viewport:

```tsx
const rect = ref.current.getBoundingClientRect();
setOpenUp(rect.bottom + 248 > window.innerHeight);
// ...
...(openUp
  ? { bottom: '100%', marginBottom: 4 }
  : { top: '100%', marginTop: 4 })
```

Используется для фильтров и CRM-статусов по всей странице.

**B) `BulkActionsBar` — inline panels + hardcoded upward dropdown**:

Bulk-операции (proxy, limit, bio, 2FA, language, names, privacy) раскрываются как inline-панели через `activePanel` state. Proxy dropdown внутри панели жёстко открывается вверх (`bottom: '100%'`), так как панель всегда находится внизу экрана:

```tsx
{proxyDropdownOpen && (
  <div style={{ position: 'absolute', bottom: '100%', marginBottom: 4, ... }}>
    {/* proxy group options */}
  </div>
)}
```

### 3. Bulk upload аватарок

Эндпоинт `POST /accounts/bulk-set-photo` (`telegram_outreach.py`) реализует логику распределения фото:
- **1 фото загружено** — одно фото устанавливается всем выбранным аккаунтам
- **N фото загружено** — каждому аккаунту назначается случайное фото из набора

Фото сохраняется на диск в `/app/tg_photos/{phone}.jpg` и путь записывается в `account.profile_photo_path`.

**Staggered TG upload** (`_staggered_photo_upload`):
- Фоновая загрузка в Telegram с рандомной задержкой между аккаунтами (anti-ban)
- Удаление старых фото из Telegram перед загрузкой нового (`GetUserPhotosRequest` → `DeletePhotosRequest`)
- Отключение устаревшего кэшированного клиента перед переподключением (`disconnect` → `connect`)
- Proxy fallback: при сбое proxy-подключения автоматически переключается на прямое соединение
- Ошибки ловятся generic `except Exception` и записываются в progress tracker
- Фронтенд отображает реальные результаты синхронизации (synced, skipped, errors) через polling `task_id`

## Изменённые файлы

- `backend/app/services/sending_worker.py` — метод `_sync_daily_counters()` для пересчёта счётчиков из реальных данных; инкремент `messages_sent_today` строго при `status == "sent"`; авто-сброс в полночь UTC
- `backend/app/api/telegram_outreach.py` — эндпоинт `bulk-set-photo` с распределением фото (1:N и N:random); `_staggered_photo_upload` с proxy fallback, удалением старых фото, stale-disconnect
- `backend/app/models/telegram_outreach.py` — поле `messages_sent_today` у `TgAccount` и `TgCampaign`; enum `TgMessageStatus` с разделением SENT/FAILED/SPAMBLOCKED
- `backend/app/schemas/telegram_outreach.py` — схемы для bulk-операций
- `frontend/src/pages/TelegramOutreachPage.tsx` — компонент `StyledSelect` с авто-upward detection (viewport threshold 248px); `BulkActionsBar` с inline panels и hardcoded-upward proxy dropdown; toast с progress tracking
- `frontend/src/api/telegramOutreach.ts` — API-клиент для `bulkSetPhoto`, `bulkAssignProxy`

## Использование

### Проверка счётчиков

Счётчики синхронизируются автоматически при старте воркера. Для ручной проверки:

```bash
ssh hetzner "docker exec leadgen-backend python -c \"
import asyncio
from app.db import async_session_maker
from app.models.telegram_outreach import TgAccount
from sqlalchemy import select

async def check():
    async with async_session_maker() as s:
        accs = (await s.execute(select(TgAccount))).scalars().all()
        for a in accs:
            if a.messages_sent_today > 0:
                print(f'{a.phone}: sent_today={a.messages_sent_today}')
asyncio.run(check())
\""
```

### Bulk photo upload

В UI: выделить аккаунты чекбоксами → нажать **Set Photo** в панели bulk actions → выбрать одно или несколько изображений. Toast покажет детали: сколько сохранено локально, сколько синхронизировано в Telegram, сколько ошибок.

### Proxy assignment

В UI: выделить аккаунты → нажать **Assign Proxy** → выбрать группу из inline-списка → **Apply**.
