# TAM Gathering System — God Architecture (Архитектура системы сбора TAM)

## Что мы строим

Переиспользуемая система, которая **запоминает всё** о сборе TAM (Total Addressable Market — общий адресуемый рынок):
- Какие фильтры были применены в каком источнике (Apollo, Clay, Sales Navigator и т.д.)
- Какие компании были найдены по каким фильтрам
- Контент сайтов, собранный скрапером (несколько страниц, версионированный с TTL — Time To Live, срок жизни кэша)
- Прогоны AI-анализа (разные модели, разные промпты, всё сохраняется)
- Проверки по blacklist (чёрному списку) против CRM/кампаний
- Approval gates (ворота одобрения) перед шагами, которые тратят деньги

**MCP-ready** (готово к подключению через MCP — Model Context Protocol): Каждый источник — подключаемый adapter-модуль. Сейчас это Puppeteer-эмуляторы; завтра пользователи подключают свои API-ключи Apollo/Clay. Слой БД один и тот же.

**Переиспользуемо между проектами**: EasyStaff Global, OnSocial, Inxy, любой будущий проект — те же таблицы, тот же pipeline (конвейер обработки).

**Запуск только на Hetzner**: Все скрипты, скраперы, миграции, запросы к БД выполняются на production-сервере (46.62.210.24). Локальные машины — только для редактирования кода. Claude Code подключается к Hetzner по SSH для любого выполнения.

---

## Pipeline Flow — Строго линейный, пропуски запрещены

```
GATHER+DEDUP → BLACKLIST → ★ CP1 → PRE-FILTER → SCRAPE → ANALYZE → ★ CP2 → VERIFY → ★ CP3 → GOD_SEQ → PUSH
     авто          авто     СТОП       авто        авто      авто     СТОП   заблок.   СТОП    авто    заблок.
                          подтверж.                                   gate в БД         gate в БД
                          проект +
                          scope
```

**CP** = Checkpoint (контрольная точка). Всего их 3.

CP1 — настоящее подтверждение проекта. Показывает кампании и контакты проекта, чтобы оператор подтвердил: он в правильном проекте И scope (область охвата) blacklist корректна.
Это нельзя обойти — это approval_gate в базе данных.

**State machine фаз** (машина состояний, поле `gathering_run.current_phase`):
```
gathered → awaiting_scope_ok → scope_approved → filtered → scraped →
analyzed → awaiting_targets_ok → targets_approved → awaiting_verify_ok →
verify_approved → verified → pushed
```

На фазах `awaiting_*` прогон физически заблокирован. В БД существует запись `approval_gate`.
Единственный путь вперёд — `POST /approval-gates/{gate_id}/approve`. Ни один код-path не пропускает это.
Переживает крэши, перезагрузки сессий, рестарты сервера — состояние в базе данных.

### Детали фаз

| # | Фаза | Стоимость | Авто? | Что делает |
|---|------|-----------|-------|------------|
| 1 | **GATHER** (сбор) | разная | авто | Выполняет adapter, получает сырой список компаний из источника |
| 2 | **DEDUP** (дедупликация) | $0 | авто | Нормализация доменов, сопоставление с существующими DiscoveredCompanies (найденные компании), создание source_links (связей с источниками). "Already known" = домен существует в discovered_companies для ЭТОГО проекта из предыдущего прогона. Ещё НЕ прошёл blacklist — это следующий шаг. |
| 3 | **BLACKLIST** (чёрный список) | $0 | авто | Проверка по scope проекта: CRM + project_blacklist + enterprise_blacklist |
| — | **★ CHECKPOINT 1** | — | **СТОП** | **Подтверждение проекта + обзор blacklist.** Показывает: имя/ID проекта, общее число контактов, ВСЕ активные кампании (имя, платформа, количество лидов), разбивку отказов по кампаниям, enterprise blacklist, предупреждения по другим проектам. Оператор подтверждает: "Да, это мой проект, и scope правильный." **Принудительно в коде — нельзя обойти.** Неправильный проект → отмена прогона. Неправильная кампания → исправить campaign_filters, перезапустить blacklist. |
| 4 | **PRE-FILTER** (предварительная фильтрация) | $0 | авто | Детерминированный отказ: офлайн-индустрии (ресторан, отель, строительство), мусорные домены (.gov, .edu), шаблоны мусора. БЕЗ AI. Отклоняет 40-60%. |
| 5 | **RESOLVE** (разрешение доменов) | $0-мало | авто | Для компаний без домена: LinkedIn URL → домен. Имя компании → поиск в Google. Пропускается, если домен уже известен. |
| 6 | **SCRAPE** (скрапинг сайтов) | $0 (httpx) | авто | Сбор контента сайта. Проверка TTL — пропуск, если данные свежие. Несколько страниц. **Дёшево — одобрение не нужно.** |
| 7 | **ANALYZE** (AI-анализ) | ~$0.01-0.05 | авто | AI-анализ (GPT-4o-mini). Оценки: industry_match (соответствие индустрии), size_match (размер), service_model (модель сервиса). **Дёшево — одобрение не нужно.** |
| — | **★ CHECKPOINT 2** | — | **СТОП** | **Оператор просматривает список целевых компаний (targets).** Должен видеть: каждую компанию, отмеченную как target, её confidence score (оценку уверенности), reasoning (обоснование), segment (сегмент). Оператор может принять, отклонить отдельные компании, переопределить вердикты. Только после подтверждения оператором pipeline продолжает работу. Здесь оператор убеждается, что AI не "галлюцинировал". **Никакие credits не тратятся до одобрения.** |
| 8 | **VERIFY** (верификация email) | $$$ | **ЗАБЛОК.** | Проверка email через FindyMail. **Это дорогой шаг.** Запускается только для одобренных оператором targets. |
| — | **★ CHECKPOINT 3** | — | **СТОП** | **Оператор одобряет расходы на FindyMail.** Должен видеть: сколько email проверить, примерную стоимость, какие компании. Оператор может убрать компании перед верификацией. |
| 9 | **GOD_SEQUENCE** (генерация последовательности писем) | ~$0.08 | авто | Генерация 5-шаговой email-последовательности из 3-уровневой базы знаний: универсальные паттерны + бизнес-знания (тот же sender_company) + ICP проекта. Оператор просматривает черновик перед push. `POST /generate-sequence/` → `POST /approve/` |
| 10 | **PUSH** (отправка в SmartLead) | $0 | **ЗАБЛОК.** | `POST /generated/{id}/push/` создаёт кампанию в SmartLead (статус DRAFT — черновик) с выходом GOD_SEQUENCE. Оператор добавляет лидов и активирует. |

### Что означают "new" и "duplicate" на каждой фазе

Это критически важно. Слова меняют значение в зависимости от того, где ты находишься:

| После фазы | "New" (новый) означает | "Duplicate" (дубликат) означает | "Rejected" (отклонён) означает |
|------------|------------------------|-------------------------------|-------------------------------|
| **GATHER+DEDUP** | Домен не в discovered_companies для ЭТОГО проекта из любого предыдущего прогона | Домен уже известен из предыдущего прогона (получает новый source_link, а не новую запись) | Ничего — фильтрация ещё не применялась |
| **BLACKLIST** | Прошёл все проверки blacklist | Н/Д | В активных кампаниях ЭТОГО проекта, ИЛИ в project blacklist, ИЛИ в enterprise blacklist. **НЕ в других проектах — это предупреждение, не отказ.** |
| **PRE-FILTER** | Прошёл паттерн-матчинг | Н/Д | Офлайн-индустрия, мусорный домен, мусорный паттерн |
| **ANALYZE** | AI говорит is_target=true | Н/Д | AI говорит "не target для этого ICP" |
| **CHECKPOINT 2** | Оператор подтвердил как target | Н/Д | Оператор отклонил / переопределил |

### Восстановление после крэша сессии

Всё состояние checkpoint сохраняется в БД (gathering_run.current_phase + таблица approval_gates).

**Что происходит если сессия Claude Code падает на checkpoint 1:**
1. Следующая сессия: Claude Code читает CLAUDE.md, где написано "сначала проверь незавершённые прогоны"
2. Запрос: `GET /runs?project_id=X` → находит прогон с `current_phase=awaiting_scope_ok`
3. Запрос: `GET /approval-gates?project_id=X` → находит pending gate с `gate_type=scope_verification`
4. Читает `gate.scope`, где хранятся ПОЛНЫЕ детали blacklist (rejected_domains, warning_domains, разбивка по кампаниям)
5. Показывает те же результаты checkpoint 1 оператору
6. Оператор одобряет → pipeline продолжает

**Данные не теряются.** JSON в поле `scope` gate хранит всё необходимое для восстановления отображения checkpoint.

### Ошибки скрапинга отображаются

Когда запускается анализ, компании без текста со скрапнутого сайта ПРОПУСКАЮТСЯ (не анализируются). Ответ анализа включает:
- `total_eligible`: сколько компаний могло быть проанализировано
- `skipped_no_scraped_text`: сколько пропущено из-за неудачного скрапинга
- `total_analyzed`: сколько реально проанализировано

Claude Code ОБЯЗАН сообщить это на checkpoint 2: "Проанализировано 300 из 500 eligible (подходящих) компаний. 200 пропущено (скрапинг не удался — нет текста сайта)."

### Почему этот порядок не обсуждается

1. **BLACKLIST перед PRE-FILTER**: Blacklist — проектная бизнес-логика (кампании, CRM). Pre-filter — обобщённый паттерн-матчинг. Бизнес-логика первая — если компания уже в твоём outreach (рассылке), какая разница, совпадает ли она с офлайн-паттерном.

2. **CHECKPOINT 1 после BLACKLIST**: Оператор ОБЯЗАН убедиться, что система правильно определила кампании проекта. Если campaign_filters настроены неправильно, blacklist неверный. Лучше поймать это до траты времени на 10K компаний.

3. **SCRAPE и ANALYZE автоматические (без checkpoint)**: httpx-скрапинг бесплатный. Анализ GPT-4o-mini стоит ~$0.01-0.05 за 500 компаний. Не стоит прерывать оператора ради $0.03.

4. **CHECKPOINT 2 после ANALYZE**: Здесь оператор видит реальный список targets. До этой точки всё одноразовое. После — начинают тратиться деньги.

5. **CHECKPOINT 3 перед VERIFY**: FindyMail — реальные деньги ($0.01/email × 1000 emails = $10). Оператор должен одобрить точный список и стоимость.

6. **Нет Apollo API в дефолтном потоке**: Дефолтное обогащение — Apollo UI emulator (Puppeteer) — скрапит контактные данные из UI Apollo бесплатно. Apollo API тратит credits. Если credits нужны, это отдельный approval gate.

### Что Claude Code должен делать на каждом checkpoint

**CHECKPOINT 1 (после blacklist)**:
```
Показать оператору:
- "Проверено 1,800 компаний против кампаний [Имя проекта]"
- "КАМПАНИИ ВАШЕГО ПРОЕКТА, которые вызвали отказы:"
  - Campaign: "EasyStaff - Dubai Agencies v3" → 45 доменов, 120 контактов
  - Campaign: "EasyStaff - UAE IT Companies" → 12 доменов, 38 контактов
- "Enterprise blacklist: 28 доменов (конкуренты)"
- "Project blacklist: 3 домена (заблокированы вручную)"
- "ПРОШЛИ: 1,712 компаний готовы к следующей фазе"
- Если cross_project=true: "ПРЕДУПРЕЖДЕНИЕ: 89 доменов также в проекте Inxy (не отклонены)"

Спросить: "Scope проекта выглядит корректно? Продолжить с pre-filter?"
НЕ ПРОДОЛЖАТЬ пока оператор не скажет "да".
```

**CHECKPOINT 2 (после analyze)**:
```
Показать оператору:
- "Проанализировано 542 компании с помощью [имя промпта]"
- "TARGETS: 180 компаний (33% target rate, средний confidence 0.72)"
- Топ-10 targets с доменом, именем, confidence, сегментом, обоснованием
- "ОТКЛОНЕНЫ: 362 компании (не соответствуют ICP)"
- Нижние 5 отказов (borderline — пограничные) с обоснованием

Спросить: "Просмотрите список targets. Уберите false positives (ложные срабатывания), затем подтвердите для перехода к верификации FindyMail."
НЕ ПРОДОЛЖАТЬ пока оператор не подтвердит список targets.
```

**CHECKPOINT 3 (перед FindyMail)**:
```
Показать оператору:
- "Готово к верификации emails для 180 целевых компаний"
- "Расчётная стоимость FindyMail: ~$X.XX (X emails × $0.01)"
- "Разбивка: 450 контактов найдено, 380 с emails для проверки"

Спросить: "Одобрить расходы FindyMail ~$X.XX?"
НЕ ВЫЗЫВАТЬ FindyMail пока оператор не скажет "да".
```

---

## Что система знает о каждом проекте

Gathering-система не работает в вакууме. Она читает существующие знания проекта для принятия умных решений.

### Контекст проекта (уже есть в БД — переиспользуй, не пересоздавай)

| Источник | Таблица/Поле | Как Gathering это использует |
|----------|-------------|------------------------------|
| **ICP Definition** (описание идеального клиента) | `projects.target_segments`, `projects.target_industries` | → AI маппит на фильтры источника. "Агентства <50 сотр. в ОАЭ" становится Apollo location + seniority + size фильтрами |
| **Segments** (сегменты) | `kb_segments` (гибкий data JSON на сегмент) | → Каждый сегмент может иметь СВОЮ конфигурацию gathering. Сегмент "Dubai Agencies" → apollo.companies.emulator с фильтрами ОАЭ. Сегмент "AU-PH Corridor" → clay.people.emulator с фильтрами по филиппинскому языку |
| **Products** (что мы продаём) | `kb_products` | → Промпт AI-анализа: "Нужна ли этой компании {product}?" |
| **Competitors** (конкуренты) | `kb_competitors` (домены, сильные/слабые стороны) | → Авто-blacklist доменов конкурентов. Не собирай компании, уже использующие конкурента |
| **Case Studies** (кейсы) | `kb_case_studies` (индустрия, размер, проблема, решение) | → Lookalike-поиск: "Найди компании, похожие на этих клиентов" |
| **Company Profile** (профиль нашей компании) | `kb_company_profile` | → Контекст AI-анализа: "Мы — {company}, предлагаем {products}" |
| **Project Knowledge** (знания проекта) | `project_knowledge` (category=icp/outreach/contacts/gtm) | → Детальный контекст ICP, правила outreach, GTM-стратегия |
| **Existing Contacts** (существующие контакты) | `contacts` + `campaigns` (CRM) | → Blacklist: не перенацеливай компании, которые уже в outreach |
| **Enterprise Blacklist** | `project_blacklist` + `enterprise_blacklist.json` | → Жёсткое исключение перед любой обработкой |
| **Past Gathering Runs** (прошлые прогоны) | `gathering_runs` (эта система) | → "Не повторяй фильтры, которые дали <5% target rate" |

### Режимы ввода оператора

Когда оператор (или MCP-агент) запускает gathering run, он может предоставить ввод несколькими способами:

**Mode 1: Natural Language** (естественный язык — самый простой, оптимизирован для MCP)
```
"Find 5000 digital agencies in UAE with <100 employees"
```
→ AI маппит на фильтры, используя ICP проекта + контекст сегмента
→ Предлагает лучший источник (Apollo для широкого, Clay для точечного)
→ Возвращает оценку результатов + стоимость

**Mode 2: Structured Filters** (структурированные фильтры — для опытных операторов, точно)
```json
{
  "source_type": "apollo.people.emulator",
  "filters": {
    "person_locations": ["Dubai, United Arab Emirates"],
    "person_seniorities": ["founder", "c_suite"],
    "organization_num_employees_ranges": ["1,10", "11,50", "51,100"]
  }
}
```
→ Минует AI-маппинг, прямое выполнение

**Mode 3: Lookalike** (похожие — на основе case studies или существующих клиентов)
```
"Find companies similar to: frizzon.ae, 10xbrand.com, zopreneurs.com"
```
→ Обратный инжиниринг паттернов (индустрия, размер, локация, tech stack)
→ Генерация фильтров, соответствующих паттерну
→ Частично уже реализовано: `reverse_engineering_service.py`

**Mode 4: Expand/Repeat** (расширение/повтор — итерация по предыдущим прогонам)
```
"Run the same search as gathering_run #42 but for Singapore instead of Dubai"
```
→ Копирование фильтров, изменение location
→ Filter dedup (проверка хэша) предотвращает случайные дубли

### Связь Gathering Run ↔ Segment

Каждый gathering run МОЖЕТ быть привязан к конкретному сегменту:

```
gathering_runs.segment_id  FK(kb_segments) NULL
```

Это позволяет системе:
- Отслеживать, какие сегменты были собраны (а какие нет)
- Считать TAM на уровне сегмента: "Сегмент Dubai Agencies: найдено 5,150 компаний, проанализировано 1,200, targets 340, обогащено 89"
- Предлагать недостаточно собранные сегменты: "AU-PH Corridor имеет 0 gathering runs — стоит начать"

---

## Data Layer — Новые таблицы

### 1. `gathering_runs` — Filter Memory (память фильтров, ключевой отсутствующий элемент)

Каждое выполнение поиска = одна запись. Запоминает ТОЧНО какие фильтры были применены.

```
gathering_runs
├── id                    SERIAL PK
├── project_id            FK(projects) NOT NULL
├── company_id            FK(companies) NOT NULL        -- tenant scope (изоляция по компании-владельцу)
│
│   ── ИДЕНТИФИКАЦИЯ ИСТОЧНИКА ──
├── source_type           VARCHAR(100) NOT NULL           -- свободная строка: "apollo.companies.emulator", "clay.people.api" и т.д.
│                                                         -- конвенция: {platform}.{target}.{method}
│                                                         -- НЕ enum — новые источники добавляются без изменений БД
├── source_label          VARCHAR(255)                    -- читаемое имя: "Apollo People Search (Puppeteer)"
├── source_subtype        VARCHAR(100)                    -- опциональная стратегия: "strategy_a" | "strategy_b" | "industry_tags"
│
│   ── ПАМЯТЬ ФИЛЬТРОВ ──
├── filters               JSONB NOT NULL                 -- source-специфичная схема (см. Filter Schemas)
├── filter_hash           VARCHAR(64) NOT NULL           -- SHA256 от отсортированного canonical JSON
│                                                        -- dedup: одинаковые фильтры = одинаковый hash
│
│   ── СОСТОЯНИЕ ВЫПОЛНЕНИЯ ──
├── status                VARCHAR(30) DEFAULT 'pending'  -- pending|running|completed|failed|cancelled|paused
├── started_at            TIMESTAMPTZ
├── completed_at          TIMESTAMPTZ
├── duration_seconds      INTEGER                        -- время выполнения (wall clock)
│
│   ── СВОДКА РЕЗУЛЬТАТОВ ──
├── raw_results_count     INTEGER DEFAULT 0              -- всего из источника до dedup
├── new_companies_count   INTEGER DEFAULT 0              -- чистые новые записи DiscoveredCompany
├── duplicate_count       INTEGER DEFAULT 0              -- уже известные (связаны через company_source_links)
├── rejected_count        INTEGER DEFAULT 0              -- не прошли blacklist/offline-фильтр
├── error_count           INTEGER DEFAULT 0
│
│   ── СТОИМОСТЬ ──
├── credits_used          INTEGER DEFAULT 0
├── total_cost_usd        NUMERIC(10,4) DEFAULT 0
│
│   ── КОНТЕКСТ ──
├── segment_id            FK(kb_segments) NULL           -- какой целевой сегмент обслуживает этот прогон
├── pipeline_run_id       FK(pipeline_runs) NULL         -- если часть автоматизированного pipeline
├── triggered_by          VARCHAR(100)                   -- operator | scheduler | mcp_agent | claude_code
├── input_mode            VARCHAR(30) DEFAULT 'structured' -- structured | natural_language | lookalike | expand
├── input_text            TEXT                           -- оригинальный ввод оператора (режим NL)
├── notes                 TEXT
├── error_message         TEXT
│
│   ── RAW OUTPUT (отладка/переобработка) ──
├── raw_output_ref        TEXT                           -- путь к файлу или S3 key для полного вывода
├── raw_output_sample     JSONB                          -- первые 50 результатов, закэшированные в БД
│
├── created_at            TIMESTAMPTZ DEFAULT now()
├── updated_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX ix_gr_project_source     (project_id, source_type, status)
├── INDEX ix_gr_filter_hash        (project_id, filter_hash)
├── INDEX ix_gr_pipeline           (pipeline_run_id)
└── INDEX ix_gr_created            (project_id, created_at DESC)
```

#### Source Architecture — Open/Closed Principle (принцип открытости/закрытости)

**Ключевое архитектурное решение**: БД **source-agnostic** (не зависит от источника). Она НЕ знает про Apollo, Clay или конкретную платформу. Добавление нового источника = новый класс adapter + регистрация. Ноль изменений БД.

**Почему не типизированные модели для каждого источника в БД?**
- Только у Apollo есть: People UI, Companies UI, People API, Org API — 4 варианта
- У Clay: Companies UI, Companies API, People UI, People API — ещё 4
- Sales Navigator, Google Maps, LinkedIn, Crunchbase, Indeed... — растёт и дальше
- Каждая платформа регулярно добавляет новые фильтры — обновления модели = миграции = простой
- Взрыв комбинаций: платформы × цели × методы = слишком много моделей

**God-подход**: Три измерения описывают любой источник:

| Измерение | Колонка | Примеры |
|-----------|---------|---------|
| **Platform** (платформа) | `source_platform` | apollo, clay, sales_navigator, google_maps, crunchbase, csv |
| **Target** (цель) | `source_target` | companies, people |
| **Method** (метод) | `source_method` | api, emulator, manual |

`source_type` = `{platform}.{target}.{method}` — напр. `apollo.companies.emulator`, `clay.people.api`

Но `source_type` — просто **свободный VARCHAR** — система никогда его не парсит. Семантикой владеет adapter. Завтра ты добавляешь `indeed.jobs.api` и ничего не меняется в БД.

#### Дизайн фильтров — БД всё равно

```
filters JSONB NOT NULL
```

Вот и всё. БД хранит то, что adapter положил. Она никогда не запрашивает отдельные поля фильтров. Использует filters для:
1. **Store** (хранение) — записать один раз при старте gathering run
2. **Display** (отображение) — прочитать и показать оператору в UI
3. **Hash** (хэш) — SHA256 для обнаружения дублей (одинаковые фильтры = одинаковый хэш)
4. **Re-execute** (повторное выполнение) — передать обратно adapter без изменений

**Нет Pydantic-валидации на уровне БД.** Валидация — работа adapter.

#### Валидация на уровне Adapter (не БД)

Каждый adapter определяет СВОЮ Pydantic-модель. Это код adapter, не код схемы:

```python
class GatheringAdapter(ABC):
    source_type: str                  # "apollo.companies.emulator"
    filter_model: Type[BaseModel]     # собственный Pydantic-класс adapter

    async def validate(self, raw_filters: dict) -> BaseModel:
        """Валидация через модель adapter. Все модели используют extra='allow'."""
        return self.filter_model(**raw_filters)
```

Каждая filter-модель adapter имеет `class Config: extra = "allow"` — неизвестные поля сохраняются. Когда Apollo добавляет новый фильтр, он проходит без изменений кода. Когда adapter обновляется для явной обработки — старые записи всё ещё загружаются.

**Текущие adapters и их фильтры** (код adapter, НЕ схема БД — этот список растёт без изменений БД):

##### Apollo (4 adapter)

| Adapter | source_type | Ключевые фильтры |
|---------|-------------|-------------------|
| People UI | `apollo.people.emulator` | person_locations[], person_seniorities[], organization_num_employees_ranges[], q_organization_name, organization_industry_tag_ids[], person_titles[], exclude_keywords[], strategy, max_pages |
| Companies UI | `apollo.companies.emulator` | organization_locations[], organization_industry_tag_ids[], q_keywords, organization_num_employees_ranges[], sort_by_field, max_pages |
| Org API | `apollo.companies.api` | q_organization_keyword_tags[], organization_locations[], organization_num_employees_ranges[], max_pages, per_page |
| People API | `apollo.people.api` | domains[], person_titles[], limit_per_domain, reveal_personal_emails |

##### Clay (4 adapter)

| Adapter | source_type | Ключевые фильтры |
|---------|-------------|-------------------|
| Companies UI | `clay.companies.emulator` | industries[], industries_exclude[], sizes[], types[], country_names[], country_names_exclude[], annual_revenues[], description_keywords[], description_keywords_exclude[], minimum/maximum_member_count, icp_text |
| Companies API | `clay.companies.api` | Те же поля, что и UI, прямой вызов API вместо Puppeteer |
| People UI | `clay.people.emulator` | domains[], use_titles, job_title, name, countries[], cities[], schools[], languages[] |
| People API | `clay.people.api` | Те же поля, что и UI, прямой вызов API |

**Лимит Clay 5,000**: Внутренний для adapter. Когда estimated_total > 5,000, adapter создаёт НЕСКОЛЬКО `gathering_runs` (по одному на geo split — разделение по географии). Все делят один `pipeline_run_id`. JSON `filters` включает `_geo_split_label` для отслеживания. Для остальной системы это прозрачно.

##### Другие (расширяемые — добавляй новые без изменений БД)

| Adapter | source_type | Ключевые фильтры |
|---------|-------------|-------------------|
| Sales Navigator | `sales_navigator.companies.emulator` | search_url, company_headcount[], geography[], industry[], annual_revenue[], seniority_level[], function[] |
| Google Maps | `google_maps.companies.api` | query, location, radius_km, type, min_rating |
| Crunchbase | `crunchbase.companies.api` | categories[], locations[], funding_rounds[], employee_count, founded_after |
| **Google Sheets** | `google_sheets.companies.manual` | sheet_url, gid, column_mapping (авто-определяется из заголовков), skip_rows |
| CSV Import | `csv.companies.manual` | file_name, file_url, column_mapping, row_count |
| Manual | `manual.companies.manual` | domains[], source_description |
| Google SERP | `google.companies.api` | queries[], max_pages, geo, language (существующий flow) |

**Google Sheets adapter**: Члены команды вручную собирают лидов в Apollo/Clay/LinkedIn, вставляют в Google Sheets. Подаёшь URL таблицы → pipeline обрабатывает (dedup, scrape, analyze). Авто-определение маппинга колонок из заголовков (domain/website/url, company/name/organization, linkedin, employees, industry, country, city, email). Таблица должна быть расшарена "Anyone with link" (доступ по ссылке).

**Добавление нового модуля завтра** (напр. `indeed.jobs.api`):
1. Написать класс `IndeedJobsAdapter` со своей Pydantic filter-моделью
2. Зарегистрировать в `ADAPTER_REGISTRY["indeed.jobs.api"] = IndeedJobsAdapter`
3. Готово. БД без изменений. UI автоматически обнаруживает через `/gathering/sources` endpoint.

### 2. `company_source_links` — Multi-Source Dedup Bridge (мост дедупликации из нескольких источников)

Решает проблему: "Acme.com найдена поиском по ключевым словам Apollo, поиском по seniority Apollo, И экспортом Clay TAM."

```
company_source_links
├── id                      SERIAL PK
├── discovered_company_id   FK(discovered_companies, CASCADE) NOT NULL
├── gathering_run_id        FK(gathering_runs, CASCADE) NOT NULL
├── source_rank             INTEGER                     -- позиция в результатах источника (1-я, 50-я и т.д.)
├── source_data             JSONB                       -- сырая запись из этого источника для этой компании
├── source_confidence       FLOAT                       -- оценка релевантности от источника
├── found_at                TIMESTAMPTZ DEFAULT now()
│
├── UNIQUE (discovered_company_id, gathering_run_id)
├── INDEX (gathering_run_id)
└── INDEX (discovered_company_id)
```

**Как работает dedup**:
1. GatheringRun #1 находит домен `acme.com` → создаёт DiscoveredCompany + company_source_link(run=1)
2. GatheringRun #2 находит `acme.com` снова → находит существующую DC по домену → создаёт только новый link(run=2)
3. `SELECT COUNT(DISTINCT gathering_run_id) FROM company_source_links WHERE discovered_company_id = X` = "найдена 2 источниками"
4. `source_data` сохраняет, что каждый источник сказал об этой компании (разное число сотрудников, индустрии и т.д.)

### 3. `company_scrapes` — Версионированный контент сайтов с TTL

Несколько страниц на компанию. Версионированно. Re-scraping (повторный сбор) на основе TTL.

```
company_scrapes
├── id                      SERIAL PK
├── discovered_company_id   FK(discovered_companies, CASCADE) NOT NULL
├── url                     TEXT NOT NULL                -- https://acme.com/about
├── page_path               VARCHAR(255) DEFAULT '/'    -- /, /about, /contact, /team, /careers
├── raw_html                TEXT                         -- сырой HTML (макс 100KB)
├── clean_text              TEXT                         -- извлечённый читаемый текст
├── metadata                JSONB                        -- {title, description, language, cyrillic_ratio, word_count, og_tags}
├── scraped_at              TIMESTAMPTZ DEFAULT now()
├── ttl_days                INTEGER DEFAULT 180          -- 6 месяцев по умолчанию
├── expires_at              TIMESTAMPTZ                  -- вычисляется: scraped_at + interval(ttl_days)
├── is_current              BOOLEAN DEFAULT true         -- последняя версия для этой (company, page_path)
├── version                 INTEGER DEFAULT 1            -- инкрементируется при re-scrape
├── scrape_method           VARCHAR(50) DEFAULT 'httpx'  -- httpx | crona | puppeteer | apify
├── scrape_status           VARCHAR(30) DEFAULT 'success' -- success | error | timeout | blocked | redirect | empty | js_only
├── error_message           TEXT
├── http_status_code        INTEGER
├── html_size_bytes         INTEGER
├── text_size_bytes         INTEGER
├── created_at              TIMESTAMPTZ DEFAULT now()
│
├── INDEX (discovered_company_id, page_path, is_current)
├── INDEX (discovered_company_id) WHERE is_current = true
├── INDEX (expires_at) WHERE is_current = true           -- планировщик re-scrape
└── INDEX (scrape_status)
```

**TTL re-scrape**: Планировщик запрашивает `WHERE is_current = true AND expires_at < now()`. При re-scrape:
1. Старая запись: `is_current = false`
2. Новая запись: `is_current = true, version = old.version + 1`
3. Все исторические scrapes сохраняются — можно сравнивать изменения сайта со временем

**Обратная совместимость**: Новый код пишет в `company_scrapes`. Также копирует последнюю главную страницу (`page_path='/'`) в `discovered_companies.scraped_html/scraped_text/scraped_at` для существующих путей кода.

### 4a. `gathering_prompts` — Переиспользуемые шаблоны AI-промптов

Один и тот же промпт переиспользуется во многих прогонах анализа. Дедуплицируется по SHA256-хэшу. Отслеживает эффективность per-prompt.

```
gathering_prompts
├── id                    SERIAL PK
├── company_id            FK(companies) NOT NULL
├── project_id            FK(projects) NULL              -- NULL = глобальный/общий промпт
├── name                  VARCHAR(255) NOT NULL           -- "EasyStaff UAE Agency ICP v2"
├── prompt_text           TEXT NOT NULL
├── prompt_hash           VARCHAR(64) NOT NULL UNIQUE     -- SHA256, одинаковый текст = одинаковый промпт
├── category              VARCHAR(50) DEFAULT 'icp_analysis'  -- icp_analysis | segment_classification | pre_filter | enrichment
├── model_default         VARCHAR(100) DEFAULT 'gpt-4o-mini'
├── version               INTEGER DEFAULT 1
├── parent_prompt_id      FK(gathering_prompts) NULL      -- цепочка версий для итераций
│
│   ── ОТСЛЕЖИВАНИЕ ЭФФЕКТИВНОСТИ (обновляется после каждого прогона анализа) ──
├── usage_count           INTEGER DEFAULT 0
├── avg_target_rate       FLOAT                           -- targets / total analyzed (доля целевых)
├── avg_confidence        FLOAT
├── total_companies_analyzed  INTEGER DEFAULT 0
│
├── created_by            VARCHAR(100)
├── is_active             BOOLEAN DEFAULT true
├── created_at            TIMESTAMPTZ DEFAULT now()
├── updated_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX (company_id, project_id)
└── INDEX (company_id, category)
```

**Жизненный цикл промпта**:
1. Оператор пишет промпт → `get_or_create_prompt()` создаёт запись (или находит существующую по хэшу)
2. Прогон анализа ссылается на промпт через FK `prompt_id`
3. После завершения прогона → `update_prompt_stats()` пересчитывает эффективность
4. Дашборд: "Какой промпт имеет лучший target rate?" → сортировка по avg_target_rate

**Итерация версий**: При улучшении промпта устанавливается `parent_prompt_id` на старую версию. Обе остаются рабочими; система отслеживает, какая версия работает лучше.

### 4b. `analysis_runs` + `analysis_results` — Версионирование AI-анализа

Несколько проходов анализа с разными моделями/промптами. Сравнение результатов. Всё хранится.

```
analysis_runs
├── id                    SERIAL PK
├── project_id            FK(projects) NOT NULL
├── company_id            FK(companies) NOT NULL
├── prompt_id             FK(gathering_prompts) NULL      -- ссылка на переиспользуемый промпт
├── model                 VARCHAR(100) NOT NULL           -- gemini-2.5-pro | gpt-4o-mini | gpt-4o | claude-sonnet-4
├── prompt_hash           VARCHAR(64) NOT NULL            -- SHA256 текста промпта
├── prompt_text           TEXT NULL                       -- inline fallback если нет prompt_id
├── scope_type            VARCHAR(50) DEFAULT 'batch'   -- batch | single | re_analysis | comparison
├── scope_filter          JSONB                         -- {gathering_run_id: 5} или {status: "new"} или {company_ids: [1,2,3]}
├── status                VARCHAR(30) DEFAULT 'pending' -- pending | running | completed | failed | cancelled
├── started_at            TIMESTAMPTZ
├── completed_at          TIMESTAMPTZ
├── total_analyzed        INTEGER DEFAULT 0
├── targets_found         INTEGER DEFAULT 0
├── rejected_count        INTEGER DEFAULT 0
├── avg_confidence        FLOAT
├── total_cost_usd        NUMERIC(10,4) DEFAULT 0
├── total_tokens          INTEGER DEFAULT 0
├── triggered_by          VARCHAR(100)
├── error_message         TEXT
├── created_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX (project_id, status)
├── INDEX (project_id, model)
└── INDEX (project_id, prompt_hash)

analysis_results
├── id                      SERIAL PK
├── analysis_run_id         FK(analysis_runs, CASCADE) NOT NULL
├── discovered_company_id   FK(discovered_companies, CASCADE) NOT NULL
├── is_target               BOOLEAN DEFAULT false
├── confidence              FLOAT                       -- 0.0-1.0
├── segment                 VARCHAR(100)                -- имя совпавшего сегмента
├── reasoning               TEXT                        -- объяснение AI
├── scores                  JSONB                       -- {industry: 0.9, size: 0.7, service: 0.6, digital: 0.8}
├── raw_output              TEXT                        -- полный ответ AI (для отладки)
├── override_verdict        BOOLEAN                     -- ручное переопределение оператором
├── override_reason         TEXT
├── overridden_at           TIMESTAMPTZ
├── tokens_used             INTEGER
├── cost_usd                NUMERIC(10,6)
├── created_at              TIMESTAMPTZ DEFAULT now()
│
├── UNIQUE (analysis_run_id, discovered_company_id)
├── INDEX (discovered_company_id)
└── INDEX (analysis_run_id, is_target)
```

**Сравнение двух прогонов анализа**:
```sql
SELECT dc.domain, dc.name,
  a1.is_target AS run1, a1.confidence AS conf1, a1.reasoning AS why1,
  a2.is_target AS run2, a2.confidence AS conf2, a2.reasoning AS why2
FROM discovered_companies dc
JOIN analysis_results a1 ON a1.discovered_company_id = dc.id AND a1.analysis_run_id = :run1
JOIN analysis_results a2 ON a2.discovered_company_id = dc.id AND a2.analysis_run_id = :run2
WHERE a1.is_target != a2.is_target  -- только расхождения
ORDER BY ABS(a1.confidence - a2.confidence) DESC;
```

### 5. `approval_gates` — Операторские checkpoint (контрольные точки)

Pipeline останавливается перед шагами, тратящими credits. Оператор просматривает scope + расчётную стоимость, затем одобряет/отклоняет.

```
approval_gates
├── id                    SERIAL PK
├── project_id            FK(projects) NOT NULL
├── pipeline_run_id       FK(pipeline_runs) NULL
├── gathering_run_id      FK(gathering_runs) NULL
├── gate_type             VARCHAR(50) NOT NULL          -- pre_scrape_crona | pre_analysis | pre_enrichment | pre_verification | pre_push
├── gate_label            VARCHAR(255) NOT NULL         -- "Одобрить 150 компаний для обогащения Apollo (~$4.50)"
├── scope                 JSONB NOT NULL                -- {count: 150, company_ids: [...], estimated_cost_usd: 4.50, estimated_credits: 150}
├── status                VARCHAR(30) DEFAULT 'pending' -- pending | approved | rejected | expired
├── decided_by            VARCHAR(100)
├── decided_at            TIMESTAMPTZ
├── decision_note         TEXT
├── expires_at            TIMESTAMPTZ                   -- авто-истечение если не принято решение
├── created_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX (project_id, status)
└── INDEX (status) WHERE status = 'pending'
```

**Когда создаются gates**:
- `pre_scrape_crona`: Crona тратит credits — gate перед batch-скрапингом через Crona
- `pre_analysis`: AI-анализ тратит токены — gate перед batch-анализом GPT/Gemini
- `pre_enrichment`: Обогащение Apollo стоит 1 credit/человек — gate перед enrich_apollo_batch
- `pre_verification`: FindyMail тратит credits — gate перед verify_emails_batch
- `pre_push`: Финальный обзор перед push в SmartLead/GetSales

**httpx-скрапинг бесплатный** — gate не нужен. Только шаги, тратящие credits, получают gates.

---

## Расширения существующих таблиц

### `discovered_companies` — Новые колонки

```python
# Отслеживание множественных источников
source_count             = Column(Integer, default=1)          # сколько gathering_runs нашли это
first_found_by           = Column(Integer, ForeignKey('gathering_runs.id'))

# Кэш CRM blacklist
blacklist_checked_at     = Column(DateTime(timezone=True))
in_active_campaign       = Column(Boolean, default=False)
campaign_ids_active      = Column(JSONB)                       # [campaign_id_1, ...]
crm_contact_id           = Column(Integer, ForeignKey('contacts.id'))  # если уже в CRM

# Ссылка на последний анализ
latest_analysis_run_id   = Column(Integer, ForeignKey('analysis_runs.id'))
latest_analysis_verdict  = Column(Boolean)                     # кэшированный is_target из последнего прогона
latest_analysis_segment  = Column(String(100))                 # кэшированный segment
```

### `search_jobs` — Новая колонка

```python
gathering_run_id = Column(Integer, ForeignKey('gathering_runs.id'))
```

---

## CRM Blacklist — Быстрый поиск в scope проекта

### Ключевое архитектурное решение: Blacklisting в scope проекта

**Проблема**: Компания X получает outreach от EasyStaff RU (проект 40, предложение payroll). Inxy (проект 10, крипто-платежи) начинает gathering и находит Компанию X. Должна ли она быть в blacklist?

**Ответ: НЕТ.** Разные проекты продают разные продукты разным ICP. Компания X может легитимно получать outreach от обоих проектов — это разные value propositions (ценностные предложения). Авто-блокировка между проектами искусственно уменьшила бы TAM.

**Правило**: Только кампании, принадлежащие ТОМУ ЖЕ проекту, вызывают авто-отказ. Кампании других проектов показываются как предупреждения (никогда не авто-отказ).

### Слои проверки Blacklist (по порядку)

| # | Слой | Scope | Действие | Что ловит |
|---|------|-------|----------|-----------|
| 1 | **Project blacklist** | Per-project (по проекту) | Авто-отказ | Таблица `project_blacklist` — ручные баны оператором |
| 2 | **Same-project campaigns** (кампании того же проекта) | Per-project | Авто-отказ | Контакты с доменами в активных кампаниях ЭТОГО проекта |
| 3 | **Enterprise blacklist** | Global (глобальный) | Авто-отказ | `enterprise_blacklist.json` — конкуренты, забаненные организации |
| 4 | **Cross-project campaigns** (кампании других проектов) | All projects | **Только предупреждение** | Домены в кампаниях ДРУГИХ проектов (информационно) |

### Что видит оператор

Для каждого отклонённого домена ответ включает:

```json
{
  "rejected_domains": [
    {
      "domain": "acme.com",
      "company_name": "Acme Corp",
      "reason": "same_project_campaign",
      "detail": "3 контакта в 2 кампаниях",
      "campaigns": ["EasyStaff - Dubai Agencies v3", "EasyStaff - UAE IT Companies"],
      "contact_count": 3
    }
  ],
  "warning_domains": [
    {
      "domain": "bigcorp.com",
      "company_name": "BigCorp",
      "other_project_name": "Inxy",
      "other_project_id": 10,
      "other_contact_count": 5,
      "other_campaigns": ["Inxy - Crypto Companies Q1"]
    }
  ]
}
```

**Почему это важно**: Если система неправильно назначила кампанию не тому проекту, оператор может увидеть это в детальной разбивке и исправить маппинг campaign → project.

### Materialized View (материализованное представление, scope проекта)

```sql
CREATE MATERIALIZED VIEW active_campaign_domains AS
SELECT DISTINCT
  lower(c.domain) AS domain,
  c.project_id,
  p.name AS project_name,
  array_agg(DISTINCT camp.id) AS campaign_ids,
  array_agg(DISTINCT camp.name) AS campaign_names,
  count(DISTINCT c.id) AS contact_count
FROM contacts c
JOIN projects p ON p.id = c.project_id
JOIN campaigns camp ON camp.project_id = c.project_id AND camp.status = 'active'
WHERE c.domain IS NOT NULL AND c.domain != ''
GROUP BY lower(c.domain), c.project_id, p.name;

CREATE UNIQUE INDEX ON active_campaign_domains(domain, project_id);
CREATE INDEX ON active_campaign_domains(project_id);
```

**Проверка того же проекта**: `WHERE domain = ANY(:domains) AND project_id = :pid`
**Проверка других проектов**: `WHERE domain = ANY(:domains) AND project_id != :pid`

**Refresh** (обновление): После синхронизации кампаний в `crm_scheduler.py` + после любого push кампании. `REFRESH MATERIALIZED VIEW CONCURRENTLY` (без блокировок).

### Edge Cases (пограничные случаи)

| Сценарий | Поведение |
|----------|----------|
| Домен в кампаниях проекта A, gathering для проекта B | **Предупреждение** (не отказ) — разные value prop |
| Домен в кампаниях проекта A, gathering для проекта A | **Отказ** — уже в outreach |
| Домен в enterprise blacklist | **Отказ** независимо от проекта |
| Домен в project blacklist проекта A, gathering для проекта B | **Не отказ** — blacklist per-project |
| Кампания ошибочно назначена проекту | Оператор видит имена кампаний в деталях → может исправить маппинг |
| У контакта NULL project_id | Игнорируется — неназначенные контакты не вызывают blacklist |

### Также проверить: DiscoveredCompanies уже проанализированные

```sql
-- Компании уже в системе для ЭТОГО проекта (не глобально)
SELECT DISTINCT domain FROM discovered_companies
WHERE domain = ANY(:domains) AND project_id = :pid AND status != 'REJECTED'
```

Это предотвращает повторную обработку компаний из предыдущих gathering runs в том же проекте.

---

## MCP Adapter Pattern (паттерн адаптеров для MCP)

### Base Class (базовый класс)

```python
class GatheringAdapter(ABC):
    """Базовый класс для всех gathering source adapters.

    Система source-agnostic. БД хранит непрозрачный JSONB фильтров.
    Каждый adapter владеет своей filter-схемой и логикой выполнения.
    Добавление нового источника = написать adapter + зарегистрировать. Ноль изменений БД.
    """

    source_type: str                              # "apollo.companies.emulator"
    filter_model: Optional[Type[BaseModel]]       # Pydantic-модель (опционально — может быть None для полностью динамических)

    @abstractmethod
    async def validate(self, raw_filters: dict) -> dict:
        """Валидация и нормализация фильтров. Возвращает очищенный dict. Поднимает исключение при невалидных."""

    @abstractmethod
    async def estimate(self, filters: dict) -> EstimateResult:
        """Оценка стоимости/результатов без выполнения."""

    @abstractmethod
    async def execute(self, filters: dict, on_progress: Callable = None) -> GatheringResult:
        """Выполнить gathering. Возвращает список компаний + метаданные."""

    def get_filter_schema(self) -> Optional[dict]:
        """JSON Schema для регистрации MCP-инструмента. None если полностью динамический."""
        if self.filter_model:
            return self.filter_model.model_json_schema()
        return None

    def get_capabilities(self) -> dict:
        """Что может этот adapter. Используется UI и MCP для обнаружения."""
        return {
            "source_type": self.source_type,
            "has_estimate": True,       # может оценить до выполнения
            "has_filter_schema": self.filter_model is not None,
            "cost_model": "free",       # free | per_result | per_page | per_credit
            "requires_auth": False,     # нужен API-ключ в integration_settings
        }
```

### Adapter Registry — Open for Extension (реестр, открытый для расширения)

```python
# Глобальный реестр — adapters самостоятельно регистрируются при импорте
ADAPTER_REGISTRY: dict[str, Type[GatheringAdapter]] = {}

def register_adapter(cls: Type[GatheringAdapter]) -> Type[GatheringAdapter]:
    """Декоратор. @register_adapter на классе adapter авто-регистрирует его."""
    ADAPTER_REGISTRY[cls.source_type] = cls
    return cls

def get_adapter(source_type: str) -> GatheringAdapter:
    cls = ADAPTER_REGISTRY.get(source_type)
    if not cls:
        raise ValueError(f"Unknown source: {source_type}. Available: {sorted(ADAPTER_REGISTRY.keys())}")
    return cls()

def list_adapters() -> list[dict]:
    """Возвращает все зарегистрированные adapters + capabilities. Используется эндпоинтом /gathering/sources."""
    return [get_adapter(st).get_capabilities() for st in sorted(ADAPTER_REGISTRY.keys())]
```

### Пример: Добавление нового источника (Ноль изменений БД)

```python
# backend/app/services/gathering_adapters/indeed_jobs.py

@register_adapter
class IndeedJobsAdapter(GatheringAdapter):
    source_type = "indeed.jobs.api"
    filter_model = IndeedJobsFilters  # Pydantic-модель с Indeed-специфичными полями

    async def validate(self, raw_filters):
        return IndeedJobsFilters(**raw_filters).model_dump()

    async def estimate(self, filters):
        # Вызов Indeed API с флагом dry_run
        return EstimateResult(estimated_companies=500, estimated_credits=0, cost_usd=0)

    async def execute(self, filters, on_progress=None):
        # Вызов Indeed API, нормализация результатов в стандартный company dict
        ...
```

Вот и всё. Система обнаруживает его через реестр. UI показывает в dropdown источников. MCP предоставляет как инструмент.

### Внутренности Adapter (НЕ в БД — прозрачно для pipeline)

- **Лимит Clay 5K**: Adapter авто-разбивает по geo, создаёт несколько `gathering_runs`
- **Пагинация Apollo**: Adapter итерирует страницы внутренне
- **Rate limiting** (ограничение частоты): Внутреннее per adapter (Apollo 0.3s, Clay export timing)
- **Auth** (аутентификация): Puppeteer adapters обрабатывают логин. API adapters читают ключи из `integration_settings`
- **Retry/backoff** (повтор/откат): Внутреннее — adapter обрабатывает 429, таймауты и т.д.

---

## Gathering Service — Orchestrator (оркестратор)

### `gathering_service.py`

```python
class GatheringService:
    """Оркестрирует полный TAM gathering pipeline."""

    # ── GATHER (сбор) ──
    async def start_gathering(
        self, project_id: int, source_type: str, filters: dict,
        triggered_by: str = "operator", notes: str = None
    ) -> GatheringRun:
        """Создать GatheringRun, валидировать фильтры, выполнить adapter, сохранить результаты."""

    # ── DEDUP (дедупликация) ──
    async def dedup_and_store(
        self, gathering_run_id: int, companies: list[dict]
    ) -> DedupeResult:
        """Нормализация доменов, проверка существующих DiscoveredCompanies, создание/связывание."""

    # ── BLACKLIST (чёрный список — детерминированный, $0) ──
    async def run_blacklist_check(
        self, gathering_run_id: int
    ) -> BlacklistResult:
        """Проверка vs project_blacklist, enterprise_blacklist, CRM mat.view, существующих DC."""

    # ── SCRAPE (скрапинг) ──
    async def scrape_companies(
        self, gathering_run_id: int, pages: list[str] = ['/'],
        method: str = 'httpx', force: bool = False
    ) -> ScrapeResult:
        """Скрапинг контента сайтов. Пропуск если текущий не-истёкший scrape существует (если force=True — принудительно)."""

    # ── ANALYZE (анализ) ──
    async def start_analysis(
        self, project_id: int, model: str, prompt_text: str,
        scope_filter: dict, triggered_by: str = "operator"
    ) -> AnalysisRun:
        """Создать прогон анализа, обработать компании, сохранить результаты."""

    async def compare_analysis_runs(
        self, run_id_1: int, run_id_2: int
    ) -> ComparisonResult:
        """Сравнить два прогона: совпадения, расхождения, дельты confidence."""

    # ── APPROVAL (одобрение) ──
    async def create_gate(
        self, project_id: int, gate_type: str, scope: dict, label: str
    ) -> ApprovalGate:
        """Создать approval gate. Pipeline приостанавливается до одобрения."""

    async def approve_gate(self, gate_id: int, operator: str, note: str = None) -> None
    async def reject_gate(self, gate_id: int, operator: str, note: str = None) -> None

    # ── CONTINUE PIPELINE (продолжить) ──
    async def continue_pipeline(
        self, gathering_run_id: int, next_phase: str
    ) -> PhaseResult:
        """Возобновить pipeline с конкретной фазы."""

    # ── HISTORY (история) ──
    async def get_runs(self, project_id: int, source_type: str = None) -> list[GatheringRun]
    async def get_run_detail(self, run_id: int) -> GatheringRunDetail
    async def get_run_companies(self, run_id: int, page: int = 1) -> PaginatedCompanies
```

---

## Миграция существующих данных EasyStaff

Существующие JSON-файлы из gathering Dubai-агентств ДОЛЖНЫ быть импортированы в новую систему.

### Что существует:

| Файл | Записей | Источник |
|------|---------|----------|
| `data/dubai_agency_companies_full.json` | 295 | apollo_people_ui, Strategy A (32 ключевых слова) |
| `data/uae_god_search_companies.json` | 5,602 | apollo_people_ui, Strategy B (seniority) |
| `data/uae_god_search_people.json` | 12,201 | apollo_people_ui, Strategy B (записи людей) |
| `data/uae_20k_companies.json` | 7,782 | apollo_companies_ui (industry tags + keywords) |

### Скрипт миграции: `scripts/migrate_existing_tam.py`

1. **Создать GatheringRuns** для каждого исторического поиска:
   - Run 1: `source_type=apollo.people.emulator, source_subtype=strategy_a, filters={person_locations: ["Dubai, UAE"], q_organization_name: "32 keywords", max_pages: 10}, status=completed`
   - Run 2: `source_type=apollo.people.emulator, source_subtype=strategy_b, filters={person_locations: [...3 города ОАЭ], person_seniorities: ["founder","c_suite","owner"], organization_num_employees_ranges: ["1,10"..."101,200"], max_pages: 10}, status=completed`
   - Run 3: `source_type=apollo.companies.emulator, source_subtype=industry_tags, filters={organization_locations: ["United Arab Emirates"], organization_industry_tag_ids: [...], organization_num_employees_ranges: [...], max_pages: 100}, status=completed`

2. **Создать/обновить DiscoveredCompanies** для каждого уникального домена:
   - Нормализация домена через `domain_service.normalize_domain()`
   - Upsert по `(company_id, project_id, domain)`
   - Установить: name, employees, linkedin_url, company_info из самого богатого источника

3. **Создать company_source_links** для каждой пары (company, run):
   - `source_data` = сырая запись из этого источника
   - `source_rank` = позиция в оригинальных результатах

4. **Импортировать людей как ExtractedContacts** (из `uae_god_search_people.json`):
   - Привязать к DiscoveredCompany по домену
   - `source = APOLLO` (извлечено через Puppeteer, не API, но та же структура данных)

5. **Обновить счётчики GatheringRun**: raw_results_count, new_companies_count, duplicate_count

### Порядок миграции:
1. Сначала миграция самого большого датасета (uae_god_search = 5,602 компании)
2. Затем keyword search (295) — в основном дубликаты, создаются source_links
3. Затем companies tab (7,782) — много новых, частичное пересечение

---

## API Endpoints (эндпоинты)

```
POST   /api/pipeline/gathering/start                        -- запустить gathering run
GET    /api/pipeline/gathering/runs                          -- список прогонов для проекта (с фильтрами: source_type, status, диапазон дат)
GET    /api/pipeline/gathering/runs/{id}                     -- детали прогона + статистика + recall фильтров
GET    /api/pipeline/gathering/runs/{id}/companies           -- компании из этого прогона (с пагинацией)
POST   /api/pipeline/gathering/continue/{id}                 -- продолжить к следующей фазе
POST   /api/pipeline/gathering/estimate                      -- оценка стоимости без выполнения

GET    /api/pipeline/gathering/sources                       -- список доступных source adapters + JSON-схемы фильтров
GET    /api/pipeline/gathering/sources/{type}/schema          -- JSON-схема для конкретного источника

GET    /api/pipeline/gathering/approval-gates                -- ожидающие gates
POST   /api/pipeline/gathering/approval-gates/{id}/approve
POST   /api/pipeline/gathering/approval-gates/{id}/reject

GET    /api/pipeline/gathering/scrapes/{company_id}           -- все scrapes для компании (все версии, все страницы)
POST   /api/pipeline/gathering/scrapes/refresh                -- запустить re-scrape для истёкшего контента

GET    /api/pipeline/gathering/analysis-runs                  -- список прогонов анализа
GET    /api/pipeline/gathering/analysis-runs/{id}             -- детали прогона с summary результатов
GET    /api/pipeline/gathering/analysis-runs/{a}/compare/{b}  -- сравнение двух прогонов (расхождения, дельты confidence)

GET    /api/pipeline/gathering/blacklist-check                -- проверить домены по CRM + blacklist (dry run — без сохранения)
```

---

## Файлы для создания

| Файл | Назначение |
|------|-----------|
| `backend/app/models/gathering.py` | GatheringRun, CompanySourceLink, CompanyScrape, AnalysisRun, AnalysisResult, ApprovalGate |
| `backend/app/schemas/gathering.py` | Pydantic filter-схемы per source + модели request/response |
| `backend/app/services/gathering_service.py` | Оркестратор pipeline |
| `backend/app/services/gathering_adapters/__init__.py` | Реестр adapters |
| `backend/app/services/gathering_adapters/base.py` | GatheringAdapter ABC (абстрактный базовый класс) |
| `backend/app/services/gathering_adapters/apollo_people_ui.py` | Обёртка вокруг apollo_god_search.js |
| `backend/app/services/gathering_adapters/apollo_companies_ui.py` | Обёртка вокруг apollo_companies_god.js |
| `backend/app/services/gathering_adapters/apollo_org_api.py` | Обёртка вокруг apollo_service.search_organizations |
| `backend/app/services/gathering_adapters/clay_companies.py` | Обёртка вокруг clay_service.run_tam_export |
| `backend/app/services/gathering_adapters/clay_people.py` | Обёртка вокруг clay_service.run_people_search |
| `backend/app/services/gathering_adapters/csv_import.py` | Импорт CSV-файлов |
| `backend/app/services/gathering_adapters/manual.py` | Прямой список доменов |
| `backend/app/api/gathering.py` | API router |
| `backend/alembic/versions/202603201_gathering_system.py` | Миграция |
| `scripts/migrate_existing_tam.py` | Импорт существующих JSON-данных EasyStaff |

## Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `backend/app/models/pipeline.py` | Добавить колонки в DiscoveredCompany |
| `backend/app/models/domain.py` | Добавить gathering_run_id в SearchJob |
| `backend/app/models/__init__.py` | Импортировать новые модели |
| `backend/app/services/scraper_service.py` | Добавить `scrape_to_db()` → пишет в company_scrapes |
| `backend/app/api/pipeline.py` | Включить gathering router |
| `backend/app/main.py` | Зарегистрировать refresh materialized view в startup/scheduler |

## Файлы для переиспользования без изменений

| Файл | Что предоставляет |
|------|-----------------|
| `backend/app/services/apollo_service.py` | search_organizations, enrich_by_domain — оборачиваются adapters |
| `backend/app/services/clay_service.py` | run_tam_export, run_people_search — оборачиваются adapters |
| `backend/app/services/pipeline_service.py` | enrich_apollo_batch, verify_emails_batch, promote_to_crm — фазы после анализа |
| `backend/app/services/domain_service.py` | normalize_domain(), matches_trash_pattern() |
| `backend/app/services/scraper_service.py` | scrape_website(), scrape_batch() — сама логика скрапинга |
| `easystaff-global/enterprise_blacklist.json` | Загружается проверкой blacklist |
| `scripts/apollo_god_search.js` | Вызывается ApolloPeopleUIAdapter |
| `scripts/apollo_companies_god.js` | Вызывается ApolloCompaniesUIAdapter |

---

## Порядок реализации

**Phase A — Data layer (слой данных, 1 день)**
1. SQLAlchemy-модели в `gathering.py`
2. Pydantic-схемы в `schemas/gathering.py`
3. Alembic-миграция (все новые таблицы + расширения колонок)
4. Materialized view для CRM blacklist

**Phase B — Core service + Apollo adapter (2 дня)**
5. GatheringAdapter ABC + adapter registry
6. ApolloOrgAPIAdapter (самый простой — прямая обёртка существующего сервиса)
7. GatheringService: start_gathering + dedup + blacklist
8. API endpoints: start, list runs, run detail

**Phase C — Scraping + analysis (1-2 дня)**
9. Путь записи company_scrapes в scraper_service
10. TTL-проверка + планировщик re-scrape
11. Путь записи analysis_runs/results
12. AI-анализ извлечён из company_search_service в переиспользуемую функцию

**Phase D — Migration + remaining adapters (1-2 дня)**
13. `migrate_existing_tam.py` — импорт JSON-данных EasyStaff
14. ApolloPeopleUIAdapter, ApolloCompaniesUIAdapter (обёртка JS-скриптов)
15. ClayCompaniesAdapter, CSVImportAdapter

**Phase E — Approval gates + remaining API (1 день)**
16. Создание/разрешение approval gates
17. Endpoint сравнения анализов
18. Endpoint refresh скрапинга

**Phase F — Подготовка к MCP (1 день)**
19. Экспорт JSON-схем для всех adapters
20. Авто-регистрация MCP-инструментов

---

## Критические Edge Cases и архитектурные решения

### 1. Company Identity Resolution (разрешение идентичности компании — Multi-Domain)

**Проблема**: Одна компания может иметь несколько доменов: `acme.com`, `acme.ae`, `acme.co.uk`. Apollo говорит "Frizzon Studios", Clay говорит "Frizzon Productions". Dedup только по домену пропускает такие случаи.

**Решение**: Двухуровневая dedup:
- **Layer 1 (мгновенный, бесплатный)**: Точное совпадение домена после нормализации (убрать www, lowercase)
- **Layer 2 (нечёткий, в фазе PRE-FILTER)**: Похожесть имён компаний (Levenshtein или trigram) + совпадение LinkedIn URL. Если две DiscoveredCompanies делят один LinkedIn company URL → объединить.

**Реализация**: `discovered_companies.linkedin_company_url` как вторичный unique identifier. При вставке проверяй и домен И linkedin URL. Если linkedin совпадает с существующей записью с другим доменом → связать как alias, не создавать дубликат.

```
-- Опционально: таблица алиасов компаний для multi-domain сущностей
company_aliases
├── primary_company_id    FK(discovered_companies)
├── alias_domain          VARCHAR(255)
├── alias_linkedin_url    TEXT
├── alias_name            VARCHAR(500)
├── detected_by           VARCHAR(50)   -- domain_match | linkedin_match | name_fuzzy | manual
```

### 2. Фаза Domain Resolution (разрешение доменов)

**Проблема**: 8,766 компаний из вкладки Companies имеют LinkedIn URL, но НЕТ доменов. Нельзя скрапить сайты или проверять email-обогащение без доменов.

**Решение**: Новая фаза pipeline RESOLVE между PRE-FILTER и SCRAPE:
1. **LinkedIn → домен**: Apollo `enrich_organization(linkedin_url)` возвращает `primary_domain` (1 credit за вызов, но высокая ценность)
2. **Имя компании → домен**: Google search `"{company_name}" site:{country_tld}` → извлечь домен из первого результата
3. **Пропуск если не нужно**: Запускать только для компаний без домена после GATHER
4. **Budget-gated** (ограничен бюджетом): Оператор одобряет размер batch перед тратой Apollo credits

### 3. Re-Run Lineage (линия повторных прогонов)

**Проблема**: Оператор хочет перезапустить поиск 2-недельной давности, потому что "у Apollo могут быть новые компании." Но dedup по `filter_hash` отклонит его как дубликат.

**Решение**: `parent_run_id` на gathering_runs:
```
gathering_runs.parent_run_id  FK(gathering_runs) NULL  -- "это повтор прогона #42"
```

Когда `parent_run_id` установлен, dedup по filter_hash обходится. Система сравнивает результаты: "Run #42 нашёл 5,602 компании. Re-run #65 нашёл 5,840. Чистые новые: 238."

### 4. Conversion Provenance (происхождение конверсий — Full Funnel Tracking)

**Проблема**: "Какой gathering run привёл к закрытой сделке?" Нельзя ответить без отслеживания цепочки: gathering_run → DiscoveredCompany → ExtractedContact → Contact → Campaign → ProcessedReply → Meeting.

**Решение**: Частично уже решено:
- `extracted_contacts.discovered_company_id` → ссылка на DiscoveredCompany
- JSON `contacts.provenance` хранит `gathering_details` (из `pipeline_service.promote_to_crm()`)
- `DiscoveredCompany → company_source_links → gathering_runs`

**Добавить**: `contacts.gathering_run_id` FK для прямой линии:
```python
# На модели Contact:
gathering_run_id = Column(Integer, ForeignKey('gathering_runs.id'))
```

Запрос полной воронки:
```sql
SELECT gr.source_type, gr.filters->>'person_locations' AS location,
  COUNT(DISTINCT dc.id) AS companies, COUNT(DISTINCT ec.id) AS contacts,
  COUNT(DISTINCT c.id) AS crm_contacts, COUNT(DISTINCT m.id) AS meetings
FROM gathering_runs gr
JOIN company_source_links csl ON csl.gathering_run_id = gr.id
JOIN discovered_companies dc ON dc.id = csl.discovered_company_id
LEFT JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id
LEFT JOIN contacts c ON c.gathering_run_id = gr.id
LEFT JOIN meetings m ON m.contact_id = c.id
WHERE gr.project_id = :project_id
GROUP BY gr.id
ORDER BY meetings DESC;
```

### 5. Central Quota Management (централизованное управление квотами)

**Проблема**: Два оператора одновременно запускают поиски Apollo → оба попадают в rate limit 429. Или MCP-агент сжигает все Clay credits за один прогон.

**Решение**: Трекер квот на уровне adapter (не БД — in-memory с Redis или простым file lock):
```python
class QuotaManager:
    """Централизованный трекер квот per source platform."""

    async def acquire(self, platform: str, credits: int, timeout: int = 300) -> bool:
        """Запросить credits. Блокирует до доступности или timeout."""

    async def release(self, platform: str, credits: int) -> None:
        """Вернуть неиспользованные credits (напр. поиск вернул меньше результатов, чем ожидалось)."""

    async def get_usage(self, platform: str) -> QuotaUsage:
        """Текущее использование: {used_today, limit_today, used_this_hour, limit_this_hour}."""
```

Каждый adapter вызывает `quota_manager.acquire()` перед API-вызовами. Manager соблюдает per-platform лимиты (Apollo 200/мин, Clay 5000 экспортов/день и т.д.).

### 6. Parallel Gathering Strategy (стратегия параллельного сбора)

**Проблема**: Для нового проекта оператор хочет искать в Apollo People + Apollo Companies + Clay TAM одновременно, затем объединить результаты.

**Решение**: Несколько `gathering_runs` с общим `pipeline_run_id`. Pipeline ждёт завершения ВСЕХ прогонов с этим `pipeline_run_id` перед переходом к DEDUP.

```python
async def start_parallel_gathering(
    project_id: int,
    searches: list[dict],  # [{source_type, filters}, ...]
) -> PipelineRun:
    """Запуск нескольких gathering runs параллельно, объединение по завершении."""
    pipeline_run = PipelineRun(project_id=project_id, status="RUNNING")
    for search in searches:
        gathering_run = GatheringRun(
            pipeline_run_id=pipeline_run.id,
            source_type=search["source_type"],
            filters=search["filters"],
        )
        # Запуск adapter.execute() как фоновой задачи
    # Pipeline переходит к DEDUP только когда все прогоны completed
```

### 7. Effectiveness Learning Loop (цикл обучения эффективности)

**Проблема**: После 10 gathering runs оператор хочет знать: "Какая комбинация source type + фильтр дала лучший target rate?"

**Решение**: Вычисляемые метрики на `gathering_runs` (заполняются после фазы ANALYZE):
```
gathering_runs (дополнительные колонки):
├── target_rate            FLOAT     -- targets_found / new_companies_count
├── avg_analysis_confidence FLOAT    -- средний confidence targets из этого прогона
├── cost_per_target_usd    NUMERIC   -- total_cost_usd / targets_found
├── enrichment_hit_rate    FLOAT     -- emails_found / targets_enriched (заполняется после ENRICH)
```

**Запрос для дашборда**: "Лучшие source types за этот месяц":
```sql
SELECT source_type, source_subtype,
  COUNT(*) AS runs,
  AVG(target_rate) AS avg_target_rate,
  AVG(cost_per_target_usd) AS avg_cost_per_target
FROM gathering_runs
WHERE project_id = :pid AND status = 'completed' AND target_rate IS NOT NULL
GROUP BY source_type, source_subtype
ORDER BY avg_target_rate DESC;
```

Этот feedback loop позволяет системе (или MCP-агенту) рекомендовать: "Поиск по seniority в Apollo имеет 22% target rate для этого проекта. Поиск компаний в Clay — 8%. Рекомендуем использовать Apollo."

### 8. Export Flexibility (гибкость экспорта — Pluggable Outputs)

**Проблема**: Результаты должны попадать в разные destination: Google Sheets (обзор), CSV (скачивание), SmartLead (кампания), GetSales (LinkedIn), Clay table (дальнейшее обогащение), webhook (кастомная интеграция).

**Решение**: Output adapters (тот же паттерн, что и gathering adapters):
```python
class OutputAdapter(ABC):
    output_type: str  # "google_sheets" | "csv" | "smartlead" | "getsales" | "clay_table" | "webhook"

    async def export(self, companies: list, contacts: list, config: dict) -> ExportResult
```

Частично уже существует: `clay_service.export_to_google_sheets()`, `pipeline_service.promote_to_crm()`, SmartLead push. Нужно просто формализовать как adapters.

---

## Реальный пример: EasyStaff Global (Project 9)

Этот pipeline был использован для сбора, анализа и верификации 7,900+ целевых компаний в 20+ городах.
Pipeline создал 8 новых кампаний SmartLead (региональные разбивки: US, UK, Gulf, India, APAC, Australia, LatAm-Africa, плюс варианты).
У EasyStaff Global ~170 кампаний всего — большинство были созданы до существования этого pipeline, через ручные процессы.

### Пошагово: Как это реально работало

```
ШАГ 1: GATHER из Apollo (Puppeteer emulator — бесплатно)
   │   Применить keyword + city + size фильтры к Apollo Companies UI
   │   ~80 ключевых слов × 20 городов = 50+ gathering runs
   │   Фильтры каждого прогона СОХРАНЕНЫ в gathering_runs.filters (JSONB)
   │   → Отслеживает, какие ключевые слова дают лучшие targets позже
   │
   v
ШАГ 2: DEDUP + BLACKLIST
   │   Нормализация доменов → company_source_links (мост multi-source)
   │   Проверка против 170 существующих кампаний EasyStaff → отклонение пересечений
   │   ★ CHECKPOINT 1: оператор подтверждает scope проекта
   │
   v
ШАГ 3: SCRAPE сайтов (httpx + Apify proxy — бесплатно)
   │   50 параллельных соединений, streaming per-company коммиты
   │   Crash-safe (устойчив к крэшам): on_result callback сохраняет каждую компанию индивидуально
   │
   v
ШАГ 4: PRE-FILTER алгоритмически (без AI — детерминированно)
   │   Убрать: сайт недоступен, офлайн-индустрии (ресторан, отель,
   │   строительство), мусорные домены (.gov, .edu), пустые/паркованные сайты
   │   ~40-60% rejection rate — дёшево, быстро, нет false negatives (ложных отказов)
   │
   v
ШАГ 5: ANALYZE через GPT-4o-mini
   │   AI классифицирует каждую компанию: is_target? confidence? segment? reasoning?
   │   Использует ICP-промпт, специфичный для проекта
   │   Стоимость: ~$0.01-0.05 на batch из 500 компаний
   │
   v
ШАГ 6: VERIFY через Opus (Claude)
   │   16 параллельных Opus-агентов проверяют ВСЕ targets GPT
   │   Каждый агент получает ~260 компаний, проверяет вердикт GPT
   │   Находит false positives: SaaS-продукты, solo-консультанты,
   │   неправильная география, государственные организации, game studios строящие свой IP
   │
   v
ШАГ 7: ADJUST PROMPT (корректировка промпта) → повтор Шагов 5-6 до ≥90% точности
   │   Это критический цикл. 8 итераций промпта для EasyStaff:
   │
   │   V1: 0%  — сложная скоринговая рубрика, совершенно неправильные сегменты
   │   V2: 76% — подход via negativa (от обратного), сегменты CAPS_LOCKED
   │   V3: 93% (малая выборка) — фильтр по географии, исключение solo-консультантов
   │   V4: 83% (полный обзор Opus) — строгая локация, исключение инвестиций
   │   V5: 86% — паттерны типов сущностей, исключение gov, определение названия страны
   │   V6: 88% — interior design, company formation, обнаружение фейковых сайтов
   │   V7: 93.6% (645/689 верифицировано) — уточнено различие SERVICE vs PRODUCT
   │   V8: 95.1% (2,645/2,782 верифицировано) — финальный фокус SERVICE business ✓
   │
   │   Цикл завершается когда верификация Opus показывает ≥90% точности.
   │   Каждая итерация: Opus находит FP-паттерны → добавить исключения в промпт → ре-анализ → ре-верификация
   │
   v
ШАГ 8: PEOPLE SEARCH (Apollo People emulator — бесплатно, или API — 1 credit/компания)
   │   Найти до 3 decision-makers (лиц, принимающих решения) на верифицированную целевую компанию
   │   Фильтры: founder, c_suite, vp, director seniority
   │   Apollo People UI скрапит контактные данные из UI Apollo
   │   Результат: ~1.4 контакта на компанию в среднем
   │
   v
ШАГ 9: FINDYMAIL верификация email ($0.01/email)
   │   Для контактов, где Apollo не предоставляет верифицированные emails
   │   ★ CHECKPOINT 3: оператор одобряет расходы
   │   438 контактов верифицировано за один 88-минутный batch
   │
   v
ШАГ 10: GOD_SEQUENCE — генерация последовательности кампании (Gemini 2.5 Pro)
   │
   │   Система собирает знания из 3 уровней в один промпт Gemini:
   │
   │   УРОВЕНЬ 1 — UNIVERSAL (campaign_patterns WHERE scope_level='universal')
   │     Механика cold email, применимая ко ВСЕМ проектам:
   │     Subject: {{first_name}} – [вопрос о боли]
   │     Тайминг: Day 0/3/4/7/7 (Шаги 2+4 привязаны к 31% тёплых ответов каждый)
   │     Тон: casual-professional (неформально-профессиональный), без hype-слов
   │     Body: 4-параграфная арка (Hook → Value → Proof → CTA)
   │     CTA: предложи ценность ("рассчитать cost benefit?"), не проси время
   │     Flow: Value → Competition → Price → Channel → Empathy
   │
   │   УРОВЕНЬ 2 — BUSINESS (campaign_patterns WHERE business_key=sender_company)
   │     Знания о продукте, общие между проектами ОДНОГО бизнеса:
   │     Группировка по Project.sender_company (напр. "easystaff.io" = проекты 9+40)
   │     Конкуренты, цены, истории замещения, proof points (точки доказательства)
   │     + ProjectKnowledge (outreach/gtm) от sister-проектов
   │
   │   УРОВЕНЬ 3 — PROJECT (campaign_patterns WHERE project_id=THIS + ProjectKnowledge)
   │     ICP этого проекта, рынок, язык, identity отправителя
   │     Target segments, industries, географическая персонализация
   │
   │   Все 3 уровня → ~3,000 token промпт → Gemini 2.5 Pro → 5-шаговая последовательность
   │
   │   API-вызовы:
   │     POST /api/campaign-intelligence/generate-sequence/
   │       {"project_id": 9, "campaign_name": "Petr ES Manchester"}
   │     → возвращает GeneratedSequence (status=draft) с 5 шагами + обоснование
   │
   │     POST /api/campaign-intelligence/generated/{id}/approve/
   │     → помечает как approved, готово к push
   │
   │   Стоимость: ~$0.08 за генерацию
   │   Полная документация: docs/GOD_SEQUENCE/ARCHITECTURE.md
   │   Содержимое базы знаний: docs/GOD_SEQUENCE/KNOWLEDGE_BASE_SNAPSHOT.md
   │
   v
ШАГ 11: SMARTLEAD создание кампании + загрузка лидов
   │
   │   API-вызов:
   │     POST /api/campaign-intelligence/generated/{id}/push/
   │     → Создаёт кампанию SmartLead (состояние DRAFT)
   │     → Устанавливает 5-шаговую последовательность GOD_SEQUENCE
   │     → Регистрирует кампанию в БД с resolution_method="god_sequence"
   │
   │   Затем вручную (оператор или отдельный скрипт):
   │     Загрузить лидов с custom fields: city, segment, sender_name
   │     Добавить email-аккаунты отправителя (типично 12 на кампанию)
   │     Переменные персонализации: {{first_name}}, {{city}}, {{Sender Name}}
   │     Активировать кампанию → начинается outreach
   │
   │   8 региональных кампаний создано через этот pipeline:
   │   "Petr ES US", "Petr ES UK", "Petr ES Gulf",
   │   "Petr ES India", "Petr ES APAC", "Petr ES Australia",
   │   "Petr ES LatAm-Africa", + варианты
```

### Цикл итерации промпта (Шаги 5-7) — это ядро

Это то, что отличает хороший gathering от плохого. Pipeline — это не "запустить GPT один раз и push."
Это замкнутый цикл:

```
  ┌──────────────────────────────────────────┐
  │                                          │
  v                                          │
GPT-4o-mini анализирует ──► Opus верифицирует ──► <90%? ──ДА──► Корректировка промпта
  │                           │                                  (добавить исключения
  │                           │                                   из FP-паттернов)
  │                           v
  │                        ≥90%? ──ДА──► ГОТОВО, переход к people search
  │
  └── Использует project-specific ICP промпт
      хранящийся в таблице gathering_prompts
      с отслеживанием эффективности (target_rate, usage_count)
```

**Что Opus ловит, а GPT пропускает:**
- Game studios, строящие свой IP (не делают клиентскую работу)
- Management/strategy consulting (используют сотрудников, не фрилансеров)
- SaaS-продукты (не сервисные бизнесы)
- Solo-консультанты / fractional CxO (1-person операции)
- Неправильная география (Индийские "Pvt Ltd" сущности, Оман, Ливан)
- Государственные дочерние компании
- Инвестиционные/VC-фирмы

### Отслеживание эффективности ключевых слов

Каждый gathering run хранит свои фильтры. После анализа `target_rate` вычисляется per run.
Это позволяет ранжировать ключевые слова по ROI:

| Tier | Target Rate | Ключевые слова |
|------|------------|----------------|
| **Tier 1** (35-45%) | Лучшие | staffing agency, design agency, marketing agency |
| **Tier 2** (26-35%) | Хорошие | outsourcing company, digital agency, creative agency |
| **Tier 3** (14-23%) | Низкие | software development, consulting firm, IT services |
| **НЕ ИСПОЛЬЗОВАТЬ** (<5%) | Трата времени | fintech, saas, blockchain, crypto |

Эти данные живут в `gathering_runs.target_rate` и информируют будущие прогоны:
```sql
SELECT source_subtype, AVG(target_rate) FROM gathering_runs
WHERE project_id = 9 AND status = 'completed'
GROUP BY source_subtype ORDER BY avg DESC;
```

### Ключевые выводы

1. **Puppeteer > API для gathering** — Apollo emulator бесплатный, API тратит credits. API использовался только для blitz-а на 10K credits, чтобы покрыть больше ключевых слов быстрее.

2. **Цикл итерации промпта необходим** — V1 имел 0% точности, V8 достиг 95.1%. Восемь итераций, каждая на основе анализа false positives от Opus. Короткого пути нет.

3. **Эффективность ключевых слов различается в 10 раз** — "staffing agency" даёт 45% target rate, "fintech" — <5%. Отслеживай `target_rate` per run, чтобы не тратить время на плохие ключевые слова.

4. **Streaming scrape необходим** — Старый batch scrape терял весь прогресс при крэше. Новый streaming-подход коммитит per-company через `on_result` callback. 50 параллельных соединений, ~344 компании/мин.

5. **People search заполняет пробел** — Apollo Companies даёт домены, но не контакты. Отдельный шаг People search находит 1-3 decision-makers на компанию. FindyMail нужен только для emails, которые Apollo не может верифицировать.

---

## Итог: Что делает это God-Level

| Принцип | Как |
|---------|-----|
| **Source-agnostic** (не зависит от источника) | БД хранит непрозрачный JSONB. Новый источник = новый adapter, ноль изменений БД |
| **Filter memory** (память фильтров) | Каждый поиск запоминается с точными параметрами. Повторяемый. |
| **Multi-source dedup** (дедупликация из нескольких источников) | Одна компания найдена 5 источниками → 1 DiscoveredCompany + 5 source_links |
| **Cheapest first** (сначала дешёвое) | Бесплатный pattern matching → бесплатный blacklist → дешёвый скрапинг → дорогой AI → затратное обогащение |
| **Full provenance** (полное происхождение) | gathering_run → DiscoveredCompany → ExtractedContact → CRM Contact → Meeting → Deal |
| **Versioned scraping** (версионированный скрапинг) | Несколько страниц на компанию, re-scrape по TTL, все версии сохраняются |
| **Multi-run analysis** (анализ в нескольких прогонах) | Разные модели, разные промпты, сравнение результатов, переопределение оператором |
| **Approval gates** (ворота одобрения) | Human-in-the-loop (человек в цикле) перед каждым шагом, тратящим credits |
| **MCP-ready** | Adapters предоставляют JSON-схемы. `tam_gather_{source}` инструменты авто-регистрируются |
| **Learning loop** (цикл обучения) | target_rate, cost_per_target отслеживаются per run. Система рекомендует лучшие источники |
| **Project-aware** (осведомлён о проекте) | Читает ICP, продукты, конкурентов, case studies, существующие контакты. Не тупая машина фильтрации |
