# Email Infrastructure — Build Guide

Создание почтовой инфры для cold outreach: от покупки доменов до warmup в SmartLead.
Универсальный гайд. Подставляй свои значения (tenant, домены, персона).

**Скрипты**: [magnum-opus/infra/](../../../magnum-opus/infra/) — все `aivy-*.js` и `.ps1`.
**Единый реестр доменов**: [Ops | Infra | Domains](https://docs.google.com/spreadsheets/d/1nht7tNVXdbLtLdUxbDguxnGbV-Zv1q5pMK3Uter7oyI).

Обозначения в гайде:
- `<tenant>` — домен primary GW tenant (например `aivy-digital.com`)
- `<domain>` — один из доменов для ящиков (например `voxpilot.co`)
- `<login>` — login-часть ящика (например `sofia`)
- `<persona>` — Given/Family Name отправителя
- `<batch-password>` — общий пароль всех ящиков одной партии
- `<redirect-url>` — корневой сайт куда редиректит `www.<domain>`
- `<client>` — кому принадлежит батч в Domain Tracker

---

## Аккаунты

| Сервис | Логин | Пароль / Key | Примечание |
|--------|-------|--------------|------------|
| Namecheap (новые домены) | `Sally2` | `A5(m+zgvm4xDDZc` | email: `services@getsally.io` |
| Namecheap API (Sally2) | `Sally2` | `d736e84e16b141b3a8cf0f51302c3aeb` | whitelisted IP: `46.62.210.24` |
| Namecheap (legacy) | `decaster3` | `wP#DSVN-8X/yF&6` | старые домены, `.ps1` |
| Namecheap API (decaster3) | `decaster3` | `f3335861b92247779364649ae2beb014` | whitelisted: `150.241.224.134`, `46.62.210.24` |
| GCP project (OAuth) | `easystaff-instantly-freshboxes` | client_id `978895579994-duj44rs0l93rpbt2vrp844nptv23k940` | `sofia-oauth-*.json` |
| SmartLead | `services@getsally.io` | `RHHvSacOKxxzp80N` | API key в `.aivy-credentials.json` |
| Instantly API | Bearer token | см. [instantly-inbox-placement.md](../../../magnum-opus/infra/instantly-inbox-placement.md) | |

Креды конкретных tenant-ов / ящиков — в `.aivy-credentials.json` (gitignored).

---

## Этапы

1. [Покупка доменов на Namecheap](#шаг-1--покупка-доменов)
2. [Подключение к Google Workspace + verification](#шаг-2--google-workspace)
3. [DNS-записи (MX, SPF, DMARC, tracking, redirect)](#шаг-3--dns)
4. [DKIM](#шаг-35--dkim)
5. [Создание почтовых ящиков](#шаг-4--почтовые-ящики)
6. [SmartLead + warmup](#шаг-5--smartlead--warmup)
7. [Instantly spam-тесты](#шаг-6--instantly)

После каждого шага обновляем Domain Tracker.

---

## Domain Tracker

**Ссылка**: [Ops | Infra | Domains](https://docs.google.com/spreadsheets/d/1nht7tNVXdbLtLdUxbDguxnGbV-Zv1q5pMK3Uter7oyI) (папка [Ops / Infra](https://drive.google.com/drive/folders/1pdHLW18i3RM7LtmTjD_vHBs4ZKpkBHNg))

Auto-renew OFF везде — это единственный источник правды по экспирации.

### Схема (19 колонок)

| # | Колонка | Пример | Заполняется на |
|---|---------|--------|----------------|
| A | `domain` | `voxpilot.co` | Шаг 1 |
| B | `tld` | `.co` | Шаг 1 |
| C | `registrar` | `Namecheap` | Шаг 1 |
| D | `registrar_account` | `Sally2` | Шаг 1 |
| E | `client` | `<client>` | Шаг 1 |
| F | `purchased_at` | `YYYY-MM-DD` | Шаг 1 |
| G | `expires_at` | `=F+365*H` (формула) | auto |
| H | `years_paid` | `1` | Шаг 1 |
| I | `days_left` | `=G-TODAY()` (формула) | auto |
| J | `auto_renew` | `N` | Шаг 1 |
| K | `dns_configured` | `Y` / `partial` / `N` | Шаг 3 |
| L | `workspace_linked` | `Y` / `N` | Шаг 2 |
| M | `redirect_url` | `<redirect-url>` | Шаг 3 |
| N | `last_health_check` | `YYYY-MM-DD` | auto (TODO cron) |
| O | `mailboxes_count` | `2` | Шаг 4 |
| P | `smartlead_connected` | `Y` / `N` | Шаг 5 |
| Q | `instantly_connected` | `Y` / `N` | Шаг 6 |
| R | `status` | `active` / `expired` / `paused` / `dropped` | lifecycle |
| S | `notes` | `batch <client>-N` | свободный текст |

### Ручные улучшения (один раз)

- Freeze header row
- Conditional formatting на `days_left`: `<30` красный, `<90` жёлтый, `<0` тёмно-красный + bold
- Data validation (Y/N, статусы) на колонках J, K, L, P, Q, R

---

## Шаг 1 — Покупка доменов

### 1.1 Именование

Паттерн `client + field`. Минимум 2 ящика на домен (см. Шаг 4), поэтому закупаем пачки созвучных.

### 1.2 Beast Mode на Namecheap

1. Залогиниться как `Sally2`
2. Рядом с поиском на главной — **Beast Mode**
3. Ввести keywords (до 5000)
4. Фильтры:
   - Price Range: верхний лимит под бюджет
   - Show Premiums: OFF
   - Hide Unavailable: ON
5. **Generate** → выбрать нужные → в корзину

### 1.3 Checkout

- **Free Domain Privacy** — автоматом (не снимаем)
- **Renewal Settings**: `Do not auto-renew` ⚠️ (дату экспирации ведём в Domain Tracker)
- **Pay Now**

После оплаты → **Account → Domain List**.

### 1.4 Автоматизация массовой регистрации

```powershell
# Только на Hetzner или whitelisted IP
.\namecheap-register-domains.ps1 -DomainsFile <your-batch>.txt
```

Скрипты в [magnum-opus/infra/](../../../magnum-opus/infra/):
- [namecheap-register-domains.ps1](../../../magnum-opus/infra/namecheap-register-domains.ps1) — батч-регистрация + WhoisGuard
- [namecheap-set-dns.ps1](../../../magnum-opus/infra/namecheap-set-dns.ps1) — установка DNS
- [namecheap-add-mx.js](../../../magnum-opus/infra/namecheap-add-mx.js) — MX only

### 1.5 Заполнить Domain Tracker

Добавить строки (колонки A-F, H, J):
- `domain`, `tld`, `registrar=Namecheap`, `registrar_account=Sally2`
- `client`
- `purchased_at` (сегодня), `years_paid=1`, `auto_renew=N`

---

## Шаг 2 — Google Workspace

Добавить домены в `<tenant>` + подтвердить ownership через TXT.

### 2.1 Pre-flight

Один раз на tenant:

| Требование | Как проверить |
|------------|---------------|
| Admin Directory API + Site Verification API в GCP | [API library](https://console.developers.google.com/apis/library) → оба Enabled |
| OAuth token со scopes `admin.directory.user`, `admin.directory.domain`, `siteverification` | `cat sofia-oauth-token.json` → `scope` должен содержать все три |
| Namecheap API на `46.62.210.24` | `curl` на `getHosts` → `Status="OK"` |

### 2.2 Refresh OAuth token (если токен протух или scope нужен)

Запускается **один раз** на Mac (нужен браузер):

```bash
cd /Users/user/sales_engineer/magnum-opus/infra
node aivy-oauth-login.js
# браузер → login под admin tenant → consent
scp sofia-oauth-token.json hetzner:~/magnum-opus-project/repo/infra/
```

Refresh token живёт вечно — после SCP всё работает с Hetzner.

### 2.3 Dry-run — сверка с текущим состоянием tenant

```bash
# На Hetzner
node aivy-dryrun-add-domains.js --domains-file <your-batch>.txt
```

Покажет какие домены **уже в tenant** (SKIP) и какие **будут добавлены** (ADD).

### 2.4 Добавление + verification

```bash
# Этап A — insert в tenant
node aivy-add-domains.js --domains-file <your-batch>.txt

# Этап B — получить TXT challenge, записать в Namecheap, verify
node aivy-finish-verification.js --domains-file <your-batch>.txt --max-wait 300

# Отладка одного домена
node aivy-finish-verification.js --domains-file X.txt --only <domain>
```

`aivy-finish-verification.js` цикл на домен:
1. `siteVerification.webResource.getToken` → TXT challenge от Google
2. Namecheap API → `setHosts` (сохраняет existing + добавляет TXT challenge)
3. `dig TXT` каждые 10 сек до propagation (default 180 сек)
4. `siteVerification.webResource.insert` → Google верифицирует
5. `admin.domains.get` → `verified: true`

### 2.5 Заполнить Domain Tracker

После `verified: true` → колонка L (`workspace_linked`) = `Y`.

---

## Шаг 3 — DNS

Полный пакет DNS на каждом домене.

### 3.1 Записи

| Host | Type | Value | Purpose |
|------|------|-------|---------|
| `@` | MX pref=1 | `SMTP.GOOGLE.COM` | доставка в Gmail (SOP-стандарт) |
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` | SPF |
| `_dmarc` | TXT | `v=DMARC1; p=reject; rua=mailto:dmarc-reports@<domain>; ruf=mailto:dmarc-reports@<domain>; sp=reject; adkim=s; fo=1;` | DMARC |
| `emailtracking` | CNAME | `open.sleadtrack.com` | SmartLead tracking |
| `www` | URL301 | `<redirect-url>` | redirect корня |
| `@` | TXT | `google-site-verification=...` | preserve из Шага 2 |
| `google._domainkey` | TXT | `v=DKIM1; k=rsa; p=MII...` | preserve из Шага 3.5 (DKIM) |

### 3.2 Запуск

```bash
# На Hetzner — dry-run
node aivy-set-dns.js --domains-file <your-batch>.txt --redirect-url <redirect-url> --dry-run

# Боевой (не трогает домены у которых MX уже есть)
node aivy-set-dns.js --domains-file <your-batch>.txt --redirect-url <redirect-url> --skip-if-has-mx

# Принудительно переписать всё (для свежих доменов)
node aivy-set-dns.js --domains-file <your-batch>.txt --redirect-url <redirect-url>
```

Скрипт сохраняет существующие `google-site-verification` и `google._domainkey` TXT при перезаписи.

### 3.3 Важный параметр `&EmailType=MX`

Скрипт передаёт `&EmailType=MX` в `setHosts`. **Без него** Namecheap на Sally2-аккаунте подставляет свои `eforward*.registrar-servers.com` MX-записи (default = Email Forwarding), перезаписывая custom Google MX.

### 3.4 Проверка

```bash
# Свежий кэш (Cloudflare)
dig +short MX <domain> @1.1.1.1
dig +short TXT <domain> @1.1.1.1 | grep spf1
dig +short TXT _dmarc.<domain> @1.1.1.1
dig +short CNAME emailtracking.<domain> @1.1.1.1

# Source of truth — Namecheap API
curl -s "https://api.namecheap.com/xml.response?ApiUser=Sally2&ApiKey=d736e84e16b141b3a8cf0f51302c3aeb&UserName=Sally2&ClientIp=46.62.210.24&Command=namecheap.domains.dns.getHosts&SLD=<sld>&TLD=<tld>"
```

8.8.8.8 может держать старый кэш до 30 мин (TTL 1800).

### 3.5 Заполнить Domain Tracker

Колонки K (`dns_configured=Y`), M (`redirect_url=<redirect-url>`).

---

## Шаг 3.5 — DKIM

DKIM генерится **только в Google Admin Console** — нет public API.

### Workflow (batch через new-tab-per-domain)

Оптимально для 2+ доменов:

1. **Cmd+T** → [admin.google.com/ac/apps/gmail/authenticateemail](https://admin.google.com/ac/apps/gmail/authenticateemail)
2. `Selected domain` → выбрать домен
3. Если записи нет → **Generate new record** (2048-bit) → скопировать TXT value
4. **Вкладку не закрывать** (вернёшься на шаге 7)
5. **Cmd+T** снова → следующий домен → шаги 2-4
6. Когда все N ключей собраны → записать все TXT в Namecheap (см. ниже)
7. Пройти по каждой открытой вкладке → **Start authentication**
8. Status = `Authenticating email with DKIM` ✓

**Почему new tab**: клик `Start auth` триггерит DNS-запрос Google. Если TXT в DNS ещё нет — вкладка «запоминает» fail. Новая вкладка = свежий запрос после записи TXT.

### Batch-запись TXT в Namecheap

Helper: [aivy-namecheap-add-txt.js](../../../magnum-opus/infra/aivy-namecheap-add-txt.js) — принимает JSON через stdin (stdin, а не argv — SSH ломает `;` в value).

```bash
# На Hetzner (whitelisted IP)
echo '{"domain":"<domain>","host":"google._domainkey","value":"v=DKIM1; k=rsa; p=..."}' \
  | node /home/leadokol/magnum-opus-project/repo/infra/aivy-namecheap-add-txt.js

# Из Mac через SSH (для batch)
for pair in "<domain1>:$KEY1" "<domain2>:$KEY2"; do
  DOMAIN="${pair%%:*}"; VALUE="${pair#*:}"
  python3 -c "import json,sys; print(json.dumps({'domain':sys.argv[1],'host':'google._domainkey','value':sys.argv[2]}))" \
    "$DOMAIN" "$VALUE" | ssh hetzner 'node /home/leadokol/magnum-opus-project/repo/infra/aivy-namecheap-add-txt.js'
done
```

Helper удаляет старую `google._domainkey` TXT (если была) и вставляет новую, сохраняя все остальные hosts + `&EmailType=MX`.

---

## Шаг 4 — Почтовые ящики

По SOP — 2 ящика на домен (`<login>@` + `<login>.<n>@`).

### 4.1 Настроить скрипт под batch

[aivy-create-users.js](../../../magnum-opus/infra/aivy-create-users.js) — перед запуском поправить `USERS` и `PASSWORD`:

```js
const PASSWORD = '<batch-password>';
const USERS = [
  { login: '<login>',       givenName: '<FirstName>', familyName: '<LastName>' },
  { login: '<login>.<n>',   givenName: '<FirstName>', familyName: '<LastName>' },
];
```

### 4.2 Запуск

```bash
# На Hetzner — dry-run
node aivy-create-users.js --domains-file <your-batch>.txt --dry-run

# Боевой — создание через admin.directory API
node aivy-create-users.js --domains-file <your-batch>.txt
```

**~1.5 сек на ящик**. Error `Entity already exists` (HTTP 409) — уже есть, не ошибка.

### 4.3 2FA + backup codes (по SOP)

```bash
node sofia-backup-codes.js --domains-file <your-batch>.txt
```

Генерит через Admin API + сохраняет CSV `<your-batch>-backup-codes.csv` (формат `email,code1,code2,...`). Этот CSV потом используется в Шаге 5 (SmartLead OAuth, если ящики с 2FA).

### 4.4 Заполнить Domain Tracker + креды

- Колонка O (`mailboxes_count=2`)
- В `.aivy-credentials.json` добавить запись batch (список ящиков, пароль, 2fa_enabled)

---

## Шаг 5 — SmartLead + Warmup

### 5.1 Подключение — через UI

Для каждого ящика в [app.smartlead.ai/app/email-accounts](https://app.smartlead.ai/app/email-accounts):

1. **Add Account** (сверху справа)
2. **Smartlead Infrastructure** → **Google OAuth**
3. Модалка «Connect your Gsuite account» → **Connect Account**
4. Google OAuth окно:
   - Email конкретного ящика
   - Password (batch password)
   - 2FA backup code если 2FA включено
   - **Allow** permissions
5. Вернуться в SmartLead → настройки warmup (см. 5.2)

**~30 сек на ящик**.

### 5.2 Warmup параметры (по SOP)

В Mailbox settings каждого ящика:

| Раздел | Параметр | Значение |
|--------|----------|----------|
| Warmup Settings | Enable Warmup | **ON** |
| Warmup Settings | Total number of warm up emails per day | **40** |
| Warmup Settings | Bulk Update Daily Rampup | **ON** |
| Warmup Settings | Reply Rate | **35%** |
| Warmup Settings | Bulk update Auto-adjust warmup/sending ratio | **ON** |
| General | Messages per day | **50** |
| General | Use a custom tracking domain | **ON** |
| General | Custom tracking domain URL | `http://emailtracking.<domain>` |

Tracking domain — конкретный на каждый ящик (`emailtracking.<domain>` где `<domain>` = домен самого ящика). CNAME уже настроен в Шаге 3.

### 5.3 Проверка

```bash
curl -s "https://server.smartlead.ai/api/v1/email-accounts?api_key=<KEY>&limit=100&offset=0" | jq '.[] | .from_email'
```

### 5.4 Заполнить Domain Tracker

Колонка P (`smartlead_connected=Y`).

---

## Шаг 6 — Instantly

Spam-тесты по SOP — 2 раза в неделю (пн/чт 10:00 MSK).

### 6.1 Подключение

Процесс аналогичен SmartLead (Google OAuth через UI).

### 6.2 Spam-тест

1. Instantly → **Inbox Placement** → **Add New**
2. Client Name (например `<client>-batch-N`)
3. One time → From Instantly → Continue → Save

Если расширение существующего клиента — добавить ящики в существующий тест.

### 6.3 Анализ результатов

Cron раз в 2 дня (Tue/Fri 06:00 UTC) → Slack отчёт.

Если deliverability < 80% для ящика:
1. Отправить ящик в Slack канал проекта
2. Удалить/выделить в Domain Tracker
3. Удалить ящик из Google Workspace

### 6.4 Заполнить Domain Tracker

Колонка Q (`instantly_connected=Y`).

Детали API и токены: [instantly-inbox-placement.md](../../../magnum-opus/infra/instantly-inbox-placement.md).

---

## Troubleshooting

### Namecheap `Invalid request IP`
Проверь с какого IP запускаешь — whitelist'ены только `46.62.210.24` (Hetzner) и `150.241.224.134`. Local run из нестандартной сети упадёт.

### Namecheap eforward-MX вместо Google
Не передал `&EmailType=MX` в `setHosts`. Скрипт `aivy-set-dns.js` это делает; при ручном `curl` — добавить параметр.

### DKIM — в Admin status `Not authenticating email`
TXT запись в DNS не совпадает с тем, что ждёт Google. Открой Admin → Selected domain → скопируй expected TXT value → запиши в Namecheap через helper → Stop/Start authentication в новой вкладке.

### DNS propagation delay
TTL 1800 (30 мин). 8.8.8.8 кэширует долго — используй `dig @1.1.1.1` или API Namecheap для мгновенной сверки.

### `infra/` каталог пропал из submodule magnum-opus
`~/.claude/hooks/auto_git_pull.sh` содержит `rm -rf infra/` как cleanup ghost dirs. Фикс: `cd magnum-opus && git restore infra/`. Гайд и скрины хранятся в parent repo (`sofia/docs/outreach/`) чтобы не попадать под хук.
