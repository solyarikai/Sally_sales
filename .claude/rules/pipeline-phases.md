# Pipeline Phase State Machine

## Фазы gathering_run (current_phase)

Порядок фаз в БД (`gathering_runs.current_phase`):

```
gathered → scope_approved → scraped → analyzed → awaiting_targets_ok → targets_approved
```

## Какой endpoint требует какую фазу

| Endpoint | Требуемая фаза | Что делает |
|----------|---------------|------------|
| POST `/runs/{id}/pre-filter` | `gathered` | Prefilter |
| POST `/runs/{id}/scrape` | `scope_approved` | Scrape |
| POST `/runs/{id}/analyze` | **`scraped`** | Classify (GPT) |
| POST `/runs/{id}/re-analyze` | **`awaiting_targets_ok`** | Re-classify |
| POST `/runs/{id}/prepare-verification` | `targets_approved` | FindyMail prep |

## ВАЖНО: /analyze — деструктивная операция

`POST /runs/{id}/analyze` немедленно запускает GPT-классификацию для ВСЕХ компаний в ране с переданным `prompt_text`. Даже тестовый вызов с заглушкой уничтожает правильно классифицированные targets.

**Никогда не тестировать `/analyze` с реальным run_id.** Для проверки endpoint — читай код или смотри backend логи.

## Ручной сброс фазы

Если нужно повторить шаг (например, classify завис и прервался):

```sql
UPDATE gathering_runs SET current_phase = 'scraped' WHERE id = {run_id};
```

Допустимые значения для сброса:
- `scraped` → позволяет запустить `/analyze` снова
- `awaiting_targets_ok` → позволяет запустить `/re-analyze`
- `targets_approved` → позволяет запустить export/upload

**Не сбрасывай фазу если не понимаешь зачем.** Неправильный сброс → backend запускает не тот шаг.

## upload_log.json — управление SmartLead кампанией

Файл: `~/magnum-opus-project/repo/state/onsocial/upload_log.json`

Pipeline читает его при `--from-step upload`. Если там есть `campaign_id` для сегмента — использует существующую кампанию. Иначе — создаёт новую.

Чтобы использовать конкретную кампанию:
```json
{
  "SOCIAL_COMMERCE": {
    "campaign_id": 3151592,
    "campaign_name": "c-OnSocial_SOCIAL_COMMERCE#C"
  }
}
```

Запиши это в upload_log.json ПЕРЕД запуском `--from-step upload`.

## enriched.json — контакты для upload

Файл: `~/magnum-opus-project/repo/state/onsocial/enriched.json`

`--from-step upload` читает контакты именно отсюда. `--apollo-csv` загружает в Step 9 cache (contacts.json), NOT сразу в enriched.json.

Формат записи:
```json
[
  {
    "first_name": "...", "last_name": "...", "email": "...",
    "title": "...", "company_name": "...", "domain": "...",
    "segment": "SOCIAL_COMMERCE", "linkedin_url": "...",
    "country": "...", "company_country": "...",
    "employees": "", "social_proof": ""
  }
]
```
