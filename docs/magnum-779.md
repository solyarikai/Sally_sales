# magnum-779 — Campaign & Inbox Fixes

**Epic** · P1 · Closed 2026-03-31

## Проблема

Набор критических багов в модуле Telegram Outreach, затрагивающих кампании и Inbox:

1. **Replies не отображались** — колонка Replies в списке кампаний показывала 0 для всех кампаний, хотя ответы существовали в БД
2. **Inbox показывал устаревшие диалоги** — при фильтрации по кампании отображались диалоги от 25 числа, а не актуальные
3. **Аккаунты кампании не сохранялись** — снятие чекбокса аккаунта и нажатие Save не применяло изменения (ORM delete/add не срабатывал корректно)
4. **Отсутствовали теги кампаний** — не было возможности группировать кампании тегами и фильтровать по ним в Inbox
5. **Не было Select All** — в настройках аккаунтов кампании нельзя было выбрать/снять все аккаунты одной кнопкой

## Решение

### 779.1 — Replies count в списке кампаний

В `list_campaigns()` добавлен подсчёт `replies_count` inline-запросом к `TgIncomingReply` для каждой кампании. Значение возвращается в `TgCampaignResponse.replies_count`. Дополнительно: `GET /campaigns/{id}/replies` — пагинированный список ответов с joinedload recipient/account; `GET /campaigns/{id}/stats` — breakdown по статусам реципиентов (`TgCampaignStatsResponse`). Фронтенд отображает `replies_count` в колонке Replies таблицы кампаний.

**Файлы:**
- `backend/app/api/telegram_outreach.py` — `list_campaigns()` (inline replies_count), `/campaigns/{id}/replies`, `/campaigns/{id}/stats`
- `backend/app/schemas/telegram_outreach.py` — `TgCampaignStatsResponse.replied`
- `frontend/src/api/telegramOutreach.ts` — `TgCampaign.replies_count`
- `frontend/src/pages/TelegramOutreachPage.tsx` — колонка Replies в таблице кампаний

### 779.2 — Inbox фильтр по кампании

Реализован endpoint `GET /inbox/threads` на сервере, который строит список тредов на основе `TgIncomingReply` с subquery для per-recipient reply stats (последний ответ + количество). Фильтрация по `campaign_id`, `account_id`, `campaign_tag` и `inbox_tag` реципиента. Сортировка по `last_reply_at DESC` — свежие диалоги всегда наверху.

**Файлы:**
- `backend/app/api/telegram_outreach.py` — `/inbox/threads` endpoint
- `frontend/src/pages/TelegramOutreachPage.tsx` — Inbox UI с фильтрами

### 779.3 — Сохранение аккаунтов кампании

Endpoint `PUT /campaigns/{campaign_id}/accounts` переписан: ORM `delete()` + `add()` заменён на SQL-level операции (`sa_delete` + `sa_insert`), что устраняет проблемы с ORM identity-map. Удаляются все существующие связи одним DELETE, затем bulk INSERT новых из переданного `account_ids: list[int]`. Middleware выполняет commit автоматически.

```python
# backend/app/api/telegram_outreach.py
@router.put("/campaigns/{campaign_id}/accounts")
async def set_campaign_accounts(campaign_id: int, account_ids: list[int], ...):
    # Remove existing (SQL-level delete, no ORM identity-map issues)
    await session.execute(
        sa_delete(TgCampaignAccount).where(TgCampaignAccount.campaign_id == campaign_id)
    )
    # Add new (bulk insert)
    if account_ids:
        await session.execute(
            sa_insert(TgCampaignAccount),
            [{"campaign_id": campaign_id, "account_id": aid} for aid in account_ids],
        )
```

**Файлы:**
- `backend/app/api/telegram_outreach.py` — `set_campaign_accounts`

### 779.4 — Campaign Tags

Добавлено JSONB-поле `tags` на модель `TgCampaign` (массив строк). Endpoint `PATCH /campaigns/{campaign_id}/tags` принимает `list[str]` и полностью заменяет теги кампании. Endpoint `GET /inbox/campaign-tags` возвращает все уникальные теги для UI-фильтров.

Frontend: модалка "Set Tags" с поиском по существующим тегам, автокомплитом и отображением тегов как пилюль. Теги также используются как фильтр `campaign_tag` в Inbox (JSONB `@>` оператор).

```python
# backend/app/api/telegram_outreach.py
@router.patch("/campaigns/{campaign_id}/tags")
async def update_campaign_tags(campaign_id: int, tags: list[str], ...):
    """Update tags on a campaign (full replace)."""
    campaign.tags = tags
```

**Файлы:**
- `backend/app/models/telegram_outreach.py` — `tags = Column(JSONB, ...)`
- `backend/app/api/telegram_outreach.py` — `update_campaign_tags`
- `frontend/src/api/telegramOutreach.ts` — `updateCampaignTags`
- `frontend/src/pages/TelegramOutreachPage.tsx` — модалка Set Tags

### 779.5 — Select All Checkbox в аккаунтах кампании

В `CampaignDetailPage.tsx` → Settings → Accounts добавлен чекбокс в заголовке таблицы. Логика:
- Все выбраны → снять все (`setCampaignAccountIds(new Set())`)
- Не все выбраны → выбрать все
- Индетерминированное состояние через `el.indeterminate`

```tsx
// frontend/src/pages/CampaignDetailPage.tsx
<input type="checkbox"
  checked={allAccounts.length > 0 && campaignAccountIds.size === allAccounts.length}
  ref={el => { if (el) el.indeterminate = campaignAccountIds.size > 0
    && campaignAccountIds.size < allAccounts.length; }}
  onChange={() => {
    if (campaignAccountIds.size === allAccounts.length) {
      setCampaignAccountIds(new Set());
    } else {
      setCampaignAccountIds(new Set(allAccounts.map(a => a.id)));
    }
  }}
/>
```

**Файлы:**
- `frontend/src/pages/CampaignDetailPage.tsx` — header checkbox

## Изменённые файлы

- `backend/app/models/telegram_outreach.py` — JSONB `tags` на `TgCampaign`
- `backend/app/api/telegram_outreach.py` — endpoints: `PUT /campaigns/{id}/accounts`, `PATCH /campaigns/{id}/tags`, `GET /campaigns/{id}/replies`, `GET /campaigns/{id}/stats`, `GET /inbox/threads`, `GET /inbox/campaign-tags`
- `backend/app/schemas/telegram_outreach.py` — `TgCampaignStatsResponse` с полем `replied`
- `frontend/src/api/telegramOutreach.ts` — `updateCampaignTags`, API клиент
- `frontend/src/pages/TelegramOutreachPage.tsx` — Campaigns tab (replies, tags modal, tag pills), Inbox tab
- `frontend/src/pages/CampaignDetailPage.tsx` — Select All checkbox в аккаунтах

## Использование

### Теги кампаний
1. Открыть Telegram Outreach → Campaigns
2. Нажать `⋮` на карточке кампании → "Set Tag"
3. Ввести теги через запятую → Save (или Enter)
4. Теги отображаются как пилюли на карточке и используются для фильтрации в Inbox

### API
```bash
# Установить теги кампании
curl -X PATCH /api/telegram-outreach/campaigns/5/tags \
  -H 'Content-Type: application/json' \
  -d '["easystaff", "ru-market"]'

# Сохранить аккаунты кампании
curl -X PUT /api/telegram-outreach/campaigns/5/accounts \
  -H 'Content-Type: application/json' \
  -d '[1, 3, 7, 12]'

# Получить replies кампании
curl /api/telegram-outreach/campaigns/5/replies?page=1&page_size=50

# Inbox threads с фильтром по тегу кампании
curl /api/telegram-outreach/inbox/threads?campaign_tag=easystaff
```
