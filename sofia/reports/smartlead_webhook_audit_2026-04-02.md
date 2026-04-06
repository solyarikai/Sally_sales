# Отчёт: потеря ~41% входящих реплаев в SmartLead webhook pipeline

**Дата:** 2 апреля 2026
**Период анализа:** 26 марта - 2 апреля 2026 (7 дней)
**Обнаружено:** при расследовании отсутствия Telegram-уведомления для 4 реплаев (Jenny Merrill, Sara Jett, Sam Ellis, Jeremy Meadows)

---

## Суть проблемы

Webhook handler в `smartlead.py:356` обрабатывает только события с `event_type == "EMAIL_REPLY"`. SmartLead при автокатегоризации реплая (Out Of Office, Not Interested и т.д.) часто отправляет **только** `LEAD_CATEGORY_UPDATED` без парного `EMAIL_REPLY`. Эти события содержат полный текст реплая в payload (`reply_message`, `lastReply`, `history`), но наш код их игнорирует - помечает как `processed=True` и не отправляет в reply pipeline.

В результате: нет записи в `processed_replies`, нет классификации, нет драфта ответа, нет Telegram-уведомления.

---

## Цифры за 7 дней

### Входящие webhook-события от SmartLead

| Тип события | Кол-во | Что с ними происходит |
|---|---|---|
| `EMAIL_REPLY` | 676 | Обрабатываются reply processor - Telegram |
| `LEAD_CATEGORY_UPDATED` (с телом реплая) | 884 | Сохраняются в `webhook_events`, но **не обрабатываются** |

### Результат обработки

| Метрика | Кол-во | % |
|---|---|---|
| `EMAIL_REPLY` - создана `processed_reply` | 662 / 676 | 98% |
| `EMAIL_REPLY` - отправлен Telegram | 630 / 676 | 93% |
| `CATEGORY_UPDATED` - покрыты парным `EMAIL_REPLY` | 188 / 884 | 21% |
| `CATEGORY_UPDATED` - **не обработаны, потеряны** | **696 / 884** | **79%** |

### Итого по уникальным лидам

| | Кол-во | % |
|---|---|---|
| Обработано (есть `processed_reply`) | 982 | 59% |
| **Потеряно (нет `processed_reply`)** | **682** | **41%** |
| Всего уникальных реплаев | ~1 664 | 100% |

---

## Что именно теряется для каждого потерянного реплая

1. **Telegram-уведомление** - оператор не узнаёт о реплае в реальном времени
2. **Классификация** (interested / not_interested / out_of_office / wrong_person) - не выполняется
3. **Автодрафт ответа** - не генерируется
4. **Запись в `processed_replies`** - реплай не появляется в Replies UI
5. **Обновление `ContactActivity`** - история контакта неполная
6. **Логирование в Google Sheets** (если настроено для automation) - не происходит

Единственное, что сохраняется - сырой payload в таблице `webhook_events` (можно восстановить задним числом).

---

## Затронутые проекты и кампании

Проблема по всем проектам и всем 55 вебхукам. Топ-10 по потерям:

| Webhook (кампания) | Потеряно реплаев |
|---|---|
| SquareFi - ES - RDMs | 123 |
| Squarefi Evgeny - RDMs (CRM Sync) | 95 |
| Squarefi Evgeny - RDMs (ручной webhook) | 92 |
| Easystaff - HQ in Russia 2 | 70 |
| Rizzult Travel 20.03.26 | 27 |
| Inxy - iGaming Services | 21 |
| Rizzult Fintech 20.03.26 | 19 |
| Palark - Easy PL 11/03 | 17 |
| Palark - DevOps segmentation | 17 |
| TFP - Pitti Uomo general | 17 |

---

## Хронология

| Дата | Потерянных реплаев |
|---|---|
| 26 марта | 10 |
| **27 марта** | **203** (резкий скачок) |
| 28 марта | 39 |
| 29 марта | 15 |
| 30 марта | 107 |
| 31 марта | 103 |
| 1 апреля | 102 |
| 2 апреля (неполный день) | 92 |

Скачок 27 марта предполагает изменение поведения на стороне SmartLead API - стали чаще отправлять `LEAD_CATEGORY_UPDATED` вместо `EMAIL_REPLY` при автокатегоризации.

---

## Корневая причина

Файл `smartlead.py`, строки 319-366:

```python
is_reply = actual_event_type in REPLY_EVENT_TYPES  # line 320

if is_reply and lead_email:                         # line 356
    full_payload = _build_reply_payload(data)
    asyncio.create_task(_process_reply_safe(...))
else:
    webhook_event.processed = True                  # line 363 - просто помечает и забывает
```

`LEAD_CATEGORY_UPDATED` не входит в `REPLY_EVENT_TYPES`, поэтому всегда попадает в `else` - сохраняется, но не обрабатывается.

---

## Предлагаемый фикс

В webhook handler добавить проверку: если `LEAD_CATEGORY_UPDATED` содержит `reply_message` или `lastReply` в payload, обрабатывать как реплай:

```python
# After line 320
is_reply = actual_event_type in REPLY_EVENT_TYPES

# NEW: LEAD_CATEGORY_UPDATED with reply body = treat as reply
if not is_reply and actual_event_type == "LEAD_CATEGORY_UPDATED":
    if data.get("reply_message") or data.get("lastReply") or data.get("last_reply"):
        is_reply = True
```

**Защита от дублей** уже встроена: `processed_replies` имеет unique constraint по content hash (`uq_processed_reply_content`). Если для того же лида уже пришёл `EMAIL_REPLY` и создал запись - повторная обработка из `CATEGORY_UPDATED` просто поймает constraint и пропустит.

**Оценка риска:** низкий. Логика дедупликации уже покрывает случай двойной обработки. Единственное изменение - расширение условия `is_reply`.

---

## Восстановление потерянных данных

Все 696 потерянных реплаев сохранены в `webhook_events` с полным payload. После деплоя фикса можно прогнать их через replay endpoint или одноразовый скрипт для создания `processed_replies` + отправки Telegram-уведомлений (по желанию, с учётом возраста реплаев).
