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
# sending_worker.py:604-609
for acc in sorted(available_accounts, key=lambda a: account_pending.get(a.id, 0)):
    acc_cold = account_cold_counts.get(acc.id, 0) + account_cold_pending.get(acc.id, 0)
    acc_hourly = account_hourly_cold.get(acc.id, 0) + account_cold_pending.get(acc.id, 0)
    if acc.id not in failed_for and acc_cold < get_effective_daily_limit(acc) and acc_hourly < MAX_COLD_PER_HOUR_PER_ACCOUNT:
        account = acc
        break
```

Дополнительно проверяется почасовой лимит: `MAX_COLD_PER_HOUR_PER_ACCOUNT = 2` — не более 2 cold сообщений в час на аккаунт.

При добавлении в batch счётчики инкрементируются:
```python
# sending_worker.py:661-665
account_pending[account.id] = account_pending.get(account.id, 0) + 1
if is_cold:
    cold_in_batch += 1
    account_cold_pending[account.id] = account_cold_pending.get(account.id, 0) + 1
```

### cln.2 — Daily Counter Reset с защитой от mid-day restart

Метод `_sync_daily_counters()` вызывается при старте worker. Он выполняет GROUP BY запрос к `TgOutreachMessage` с `status=SENT` и `sent_at >= сегодня (UTC)`, получая реальное количество отправленных сообщений за день по каждому аккаунту и кампании.

- Все счётчики сначала обнуляются, затем устанавливаются реальные значения из БД
- Spamblock counters (`consecutive_spamblock_errors`) сбрасываются **только** если `total_today == 0` (настоящий новый день)
- При mid-day restart (messages exist today) — счётчики синхронизируются, spamblock counters сохраняются

```python
# sending_worker.py:1175-1242
async def _sync_daily_counters(self):
    async with async_session_maker() as session:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Count today's sent messages per account (single GROUP BY query)
        acc_counts = dict((await session.execute(
            select(TgOutreachMessage.account_id, func.count(TgOutreachMessage.id))
            .where(TgOutreachMessage.status == TgMessageStatus.SENT,
                   TgOutreachMessage.sent_at >= today_start)
            .group_by(TgOutreachMessage.account_id)
        )).all())

        # Also count per campaign
        camp_counts = dict((await session.execute(...)).all())

        total_today = sum(acc_counts.values()) if acc_counts else 0

        # Reset all to 0, then set real counts from DB
        await session.execute(TgAccount.__table__.update().values(messages_sent_today=0))
        for acc_id, cnt in acc_counts.items():
            await session.execute(TgAccount.__table__.update()
                .where(TgAccount.__table__.c.id == acc_id)
                .values(messages_sent_today=cnt))

        # Reset spamblock only on true new day
        if total_today == 0:
            await session.execute(
                TgCampaignAccount.__table__.update().values(consecutive_spamblock_errors=0))
```

### cln.3 — Spamblock Logic: per-account threshold

Добавлено поле `consecutive_spamblock_errors` в `TgCampaignAccount`. Порог задаётся константой `SPAMBLOCK_THRESHOLD = 5` в `sending_worker.py`. Логика обработки статусов:

| Статус | Действие со счётчиком | Описание |
|---|---|---|
| `spamblocked` (PeerFloodError) | `+= 1` | Единственный статус, инкрементирующий счётчик |
| `sent` | `= 0` | Успешная отправка сбрасывает счётчик |
| `bounced` | `= 0` | Пользователь не найден — не спамблок |
| `flood` | `= 0` | FloodWaitError — таймаут, не спамблок |
| другие ошибки | `= 0` | Любая другая ошибка сбрасывает счётчик |

При достижении threshold (`consecutive_spamblock_errors >= SPAMBLOCK_THRESHOLD`):
- Аккаунт переводится в `SPAMBLOCKED TEMPORARY`
- На следующий день `_sync_daily_counters()` обнуляет счётчик и аккаунт возвращается в работу

```python
# sending_worker.py:832-846
elif status == "spamblocked":
    if ca_link:
        ca_link.consecutive_spamblock_errors += 1
    threshold = SPAMBLOCK_THRESHOLD  # hardcoded constant = 5
    errors_count = ca_link.consecutive_spamblock_errors if ca_link else 1
    if errors_count >= threshold:
        account.status = TgAccountStatus.SPAMBLOCKED
        account.spamblock_type = TgSpamblockType.TEMPORARY
        account.spamblocked_at = datetime.utcnow()
        # Cascade: reassign ALL pending recipients bound to this account
        await self._cascade_reassign_all(campaign, account, session)
```

**Smart cascade** (cold messages): при спамблоке получатель возвращается в PENDING с `_failed_account_ids`, чтобы другой аккаунт повторил попытку. Если все аккаунты кампании перепробованы — FAILED.

**Emergency stop**: при 30 подряд глобальных спамблоках все активные кампании переводятся в PAUSED.

## Изменённые файлы

- `backend/app/services/sending_worker.py` — batch limit protection (строки 565-665), spamblock threshold logic (строки 832-879), daily counter sync (строки 1175-1242)
- `backend/app/models/telegram_outreach.py` — поля `consecutive_spamblock_errors` (TgCampaignAccount), `spamblock_errors_to_skip` (TgCampaign)

## Конфигурация

| Параметр | Модель | Default | Описание |
|---|---|---|---|
| `daily_message_limit` | TgAccount | — | Максимум сообщений в день для аккаунта |
| `daily_message_limit` | TgCampaign | — | Максимум сообщений в день для кампании |
| `SPAMBLOCK_THRESHOLD` | sending_worker.py (constant) | 5 | Порог consecutive PeerFloodError до SPAMBLOCKED TEMPORARY |
| `MAX_COLD_PER_HOUR_PER_ACCOUNT` | sending_worker.py (constant) | 2 | Максимум cold сообщений в час на аккаунт |
| `_EMERGENCY_THRESHOLD` | SendingWorker | 30 | Глобальный порог подряд спамблоков для emergency stop всех кампаний |
