# GetSales Import Guide — для Claude

> Подключи этот файл к чату, когда нужно подготовить лист к загрузке в GetSales.
> Claude прочитает и сделает всё сам.

---

## Что делать

Пользователь даст тебе данные (Google Sheet вкладку, CSV, или просто список лидов).
Твоя задача: создать **новую Google Spreadsheet** в формате, готовом для импорта в GetSales.

---

## Формат импорта GetSales

### Вариант 1 — Минимальный (4 колонки)
Работает для LinkedIn-only кампаний, когда нет email.

```
First Name | Last Name | LinkedIn | Company Name
```

- **LinkedIn** — полный URL: `https://www.linkedin.com/in/nickname`
- Нормализуй `http://www.linkedin.com` → `https://www.linkedin.com`
- Если Last Name пустой — оставь пустым, не выдумывай

### Вариант 2 — Полный (49 колонок)
Используй когда есть дополнительные данные (position, domain, tags, segment reason и т.д.).

Порядок колонок (все 49, обязательно в этом порядке):

```
system_uuid, pipeline_stage, full_name, first_name, last_name,
position, headline, about, linkedin_id, sales_navigator_id,
linkedin_nickname, linkedin_url, facebook_nickname, twitter_nickname,
work_email, personal_email, work_phone, personal_phone,
connections_number, followers_number, primary_language,
has_open_profile, has_verified_profile, has_premium,
location_country, location_state, location_city,
active_flows, list_name, tags,
company_name, company_industry, company_linkedin_id, company_domain,
company_linkedin_url, company_employees_range, company_headquarter,
cf_location, cf_competitor_client, cf_message1, cf_message2, cf_message3,
cf_personalization, cf_compersonalization, cf_personalization1,
cf_message4, cf_linkedin_personalization, cf_subject, created_at
```

**Правила маппинга:**

| Данные из источника | Куда в GetSales |
|---------------------|-----------------|
| First Name | `first_name` |
| Last Name | `last_name` |
| First + Last | `full_name` |
| Title / Position | `position` |
| LinkedIn URL | `linkedin_url` + извлечь `linkedin_nickname` из URL |
| Company Website / Domain | `company_domain` |
| Company Name | `company_name` |
| Segment (INFLUENCER_PLATFORMS и т.д.) | `tags` |
| Segment Reason / описание компании | `cf_compersonalization` |
| Название батча / источника | `list_name` |
| Email (если есть) | `work_email` |

Пустые поля — оставляй пустыми (`""`), не заполняй мусором.

---

## Алгоритм подготовки

### 1. Прочитать источник
- Скачать данные из Google Sheet / CSV / текста
- Понять какие колонки есть

### 2. Очистка данных
- Убрать пустые строки
- Убрать строки-счётчики ("33 contacts", "Total" и т.п.)
- Убрать контакты без LinkedIn URL (бесполезны для GetSales LI-кампаний)
- Нормализовать LinkedIn URL: `http://www.linkedin.com` → `https://www.linkedin.com`
- Извлечь `linkedin_nickname` из URL (regex: `/in/([^/?]+)`)

### 3. Выбрать формат
- Есть только имя + LinkedIn + компания → **Вариант 1 (4 колонки)**
- Есть position, domain, tags, segment → **Вариант 2 (49 колонок)**

### 4. Создать Google Spreadsheet
- Название: `GetSales Import — [описание батча]`
- Если просят по сегментам → создать отдельный лист на каждый сегмент
- Если один сегмент → один лист
- Удалить пустой Sheet1 после создания листов с данными

### 5. Загрузить данные
- Первая строка — header
- Данные начинаются со 2-й строки
- Если > 65 строк — загружать чанками (API limit)

### 6. Отчитаться
Показать пользователю:
- Ссылку на таблицу
- Количество контактов по сегментам (если разбито)
- Общее количество

---

## Типичные источники данных

### Google Sheet вкладка "Without Email"
Колонки: `First Name, Last Name, Title, LinkedIn, Company Website, Company Name, Segment, Segment Reason`
→ Использовать **Вариант 2** (49 колонок), маппинг по таблице выше.
→ Разбивать по сегментам на отдельные листы если попросят.

### Apollo export CSV
Колонки: `First Name, Last Name, Title, Company, Email, LinkedIn Url, ...`
→ Если есть email → `work_email`
→ Если нет email → LinkedIn-only, оба варианта подходят

### Ручной список
Пользователь даёт имена + LinkedIn ссылки.
→ **Вариант 1** (4 колонки) — самый быстрый.

---

## Чеклист перед отдачей

- [ ] LinkedIn URL начинается с `https://` (не `http://`)
- [ ] Нет пустых строк между данными
- [ ] Нет строк-счётчиков или разделителей
- [ ] Header в первой строке
- [ ] Все контакты имеют LinkedIn URL
- [ ] Количество колонок одинаковое во всех строках
- [ ] Если 49 колонок — порядок точно совпадает с шаблоном

---

## Пример готовой таблицы (Вариант 1)

| First Name | Last Name | LinkedIn | Company Name |
|------------|-----------|----------|--------------|
| Alessandro | Bogliari | https://www.linkedin.com/in/alessandrobogliari/ | Influencer Marketing Factory |
| Thibaut | Mathias | https://www.linkedin.com/in/thibaut-mathias-9b85aa4a/ | Branding |

## Пример готовой таблицы (Вариант 2)

Все 49 колонок, большинство пустые. Ключевые заполнены:
- `full_name`, `first_name`, `last_name`
- `position`
- `linkedin_nickname`, `linkedin_url`
- `list_name`, `tags`
- `company_name`, `company_domain`
- `cf_compersonalization` (описание компании / segment reason)

---

## API и инфраструктура (справка)

- **GetSales UI:** `https://amazing.getsales.io`
- **Backend API:** `http://46.62.210.24:8000`
- **OnSocial project_id:** 42
- **GetSales кампании OnSocial** можно проверить:
  ```
  GET /api/god-panel/projects/42/campaign-metrics
  Header: X-Company-ID: 1
  ```
- **Все кампании** (с flow UUID):
  ```
  GET /api/god-panel/campaigns/?limit=500
  Header: X-Company-ID: 1
  ```
- **Google Sheet OnSocial <> Sally:** `1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E`
