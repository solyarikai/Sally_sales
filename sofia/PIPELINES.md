# Pipelines — Sales Engineer

Документация всех лидген-пайплайнов. Скрипты в `magnum-opus/scripts/sofia/`.

---

## 1. Universal Pipeline (основной)

**Скрипт**: `onsocial_universal_pipeline.py`
**Где запускать**: Hetzner (`ssh hetzner`), backend на localhost:8000
**Env**: `FINDYMAIL_API_KEY`, `SMARTLEAD_API_KEY`

### Полный цикл (12 шагов):
```
Gather → Dedup → Blacklist → Prefilter → Scrape → Classify → Verify → Export → People → FindyMail → Sequences → SmartLead
```

### Режимы запуска:
| Режим | Флаг | Что делает | Стоимость |
|-------|------|-----------|-----------|
| Clay ICP | `--mode structured --segment <slug>` | AI маппит ICP в Clay фильтры | ~$0.01/компания |
| Clay Keywords | `--mode keywords --filters '{...}'` | Явные keywords в Clay | ~$0.01/компания |
| Apollo | `--mode apollo --filters '{...}'` | Internal API через Puppeteer | БЕСПЛАТНО |
| Lookalike | `--mode lookalike --examples "a.com,b.com"` | Reverse-engineering фильтров | ~$0.01/компания |
| Expand | `--mode expand --base-run <id>` | Клон рана с новыми параметрами | зависит от режима |

### Gotchas:
- Backend должен работать на Hetzner перед запуском
- `--dry-run` для проверки параметров без API
- `--from-step people` для продолжения с любого шага
- `--re-analyze --run-id <id>` для повторной классификации
- НИКОГДА не активировать кампании через API
- A/B варианты — только в SmartLead UI

---

## 2. FindyMail → SmartLead

**Скрипт**: `findymail_to_smartlead.py` (есть в `magnum-opus/scripts/` и `sofia/scripts/`)
**Где запускать**: локально или Hetzner
**Env**: `FINDYMAIL_API_KEY`, `SMARTLEAD_API_KEY`

### Что делает:
CSV с контактами → обогащение email через FindyMail → создание кампании SmartLead

### Использование:
```bash
python3.11 findymail_to_smartlead.py \
  --input "targets.csv" \
  --campaign-name "c-OnSocial_SEGMENT #1 v1" \
  --sequence sequences/onsocial_default.json \
  --email-accounts 2718958,2718959,2718960 \
  --max-contacts 1500
```

### Флаги:
- `--skip-upload` — только enrichment, без SmartLead
- `--max-contacts N` — лимит контактов
- `--timezone` — таймзона кампании (default: America/New_York)

### Output:
- `<input> - emails.csv` — все контакты + Email/Verified
- `<input> - with_email.csv` — только с email
- GetSales CSV — контакты без email

### Gotchas:
- Авто-резюм при повторном запуске (progress в `/tmp/`)
- Em dashes (`—`) ломают email-клиенты → используй `-`
- `\n` → `<br>` для SmartLead API

---

## 3. GOD Pipeline (OnSocial)

**Скрипт**: `GOD_pipeline_onsocial_restored.py` (в `sofia/scripts/`)
**Где запускать**: Hetzner
**Env**: стандартные

### Что делает:
CSV компаний (Apollo/Clay) → классификация по ICP сегментам → targets.json + Google Sheets

### Шаги:
```
Load Blacklist → Load CSV → Deduplicate → Blacklist Filter → Deterministic Filter → AI Classify (сегменты: INFPLAT, IMAGENCY, AFFPERF, OTHER)
```

---

## 4. Apollo скрипты (поиск)

### Companies Search
**Скрипт**: `onsocial_apollo_companies_search.js`
**Стоимость**: БЕСПЛАТНО (internal API через Puppeteer)

```bash
node onsocial_apollo_companies_search.js \
  --keywords "influencer marketing platform" \
  --locations "United Kingdom,France"
```

### People Search
**Скрипт**: `onsocial_apollo_people_search.js`
**Стоимость**: БЕСПЛАТНО

```bash
node onsocial_apollo_people_search.js \
  --domains "impact.com,modash.io" \
  --titles "CEO,CTO,VP Marketing"
```

---

## 5. Clay скрипты

### TAM Export
**Скрипт**: `onsocial_clay_tam_export.js`
ICP текст → GPT-4o-mini маппит в Clay фильтры → Puppeteer stealth → экспорт

### Lookalike Export
**Скрипт**: `onsocial_clay_lookalike_export.js`
Домены-примеры → reverse-engineering фильтров → экспорт

### People Search
**Скрипт**: `onsocial_clay_people_search.js`
Поиск людей через Clay

---

## 6. Вспомогательные скрипты

| Скрипт | Что делает |
|--------|-----------|
| `targets_to_contacts.py` | Конвертация targets → контакты для аутрича |
| `upload_leads_to_campaign.py` | Загрузка CSV в существующую кампанию SmartLead |
| `upload_xlsx_to_getsales.py` | Загрузка в GetSales |
| `getsales_dedup_check.py` | Проверка дубликатов в GetSales |
| `export_score_campaigns.py` | Экспорт и скоринг кампаний |
| `build_smartlead_csvs.py` | Сборка CSV для SmartLead |

---

## Общие правила

- **Python**: `python3.11` локально, `python3` на Hetzner
- **Dual Save**: CSV + Google Sheets (naming: `[PROJECT] | [TYPE] | [SEGMENT] — [DATE]`)
- **Blacklist**: всегда проверять перед загрузкой
- **Активация кампаний**: ТОЛЬКО вручную в SmartLead UI
- **Новые скрипты**: создавать в `magnum-opus/scripts/sofia/`
