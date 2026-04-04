# magnum-dtu — UI/UX Fixes: модалки и прокси

## Проблема

Два отдельных UX-бага в Telegram Outreach:

1. **Delete modal внутри bulk bar** — при нажатии Delete на кампании окно подтверждения рендерилось внутри floating bulk actions bar внизу экрана. Модалка была привязана к контейнеру, а не к viewport, из-за чего отображалась некорректно (обрезалась, перекрывалась другими элементами). Аналогичная проблема была с кнопкой "Check & Clean" в Proxies — использовался нативный `confirm()`.

2. **Прокси не привязаны к аккаунтам 1:1** — несколько аккаунтов могли использовать один и тот же прокси, что приводило к детекту и банам со стороны Telegram. При удалении нерабочего прокси аккаунт оставался без прокси, и не было механизма автоматического переназначения.

## Решение

### 1. Delete Confirmation Modal — fullscreen overlay

Модалка удаления кампании вынесена из bulk actions bar и рендерится как полноэкранный overlay с `position: fixed, inset: 0, zIndex: 50`:

```tsx
// frontend/src/pages/TelegramOutreachPage.tsx:1359-1384
{deleteConfirm && (
  <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)' }}
         onClick={() => setDeleteConfirm(null)} />
    <div style={{ position: 'relative', zIndex: 10, width: 400, borderRadius: 16,
                  background: A.surface, padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
      {/* AlertTriangle icon + "Delete Campaign" title */}
      <p>Are you sure you want to delete "<b>{deleteConfirm.name}</b>"?</p>
      <button onClick={() => setDeleteConfirm(null)}>Cancel</button>
      <button onClick={() => handleDelete(deleteConfirm.id)}>Delete</button>
    </div>
  </div>
)}
```

Дополнительно создано два переиспользуемых компонента:

- **`ConfirmDialog`** (`frontend/src/components/ConfirmDialog.tsx`) — полноценный компонент с вариантами `danger`, `warning`, `default`. Используется на страницах AllProspects, Contacts, Datasets.

- **`ConfirmModal` + `ModalBackdrop`** (внутри `TelegramOutreachPage.tsx:2573-2611`) — локальные компоненты для Telegram Outreach. `ModalBackdrop` оборачивает в `fixed inset-0 z-50`, `ConfirmModal` добавляет стилизованные кнопки Cancel/Delete.

### 2. Check & Clean — styled confirm вместо native confirm()

Кнопка "Check & Clean" в Proxies tab заменена с нативного `confirm()` на `ConfirmModal`:

```tsx
// Было:
if (!confirm('Check all proxies and DELETE non-working ones?')) return;

// Стало:
<button onClick={() => setShowCleanConfirm(true)} ...>Check & Clean</button>
{showCleanConfirm && selectedGroup && (
  <ConfirmModal
    message={`Check all proxies in "${selectedGroup.name}" and DELETE non-working ones?`}
    onCancel={() => setShowCleanConfirm(false)}
    onConfirm={async () => { /* check & delete logic */ }}
  />
)}
```

### 3. Прокси автоназначение: 1 прокси = 1 аккаунт

Модель `TgAccount` расширена полями:
- `assigned_proxy_id` — FK на конкретный прокси (`tg_proxies.id`, `ondelete=SET NULL`)
- `proxy_group_id` — FK на группу прокси (`tg_proxy_groups.id`)

Три механизма автоназначения:

**a) `_try_reassign_proxy()`** — ищет свободный прокси из текущей группы аккаунта:
```python
# backend/app/api/telegram_outreach.py:347-356
async def _try_reassign_proxy(session, account):
    free = await _get_free_proxies(session, account.proxy_group_id,
                                   exclude_account_ids=[account.id])
    if free:
        account.assigned_proxy_id = free[0].id
        return free[0]
    return None
```

**b) `_auto_assign_infatica_proxy()`** — fallback через Infatica residential proxy:
```python
# backend/app/api/telegram_outreach.py:429-473
async def _auto_assign_infatica_proxy(account, session):
    if account.assigned_proxy_id or not infatica_proxy_service.is_configured:
        return None
    cfg = infatica_proxy_service.get_proxy_for_account(account.phone, account.id)
    group_id = await _get_or_create_infatica_group(session)
    proxy = TgProxy(proxy_group_id=group_id, host=cfg["host"], port=cfg["port"],
                    username=cfg["username"], password=cfg["password"],
                    protocol=TgProxyProtocol.SOCKS5, is_active=True)
    session.add(proxy)
    await session.flush()
    account.proxy_group_id = group_id
    account.assigned_proxy_id = proxy.id
    await _sync_proxy_to_dm_account(session, account.phone, proxy)
    return cfg
```

**c) Check & Clean cascade** — при удалении нерабочих прокси, каскадное переназначение:
1. Сначала `_try_reassign_proxy()` — ищет свободный из той же группы
2. Если нет свободных — `_auto_assign_infatica_proxy()` создаёт Infatica прокси
3. Ответ включает счётчик `infatica_assigned`

## Изменённые файлы

- `frontend/src/pages/TelegramOutreachPage.tsx` — delete modal как fullscreen overlay, `ConfirmModal`/`ModalBackdrop` компоненты, styled confirm для Check & Clean
- `frontend/src/components/ConfirmDialog.tsx` — переиспользуемый компонент подтверждения (danger/warning/default)
- `backend/app/models/telegram_outreach.py` — поля `assigned_proxy_id`, `proxy_group_id` в модели `TgAccount`
- `backend/app/api/telegram_outreach.py` — функции `_try_reassign_proxy()`, `_auto_assign_infatica_proxy()`, эндпоинт `POST /accounts/bulk-assign-proxy`, Infatica fallback в Check & Clean

## Использование

### Delete modal
Работает автоматически — при нажатии Delete на кампании появляется fullscreen overlay с затемнением фона и кнопками Cancel/Delete.

### Check & Clean
При нажатии "Check & Clean" в Proxies tab появляется стилизованное модальное окно подтверждения вместо нативного `confirm()`. После подтверждения:
- Проверяются все прокси группы
- Нерабочие удаляются
- Аккаунты автоматически переназначаются на свободные прокси или Infatica

### Bulk-назначение прокси (API)
```bash
# POST /api/tg-outreach/accounts/bulk-assign-proxy
curl -X POST http://localhost:8000/api/tg-outreach/accounts/bulk-assign-proxy \
  -H "Content-Type: application/json" \
  -d '{"account_ids": [1, 2, 3], "proxy_group_id": 5}'

# Response:
# {"ok": true, "count": 3, "proxies_assigned": 3, "proxies_available": 10}
```

Если свободных прокси меньше чем аккаунтов — назначаются сколько есть, остальные получают `assigned_proxy_id = null`.
