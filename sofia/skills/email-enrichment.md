# Скилл: Email Enrichment & Company Name Normalization

Находит верифицированные имейлы через Findymail API и нормализует названия компаний перед загрузкой в Smartlead.

## Когда использовать

Пользователь говорит:
- "найди имейлы"
- "обогати имейлами"
- "прогони через Findymail"
- "нормализуй компании"
- "подготовь для Smartlead"

---

## Шаг 1 — Findymail Email Enrichment

Findymail API находит верифицированные имейлы по LinkedIn URL. Дополнительная верификация НЕ нужна — API возвращает только проверенные адреса.

### API

- **Endpoint**: `POST https://app.findymail.com/api/search/linkedin`
- **Auth**: `Authorization: Bearer <API_KEY>`
- **Body**: `{"linkedin_url": "https://linkedin.com/in/..."}`
- **Ответы**:
  - `200` → `{contact: {email, name, domain, company, ...}}` — найден
  - `404` → не найден (имейл не прошёл верификацию)
  - `402` → нет кредитов (остановить скрипт)

### API Key

Хранится в `/tmp/findymail_enrich.py` — брать оттуда.

### Скрипт

```python
import csv, requests, time

API_KEY = "<FINDYMAIL_API_KEY>"
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def find_email(linkedin_url):
    try:
        r = requests.post("https://app.findymail.com/api/search/linkedin",
                         headers=headers, json={"linkedin_url": linkedin_url}, timeout=15)
        if r.status_code == 200:
            contact = r.json().get('contact', {})
            return contact.get('email'), 'found'
        elif r.status_code == 404:
            return None, 'not_found'
        elif r.status_code == 402:
            return None, 'no_credits'
        else:
            return None, f'error_{r.status_code}'
    except Exception as e:
        return None, f'exception: {str(e)[:40]}'

# Применить к CSV
rows = list(csv.DictReader(open('contacts.csv', encoding='utf-8')))
fieldnames = list(rows[0].keys()) + ['Email', 'Email_status']

for i, row in enumerate(rows):
    linkedin = row.get('Links · LinkedIn', '').strip()
    if linkedin:
        email, status = find_email(linkedin)
    else:
        email, status = None, 'no_linkedin'
    row['Email'] = email or ''
    row['Email_status'] = status

    if status == 'no_credits':
        print(f"⚠️  No credits at row {i}!")
        break

    if (i+1) % 20 == 0:
        print(f"  {i+1}/{len(rows)}")

with open('contacts_with_emails.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
```

### Rate limiting

Без задержки — API справляется. ~265 контактов ≈ 1-2 минуты.

---

## Шаг 2 — Нормализация названий компаний

Перед загрузкой в Smartlead убрать мусор из названий.

### Правила нормализации

| Паттерн | Пример | Результат |
|---------|--------|-----------|
| Юр. суффиксы | `Cision Germany GmbH` | `Cision Germany` |
| Тикеры в скобках | `Society Pass Inc. (NASDAQ: SOPA)` | `Society Pass` |
| Пайп-разделители | `MHS \| My Haul Store` | `My Haul Store` |
| Описание после `-` | `Audiencly - Influencer Marketing Agency` | `Audiencly` |
| Длинные скобки | `Galleri5 (now, part of ...)` | `Galleri5` |
| Домены как имена | `whalar.com` | `Whalar` |
| Замаскированные | `vid**` | Определить вручную (VidMob) |

### Код

```python
import re

# Явные замены (заполнять по ситуации)
RENAMES = {
    # 'vid**': 'VidMob',
    # 'billiondollarboy.com': 'Billion Dollar Boy',
}

def normalize_company(name):
    if name in RENAMES:
        return RENAMES[name]

    # Убрать тикеры: "Company (NASDAQ: XXX)"
    name = re.sub(r'\s*\((?:NASDAQ|NYSE|LSE|TSX)[^)]*\)', '', name)

    # Убрать длинные скобки: "Company (now, part of ...)"
    name = re.sub(r'\s*\((?:now|formerly|prev)[^)]*\)', '', name, flags=re.IGNORECASE)

    # Убрать описание после " - ": "Company - Some Description"
    name = re.sub(r'\s+-\s+.{15,}$', '', name)

    # Убрать юр. суффиксы
    name = re.sub(r'\s*,?\s*\b(Inc\.?|LLC|GmbH|Ltd\.?|PTE|Corp\.?|S\.?R\.?L\.?|AB)\s*$', '', name, flags=re.IGNORECASE)

    # Домены → имена: "company.com" → "Company"
    if re.match(r'^[a-z0-9.-]+\.(com|io|ai|co|ly|es|me)$', name):
        domain = name.split('.')[0]
        name = domain.capitalize()

    return name.strip()
```

### Порядок работы

1. Прочитать уникальные компании из CSV
2. Прогнать через `normalize_company()`
3. Вывести список замен пользователю для подтверждения
4. Применить после одобрения

---

## Типичный результат

- 265 контактов → **239 имейлов** (90% hit rate)
- S1 (платформы): 95% hit rate
- S3 (агентства): 87% hit rate
- ~15-20% компаний требуют нормализации названий

---

## Стоимость

| Шаг | Стоимость |
|-----|-----------|
| Findymail email enrichment | 1 кредит/контакт |
| Нормализация названий | Бесплатно |

---

## Примечания

- Findymail возвращает ТОЛЬКО верифицированные имейлы — дополнительная проверка не нужна
- Если API вернул 402 — закончились кредиты, остановить и сообщить
- Всегда показывать пользователю список замен названий ПЕРЕД применением
- `python3.11` — использовать его (requests установлен)
