# magnum-cln: Sending Worker Fixes — защита лимитов и счётчики

## Проблема

Sending Worker (фоновый процесс отправки Telegram outreach сообщений) имел три критических бага:

1. **Превышение дневного лимита** — аккаунт с лимитом 10 сообщений отправлял 11-12, потому что параллельный batch не учитывал pending-сообщения. Несколько сообщений назначались на один аккаунт одновременно, и к моменту проверки лимита счётчик ещё не был обновлён.

2. **Сброс счётчиков при перезапуске** — при mid-day restart worker обнулял `messages_sent_today`, из-за чего аккаунты повторно отправляли сообщения сверх дневного лимита. Не было механизма определить, что это перезапуск в тот же день, а не начало нового дня.

3. **Отсутствие per-account spamblock tracking** — не было логики отслеживания consecutive spamblock errors по каждому аккаунту в привязке к кампании. Один PeerFloodError не отличался от серии, и аккаунт продолжал использоваться даже при системных проблемах.

## Решение

### cln.1 — Batch Limit Protection

При формировании batch в `_process_campaign()` worker теперь ведёт два in-memory словаря: `account_pending` (все pending-сообщения в batch) и `account_cold_pending` (только cold sends в batch). При выборе аккаунта для получателя проверяется `acc_cold_counts + account_cold_pending < effective_daily_limit`. Аккаунты сортируются по текущей нагрузке (pending), что обеспечивает равномерное распределение.

```python
# sending_worker.py:513-517
for acc in sorted(available_accounts, key=lambda a: account_pending.get(a.id, 0)):
    acc_cold = account_cold_counts.get(acc.id, 0) + account_cold_pending.get(acc.id, 0)
    if acc.id not in failed_for and acc_cold < get_effective_daily_limit(acc):
        account = acc
        break
```

При добавлении в batch счётчики инкрементируются:
```python
# sending_worker.py:569-573
account_pending[account.id] = account_pending.get(account.id, 0) + 1
if is_cold:
    account_cold_pending[account.id] = account_cold_pending.get(account.id, 0) + 1
```

### cln.2 — Daily Counter Reset с защитой от mid-day restart

Метод `_sync_daily_counters()` вызывается при старте worker. Он выполняет GROUP BY запрос к `TgOutreachMessage` с `status=SENT` и `sent_at >= сегодня (UTC)`, получая реальное количество отправленных сообщений за день по каждому аккаунту и кампании.

- Все счётчики сначала обнуляются, затем устанавливаются реальные значения из БД
- Spamblock counters (`consecutive_spamblock_errors`) сбрасываются **только** если `total_today == 0` (настоящий новый день)
- При mid-day restart (messages exist today) — счётчики синхронизируются, spamblock counters сохраняются

```python
# sending_worker.py:1001-1068
async def _sync_daily_counters(self):
    # COUNT sent messages per account today
    acc_counts = dict(await session.execute(
        select(TgOutreachMessage.account_id, func.count(TgOutreachMessage.id))
        .where(status == SENT, sent_at >= today_start)
        .group_by(TgOutreachMessage.account_id)
    ).all())

    # Reset spamblock only on true new day
    if total_today == 0:
        await session.execute(
            TgCampaignAccount.__table__.update().values(consecutive_spamblock_errors=0))
```

### cln.3 — Spamblock Logic: per-account threshold

Добавлено поле `consecutive_spamblock_errors` в `TgCampaignAccount` и `spamblock_errors_to_skip` в `TgCampaign` (default=5). Логика обработки статусов:

| Статус | Действие со счётчиком | Описание |
|---|---|---|
| `spamblocked` (PeerFloodError) | `+= 1` | Единственный статус, инкрементирующий счётчик |
| `sent` | `= 0` | Успешная отправка сбрасывает счётчик |
| `bounced` | `= 0` | Пользователь не найден — не спамблок |
| `flood` | `= 0` | FloodWaitError — таймаут, не спамблок |
| другие ошибки | `= 0` | Любая другая ошибка сбрасывает счётчик |

При достижении threshold (`consecutive_spamblock_errors >= spamblock_errors_to_skip`):
- Аккаунт переводится в `SPAMBLOCKED TEMPORARY`
- На следующий день `_sync_daily_counters()` обнуляет счётчик и аккаунт возвращается в работу

```python
# sending_worker.py:719-734
elif status == "spamblocked":
    if ca_link:
        ca_link.consecutive_spamblock_errors += 1
    threshold = campaign.spamblock_errors_to_skip or 5
    errors_count = ca_link.consecutive_spamblock_errors if ca_link else 1
    if errors_count >= threshold:
        account.status = TgAccountStatus.SPAMBLOCKED
        account.spamblock_type = TgSpamblockType.TEMPORARY
```

**Smart cascade** (cold messages): при спамблоке получатель возвращается в PENDING с `_failed_account_ids`, чтобы другой аккаунт повторил попытку. Если все аккаунты кампании перепробованы — FAILED.

**Emergency stop**: при 30 подряд глобальных спамблоках все активные кампании переводятся в PAUSED.

## Изменённые файлы

- `backend/app/services/sending_worker.py` — batch limit protection (строки 510-573), spamblock threshold logic (строки 719-763), daily counter sync (строки 1001-1068)
- `backend/app/models/telegram_outreach.py` — поля `consecutive_spamblock_errors` (TgCampaignAccount), `spamblock_errors_to_skip` (TgCampaign)

## Конфигурация

| Параметр | Модель | Default | Описание |
|---|---|---|---|
| `daily_message_limit` | TgAccount | — | Максимум сообщений в день для аккаунта |
| `daily_message_limit` | TgCampaign | — | Максимум сообщений в день для кампании |
| `spamblock_errors_to_skip` | TgCampaign | 5 | Порог consecutive PeerFloodError до SPAMBLOCKED TEMPORARY |
| `_EMERGENCY_THRESHOLD` | SendingWorker | 30 | Глобальный порог подряд спамблоков для emergency stop всех кампаний |
