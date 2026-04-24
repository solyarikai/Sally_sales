# Email Infrastructure — Build Guide

Пошаговый гайд по созданию почтовой инфры для cold outreach: от покупки доменов до запуска spam-тестов. Внутренний документ, содержит креды.

> Базовый SOP: [magnum-opus/infra/Instruction](../../../magnum-opus/infra/Instruction). Этот гайд — расширенная версия со скринами, текущим состоянием и ссылками на автоматизацию.
>
> **Скрипты автоматизации** лежат в submodule: [magnum-opus/infra/](../../../magnum-opus/infra/). Все `aivy-*.js` и `.ps1` файлы. Причина отделения гайда: `auto_git_pull.sh` хук удаляет `infra/` каталог в submodule как "ghost directory" — подробнее в разделе «Известные подводные камни» ниже.

---

## Аккаунты

| Сервис | Логин | Пароль / Key | Примечание |
|--------|-------|--------------|------------|
| Namecheap (основной для новых доменов) | `Sally2` | `A5(m+zgvm4xDDZc` | email: `services@getsally.io` |
| Namecheap API (Sally2) | `Sally2` | `d736e84e16b141b3a8cf0f51302c3aeb` | whitelisted IP: `46.62.210.24` (Hetzner) |
| Namecheap (legacy) | `decaster3` | `wP#DSVN-8X/yF&6` | старые домены, API в `.ps1` |
| Namecheap API (decaster3) | `decaster3` | `f3335861b92247779364649ae2beb014` | whitelisted IPs: `150.241.224.134`, `46.62.210.24` |
| Google Workspace — `aivy-digital.com` | `artem@aivy-digital.com` | `~7R8zsWJPTxB`, 2FA: `4156 3178` | **основной tenant для новых доменов** |
| Google Workspace — legacy | `services@getsally.io` | см. [Instruction](../../../magnum-opus/infra/Instruction) | legacy OnSocial tenant |
| GCP project (OAuth) | `easystaff-instantly-freshboxes` | client_id: `978895579994-duj44rs0l93rpbt2vrp844nptv23k940` | creds: `sofia-oauth-client.json` + `sofia-oauth-token.json` |
| SmartLead | `services@getsally.io` | `yLBuCn%P&&TJ8aM<1` | |
| Instantly API | Bearer token | см. [instantly-inbox-placement.md](../../../magnum-opus/infra/instantly-inbox-placement.md) | |

### Какой Namecheap-аккаунт использовать

- **Sally2** — все новые покупки под `aivy-digital` tenant. В `aivy-*.js` скриптах.
- **decaster3** — legacy домены, старые `.ps1` скрипты. Не трогать без нужды.

---

## Этапы

1. [Покупка доменов на Namecheap](#шаг-1--покупка-доменов-на-namecheap)
2. [Подключение доменов к Google Workspace](#шаг-2--подключение-доменов-к-google-workspace)
3. DNS-записи (MX, SPF, DMARC, DKIM, email tracking, redirect)
4. Создание почтовых ящиков + 2FA + backup codes
5. Подключение к SmartLead и warmup
6. Подключение к Instantly и spam-тесты

После каждого шага обновляем [Domain Tracker](#domain-tracker) — единый реестр доменов со сроками экспирации и статусом инфры.

---

## Domain Tracker

Единый реестр всех доменов Sally (не только OnSocial). Поскольку auto-renew OFF — это **единственный источник правды** по тому, когда что продлевать.

**Ссылка**: [Ops | Infra | Domains](https://docs.google.com/spreadsheets/d/1nht7tNVXdbLtLdUxbDguxnGbV-Zv1q5pMK3Uter7oyI)
**Папка Drive**: [Ops / Infra](https://drive.google.com/drive/folders/1pdHLW18i3RM7LtmTjD_vHBs4ZKpkBHNg)

### Схема (19 колонок)

| # | Колонка | Пример | Заполняется на шаге |
|---|---------|--------|---------------------|
| A | `domain` | `voxpilot.co` | Шаг 1 |
| B | `tld` | `.co` | Шаг 1 |
| C | `registrar` | `Namecheap` | Шаг 1 |
| D | `registrar_account` | `Sally2` | Шаг 1 |
| E | `client` | `OnSocial` / `INXY` / `Crona` / `Sally` | Шаг 1 |
| F | `purchased_at` | `2026-04-24` | Шаг 1 (после оплаты) |
| G | `expires_at` | `=F+365*H` (авто-формула) | auto |
| H | `years_paid` | `1` | Шаг 1 |
| I | `days_left` | `=G-TODAY()` (авто-формула) | auto |
| J | `auto_renew` | `N` | Шаг 1 (по умолчанию `N`) |
| K | `dns_configured` | `Y` / `partial` / `N` | Шаг 3 |
| L | `workspace_linked` | `Y` / `N` | Шаг 2 |
| M | `redirect_url` | `https://onsocial.com` | Шаг 3 |
| N | `last_health_check` | `2026-04-24` | auto (cron, TODO) |
| O | `mailboxes_count` | `2` | Шаг 4 |
| P | `smartlead_connected` | `Y` / `N` | Шаг 5 |
| Q | `instantly_connected` | `Y` / `N` | Шаг 6 |
| R | `status` | `active` / `expired` / `paused` / `dropped` | lifecycle |
| S | `notes` | `batch INXY #2` | любые комменты |

### Ручные улучшения (сделать один раз)

- **Freeze header**: View → Freeze → 1 row
- **Conditional formatting на `days_left`**:
  - `<30` → красный фон (скоро экспирация)
  - `<90` → жёлтый фон (пора планировать продление)
  - `<0` → тёмно-красный + bold (пропущено продление!)
- **Data validation** для быстрого ввода (Y/N, статусы) — Data → Data validation на колонках J, K, L, P, Q, R

### Автоматизации (TODO)

1. **Health-check cron** — раз в сутки на Hetzner: dig MX/TXT/CNAME + HEAD на redirect → обновляет `dns_configured` + `last_health_check`. Закрывает запрос Петра из [From Petr](../../../magnum-opus/infra/From%20Petr).
2. **Slack alert** — раз в неделю: «домены с `days_left < 30`» → в канал `#infra-renewals`
3. **Auto-sync из Namecheap API** — при покупке через `namecheap-register-domains.ps1` автоматически аппендить строку в tracker (сейчас скрипт этого не делает)

---

## Шаг 1 — Покупка доменов на Namecheap

### 1.1 Принцип именования

Домены формируются по паттерну `client + field`. Пример для клиента `inxy` (crypto payments):

```
inxycrypto.com
inxypayments.com
inxy-crypto.com
...
```

Цель — закупить пачку созвучных доменов, чтобы потом разнести ящики по разным доменам (минимум 2 ящика на домен, см. Шаг 4).

### 1.2 Открыть Beast Mode

Заходим на namecheap.com под аккаунтом `Sally2`. В строке поиска на главной рядом с кнопкой `Search` — ссылка **Beast Mode**. Переходим туда.

![Namecheap homepage — Beast Mode entry](images/email-infra/01-namecheap-home.png)

### 1.3 Сгенерировать и отфильтровать список

В Beast Mode в строке поиска вводим список нужных доменов (до 5000 keywords). Настройки:

- **Price Range** — ставим верхний лимит по цене (дефолт — $500k, реально ограничиваем под бюджет)
- **Show Premiums** — OFF (убираем премиум-домены, они дорогие)
- **Hide Unavailable** — ON (показывать только свободные)
- **TLD** — можно выбрать зоны (`.com`, `.io`, `.net`), но обычно не ограничиваем — берём что доступно

Жмём **Generate** и из результатов выбираем нужные.

![Namecheap Beast Mode — filters and keyword input](images/email-infra/02-namecheap-beast-mode.png)

### 1.4 Оформление заказа и оплата

После выбора подходящих доменов в Beast Mode идём в корзину и оформляем заказ. На странице checkout:

- **Free Domain Privacy** — включается автоматически для каждого домена (FREE Forever, не снимаем)
- **Renewal Settings** — `Do not auto-renew` ⚠️ выключаем авто-продление (чтобы не списало за домены, которые больше не нужны). Вместо этого дату экспирации трекаем в Domain Tracker
- **Payment Method** — дефолтная карта аккаунта

Жмём **Pay Now**.

> **Важно**: раз auto-renew OFF — дату покупки + дату экспирации (purchase + 1 year) ОБЯЗАТЕЛЬНО заносим в **Domain Tracker**, иначе потеряем домены.

![Namecheap checkout page](images/email-infra/03-namecheap-checkout.png)

### 1.5 Где смотреть купленные домены

После оплаты домены появляются в разделе **Domain List**. Путь: правый верхний угол → клик по **Account** → в выпадающем меню выбрать **Domain List**.

![Account menu — Domain List entry](images/email-infra/04-namecheap-account-menu.png)

В Domain List отсюда дальше заходим в настройки каждого домена (Шаг 3 — прописывание DNS-записей).

### 1.6 Автоматизация

| Что | Как | Файл (в submodule) |
|-----|-----|--------------------|
| **Регистрация пачки доменов** | Namecheap API, батч | [namecheap-register-domains.ps1](../../../magnum-opus/infra/namecheap-register-domains.ps1) |
| **WhoisGuard enable** | авто при регистрации (`WGEnabled=yes`) | same script |
| **Set DNS** | после регистрации | [namecheap-set-dns.ps1](../../../magnum-opus/infra/namecheap-set-dns.ps1) |
| **Add MX records** | для Google Workspace | [namecheap-add-mx.js](../../../magnum-opus/infra/namecheap-add-mx.js) |

Пример:
```powershell
# На Hetzner (IP 46.62.210.24 в whitelist обоих аккаунтов)
.\namecheap-register-domains.ps1 -DomainsFile crona-domains.txt
```

**Ещё не автоматизировано** (TODO):
- Генерация списка доменов из `client + field` (сейчас ручной брейнштурм в Beast Mode) → можно LLM-скриптом
- Авто-запись купленных доменов в Domain Tracker
- Health-check: проверка DNS-записей + redirect, см. [From Petr](../../../magnum-opus/infra/From%20Petr)

---

## Шаг 2 — Подключение доменов к Google Workspace

Задача: добавить домен в Google Workspace tenant (у нас — `aivy-digital.com`), пройти **ownership verification** через TXT-запись в DNS.

### 2.1 Ручной процесс (для понимания)

1. Admin Console ([admin.google.com](https://admin.google.com)) → **Domains** → **Add a domain** → ввести имя
2. Google выдаёт TXT-challenge вида `google-site-verification=XXXXX`
3. В Namecheap (Domain List → Advanced DNS) добавить TXT с host `@` и этим значением
4. Подождать 5-15 мин propagation → вернуться в Admin Console → **Verify**

Для 20-50 доменов это ~час кликов — поэтому автоматизируем.

### 2.2 Полная автоматизация — цепочка скриптов

Процесс разбит на 2 этапа, потому что каждый требует разных Google API:

**Этап A — добавить домены в tenant** (без verification)
- Скрипт: [aivy-add-domains.js](../../../magnum-opus/infra/aivy-add-domains.js)
- Что делает: `admin.domains.insert()` для каждого домена из списка
- Scope: `admin.directory.domain`
- После запуска: домены в tenant со статусом `verified: false`

**Этап B — получить TXT challenge + прописать + верифицировать**
- Скрипт: [aivy-finish-verification.js](../../../magnum-opus/infra/aivy-finish-verification.js)
- Что делает для каждого домена:
  1. `siteVerification.webResource.getToken()` → получить `google-site-verification=...`
  2. Namecheap API → добавить TXT-запись (сохраняя existing hosts)
  3. `dig +short TXT` каждые 10 сек, ждать пока запись не пропагируется (default 180 сек)
  4. `siteVerification.webResource.insert()` → Google подтверждает ownership
  5. `admin.domains.get()` → проверить `verified: true`
- Scope: `admin.directory.domain` + **`siteverification`**

### 2.3 Pre-flight — что должно быть готово

| Требование | Как проверить |
|------------|---------------|
| **Site Verification API** включён в GCP project `easystaff-instantly-freshboxes` | [Library](https://console.developers.google.com/apis/api/siteverification.googleapis.com/overview?project=978895579994) → должно быть Enabled |
| **OAuth token с scope `siteverification`** | `python3 -c 'import json; print(json.load(open("sofia-oauth-token.json"))["scope"])'` — должен включать `siteverification` |
| **Namecheap API Sally2 активен**, IP `46.62.210.24` в whitelist | Test: `curl "https://api.namecheap.com/xml.response?ApiUser=Sally2&ApiKey=d736e84e16b141b3a8cf0f51302c3aeb&UserName=Sally2&ClientIp=46.62.210.24&Command=namecheap.domains.dns.getHosts&SLD=<domain>&TLD=co"` — `Status="OK"` |

### 2.4 Если нужно обновить OAuth scope (первый раз)

OAuth consent происходит в браузере → делается один раз на Mac, потом токен живёт вечно через `refresh_token`:

```bash
cd /Users/user/sales_engineer/magnum-opus/infra
node aivy-oauth-login.js
# открывается браузер → логин под artem@aivy-digital.com → consent всех 4 scope
# токен сохраняется в sofia-oauth-token.json
scp sofia-oauth-token.json hetzner:~/magnum-opus-project/repo/infra/
```

Источник: [aivy-oauth-login.js](../../../magnum-opus/infra/aivy-oauth-login.js)

### 2.5 Боевой запуск

На Hetzner:
```bash
cd ~/magnum-opus-project/repo/infra

# Этап A — добавить 7 доменов в tenant
node aivy-add-domains.js --domains-file aivy-domains-batch1.txt

# Dry-run проверка (опционально) — какие домены уже есть vs будут добавлены
node aivy-dryrun-add-domains.js --domains-file aivy-domains-batch1.txt

# Этап B — получить TXT, прописать, верифицировать (полный цикл)
node aivy-finish-verification.js --domains-file aivy-domains-batch1.txt --max-wait 300

# Запуск только на одном домене (для дебага)
node aivy-finish-verification.js --domains-file aivy-domains-batch1.txt --only syntab.co
```

### 2.6 Что делать если упал

| Ошибка | Причина | Фикс |
|--------|---------|------|
| `Site Verification API has not been used in project 978895579994` | API не включён в GCP | Кликнуть Enable на [странице API](https://console.developers.google.com/apis/api/siteverification.googleapis.com/overview?project=978895579994), подождать 1-2 мин |
| `The domain (X) doesn't seem to be associated with your account` | Wrong Namecheap account | Домен куплен не на `Sally2`, проверить owner, возможно надо использовать `decaster3` API key |
| `TIMEOUT waiting for TXT propagation` | DNS долго пропагируется | Запустить скрипт повторно — он умеет читать существующие записи и не дублирует |
| `admin.domains.get`: `Resource Not Found: domain` | Домен не добавлен в tenant на Этапе A | Запустить `aivy-add-domains.js` сначала |

### 2.7 Результат сессии 2026-04-24

| Домен | Status | Пояснение |
|-------|--------|-----------|
| syntab.co | verified ✓ | pilot run, потеряли дефолтный Namecheap URL-redirect (переопределим в Шаге 3) |
| voxpilot.co | verified ✓ | |
| contactpilot.co | verified ✓ | |
| salestide.co | verified ✓ | |
| verostack.co | verified ✓ | |
| growthnode.co | verified ✓ | |
| fronttide.co | verified ✓ | был добавлен ранее (2026-04-22), скрипт пропустил |

Все 7 доменов в Domain Tracker помечены `workspace_linked = Y`.

### 2.8 Known issues в существующих скриптах Артёма

⚠️ **Regex-баг в `google-workspace-add-domains.js` и `namecheap-add-mx.js`** (строки ~109, ~22 соответственно):

```js
const hostMatches = [...getXml.matchAll(/<host\s([^/]*?)\/>/g)];
//                                         ^^^ стопорится на '/' внутри Address
```

Проблема: `[^/]*?` не матчит host-записи типа URL-redirect (Address содержит `http://...`). При SetHosts эти записи теряются. Исправление — замена на `[^>]*?`:

```js
const hostMatches = [...getXml.matchAll(/<host\s([^>]*?)\/>/g)];
```

Уже исправлено в [aivy-finish-verification.js](../../../magnum-opus/infra/aivy-finish-verification.js). **Старые скрипты Артёма не трогал** — если запустишь их на доменах с URL/CNAME, получишь тихое удаление записей.

---

## Шаг 3 — DNS-записи

Задача: прописать полный пакет DNS на каждом домене — MX, SPF, DMARC, email tracking CNAME, redirect URL. **DKIM идёт отдельно** (нужен Google Admin Console, см. Шаг 3.5).

### 3.1 Что прописываем (Sally SOP)

| Host | Type | Value | Purpose |
|------|------|-------|---------|
| `@` | MX | `SMTP.GOOGLE.COM` pref=1 | доставка в Gmail |
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` | SPF — кто имеет право отправлять |
| `_dmarc` | TXT | `v=DMARC1; p=reject; rua=mailto:dmarc-reports@{domain}; ruf=mailto:dmarc-reports@{domain}; sp=reject; adkim=s; fo=1;` | DMARC политика |
| `emailtracking` | CNAME | `open.sleadtrack.com` | SmartLead tracking domain |
| `www` | URL301 | `https://onsocial.ai/` | redirect корня домена |
| `@` | TXT | `google-site-verification=...` | **preserve** из Шага 2 |
| `google._domainkey` | TXT | `v=DKIM1; k=rsa; p=MII...` | **preserve** если уже есть DKIM (Шаг 3.5) |

### 3.2 MX — какую запись использовать

У Петра два скрипта с разной MX-конфигурацией:

| Скрипт | MX value |
|--------|----------|
| [Instruction](../../../magnum-opus/infra/Instruction) + [namecheap-set-dns.ps1](../../../magnum-opus/infra/namecheap-set-dns.ps1) | `SMTP.GOOGLE.COM` pref=1 |
| [namecheap-add-mx.js](../../../magnum-opus/infra/namecheap-add-mx.js) | `ASPMX.L.GOOGLE.COM` pref=1 |

**Мы следуем SOP → используем `SMTP.GOOGLE.COM`**. Оба варианта работают с Gmail.

Для справки: Google docs рекомендует 5 MX (ASPMX.L + 4 ALT), но для совместимости с Petrовской документацией идём через `SMTP.GOOGLE.COM`.

### 3.3 Автоматизация — `aivy-set-dns.js`

Файл: [aivy-set-dns.js](../../../magnum-opus/infra/aivy-set-dns.js)

```bash
# На Hetzner
cd ~/magnum-opus-project/repo/infra

# Dry-run (обязательно сначала!)
node aivy-set-dns.js --domains-file aivy-domains-batch1.txt --redirect-url https://onsocial.ai/ --dry-run

# Боевой запуск на чистых доменах (--skip-if-has-mx защищает уже настроенные)
node aivy-set-dns.js --domains-file aivy-domains-batch1.txt --redirect-url https://onsocial.ai/ --skip-if-has-mx

# Для replace MX на доменах где MX уже есть — отдельный файл без уже настроенных
node aivy-set-dns.js --domains-file aivy-domains-batch1-except-fronttide.txt --redirect-url https://onsocial.ai/
```

Скрипт:
1. Читает `existing hosts` через Namecheap API (regex `[^>]*?` — спец-фикс чтобы URL-записи с `/` не терялись)
2. Сохраняет TXT google-site-verification + TXT google._domainkey (DKIM) — они НЕ перетираются
3. Добавляет новый пакет (MX/SPF/DMARC/CNAME/URL)
4. Делает `setHosts` с `&EmailType=MX` — обязательный параметр, иначе Namecheap накроет MX eforward'ами

### 3.4 Подводные камни

#### ⚠️ `EmailType=FWD` (критичный)

На **Sally2** аккаунте новые домены по умолчанию идут с `EmailType=FWD` — Namecheap email forwarding. При `setHosts` без `&EmailType=MX` Namecheap **удаляет все custom MX записи** и вставляет свои `eforward1-5.registrar-servers.com`.

Признак: `dig MX domain.co` показывает `*.registrar-servers.com` вместо Google.

Фикс: в URL setHosts добавить `&EmailType=MX` — наш `aivy-set-dns.js` это делает. Оригинальный `namecheap-set-dns.ps1` Петра **этого не делает** — на `decaster3` домены могут быть с `EmailType=MX` по дефолту (другой профиль аккаунта), поэтому там проблема не проявлялась.

#### ⚠️ Regex-баг в старых скриптах Петра

В [namecheap-add-mx.js](../../../magnum-opus/infra/namecheap-add-mx.js:22) и `google-workspace-add-domains.js`:

```js
const hostMatches = [...getXml.matchAll(/<host\s([^/]*?)\/>/g)];
//                                         ^^^ стопорится на '/' внутри Address
```

URL-redirect записи (`http://...`) содержат `/` в Address → regex обрывается → запись **не попадает в preserve list** → теряется при setHosts.

В `aivy-set-dns.js` использован `[^>]*?` — фикс. Старые скрипты Петра не чиню (могут быть рабочие зависимости), но **не запускай их на доменах с URL-записями** без форка.

#### ⚠️ DNS propagation lag

TTL 1800 сек (30 мин). `dig @8.8.8.8` может показывать старое содержимое ещё полчаса. Для свежей проверки используй:
- Namecheap API `getHosts` — мгновенно из source of truth
- `dig @1.1.1.1` (Cloudflare) — часто быстрее обновляется чем Google

### 3.5 DKIM — отдельная подзадача

DKIM генерится **в Google Admin Console**, НЕ через Namecheap. Путь:
1. [admin.google.com](https://admin.google.com) → Apps → Google Workspace → Gmail → **Authenticate email**
2. Выбрать домен → **Generate new record** (2048-bit recommended)
3. Google выдаст TXT запись с `Host: google._domainkey` и value `v=DKIM1; k=rsa; p=...`
4. Прописать в Namecheap (host `google._domainkey`, type `TXT`)
5. В Admin вернуться → **Start authentication**

**Автоматизация**: есть [google-workspace-enable-dkim.js](../../../magnum-opus/infra/google-workspace-enable-dkim.js) — Puppeteer скрипт для батч-enable, но написан под **русский UI** Admin Console. На `artem@aivy-digital.com` UI может быть английским — потребуется адаптация.

**Рекомендация**: на первый батч **6 доменов вручную** (~12 минут), потом если доменов будет много — адаптировать Puppeteer.

### 3.6 Результат сессии 2026-04-24

| Домен | MX | SPF | DMARC | Tracking | Redirect | DKIM | dns_configured |
|-------|----|----|-------|----------|----------|------|----------------|
| syntab.co | ✓ | ✓ | ✓ | ✓ | ✓ | **TODO** | Y |
| voxpilot.co | ✓ | ✓ | ✓ | ✓ | ✓ | **TODO** | Y |
| contactpilot.co | ✓ | ✓ | ✓ | ✓ | ✓ | **TODO** | Y |
| salestide.co | ✓ | ✓ | ✓ | ✓ | ✓ | **TODO** | Y |
| verostack.co | ✓ | ✓ | ✓ | ✓ | ✓ | **TODO** | Y |
| growthnode.co | ✓ | ✓ | ✓ | ✓ | ✓ | **TODO** | Y |
| fronttide.co | ✓ (не трогали) | ✓ | ✓ | ✓ | нет | ✓ | Y |

**Следующий шаг — DKIM на 6 новых доменах**, потом Шаг 4 (создание ящиков).

---

## Шаг 4 — Создание почтовых ящиков

_TODO_

---

## Шаг 5 — SmartLead + Warmup

_TODO_

---

## Шаг 6 — Instantly + Spam-тесты

_TODO_

---

## Известные подводные камни

### Гайд живёт вне submodule — почему

В `~/.claude/hooks/auto_git_pull.sh` есть блок:
```bash
GHOST_DIRS="backend checks ... infra mcp ..."
for dir in $GHOST_DIRS; do
    if [[ -d "$GIT_ROOT/$dir" ]]; then rm -rf "$GIT_ROOT/$dir"; fi
done
```

Hook сносит `infra/` когда GIT_ROOT = submodule `magnum-opus`. **Это сломало работу с гайдом внутри submodule**: каждая `Write/Edit` триггерила pre-hook, который рекурсивно удалял `infra/` (и гайд, и все скрины).

Решение:
- **Гайд** лежит в parent repo: `sofia/docs/outreach/email-infra-guide.md`
- **Скрины** тоже в parent: `sofia/docs/outreach/images/email-infra/`
- **Скрипты** остаются в submodule: `magnum-opus/infra/*.js, *.ps1` — они tracked в git и восстанавливаются через `git restore infra/` когда hook их сносит

TODO: поправить hook чтобы не трогал `infra/` внутри submodule. Или добавить `magnum-opus/infra` в exception.
