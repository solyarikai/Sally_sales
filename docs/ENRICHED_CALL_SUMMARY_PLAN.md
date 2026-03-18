# Enriched Call Summary — План реализации

## Проблема

Сейчас саммари звонков (Fireflies) хранятся as-is без контекста проекта. Система не учитывает переписку до звонка, статус лида в кампании, аналитику сегмента и знания проекта (ICP, продукты). Из-за этого follow-up после звонков делается вручную, без учёта полной картины.

## Цель

Создать enriched call summary — AI-саммари, которое объединяет транскрипт звонка с перепиской SmartLead/GetSales, аналитикой кампаний и знаниями проекта. На выходе: структурированный анализ + готовый драфт follow-up.

## Архитектура

```
                    ┌──────────────┐
                    │  Fireflies   │
                    │  Transcript  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
 ThreadMessage ────►│ ENRICHED     │◄──── OutreachStats
 (переписка)       │ CALL SUMMARY │      (аналитика)
                    │ SERVICE      │
 ProjectKnowledge──►│ Gemini 2.5   │◄──── Contact
 (ICP, KB)         │              │      (статус, воронка)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ enriched_    │
                    │ summary JSON │
                    │ + follow-up  │
                    │ draft        │
                    └──────────────┘
```

## Шаги реализации

### Шаг 1: Миграция — новые поля в CallTranscript

Файл: `backend/alembic/versions/YYYYMMDD_add_enriched_call_summary.py`

Добавить в модель `CallTranscript` (`backend/app/models/call_transcript.py`):

```python
enriched_summary = Column(JSON, nullable=True)       # Структурированный AI-анализ
enriched_at = Column(DateTime, nullable=True)         # Когда был сгенерирован
enrichment_model = Column(String(100), nullable=True) # Какая модель использовалась
enrichment_error = Column(Text, nullable=True)        # Ошибка если не удалось
```

Команды:
```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "add_enriched_call_summary"
alembic upgrade head
```

### Шаг 2: Сервис `call_analysis_service.py`

Файл: `backend/app/services/call_analysis_service.py`

#### 2.1 Сбор контекста

Функция `_build_call_context(session, transcript, contact, project)`:

1. **Переписка до звонка** — из `ThreadMessage` и `ContactActivity`:
   ```python
   # Все сообщения с этим контактом ДО даты звонка
   activities = await session.execute(
       select(ContactActivity)
       .where(ContactActivity.contact_id == contact.id)
       .where(ContactActivity.activity_at < transcript.date)
       .order_by(ContactActivity.activity_at)
   )
   ```

2. **Все ProcessedReply по этому контакту** — классификация, intent, warmth:
   ```python
   replies = await session.execute(
       select(ProcessedReply)
       .where(func.lower(ProcessedReply.lead_email) == contact.email.lower())
       .where(ProcessedReply.received_at < transcript.date)
       .order_by(ProcessedReply.received_at)
   )
   ```

3. **ReplyAnalysis** (если есть) — intent, warmth_score, interests, tags

4. **Аналитика кампании** — из `OutreachStats` и `Campaign`:
   ```python
   # Кампании контакта из platform_state
   campaign_ids = extract_campaign_ids(contact.platform_state)
   campaigns = await session.execute(
       select(Campaign).where(Campaign.id.in_(campaign_ids))
   )
   # Статистика по сегменту
   stats = await outreach_stats_service.get_project_stats(project.id)
   ```

5. **Знания проекта** — ICP, продукты, KB:
   ```python
   knowledge = await project_knowledge_service.get_summary(session, project.id)
   ```

6. **Предыдущие звонки** с этим контактом (если были):
   ```python
   prev_calls = await session.execute(
       select(CallTranscript)
       .where(CallTranscript.contact_id == contact.id)
       .where(CallTranscript.id != transcript.id)
       .order_by(CallTranscript.date)
   )
   ```

#### 2.2 Генерация enriched summary

Функция `async def generate_enriched_summary(session, transcript_id)`:

Промпт для Gemini 2.5 Pro (основная модель, fallback на GPT-4o):

```
SYSTEM:
Ты — аналитик продаж. Тебе дан транскрипт звонка с потенциальным клиентом
и полный контекст взаимодействия до этого звонка.

Твоя задача — создать структурированный анализ звонка, который поможет
менеджеру сделать максимально эффективный follow-up.

КОНТЕКСТ ПРОЕКТА:
{project_knowledge}  # ICP, продукты, сегменты

ИСТОРИЯ ПЕРЕПИСКИ ДО ЗВОНКА:
{conversation_history}  # Все ThreadMessage/ContactActivity до звонка

КЛАССИФИКАЦИЯ ПЕРЕПИСКИ:
{reply_analysis}  # intent, warmth, interests, tags

АНАЛИТИКА КАМПАНИИ:
- Кампания: {campaign_name}
- Сегмент: {segment}
- Reply rate по сегменту: {reply_rate}%
- Positive rate: {positive_rate}%
- Шаг последовательности, на котором ответил: {sequence_step}

ПРЕДЫДУЩИЕ ЗВОНКИ:
{previous_calls_summary}

ТРАНСКРИПТ ТЕКУЩЕГО ЗВОНКА:
{transcript_text}

Верни JSON:
{
  "executive_summary": "3-5 предложений: кто, о чём, итог",
  "pre_call_context": "Что было до звонка: как вышли на контакт, переписка, на каком шаге",
  "discussed_topics": [
    {"topic": "...", "details": "...", "related_product": "..."}
  ],
  "prospect_signals": {
    "positive": ["заинтересован в X", "спросил про pricing"],
    "negative": ["уже работает с конкурентом Y"],
    "neutral": ["попросил больше информации"]
  },
  "objections": [
    {"objection": "...", "our_response": "...", "resolved": true/false}
  ],
  "commitments": {
    "ours": ["отправить презентацию", "подготовить KP до пятницы"],
    "theirs": ["обсудить с командой", "вернуться на следующей неделе"]
  },
  "follow_up_actions": [
    {
      "action": "Отправить презентацию продукта",
      "deadline": "2026-03-19",
      "priority": "high",
      "type": "email"
    }
  ],
  "suggested_follow_up_message": {
    "subject": "...",
    "body": "..."
  },
  "warmth_assessment": {
    "before_call": 3,
    "after_call": 4,
    "reasoning": "Проявил интерес к ценообразованию, спросил о кейсах"
  },
  "status_recommendation": "negotiating_meeting",
  "tags": ["pricing-discussed", "competitor-mentioned"],
  "next_call_topics": ["Обсудить результаты пилота", "Познакомить с техдиром"]
}
```

#### 2.3 Формат ответа

Использовать `response_format={"type": "json_object"}` для гарантии валидного JSON.

Валидация через Pydantic-схему `EnrichedCallSummary` в `backend/app/schemas/call_transcript.py`.

### Шаг 3: Интеграция в pipeline

Файл: `backend/app/api/fireflies.py`

Вызывать enrichment после `_store_transcript()`:

```python
async def _process_webhook_transcript(meeting_id: str):
    # ... существующий код ...
    transcript = await _store_transcript(session, data, project_id, source="webhook")

    # NEW: Запустить enriched analysis в фоне
    if transcript and transcript.contact_id:
        asyncio.create_task(
            _enrich_transcript_safe(transcript.id)
        )

async def _enrich_transcript_safe(transcript_id: int):
    """Обёртка с error handling для фонового обогащения."""
    try:
        async with async_session_maker() as session:
            await call_analysis_service.generate_enriched_summary(session, transcript_id)
    except Exception as e:
        logger.error(f"Failed to enrich transcript {transcript_id}: {e}")
```

### Шаг 4: API эндпоинты

Файл: `backend/app/api/fireflies.py` (добавить к существующим)

```python
# Получить enriched summary
GET /fireflies/transcripts/{id}/enriched-summary

# Перегенерировать enriched summary (если контекст обновился)
POST /fireflies/transcripts/{id}/re-enrich

# Получить suggested follow-up message
GET /fireflies/transcripts/{id}/follow-up-draft
```

### Шаг 5: Автоматические действия после анализа

В `call_analysis_service.py` после генерации summary:

1. **Обновить Contact.status** если `status_recommendation` отличается:
   ```python
   if summary.status_recommendation != contact.status:
       await status_machine.transition_status(
           contact, summary.status_recommendation, source="call_analysis"
       )
   ```

2. **Создать follow-up ProcessedReply** (как в follow_up_service.py):
   ```python
   if summary.suggested_follow_up_message:
       follow_up = ProcessedReply(
           lead_email=contact.email,
           draft_reply=summary.suggested_follow_up_message.body,
           draft_subject=summary.suggested_follow_up_message.subject,
           category="interested",
           source="call_analysis",
           approval_status=None,  # Ждёт одобрения оператора
       )
   ```

3. **Создать Task** для оператора с action items:
   ```python
   for action in summary.follow_up_actions:
       await task_service.create_task(
           project_id=project.id,
           title=action["action"],
           due_date=action["deadline"],
           priority=action["priority"],
           source="call_analysis",
           related_contact_id=contact.id,
       )
   ```

4. **Обновить learning signals** — positive/negative сигналы в ProjectKnowledge:
   ```python
   if summary.prospect_signals:
       await project_knowledge_service.upsert(
           session, project.id,
           category="icp",
           key="call_signals",
           value=summary.prospect_signals,
           source="call_analysis"
       )
   ```

### Шаг 6: Frontend — отображение

Файл: `frontend/src/components/EnrichedCallSummary.tsx`

Компонент для отображения enriched summary на странице контакта:
- Executive summary блок
- Timeline: переписка → звонок → follow-up
- Карточки с commitments (наши / их)
- Follow-up actions с чекбоксами
- Кнопка "Отправить follow-up" (берёт suggested_follow_up_message)
- Warmth gauge (до/после звонка)

Встроить в:
- `ContactDetailPage` / `ContactDetailModal` — таб "Звонки"
- `ProjectPage` — секция "Последние звонки"

### Шаг 7: Re-enrichment при обновлении контекста

Добавить в `learning_service.py`:

После каждого learning cycle проверять, есть ли недавние CallTranscript без enriched_summary или с устаревшим (enriched_at < learning_cycle_at). Перегенерировать при необходимости.

## Зависимости между шагами

```
Шаг 1 (миграция) → Шаг 2 (сервис) → Шаг 3 (интеграция)
                                    → Шаг 4 (API)
                                    → Шаг 5 (авто-действия)
                                    → Шаг 6 (фронтенд)
                                    → Шаг 7 (re-enrichment)
```

Шаги 3-7 можно делать параллельно после шага 2.

## Ключевые файлы для изменения

| Файл | Действие |
|------|----------|
| `backend/app/models/call_transcript.py` | Добавить поля enriched_summary, enriched_at |
| `backend/app/services/call_analysis_service.py` | **НОВЫЙ** — основная логика |
| `backend/app/schemas/call_transcript.py` | Pydantic-схема EnrichedCallSummary |
| `backend/app/api/fireflies.py` | Добавить вызов enrichment + новые эндпоинты |
| `backend/app/services/follow_up_service.py` | Учитывать call-based follow-ups |
| `frontend/src/components/EnrichedCallSummary.tsx` | **НОВЫЙ** — UI компонент |
| `frontend/src/pages/ContactDetailPage.tsx` | Добавить таб звонков |
| `frontend/src/api/fireflies.ts` | Новые API-функции |

## Архитектурные правила (не забыть)

- Gemini 2.5 Pro — основная модель (лучше работает с длинным контекстом), fallback на GPT-4o
- Фоновая задача с error handling (правило #4 из architecture.mdc)
- Статус-переходы через status_machine.py (правило #7)
- Знания проекта через project_knowledge_service, не дублировать логику
- Reference examples через существующий _load_reference_examples()
- Кеш enriched_summary — не перегенерировать если контекст не менялся
