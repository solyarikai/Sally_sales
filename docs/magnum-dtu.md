# magnum-dtu — UI/UX Fixes: модалки и прокси

## Проблема

Два отдельных UX-бага в Telegram Outreach:

1. **Delete modal внутри bulk bar** — при нажатии Delete на кампании окно подтверждения рендерилось внутри floating bulk actions bar внизу экрана. Модалка была привязана к контейнеру, а не к viewport, из-за чего отображалась некорректно (обрезалась, перекрывалась другими элементами).

2. **Прокси не привязаны к аккаунтам 1:1** — несколько аккаунтов могли использовать один и тот же прокси, что приводило к детекту и банам со стороны Telegram. Не было механизма автоматического назначения свободных прокси.

## Решение

### 1. Delete Confirmation Modal — fullscreen overlay

Модалка удаления вынесена из bulk actions bar и рендерится как полноэкранный overlay с `fixed inset-0 z-50`:

**Было** (inline styles, привязка к контейнеру):
```tsx
<div style={{ position: 'fixed', inset: 0, zIndex: 50, ... }}>
  <div style={{ background: 'rgba(0,0,0,0.4)' }} />
  <div style={{ width: 400, borderRadius: 16, background: A.surface, ... }}>
```

**Стало** (Tailwind, dark mode, вне bulk bar):
```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center">
  <div className="absolute inset-0 bg-black/50" onClick={() => setDeleteConfirm(null)} />
  <div className={cn('relative z-10 w-[400px] rounded-xl shadow-lg p-6',
    isDark ? 'bg-gray-900 ring-1 ring-white/10' : 'bg-white ring-1 ring-black/5')}>
```

Также создан переиспользуемый компонент `ConfirmDialog` (`frontend/src/components/ConfirmDialog.tsx`) с вариантами `danger`, `warning`, `default`.

### 2. Прокси автоназначение: 1 прокси = 1 аккаунт

Скрипт `scripts/assign_proxies.py` реализует логику:
- Находит аккаунты без `assigned_proxy_id`
- Находит активные прокси, не занятые другими аккаунтами
- Назначает 1:1 через `zip(accounts, proxies)`
- Если прокси меньше чем аккаунтов — выводит предупреждение
- Также проставляет `proxy_group_id` если не задан

Модель `TgAccount` расширена полями:
- `assigned_proxy_id` — FK на конкретный прокси (1:1)
- `proxy_group_id` — FK на группу прокси (для bulk-операций)

## Изменённые файлы

- `frontend/src/pages/TelegramOutreachPage.tsx` — delete modal вынесен из bulk bar, рендерится как `fixed inset-0 z-50` overlay с backdrop
- `frontend/src/components/ConfirmDialog.tsx` — новый переиспользуемый компонент подтверждения (danger/warning/default)
- `scripts/assign_proxies.py` — скрипт автоназначения прокси 1:1
- `backend/app/models/telegram_outreach.py` — поля `assigned_proxy_id`, `proxy_group_id` в модели `TgAccount`
- `backend/app/api/telegram_outreach.py` — эндпоинт `POST /accounts/bulk-assign-proxy`

## Использование

### Delete modal
Работает автоматически — при нажатии Delete на кампании появляется fullscreen overlay с затемнением фона и кнопками Cancel/Delete.

### Прокси автоназначение
```bash
# Скопировать и запустить скрипт в контейнере
scp scripts/assign_proxies.py hetzner:/tmp/
ssh hetzner "docker cp /tmp/assign_proxies.py leadgen-backend:/tmp/ && docker exec leadgen-backend python /tmp/assign_proxies.py"
```

Вывод:
```
Accounts needing proxy: 12
Available proxies: 15
  +79001234567 (id=1, status=active) -> proxy id=3 (proxy.example.com:1080)
  ...
Done: 12 accounts assigned proxies.
```

Если свободных прокси не хватает:
```
WARNING: Not enough proxies! 12 accounts but only 5 free proxies.
```
