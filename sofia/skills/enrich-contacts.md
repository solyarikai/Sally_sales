# Скилл: Enrich Contacts CSV

Обогащение CSV с контактами: заполняет пустые имена из LinkedIn URL и находит сайты компаний.

## Когда использовать

Пользователь говорит:
- "найди сайты компаний"
- "заполни имена"
- "обогати контакты"
- "вот CSV из Apollo, надо добавить сайты"

---

## Пайплайн

### Шаг 1 — Заполнить пустые имена из LinkedIn URL

Многие контакты из Apollo приходят без имени (поле `Name` пустое), но с LinkedIn URL.

```python
import re, urllib.parse, csv

def name_from_linkedin(url):
    m = re.search(r'/in/([^/?]+)', url)
    if not m: return None
    slug = m.group(1).rstrip('/')
    slug = re.sub(r'-[a-f0-9]{6,10}$', '', slug)  # убрать hex-суффикс
    slug = urllib.parse.unquote(slug)               # URL-decode Unicode
    return ' '.join(p.capitalize() for p in slug.split('-') if p)

# Применить к CSV
rows = list(csv.DictReader(open('contacts.csv')))
for row in rows:
    if not row['Name'] and row.get('Links · LinkedIn'):
        row['Name'] = name_from_linkedin(row['Links · LinkedIn']) or ''
```

---

### Шаг 2 — Найти сайты компаний (3 этапа)

#### 2a. Эвристика — угадать домен по названию компании

```python
import re

def guess_domain(company_name):
    name = company_name.lower()
    name = re.sub(r'\b(inc|llc|gmbh|ltd|srl|ab|pte|corp|co|group|media|agency)\b\.?', '', name)
    name = re.sub(r'[^a-z0-9]', '', name)
    return f"{name}.com"
```

#### 2b. DNS верификация — проверить что домен резолвится

```python
import socket

def dns_ok(domain):
    try:
        socket.gethostbyname(domain)
        return True
    except:
        return False
```

~90% угаданных доменов резолвятся. Остальные — следующий шаг.

#### 2c. Claude по своим знаниям — для оставшихся компаний

Для компаний без подтверждённого домена — я генерирую домен напрямую из знаний.
Передаю список названий компаний батчами по 50, возвращаю `{"Company Name": "domain.com"}`.

**Итого: ~98% покрытие.**

Финальный формат в CSV: `https://domain.com`

---

### Шаг 3 — Параллельный фетчинг сайтов (опционально)

Если нужно получить описание компании с сайта (для классификации или проверки):

```python
import aiohttp, asyncio
from bs4 import BeautifulSoup

# python3.11 -m pip install aiohttp beautifulsoup4

async def fetch_all(urls, concurrency=20):
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
        tasks = [fetch_one(session, sem, url) for url in urls]
        return await asyncio.gather(*tasks)

def extract_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script','style','nav','footer']): tag.decompose()
    return {
        'title': soup.title.get_text(strip=True) if soup.title else '',
        'meta_desc': (soup.find('meta', attrs={'name': 'description'}) or {}).get('content', '')[:300],
        'h1': ' | '.join(h.get_text(strip=True) for h in soup.find_all('h1')[:3]),
        'body': ' '.join(soup.get_text().split())[:1200],
    }
```

Результат сохранять в `/tmp/website_content.json` — потом не нужно перефетчивать.

---

## Файловая структура

```
segments/[дата]/
├── raw_export.csv          # оригинал из Apollo (не трогать)
└── contacts_enriched.csv   # + Name заполнены + Website добавлен
```

---

## Стоимость

| Шаг | Стоимость |
|-----|-----------|
| Имена из LinkedIn URL | Бесплатно |
| Сайты (эвристика + DNS + Claude) | Бесплатно |
| Фетчинг сайтов | Бесплатно |
| Email (Crona Verified Email) | 10 кредитов/контакт |

---

## Типичный результат

- 400 контактов → ~5 минут работы
- 299 пустых имён → заполнены из LinkedIn
- ~98% компаний получают сайт

---

## Примечания

- Скрипты лежат в `scripts/enrich_contacts/`
- `python3.11` — используем его (есть aiohttp)
- Apollo фильтры часто ошибаются в классификации — не доверять без проверки сайта
