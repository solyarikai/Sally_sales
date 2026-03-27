---
name: reply-onsocial
description: Анализирует входящий ответ на аутрич OnSocial и генерирует готовый ответ на английском. Используй когда пользователь говорит "skill reply onsocial", "напиши ответ", "что ответить", "onsocial reply", или вставляет текст входящего письма/LinkedIn-сообщения по OnSocial.
---

# Reply — OnSocial

Источник правды: `projects/OnSocial/docs/operator_playbook.md`

## Инструкции

**Шаг 1 — Классифицируй ответ**

Определи тип:
- `interested` → хочет демо, просит материалы, общий позитив
- `meeting_request` → предлагает конкретное время, просит calendar link, хочет созвон
- `question` → цена, как работает, API, сравнение с конкурентом, покрытие
- `not_interested` → есть решение, вежливый/агрессивный отказ
- `ooo` → автоответ об отсутствии
- `wrong_person` → редирект на другого человека

**Шаг 2 — Собери контекст**

Из того что дал пользователь:
- Имя, компания, должность
- Точно что написал (дословно важно — особенно если предложил время или задал вопрос)
- Чем занимается компания — для персонализации первой строки

**Шаг 3 — Напиши ответ**

Правила (из реальных успешных replies):
- **2-4 предложения** — не больше
- **Первая строка = ответ на их конкретную реплику**, не "Thanks for your reply"
- **Если предложили время → подтверди это время** (не посылай просто calendar link)
- **Если спросили вопрос → ответь прямо**, потом предложи call
- **Зеркали язык**: если написали по-русски — отвечай по-русски
- **Один CTA**: calendar link, подтверждение времени, или вопрос в ответ
- **Подпись**: `Bhaskar` (email) / `Bhaskar Vishnu` (LinkedIn)
- **Ноль пустых фраз**: "Great to hear from you!", "Thanks for your interest!" — не пиши

**Шаг 4 — Action**

Одна строка после письма:
`→ Action: [что сделать в SmartLead/GetSales]`

## Шаблоны по типу

### meeting_request — предложил конкретное время
```
Hi {name},

{day + time} works for me. Sending a calendar invite now.

Talk soon,
Bhaskar
```
*→ Action: confirm в SmartLead, создай meeting в календаре*

### meeting_request — просит calendar link / "let's talk"
```
Hi {name},

Here's my calendar: {calendar_link}

Bhaskar
```

### interested — просит материалы / "send more info"
```
Hi {name},

Happy to share. {one sentence on what's most relevant to their use case}.

Here's our overview: {link}. Worth a 15-min call to walk through it for your specific setup — {calendar_link}

Bhaskar
```

### interested — общий позитив / "sounds good"
```
Hi {name},

Let's do it — here's my calendar: {calendar_link}

Bhaskar
```

### question — цена
```
Hi {name},

Pricing is pay-per-request — you pay per successful API call, no monthly minimums. Custom rates based on volume.

To give you an accurate number: how many creator profiles do you typically analyze per month, and which platforms?

{calendar_link} if easier to talk through.

Bhaskar
```

### question — как работает / API
```
Hi {name},

{direct answer in 1-2 sentences, specific to what they asked}.

Happy to show it live — {calendar_link}

Bhaskar
```

### question — сравнение с конкурентом
```
Hi {name},

vs {competitor}: we update profiles every 24-48h (they're weekly), city-level demographics for LATAM/EU/US, fraud scoring built in. No campaign layer — just raw data and API.

Want me to run a side-by-side on 5-10 profiles from your portfolio?

Bhaskar
```

### not_interested — есть решение
```
Hi {name},

Understood. If you ever want to compare on specific profiles, happy to run it. Good luck with {their tool/project}.

Bhaskar
```
*→ Action: mark as "not now", add 3-month follow-up reminder*

### not_interested — агрессивный / spam complaint
*→ Action: remove from ALL campaigns immediately. Do not reply.*

### ooo
*→ Action: note return date, schedule follow-up for return date + 2 days. No reply now.*

### wrong_person — редирект
```
Hi {name},

Thanks for the redirect — I'll reach out to {referred_person} directly.

Bhaskar
```
*→ Action: add {referred_person} to SmartLead/GetSales, mention "{name} suggested I reach out" in opening line*

## Ключевые факты об OnSocial

- 450M+ creator profiles: Instagram, TikTok, YouTube
- 25M+ LATAM creators (Brazil, Mexico, Colombia — city level)
- 27 discovery filters: geo, engagement, interests, credibility
- Fraud scoring built in
- Pay-per-request (per successful API call), no public pricing — custom deals
- NOT a campaign management tool — only data, filters, API
- Modash, Captiv8, Lefty, Obviously already run on their API
- White-label available for agencies/platforms
- Trusted by: Viral Nation, Whalar, Billion Dollar Boy
