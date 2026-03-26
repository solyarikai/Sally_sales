# Instantly — Inbox Placement Tests

## Аутентификация

API v2, Bearer токен (base64 строка используется as-is):

```
Authorization: Bearer OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OnJoWER1SGpuakVodA==
```

Decoded: `9ded7b47-2546-47ea-9964-5c71d57b78b6:rhXDuHjnjEht`

> Ключ настроен только на Inbox Placement тесты. Доступ к аккаунтам (`/api/v2/accounts`) — 401.

---

## Что сделано (24.03.2026)

### 1. Дублирование тестов от 20.03

Найдено **13 тестов** от 20.03.2026. Все продублированы (POST `/api/v2/inbox-placement-tests` с теми же параметрами + `(Copy)` в названии).

| Оригинал (20.03) | Копия (24.03) |
|---|---|
| Mifort (Copy) | Mifort (Copy) (Copy) |
| Palark (Copy) (Copy) | Palark (Copy) (Copy) (Copy) |
| Inxy (Copy) | Inxy (Copy) (Copy) |
| Squarefi (Copy) (Copy) | Squarefi (Copy) (Copy) (Copy) |
| Easy Global (Copy) (Copy) | Easy Global (Copy) (Copy) (Copy) |
| Internal (Easy Global) (Copy) (Copy) | Internal (Easy Global) (Copy) (Copy) (Copy) |
| Maincard (Easystaff) (Copy) (Copy) | Maincard (Easystaff) (Copy) (Copy) (Copy) |
| TFP (Copy) (Copy) | TFP (Copy) (Copy) (Copy) |
| Easystaff (Copy) (Copy) | Easystaff (Copy) (Copy) (Copy) |
| Delyrio (Easystaff) (Copy) (Copy) | Delyrio (Easystaff) (Copy) (Copy) (Copy) |
| Paybis (Copy) (Copy) | Paybis (Copy) (Copy) (Copy) |
| Onsocial (Copy) (Copy) | Onsocial (Copy) (Copy) (Copy) |
| Rizzult (Copy) (Copy) (Copy) (Copy) | Rizzult (Copy) (Copy) (Copy) (Copy) (Copy) |

### 2. Тест GWC

Создан тест **GWC** (`id: 019d207b-821b-7274-9ebc-3c7620530cba`) с 14 ящиками Hugo:

```
hugo.k@gatewaycryptosolutions.com
hugo@gatewaycryptosolution.com
hugo@gatewaycryptosolutions.com
hugo.k@gatewaycrypto-processor.com
hugo.k@gatewaycryptotools.com
hugo@gatewaycrypto-solution.com
hugo.k@gatewaycrypto-solutions.com
hugo.k@gatewaycrypto-solution.com
hugo@gatewaycrypto-processor.com
hugo@gatewaycrypto-solutions.com
hugo@gatewaycryptotools.com
hugo.k@gatewaycryptoprocessor.com
hugo@gatewaycryptoprocessor.com
hugo.k@gatewaycryptosolution.com
```

> Email subject/body скопированы из теста Mifort как заглушка — обновить вручную в Instantly если нужно.

---

## Задача на 23:00 (PENDING — ждём Slack webhooks)

**Цель:** для каждого теста (все созданные 24.03 копии + GWC) достать ящики с доставляемостью < 80% и отправить в соответствующий Slack канал.

**Статус:** Slack приложения уже созданы, webhook URL-ы ещё не получены.

### Как получить результаты теста

```
GET /api/v2/inbox-placement-tests/{id}/report
Authorization: Bearer <token>
```

Фильтровать: `deliverability < 0.8` (или `< 80` — уточнить формат).

### Что нужно сделать когда получим webhooks

1. Составить маппинг: название теста → Slack webhook URL
2. Создать scheduled job (cron / `schedule` skill в Claude Code) на 23:00
3. Скрипт: итерируется по тестам, дёргает report API, фильтрует < 80%, постит в Slack

---

## Полезные endpoints

```
GET  /api/v2/inbox-placement-tests?limit=50    # список тестов
POST /api/v2/inbox-placement-tests             # создать тест
GET  /api/v2/inbox-placement-tests/{id}        # детали теста
GET  /api/v2/inbox-placement-tests/{id}/report # результаты / доставляемость
```
