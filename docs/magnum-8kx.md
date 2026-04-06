# magnum-8kx — CRM Blacklist и добавление лидов из CRM в кампании

**Epic** · P2 · Closed 2026-03-31

## Проблема

Два пробела в Telegram Outreach CRM:

1. **Отсутствие blacklist** — не было возможности заблокировать контакты от получения сообщений. Если username попадал в кампанию повторно или принадлежал нежелательному контакту (конкурент, жалоба), единственный вариант — вручную удалить recipient. Нет централизованного списка блокировки, который действовал бы на все кампании.

2. **Нет добавления из CRM в кампанию** — recipients загружались только через текст или CSV. Контакты, уже существующие в CRM (ранее обработанные, с историей), нельзя было добавить в новую кампанию без повторного ручного ввода usernames.

## Решение

### 8kx.1 — CRM Blacklist

Новая таблица `tg_blacklist` с CRUD API и UI-подвкладкой в CRM.

**Модель** (`backend/app/models/telegram_outreach.py:576-583`):
```python
class TgBlacklist(Base, TimestampMixin):
    """Blacklisted Telegram usernames — recipients matching these are filtered out on upload."""
    __tablename__ = "tg_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    reason = Column(String(255), nullable=True)
    added_by = Column(String(100), nullable=True)
```

**Нормализация usernames** (`backend/app/api/telegram_outreach.py:8166`):
Функция `_normalize_username` приводит все форматы Telegram-ссылок к чистому username:
- `@user` → `user`
- `t.me/user` → `user`
- `https://t.me/user` → `user`
- `telegram.me/user` → `user`
- URL с query-параметрами и trailing slash — очищаются
- Всё приводится к lowercase

```python
_TG_LINK_RE = re.compile(
    r'(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', re.IGNORECASE
)

def _normalize_username(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    m = _TG_LINK_RE.match(raw)
    if m:
        return m.group(1).lower()
    return raw.lstrip("@").lower()
```

**API endpoints** (`/telegram-outreach/blacklist`):

| Метод | Endpoint | Назначение |
|-------|----------|------------|
| GET | `/blacklist` | Список с пагинацией и поиском |
| POST | `/blacklist/upload` | Массовая загрузка usernames (textarea) |
| DELETE | `/blacklist/{entry_id}` | Удаление одной записи |
| POST | `/blacklist/bulk-delete` | Удаление нескольких записей по ID |
| GET | `/blacklist/count` | Общее количество записей в blacklist |

**Фильтрация при загрузке recipients:**
При загрузке recipients (текст, CSV, или из CRM) blacklist загружается в `set` для O(1) проверки. Заблокированные usernames пропускаются, в ответе возвращается количество отфильтрованных:

```python
bl_rows = (await session.execute(select(TgBlacklist.username))).scalars().all()
blacklisted = set(bl_rows)

if username.lower() in blacklisted:
    blacklisted_count += 1
    continue

return {"ok": True, "added": added, "total": campaign.total_recipients,
        "blacklisted": blacklisted_count}
```

**UI** — подвкладка "Blacklist" в TG Outreach (`frontend/src/pages/TelegramOutreachPage.tsx:6909-7131`):
- Поиск по username с live-фильтрацией
- Кнопка "Add Usernames" — textarea для массовой загрузки с необязательным полем reason
- Таблица: Username | Reason | Added by | Дата добавления
- Чекбоксы для выбора + bulk delete
- Маршрут: `/outreach/tools/blacklist`

### 8kx.2 — Добавление лидов из CRM в кампанию

Endpoint `POST /campaigns/{campaign_id}/recipients/add-from-crm` (`backend/app/api/telegram_outreach.py:4178`) принимает массив `contact_ids` из CRM и добавляет их как recipients кампании:

```python
@router.post("/campaigns/{campaign_id}/recipients/add-from-crm")
async def add_recipients_from_crm(campaign_id: int, data: dict,
                                   session: AsyncSession = Depends(get_session)):
    contact_ids = data.get("contact_ids", [])
    bl_rows = (await session.execute(select(TgBlacklist.username))).scalars().all()
    blacklisted = set(bl_rows)
    # Для каждого контакта: blacklist → дубликаты → создание recipient
    ...
    return {"ok": True, "added": added, "skipped": skipped,
            "total": campaign.total_recipients, "blacklisted": blacklisted_count}
```

**Frontend** — модальное окно "Add from CRM" (`frontend/src/pages/CampaignDetailPage.tsx:1740-2300`):
- Открывается кнопкой рядом с CSV upload в Recipients tab
- Левая панель фильтров: поиск по username, фильтр по статусу контакта
- Таблица контактов: Username, Name, Company, Status, Sent, Replies
- Чекбоксы для выбора + Select All
- Пагинация: Prev/Next
- Кнопка "Add X Selected" — добавляет выбранные контакты в кампанию
- Toast-уведомления: added, skipped (дубликаты), blacklisted, cross-campaign duplicates

**Frontend API** (`frontend/src/api/telegramOutreach.ts:514`):
```typescript
addRecipientsFromCrm: async (campaignId: number, contactIds: number[]) =>
  (await api.post(`${BASE}/campaigns/${campaignId}/recipients/add-from-crm`,
    { contact_ids: contactIds })).data,
```

Также при загрузке recipients через текст (`upload-text`) автоматически создаются CRM-контакты для новых usernames со статусом `cold`:

```python
crm_q = await session.execute(select(TgContact).where(TgContact.username == username))
if not crm_q.scalar():
    session.add(TgContact(username=username, status=TgContactStatus.COLD,
        source_campaign_id=campaign_id,
        campaigns=[{"id": campaign_id, "name": campaign.name}]))
```

## Изменённые файлы

- `backend/app/models/telegram_outreach.py` — модель `TgBlacklist` (таблица `tg_blacklist`)
- `backend/app/schemas/telegram_outreach.py` — схемы `TgBlacklistUploadText`, `TgBlacklistResponse`, `TgBlacklistListResponse`
- `backend/app/api/telegram_outreach.py` — CRUD endpoints blacklist, нормализация usernames, blacklist-фильтрация в upload-text/CSV/add-from-crm, endpoint add-from-crm
- `backend/alembic/versions/a1b2c3d4e5f6_add_tg_blacklist_table.py` — миграция для создания таблицы
- `frontend/src/api/telegramOutreach.ts` — API-клиент: `addRecipientsFromCrm`, blacklist методы (list, upload, delete, bulkDelete, count)
- `frontend/src/pages/TelegramOutreachPage.tsx` — UI: подвкладка Blacklist в CRM с upload/search/delete
- `frontend/src/pages/CampaignDetailPage.tsx` — UI: модальное окно "Add from CRM" в Recipients tab

## Использование

### Добавление в blacklist
TG Outreach → Tools → Blacklist → "Add Usernames" → вставить usernames (по одному на строку, любой формат) → указать reason (опционально) → Upload.

### Добавление контактов из CRM в кампанию
Campaign → Recipients → "Add from CRM" → фильтровать по username/статусу → выбрать контакты чекбоксами → Add Selected. Blacklisted контакты автоматически отфильтруются.

### Автоматическая фильтрация
При любой загрузке recipients (текст, CSV, из CRM) blacklist проверяется автоматически. Заблокированные пропускаются, показывается toast с количеством отфильтрованных.

### Поддерживаемые форматы username
```
@username
username
t.me/username
https://t.me/username
telegram.me/username
```
Все приводятся к нормализованному `username` (lowercase, без префиксов).
