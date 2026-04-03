# Inbox Reference — TG Outreach

Эта папка содержит актуальные файлы и документацию для воссоздания вкладки Inbox в TG Outreach.
Файлы извлечены из ветки `main` (коммит f926454 и позже).

## Файлы

### Backend
- `backend/inbox_sync_service.py` — сервис синхронизации диалогов из Telegram
- `backend/inbox_api_endpoints.py` — API endpoints для /inbox/* (извлечены из telegram_outreach.py, строки 3380-3760)
- `backend/telegram_outreach_model.py` — все модели (TgAccount, TgCampaign, TgInboxDialog, TgContact и т.д.)
- `backend/telegram_outreach_schemas.py` — Pydantic схемы
- `backend/telegram_engine.py` — Telethon клиент менеджер + session_file_to_string_session()

### Frontend
- `frontend/TelegramOutreachPage.tsx` — полная страница TG Outreach (все вкладки включая Inbox)
- `frontend/telegramOutreach.ts` — API клиент для фронтенда

---

## Как работает Inbox

### Архитектура: два типа аккаунтов

- **tg_accounts** — для Outreach рассылки. api_id, api_hash, .session файл на диске
- **telegram_dm_accounts** — для Inbox. StringSession в БД (текстовая строка)

При импорте аккаунтов с .session файлами система автоматически:
1. Сохраняет .session на диск
2. Извлекает StringSession через `session_file_to_string_session()` в telegram_engine.py
3. Создаёт запись в telegram_dm_accounts
4. Подтягивает telegram_user_id, username через get_me()

### Sync диалогов (inbox_sync_service.py)

Inbox работает с кешем в таблице `tg_inbox_dialogs`, не ходит в Telegram в реальном времени.

1. Берёт аккаунт из telegram_dm_accounts
2. Проверяет string_session и auth_status != "error"
3. Подключается через telegram_dm_service.connect_account()
4. Вызывает telegram_dm_service.get_dialogs() — список DM
5. Для каждого диалога UPSERT в tg_inbox_dialogs
6. Пытается привязать к кампании через username

Вызывается через POST /inbox/sync?account_id=N или POST /inbox/sync (все).

### API endpoints

- **GET /inbox/accounts** — список DM аккаунтов с string_session (для дропдауна)
- **GET /inbox/dialogs** — список диалогов из кеша. Фильтры: account_id, campaign_id, campaign_tag, tag, search. Минимум один фильтр обязателен
- **GET /inbox/dialogs/{dialog_id}/messages** — реальные сообщения из Telegram через telegram_dm_service.get_messages()
- **POST /inbox/dialogs/{dialog_id}/send** — отправка через аккаунт диалога, telegram_dm_service.send_message()
- **PATCH /inbox/dialogs/{dialog_id}/tag** — тегирование: interested, info_requested, not_interested
- **POST /inbox/sync** — запуск синхронизации

### Frontend (InboxTab в TelegramOutreachPage.tsx)

Двухпанельный layout:

**Левая панель (320px):**
- Поиск по имени/username
- Дропдауны: Account, Campaign, Tag
- Кнопка Apply (обязательна)
- Кнопка Sync
- Список диалогов с аватарками, превью, тегами

**Правая панель:**
- Хедер с аватаркой, именем, кампанией, иконкой CRM инфо
- Чат-баблы (outbound=голубой, inbound=серый)
- Теги: Interested/Info Requested/Not Interested
- Quick reply templates (5 шаблонов)
- Поле ввода + Send

### Дизайн токены

```javascript
const A = {
  blue: '#4F6BF0', blueHover: '#4360D9', blueBg: '#EEF1FE',
  teal: '#0D9488', tealBg: '#ECFDF5',
  rose: '#E05D6F', roseBg: '#FFF1F2',
  bg: '#FAFAF8', surface: '#FFFFFF', border: '#E8E6E3',
  text1: '#1A1A1A', text2: '#6B6B6B', text3: '#9CA3AF',
};
```

---

## БД таблицы и колонки (миграции)

```sql
-- Таблица кеша диалогов
CREATE TABLE IF NOT EXISTS tg_inbox_dialogs (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES tg_accounts(id) ON DELETE CASCADE,
    peer_id BIGINT NOT NULL,
    peer_name VARCHAR(200),
    peer_username VARCHAR(100),
    peer_photo_small VARCHAR(500),
    last_message_text TEXT,
    last_message_at TIMESTAMP,
    last_message_outbound BOOLEAN,
    unread_count INTEGER NOT NULL DEFAULT 0,
    campaign_id INTEGER REFERENCES tg_campaigns(id) ON DELETE SET NULL,
    inbox_tag VARCHAR(50),
    synced_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tg_inbox_dialogs_account_peer ON tg_inbox_dialogs(account_id, peer_id);

-- Дополнительные колонки
ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS string_session TEXT;
ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT;
ALTER TABLE tg_campaigns ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE tg_recipients ADD COLUMN IF NOT EXISTS inbox_tag VARCHAR(50);
```

## ENV переменные

```
TELEGRAM_CHECKER_API_ID=2040
TELEGRAM_CHECKER_API_HASH=b18441a1ff607e10a989891a5462e627
```

Без них telegram_dm_service не может подключаться к Telegram.

---

## Как восстановить Inbox с нуля

1. Применить SQL миграции (выше)
2. Добавить ENV переменные в .env
3. Скопировать inbox_sync_service.py в backend/app/services/
4. Добавить inbox endpoints в backend/app/api/telegram_outreach.py (из inbox_api_endpoints.py)
5. Добавить модель TgInboxDialog в telegram_outreach.py (из telegram_outreach_model.py)
6. Добавить session_file_to_string_session() в telegram_engine.py
7. Обновить фронтенд: InboxTab, API клиент
8. Загрузить аккаунты с .session файлами через Import
9. В Inbox: выбрать аккаунт -> Sync -> Apply
