# Tier 1 Candidate Re-classify — Current State

**Status**: PAUSED on 2026-04-20. Can resume at any time.

## Что сделано

Переклассификация компаний из «other» (verdict='f') проекта 42 (OnSocial) против 5 новых гипотез: `SOCIAL_LISTENING`, `REVIEW_UGC`, `LOYALTY_COMMUNITY`, `AI_CONTENT_MARKETING`, `CREATOR_PLATFORM`.

Промт: [classify-prompt-tier1-candidates.md](./classify-prompt-tier1-candidates.md)
Промт на Hetzner: `/tmp/tier1_prompt.txt`

## Обработано

| analysis_run | gathering_run | linked | analyzed | targets | cost | status |
|--|--|--|--|--|--|--|
| 380 | 568 | 171 | 171 | 55 | $0.09 | ✅ completed |
| 381 | 569 | 4,600 | 1,950 | 73 | $0.88 | ⏸ paused @1950 |
| — | 570 | 4,600 | 0 | 0 | — | ⏸ not started |
| — | 571 | 4,600 | 0 | 0 | — | ⏸ not started |
| — | 572 | 4,600 | 0 | 0 | — | ⏸ not started |
| — | 573 | 4,112 | 0 | 0 | — | ⏸ not started |

**Всего классифицировано**: 2,121 из 22,683 (9.3%)
**Всего targets найдено**: 128
**Cost к этому моменту**: $0.97

## Распределение target'ов по сегментам

| Сегмент | Targets | Avg confidence |
|--|--|--|
| CREATOR_PLATFORM | 41 | 0.85 |
| AI_CONTENT_MARKETING | 30 | 0.88 |
| LOYALTY_COMMUNITY | 25 | 0.85 |
| REVIEW_UGC | 23 | 0.87 |
| SOCIAL_LISTENING | 9 | 0.87 |

**Hit rate**: 128/2121 = 6.0% overall (32% на NEW:* bucket, 3.7% на NOT_A_MATCH/OTHER bucket — как и ожидалось).

Экспорт: [OS_Tier1Targets_Combined_2026-04-20.csv](../../exports/OS_Tier1Targets_Combined_2026-04-20.csv)

## Как резюмнуть

### Вариант 1 — доработать batch 1 (gathering_run 569) с того же места

Backend сам не умеет «resume» для partial analysis_run. Простой путь — создать новый analysis_run на том же gathering_run=569, с тем же промтом. Он переклассифицирует ВСЕ 4600, включая 1950 уже готовых (overwrite). Стоимость ~$2.

Проще: пропустить batch 1, двинуть на 570-573 (там 0 работы, чистый старт).

### Вариант 2 — запустить остальные batch'и (570-573)

На Hetzner:

```bash
ssh hetzner
# Скрипт уже лежит: /tmp/tier1_batch_run.py — но он создаёт новые runs.
# Чтобы просто запустить /analyze на существующих 570-573:
for RUN in 570 571 572 573; do
  docker exec leadgen-postgres psql -U leadgen -d leadgen -c "UPDATE gathering_runs SET status='running', paused_at=NULL WHERE id=$RUN"
  python3 -c "
import httpx
with open('/tmp/tier1_prompt.txt') as f: prompt = f.read()
r = httpx.post(
  'http://localhost:8000/api/pipeline/gathering/runs/$RUN/analyze',
  params={'prompt_text': prompt, 'model': 'gpt-4o-mini', 'prompt_name': 'Tier1 Bulk (run $RUN)'},
  headers={'X-Company-ID': '1'}, timeout=7200
)
print('$RUN:', r.status_code)
"
done
```

Ожидаемо: ~4 часа, ~$10, ~700 новых targets при 4% hit rate.

### Вариант 3 — выкинуть паузу и взять что есть

1. Пометить 570-573 как `cancelled` (они идеально в этом состоянии — 0 работы).
2. Работать с 128 target'ами из CSV.

Команда:
```sql
UPDATE gathering_runs SET status='cancelled', notes=CONCAT(notes,' | CANCELLED 2026-04-20') WHERE id IN (570,571,572,573);
UPDATE gathering_runs SET status='cancelled', notes=CONCAT(notes,' | CANCELLED 2026-04-20') WHERE id=569;
```

## База запросов для повторного анализа

### Весь список target'ов (все Tier1 сегменты, обе analysis_runs):
```sql
SELECT ar.segment, ar.confidence, dc.domain, dc.name, ar.reasoning
FROM analysis_results ar
JOIN discovered_companies dc ON dc.id=ar.discovered_company_id
WHERE ar.analysis_run_id IN (380, 381) AND ar.is_target=true
ORDER BY ar.segment, ar.confidence DESC;
```

### По одному сегменту:
```sql
SELECT ar.confidence, dc.domain, dc.name, dc.website_url, ar.reasoning
FROM analysis_results ar
JOIN discovered_companies dc ON dc.id=ar.discovered_company_id
WHERE ar.analysis_run_id IN (380, 381)
  AND ar.is_target=true
  AND ar.segment='CREATOR_PLATFORM'   -- или любой из пяти
ORDER BY ar.confidence DESC;
```

### Оценка прогресса если резюмнёшь:
```sql
SELECT ar.id, ar.status, ar.total_analyzed, ar.targets_found, ar.total_cost_usd
FROM analysis_runs ar
WHERE ar.scope_filter->>'gathering_run_id' IN ('569','570','571','572','573')
ORDER BY ar.id;
```

## Что ещё остаётся нетронутым в «other»

- **~20,391 компаний** не прогоняли через Tier1 (распределены по 570/571/572/573 + несколько сотен в 569 не доделанных)
- Эти компании всё ещё имеют `latest_analysis_verdict='f'` с их ОРИГИНАЛЬНЫМ segment label (NOT_A_MATCH / OTHER / fashion clusters / etc). Т.е. запросы типа «все NOT_A_MATCH для project 42» продолжают работать без изменений.
- После резюма — `latest_analysis_verdict/segment` у этих 20K будут обновлены Tier1 классификацией (старое сохранится в `analysis_results.raw_output`).
