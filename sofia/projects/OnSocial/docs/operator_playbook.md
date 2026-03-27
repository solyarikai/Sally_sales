# Operator Playbook — OnSocial Reply Handling

Based on analysis of 36,192 conversations across SmartLead (email) and GetSales (LinkedIn).

---

## Overview

| Category | Count | % | Action Required |
|----------|-------|---|-----------------|
| interested | 738 | 2.0% | HIGH — respond within 2h |
| meeting_request | 1286 | 3.5% | HIGH — respond within 1h |
| question | 803 | 2.2% | HIGH — respond within 4h |
| not_interested | 2894 | 8.0% | LOW — acknowledge gracefully |
| out_of_office | 4785 | 13.2% | MEDIUM — schedule follow-up |
| wrong_person | 6725 | 18.5% | MEDIUM — update contact, redirect |
| unsubscribe | 569 | 1.6% | NONE — auto-handle, remove from list |
| other | 18517 | 51.0% | REVIEW — manual triage needed |

---
## 1. INTERESTED — Lead wants to engage

**Priority:** Respond within 2 hours. This is your hottest lead.

### 1.1 Wants Demo/Walkthrough (37 cases)

**Pattern:** Lead explicitly asks to see the product in action.

**Action:**
1. Send calendar link immediately
2. Suggest 2-3 time slots
3. Mention you'll prepare a personalized demo based on their use case

**Template:**
```
Hi {name},

Great to hear you're interested! I'd love to walk you through OnSocial
and show you how it works with {their_use_case}.

Here's my calendar to pick a time that works:
{calendar_link}

Alternatively, I'm available {slot_1} or {slot_2}.

Looking forward to it!
```

**Real examples:**
- **Andrei Ptitsyn (Algotoria)**: "Спасибо, Андрей! Изучим и вернемся к вам если будет интересно. -- Катерина чт, 24 апр. 2025 г. в 11:40, Andrei Ptitsyn : Добрый день, Вот условия нашей агентской программы. https://docs.google.com/pre"
- **Beatrice Panait (GrowCentric)**: "Hello, 

Please share with me your website & a presentation of your services. 

Thanks,

Beatrice"
- **Amanda Bukowski (Adoore)**: "Hej Dias, Tack för mejl. Skicka gärna över en kort presentation med lösning, prisbild och ref. case så kikar jag igenom! Ha en fin dag, Amanda Amanda Bukowski CEO amanda@adoore.se | 0767973512 Humlegå"

### 1.2 Asks About Pricing (101 cases)

**Pattern:** Lead wants to know cost before committing to a call.

**Action:**
1. Share general pricing framework (NOT exact numbers via email)
2. Emphasize value: what they get for the price
3. Redirect to a call to discuss custom pricing

**Template:**
```
Hi {name},

Great question! Our pricing depends on your data volume and
use case. Generally, plans start from $X/month for {basic_tier}.

To give you an accurate quote, it would help to understand:
- How many creator profiles you need to analyze monthly?
- Which platforms (Instagram, TikTok, YouTube)?
- Do you need API access or dashboard only?

Happy to jump on a quick call to discuss — here's my calendar:
{calendar_link}
```

**Real examples:**
- ** (Playson)**: "Hi,

Thank you for reaching out and expressing interest in our products and services. We

appreciate your inquiry and would be delighted to provide you with more information. To

ensure that we tailor"
- **Saleh Alsdudi (Aussui)**: "Hi Serge, Thank you for following up, and apologies for the delay in getting back to you. Your offering sounds very relevant to our goals, especially as we continue to expand into new markets. I’d be "
- **Dominik Hanel (Lumiform)**: "Hi Petr, Thanks for your message. Please send over a sample for me to understand your capabilities to understand our ICP. Thanks, Dominik Am Fr., 1. Aug. 2025 um 15:16 Uhr schrieb Petr Nikolaev : Hey "

### 1.3 Wants Materials/Info (103 cases)

**Pattern:** Lead wants to review documentation before meeting.

**Action:**
1. Send requested materials (one-pager, deck, API docs)
2. Add a brief personalized note about relevance to their business
3. Follow up in 2-3 days if no response

**Template:**
```
Hi {name},

Thanks for your interest! I've attached {material_type} that covers
our key capabilities and how {their_company} could benefit.

A few highlights relevant to your work:
- {relevant_feature_1}
- {relevant_feature_2}

Would love to hear your thoughts after you've had a chance to review.
Happy to set up a walkthrough if anything catches your eye!
```

### 1.4 Positive General Response (63 cases)

**Pattern:** Lead expresses interest without specific ask ("sounds good", "let's do it").

**Action:**
1. Strike while iron is hot — propose a meeting immediately
2. Keep it brief and action-oriented

**Template:**
```
Hi {name},

Glad this resonated! Let's set up a quick call so I can
show you how OnSocial works for {their_use_case}.

Pick a time here: {calendar_link}

Talk soon!
```

### 1.5 Redirects to Colleague (41 cases)

**Pattern:** Lead is interested but says someone else handles this.

**Action:**
1. Thank the referrer
2. Email/message the referred person
3. Mention who referred you
4. Add the new contact to CRM

### 1.6 Wants Trial/Test (7 cases)

**Pattern:** Lead wants hands-on experience before buying.

**Action:**
1. Set up trial/demo account
2. Offer guided onboarding call
3. Schedule check-in after 3-5 days

---
## 2. MEETING REQUEST — Lead wants to meet

**Priority:** Respond within 1 hour. Confirm immediately.

### 2.1 Proposes Specific Time (219 cases)

**Action:** Confirm immediately. If time doesn't work, propose alternative within 24h.

### 2.2 Asks for Calendar Link (309 cases)

**Action:** Send calendar link. Done.

### 2.3 Wants Call (Generic) (287 cases)

**Action:** Send calendar link + suggest 2 time slots.

---
## 3. QUESTION — Lead has questions

**Priority:** Respond within 4 hours. Thorough answer = trust.

### 3.1 Pricing Question (159 cases)

**Action:** Same as 1.2 above — share framework, redirect to call.

### 3.2 How It Works (39 cases)

**Action:**
1. Answer the specific question concisely (2-3 sentences)
2. Offer to show in a demo
3. Attach relevant materials if applicable

### 3.3 Technical/API Question (55 cases)

**Action:**
1. Answer with specifics (data points, endpoints, formats)
2. Share API documentation link
3. Offer to connect with technical team for deep dive

### 3.4 Competitor Comparison (2 cases)

**Pattern:** Lead asks how you differ from HypeAuditor, Modash, Phyllo, etc.

**Action:**
1. Never badmouth competitors
2. Focus on unique differentiators (data freshness, coverage, price)
3. Offer to run a side-by-side comparison on their specific use case

**Template:**
```
Hi {name},

Great question! While {competitor} is a solid tool, here's where OnSocial
differs:
- Data freshness: we update profiles every 24-48h vs weekly
- Coverage: {X}M+ creators across Instagram, TikTok, YouTube
- Pricing: significantly more competitive for high-volume needs

Happy to run a comparison on 5-10 profiles from your portfolio
so you can see the difference firsthand. Want me to set that up?
```

### 3.5 Coverage/Platform Question (50 cases)

**Action:** Share specific numbers for platforms and regions they ask about.

---
## 4. NOT INTERESTED — Graceful exit

**Priority:** Low. Acknowledge and move on.

### 4.1 Has Existing Solution (390 cases)

**Action:**
1. Acknowledge respectfully
2. Mention you're available if they ever want to compare
3. Mark as "not now" (not dead) — follow up in 3-6 months

### 4.2 Polite Decline (136 cases)

**Action:** Thank them, wish them well. No follow-up.

### 4.3 Aggressive Decline / Spam Complaint (73 cases)

**Action:** Immediately remove from all campaigns. Do NOT reply.

### 4.4 Not Relevant to Them (439 cases)

**Action:** Thank them. Update ICP data — this segment may not be a fit.

---
## 5. OUT OF OFFICE

**Priority:** Medium. Schedule follow-up.

**Action for all OOO types:**
1. Note their return date
2. Schedule follow-up email for return date + 2 days
3. If they mention a colleague for urgent matters → contact that person if relevant

**Sub-types:**
- generic_ooo: 3590 cases
- vacation: 687 cases
- traveling: 260 cases
- maternity_leave: 231 cases
- sick_leave: 17 cases

---
## 6. WRONG PERSON

**Priority:** Medium. Update contact, reach out to right person.

### 6.1 Left the Company (354 cases)

**Action:**
1. Mark contact as "left" in CRM
2. If they mention successor → add new contact and reach out
3. If no successor → find replacement via LinkedIn/Apollo

### 6.2 Redirects to Another Person (5840 cases)

**Action:**
1. Thank them
2. Email the person they suggest, mentioning the referral
3. Add new contact to CRM

---
## 7. UNSUBSCRIBE

**Total:** 569 cases

**Action:** Automatically remove from all campaigns. No manual action needed.

---
## 8. BEST PRACTICES — What Worked

These are patterns from replies that were approved and sent:

### MEETING_REQUEST — Successful Replies

**Lead:** Сергей Vardomatski (Hqsoftware) (email)
**Their message:** Давайте. Но заплатим процент от выручки. Давайте? вс, 13 апр. 2025 г., 05:50 Maxim Samoylov : Здравствуйте, Сергей! Я из Sally AI, решил написать - интересно как вы работаете с аутбаунд продажами. Мы привлекаем квал. лидов через аутрич, нашим клиентам в разных вертикалях и приводим 10-40 квал лидов 
**Our reply:** Здравствуйте, Сергей!

Спасибо за ваш ответ и интерес к нашей работе. Мы можем обсудить модель оплаты с процентом от выручки и найти оптимальное решение, которое будет выгодно для обеих сторон. Давайте назначим встречу, чтобы подробнее обсудить, как мы можем помочь вам в генерации качественных лидов.

Пожалуйста, дайте знать, когда вам будет удобно встретиться, и я подберу время, которое подойдет 

**Lead:** Алексей (220 Volt) (email)
**Their message:** Ваш номер вотсапп? Best regards 12 июня 2025 г., в 12:47, Anastasia Simonets написал(а): ﻿ RE: выплаты за рубеж Добрый день, Алексей, Работа с международными контракторами часто связана с серьезными сложностями: - Подготовка договоров и счетов для каждого. - Банки запрашивают доп. документы (KYC, сч
**Our reply:** Добрый день, Алексей!  
Спасибо за ваш интерес. Мой номер WhatsApp: [ваш номер]. Буду рада обсудить, как Finboo.io может облегчить вашу работу с международными контрактами.  
Предлагаю назначить короткий звонок, чтобы подробнее обсудить наши решения. Пожалуйста, дайте знать, когда вам будет удобно.  
С уважением,  
Анастасия Симонец  
BDM @ Finboo.io

**Lead:** Дмитрий (Boost.Express) (email)
**Their message:** Добрый день, Анастасия,

Завтра в 14 или 15 мск могу.

Маршрут такой: компания платит $ со счета в США. Есть 2-3 контрактора, которые хотели бы получать рубли на счета в РФ. Если этот вариант совсем не работает либо очень дорогой - крипта (USDT) тоже ок. Объемы небольшие, т.к. большинство сотруднико
**Our reply:** Добрый день, Дмитрий,

Спасибо за ваш ответ! Завтра в 14:00 МСК отлично подходит для меня. Я рад обсудить варианты, которые подойдут для вашей компании, включая возможность использования криптовалюты, если это будет более удобно.

Пожалуйста, подтвердите время, и я отправлю ссылку на встречу.

С уважением,
Анастасия

**Lead:** Нина Shapshovich (Mobupps) (email)
**Their message:** Да позвоните пожалуйста в понедельник

"

Также подскажите, пожалуйста, откуда / куда обычно платите и какой примерный объем выплат?"

Пока не знаю .Получу от вас информацию потом решу
**Our reply:** Здравствуйте, Нина!

Спасибо за ваш ответ. Я позвоню вам в понедельник, чтобы обсудить все детали, включая информацию о том, откуда и куда мы обычно производим выплаты, а также примерный объем. Это поможет вам лучше понять, как мы можем сотрудничать.

Если у вас есть дополнительные вопросы или пожелания, не стесняйтесь сообщить мне. Жду нашего разговора!

С уважением,
[Ваше имя]  
[Ваша должность]

**Lead:** Дмитрий Sukhotski (Word of the Day app) (email)
**Their message:** Здравствуйте, Анастасия!

Я пересылал ваше письмо Надежде из моей команды. Насколько я знаю, у вас сегодня должен был быть звонок. Но его не случилось.

Дмитрий
**Our reply:** Здравствуйте, Дмитрий!

Спасибо за ваше письмо. Я приношу извинения за то, что наш запланированный звонок не состоялся. Давайте перенесем его на удобное для вас время. Я готова обсудить детали и ответить на все ваши вопросы.

Пожалуйста, дайте знать, когда вам будет удобно провести встречу.

С уважением,
Анастасия

### INTERESTED — Successful Replies

**Lead:** Антон Rybakov (JoyBits) (email)
**Their message:** Привет

Нам интересен такой транзит

UK USD wire transfer -> TikTok Singapore USD wire transfer.

Только платить вам будет одна UK компания в USD
А ваше юрилцо будет платить в TikTok, НО за другое юрилцо, не UK а Грузинскую компанию

Ожидаем комиссию за транзит до 2%
**Our reply:** Привет, Антон!

Спасибо за ваш интерес к транзиту между UK и TikTok Singapore. Мы можем предложить комиссию в пределах 2%, как вы и ожидали. Для того чтобы двигаться вперед, давайте обсудим детали и согласуем все необходимые шаги.

Когда вам будет удобно провести короткий звонок или встречу для уточнения всех нюансов? Жду вашего ответа!

С уважением,
[Ваше имя]  
[Ваша должность]  
[Ваша компания]

**Lead:** Евгения Sotina (Bogg Art) (email)
**Their message:** Здравствуйте, пришлите презентацию, пожалуйста ___________ С уважением, Евгения Сотина, CEO, BOGG.ART TG @zhe_sotina Ср, 25 июня 2025 г. в 13:47, Anastasia Simonets : Евгения, могу я отправить презентацию, чтобы вы ознакомились, если для вас это актуально? Напомню, мы можем помочь вам с выплатами ме
**Our reply:** Здравствуйте, Евгения,

Спасибо за ваш интерес! Я с удовольствием прикладываю презентацию, чтобы вы могли ознакомиться с нашими услугами по международным выплатам. Если у вас возникнут вопросы или вы захотите обсудить детали, пожалуйста, дайте знать. Мы также можем назначить встречу для более подробного обсуждения.

С уважением,
Анастасия Симонец

**Lead:** Stavros Dafnomilis (Rollblock Partners) (email)
**Their message:** Hello Rinat,

Please share more info!

Thanks
**Our reply:** Hello Stavros,

Thank you for your interest! I would be happy to share more information about our lead generation services tailored for Rollblock Partners. We specialize in providing customized solutions that can help enhance your outreach and engagement with potential clients.

Could we schedule a brief call to discuss your specific needs and how we can assist you? Please let me know your availab

**Lead:** Давид Yakubov (Unifin) (email)
**Their message:** Евгений, добрый день!


Спасибо за Ваше письмо. Вкратце представлюсь: мы являемся финтех-консалтинговой компанией и одновременно владельцами лицензированного платёжного бизнеса, поэтому многие из описанных Вами сервисов у нас уже реализованы внутри компании.


Тем не менее, для наших клиентов — ре
**Our reply:** Давид, доброе утро!

С огромным огорчением обнаружил, что не отправился Вам мой ответ полгода назад - прошу прощения!

По Вашим вопросам хотел бы запланировать звонок с нашим CEO - я показал ему Ваше письмо и он видит внятный потенциал в звонке - есть возможность запланировать звонок на Пн, 19.30, Вт - 18.30/19/19.30 или среду 19.30 по Израилю, Давид?

Был бы очень признателен Вам, если получится 

**Lead:** Sergey Vodolagin (вестсайд) (email)
**Their message:** Добрый день, да,,отправьте, пожалуйста, презентацию. С уважением, С. Водолагин Отправлено с устройства Galaxy -------- Исходное сообщение -------- От: Katya Khoroshilova Дата: 06.10.2025 09:41 (GMT+03:00) Кому: vodolagin@wslaw.ru Тема: RE: выплаты фрилансерам Сергей, могу я отправить презентацию, чт
**Our reply:** Добрый день, Сергей,Добавлю, что компании часто сталкиваются с высокими налогами или сложностями при выплатах в сложные регионы.Мы в Easystaff решаем это: выплаты из СНГ и в СНГ в EUR, USDT и локальной валюте, с закрывающими документами и НДС только на комиссию для УСН. Настройка - 10 минут, а поддержка всегда готова помочь.Будет ли у вас 15 минут на звонок, чтобы обсудить ваш кейс?Katya Khoroshil

### QUESTION — Successful Replies

**Lead:** Андрей Oblov (MyGig) (email)
**Their message:** &Dcy;&ocy;&bcy;&rcy;&ycy;&jcy; &dcy;&iecy;&ncy;&softcy;! &Ncy;&acy;&mcy; &ncy;&iecy; &acy;&kcy;&tcy;&ucy;&acy;&lcy;&softcy;&ncy;&ocy;, &mcy;&ycy; &ncy;&iecy; &pcy;&lcy;&acy;&tcy;&icy;&mcy; &zcy;&acy; &rcy;&ucy;&bcy;&iecy;&zhcy; &ncy;&icy;&kcy;&ocy;&mcy;&ucy;. &Acy;&ncy;&dcy;&rcy;&iecy;&jcy; &Ocy;&bc
**Our reply:** Здравствуйте, Андрей!  
  
Спасибо за ваш ответ. Я рад услышать от вас. Если вам нужна дополнительная информация о международных выплатах или есть какие-либо вопросы, пожалуйста, дайте мне знать. Мы можем организовать встречу, чтобы обсудить детали и найти наилучшее решение для вашей компании.  
  
С нетерпением жду вашего ответа!  
  
С уважением,  
Анастасия Симоноц

**Lead:** Александр Litvinov (Ituniversum) (email)
**Their message:** Евгений, добрый день!

Вы можете помочь с переводом денег в Россию для оплаты услуг разработчиков софта?

Спасибо, Александр
**Our reply:** Александр, спасибо за Ваш вопрос!К сожалению, с российскими юрлицами, а также с рублём как с валютой мы не работаем и переводы в фиате в РФ/РБ не делаемЕсли юрлицо не российское, сможем предложить переводы в крипте - в таком случае, для нас не имеет значения, где географически находятся получатели криптопереводовЕсли такое вариант для вас актуален, дайте знать, пожалуйстаС уважением,Евгений

**Lead:** Ирина Protasova (American Farmers) (email)
**Their message:** English?
**Our reply:** Hello Irina,Yes, English is not a problem, apologies for Russian!Actually, I wanted to give you a brief overview of how our service works as an all-in-one financial platform for your businessOur solution is called SquareFi and is built on three core elements:1. On/Off-RampA service for instant and compliant conversion between cryptocurrency and fiatThis allows you to easily pay partners, settle wi

**Lead:** Антон Rybakov (JoyBits) (email)
**Their message:** Привет

Есть другая задача из UK компании по wire transfer отправлять USD на какое-то ваше юрлицо, которое связано с разработкой ПО или Ad Networks...

И получать usdt на один кошелек. 

Какая у вас комиссия в таком случае?
**Our reply:** Антон, доброе утро!Смотрите, при таком запросе Вы можете заонбордить к нам свою какую-то компанию с разработкой ПО и отправлять такие платежи в среднем за 0,8% Если же как услуга на нашу компанию, то зависит от обьема - надо обсуждать напрямуюЕсли в целом интересно рассмотреть, можем назначить звонок с нашим CEO?Мы с Вами как-то общались по другому проекту и я запомнил, что Вам часто удобно общать

**Lead:** Майк Roganov (IMPAYA) (email)
**Their message:** &IEcy;&vcy;&gcy;&iecy;&ncy;&icy;&jcy;, &dcy;&ocy;&bcy;&rcy;&ycy;&jcy; &dcy;&iecy;&ncy;&softcy;. &Bcy;&lcy;&acy;&gcy;&ocy;&dcy;&acy;&rcy;&yucy; &zcy;&acy; &pcy;&rcy;&iecy;&dcy;&lcy;&ocy;&zhcy;&iecy;&ncy;&icy;&iecy;. &Mcy;&ocy;&icy; &kcy;&ocy;&lcy;&lcy;&iecy;&gcy;&icy; &pcy;&ocy;&scy;&mcy;&ocy;&tcy;&r
**Our reply:** Здравствуйте, Майк!Если позволите, ещё несколько слов о нашем решенииГлавные преимущества нашей инфраструктуры: универсальность, скорость и гибкостьВы можете запустить готовые решения для крипто-фиатных платежей и выпуска карт всего за 1-3 недели, интегрировав их через API или запустив White Label продукт под вашим брендомЭто позволяет избежать долгой и дорогой внутренней разработкиПодскажите, пож

---
## 9. MULTI-TURN CONVERSATION EXAMPLES

These show how conversations develop over multiple exchanges:

### Виктор Fedoseev (4ru) — question (email)

**→ US:**
Виктор, привет!Подскажите, для компании Puerto De EspañA актуально принимать и отправлять криптоплатежи от клиентов и обратно - с комиссиями менее 1% и полным соблюдением законодательства (лицензии: польский VASP, канадский MSB) ?Возможно, готовы рассмотреть внедрение платежей в крипте?Если у вас уже есть решение, предложим своё на 30% выгоднее того, что вы используете сейчас!Давайте созвонимся - 

**→ US:**
Привет, Виктор!Как Вы знаете, у многих классических шлюзов комиссии 2-3%Inxy позволяет принимать крипту с комиссиями <1% (или ниже - при значительных объемах) и выводить в фиат напрямую на юрлицоРеально удобно для подписок, API или большого потока платежей!Подскажите, найдется 15 минут чтобы пообщаться более предметно?Serge KuznetsovCo-founder @ INXY.io

**→ US:**
Виктор, привет еще раз )Напомню - мы можем предложить подключение Inxy со скидкой до 30% по сравнению с тем, что Вы используете сейчасТак, Hostry.com добавили Inxy и уже в первый месяц получили +15% к выручке - за счёт клиентов, которым неудобно платить иначеХотите - покажем, как это может выглядеть в вашем случае?Serge KuznetsovCo-founder @ INXY.io

**← LEAD:**
p {margin:0}; 

От: "Serge Kuznetsov" <serge.k@pay-inxy.com> 
 Кому: "undefined" <victor@4ru.es> 
Отправлено: среда, 25 июня 2025 г., 9:46 
 Тема: RE: Re: поможем снизить комиссии на 30% и получить новых клиентов 

  
  Виктор, привет еще раз )

Напомню - мы можем предложить подключение Inxy со скидкой до 30% по сравнению с тем, что Вы используете сейчас
Так, Hostry.com добавили Inxy и уже в первы

**→ US:**
Виктор, здравствуйте!От Вас пришло пустое письмо - хотел уточнить, для Вас может быть актуален наш сервис по криптоплатежам?С уважением,Сергей

**← LEAD:**
p {margin:0}; 
Я еще раз задаю вопрос - где вы на моем сайте увидели любые платежи? Может быть я что-то не вижу на нем



От: "Serge Kuznetsov" <serge.k@pay-inxy.com> 
Кому: "undefined" <victor@4ru.es> 
Отправлено: среда, 25 июня 2025 г., 17:06 
Тема: RE: RE: Re: поможем снизить комиссии на 30% и получить новых клиентов 


Виктор, здравствуйте!

От Вас пришло пустое письмо - хотел уточнить, д

**→ US:**
Виктор, Вы правы - наша ошибкаПриношу извинения - больше Вас не побеспокоим!Хорошего дня Вам! С уважением,Сергей

---

### Владислав Gershkovich (SPEC Finance) — interested (email)

**→ US:**
Владислав, привет!Подскажите, для компании Spec Finance актуально принимать и отправлять криптоплатежи от клиентов и обратно - с комиссиями менее 1% и полным соблюдением законодательства (лицензии: польский VASP, канадский MSB) ?Возможно, вы переводите крипту своим сотрудникам/контракторам или готовы рассмотреть внедрение платежей в крипте?Если у вас уже есть решение, предложим своё на 30% выгодне

**→ US:**
Привет, Владислав!Как Вы знаете, у многих классических шлюзов комиссии 2-3%Inxy позволяет принимать крипту с комиссиями <1% (или ниже - при значительных объемах) и выводить в фиат напрямую на юрлицоРеально удобно для подписок, API или просто большого потока платежей!Подскажите, найдется 15 минут чтобы пообщаться более предметно?Serge KuznetsovCo-founder @ INXY.io

**← LEAD:**
Добрый день, Сергей Кузнецов!

Благодарю Вас за интересное предложение. Мы обязательно изучим его
 и вернемся к Вам с обратной связью в случае, если оно нас заинтересует!

С уважением,Vladislav Gershkovich

---- пт, 20 июн. 2025 11:22:10 +0300 пользователь Serge Kuznetsov <serge.k@inxydata.com> написал ---

Привет, Владислав!Как Вы знаете, у многих классических шлюзов комиссии 2-3%Inxy позволяет 

**→ US:**
Владислав, здравствуйте!Хорошо, буду ждать )Хорошей Вам пятницы и выходных!С уважением,Сергей

---

### Алекс Shyrkov (NIS USA) — interested (email)

**→ US:**
Алекс, привет!Подскажите, для компании Nis актуально принимать и отправлять криптоплатежи от клиентов и обратно - с комиссиями менее 1% и полным соблюдением законодательства (лицензии: польский VASP, канадский MSB) ?Возможно, готовы рассмотреть внедрение платежей в крипте?Если у вас уже есть решение, предложим своё на 30% выгоднее того, что вы используете сейчас!Давайте созвонимся - и я покажу, ка

**→ US:**
Привет, Алекс!Как Вы знаете, у многих классических шлюзов комиссии 2-3%Inxy позволяет принимать крипту с комиссиями <1% (или ниже - при значительных объемах) и выводить в фиат напрямую на юрлицоРеально удобно для подписок, API или большого потока платежей!Подскажите, найдется 15 минут чтобы пообщаться более предметно?Serge KuznetsovCo-founder @ INXY.io

**→ US:**
Алекс, привет еще раз )Напомню - мы можем предложить подключение Inxy со скидкой до 30% по сравнению с тем, что Вы используете сейчасТак, Hostry.com добавили Inxy и уже в первый месяц получили +15% к выручке - за счёт клиентов, которым неудобно платить иначеХотите - покажем, как это может выглядеть в вашем случае?Serge KuznetsovCo-founder @ INXY.io

**→ US:**
Алекс,Подскажите, пожалуйста, это же Ваш профиль http://www.linkedin.com/in/alex-shyrkov-b0469b20 ?Возможно, Вам удобнее было бы пообщаться там? Или в WA / ТГ?Буду рад контакту любым удобным способом )Отправлено с iPhone

**→ US:**
Алекс,Хорошо понимаю, что у вас может уже быть платёжное решениеОднако многие наши конкуренты: - не дают никаких гарантий - а у нас лицензии VASP (Польша) и MSB (Канада) - не заточены для микроплатежей - берут более высокие комиссииОговорюсь, вы можете попробовать наш сервис как дополнительный канал - с условиями на 30% выгоднее вашего нынешнего решенияМожем начать с небольших оборотов - чтобы вы 

**← LEAD:**
RE: Re: поможем снизить комиссии на 30% и получить новых клиентов




STOP   From: Serge Kuznetsov [mailto:serge@inxyplatform.com] 
Sent: Thursday, July 3, 2025 10:02 AM
To: alex_shyrkov@nis.ua
Subject: RE: Re: поможем снизить комиссии на 30% и получить новых клиентов Алекс,
Хорошо понимаю, что у вас может уже быть платёжное решение Однако многие наши конкуренты: - не дают никаких гарантий - 

---

### Denis Gedz (Clickleadar) — meeting_request (email)

**→ US:**
Hi Denis,Is crypto-to-fiat conversion something you’ve had to manage for payouts or operational spend?At SquareFi, we’re already helping networks like ClickDealer and Betfury streamline global payouts with on/off ramps (from 0.5%) and crypto top-up cards (0.8 to 1.2%).Would it make sense to see if this is relevant for your team?Denis Spasibo Co-founder @ SquareFi

**← LEAD:**
v\:* {behavior:url(#default#VML);}
o\:* {behavior:url(#default#VML);}
w\:* {behavior:url(#default#VML);}
.shape {behavior:url(#default#VML);}
Crypto to fiat exchange for payments




Hi Denis.We are the Clickdealer – did not know that we are already working with you. We have offers 0,35% for single payouts and 0,7% for mass payouts, if you can offer this or bellow – let’s have a meeting a

**→ US:**
[TEST — original recipient: denis.gedz@clickdealer.com]Hi Denis,Thank you for your prompt response and for sharing your offers. We appreciate the opportunity to explore potential collaboration. Our rates for crypto-to-fiat exchanges align closely with what you mentioned, and I believe we can find a mutually beneficial arrangement.I would love to set up a meeting to discuss this in further detail. 

---

### Dung Kim (Ecomobi) — interested (email)

**→ US:**
Hi Dung,Is crypto-to-fiat conversion something you’ve had to manage for international payments?At SquareFi, we’re already helping companies like ClickDealer and WakeApp streamline global payouts and media buying with on/off ramps (from 0.5%) and crypto top-up cards.Would it make sense to see if this is relevant for your team right now?Kind regards,Denis Spasibo Co-founder @ SquareFi

**← LEAD:**
Hi Denis, 
Thanks for reaching out! Could you please provide more specific details about your services? We&#39;re interested in learning more.
Thanks,

On Tue, Jul 15, 2025 at 3:02 PM Denis Spasibo <denis@pay-squarefi.com> wrote:

  
  
    
    
     
      
    
  
  
  
  Hi Dung,Is crypto-to-fiat conversion something you’ve had to manage for international payments?At SquareFi, we’re

**→ US:**
Hi Dung,Nice to e-meet you, happy to share more.At SquareFi, we help companies simplify global payouts, manage cross-border budgets in crypto and fiat, and move faster when dealing with international teams, partners, and creators.Here’s where we can help:Same-day payouts to partners or buyers via crypto or fiat (SEPA, SWIFT, ACH);Virtual and physical cards for internal budgets, creator rewards, or

---

### Kliment Kalchev (LeapBlock) — question (email)

**→ US:**
Hi Kliment,  My name is Serge, I am a Co-founder at INXY.io — I came across your company's account on LinkedIn. Does your project currently use cryptocurrencies or tokens for payments/payouts?If yes: INXY’s unified gateway processes 20+ cryptos + fiat (cards/e-wallets) in one integration, with instant auto-conversion to EUR/USD. Could we explore how this streamlines operations for LeapBlock?Best r

**→ US:**
Hi, Kliment, it's Serge — Co-founder at INXY.io. Building on our payment discussion: are mass payouts (e.g., player rewards) creating operational bottlenecks?If yes: Our CSV/API automation sends 2,500+ payouts/minute in local fiat/crypto across 30+ countries.Happy to show you how project like yours reduced payout processing by 80%. Could we schedule 15 min?Best,Serge KuznetsovINXY Payments, Co-fou

**→ US:**
Dear Kliment,Unfortunately, I have got no feedback from you :( I've reached out a few times to discuss how we at INXY could help LeapBlock with hybrid payments and mass payouts.Just to follow up — If expanding globally is a priority, regulatory hurdles can delay market entry.If you are planning expansion within EU/Asia/Latin America we could schedule a quick call — I'll show you how our EU VASP li

**← LEAD:**
Hey Serge,
Sorry for the late reply!
I&#39;ve just become a father, so I haven&#39;t been able to give this the attention it requires. 
That said, I&#39;ll CC Tsvetomir in so he can get all the details from you. 
Thank you for reaching out and for your understanding!
K
On Mon, Jul 21, 2025 at 10:59 AM Serge Kuznetsov <serge@contactsquarefi.com> wrote:

  
  
    
    
     
      
    
  

**← LEAD:**
Hi Serge! Can you clue me in about what you&#39;ve discussed with Kliment and we can take it from there?
On Mon, Jul 21, 2025 at 11:24 AM Kliment <iamkliment@gmail.com> wrote:
Hey Serge,
Sorry for the late reply!
I&#39;ve just become a father, so I haven&#39;t been able to give this the attention it requires. 
That said, I&#39;ll CC Tsvetomir in so he can get all the details from you. 
Thank you f

---

### Saleh Alsdudi (Aussui) — interested (email)

**→ US:**
Hi Saleh,  My name is Serge, I am a Co-founder at INXY.io — I came across your company's account on LinkedIn. Does your project currently use cryptocurrencies or tokens for payments/payouts?If yes: INXY’s unified gateway processes 20+ cryptos + fiat (cards/e-wallets) in one integration, with instant auto-conversion to EUR/USD. Could we explore how this streamlines operations for Aussui?Best regard

**→ US:**
Hi, Saleh, it's Serge — Co-founder at INXY.io. Building on our payment discussion: are mass payouts (e.g., player rewards) creating operational bottlenecks?If yes: Our CSV/API automation sends 2,500+ payouts/minute in local fiat/crypto across 30+ countries.Happy to show you how project like yours reduced payout processing by 80%. Could we schedule 15 min?Best,Serge KuznetsovINXY Payments, Co-found

**→ US:**
Dear Saleh,Unfortunately, I have got no feedback from you :( I've reached out a few times to discuss how we at INXY could help Aussui with hybrid payments and mass payouts.Just to follow up — If expanding globally is a priority, regulatory hurdles can delay market entry.If you are planning expansion within EU/Asia/Latin America we could schedule a quick call — I'll show you how our EU VASP license

**→ US:**
Hi Saleh ,Following up on my previous emails about gaming payment challenges, I wanted to address another critical area. Payment friction directly impacts revenue — especially for global audiences.So, do your clients tend to abandon purchases because of limited payment options?How does Aussui handle this today?Our solution: 20+ cryptos + local methods (Apple Pay, iDeal, Pix) increases checkout con

**← LEAD:**
Hi Serge,

Thank you for following up, and apologies for the delay in getting back to you.

Your offering sounds very relevant to our goals, especially as we continue to expand into new markets. I’d be interested to learn more about:

The payment methods you currently support (crypto + local options)
Pricing structure for both processing and payouts
Any real-world examples or use cases of how busi

---

### Jacob Appel (Binderr) — question (email)

**→ US:**
Hey Jacob! How are you currently facilitating international payments and managing cross-border FX for your clients seeking banking and legal services?

At Inxy, we offer a regulated (EU VASP/Canadian MSB) Paygate for global crypto acceptance and OTC/Treasury services for efficient crypto asset management and conversion.

Would you be open to a 15-minute call to explore how we can enhance your paym

**→ US:**
Hi Jacob,Just following up — traditional gateways often charge 2–3% fees and block users from certain regions.Inxy lets you accept crypto with <1% fees (or lower at volume) — and settle in fiat directly to your legal entity.Open for a 15-min call to see how this could work for Binderr ?

**← LEAD:**
Hi Serge, could you provide more details on how the integration works?
        
        

        
    Jacob AppelChief Executive OfficerBinderr

    

    
    
    

    
        On Wed, 23 Jul 2025 at 17:42, Serge Kuznetsov
        <serge.k@inxyservices.com>
        wrote:
        

        
        Hi Jacob,

Just following up — traditional gateways often charge 2–3% fees an

**→ US:**
Hi Jacob,Happy to clarify!Integration is simple. For full automation of both accepting payments and making payouts, you can use our REST API. For mass payouts without any code, you can just upload a CSV file.Both methods are straightforward, and we provide full documentation and support.The best fit depends on your exact needs. Would a quick 15-min call work to show you how it would look for your 

**→ US:**
Hi Jacob,Just following up on my note about our API and CSV integration.Many teams we talk to are looking to move away from the time-consuming process of manual bank wires, especially when paying international contractors. Our platform is designed to automate that entire workflow, saving significant time and reducing fees.Is that an area you're currently looking to optimize? If so, I'd be happy to

---

### Stefano Andreani (Opentech) — question (email)

**→ US:**
Hey Stefano! As a provider of digital finance services and payment solutions, how are you currently managing the global money transfer and cross-border payment flows for your clients?

At Inxy, we offer a regulated (EU VASP/Canadian MSB) platform that includes OpenPay™ Send's capabilities for seamless global money transfers and cross-border payments, acting as a robust infrastructure partner.

Wou

**← LEAD:**
Could you please explain what you mean with &quot;platform that includes OpenPay™ Send&#39;s capabilities&quot;?
BR,Stefano.
On Fri, Jul 25, 2025 at 4:23 PM Serge Kuznetsov <serge.k@inxytools.com> wrote:
Hey Stefano! 





As a provider of digital finance services and payment solutions, how are you currently managing the global money transfer and cross-border payment flows for your clients?




**→ US:**
Hi Stefano,That's a great question, and my apologies for the lack of clarity in my previous email.I used "OpenPay™ Send's capabilities" as a shorthand to describe a specific function, but I should have explained it in our own terms.What I was referring to is Inxy's core infrastructure for automating global mass payouts. Essentially, our platform allows a business to initiate thousands of cross-bor

**→ US:**
Hey Stefano,Just following up on my last note. In short, we provide the regulated infrastructure for you to offer faster, more cost-effective global payouts to your clients—without building it from scratch.Would a quick 15-minute demo be the best way to see it in action?Best,Serge

---

### Антон Simanikhin (Schooly.) — meeting_request (email)

**→ US:**
Антон, привет!Скажите, для компании Schooly. актуально принимать и отправлять криптоплатежи от клиентов и обратно с опциональной конвертацией в фиат?Возможно, вы готовы рассмотреть внедрение платежей в крипте?Мы в SquareFi создали единую платформу, которая закрывает все узкие места:Легальный On/Off-Ramp для бесшовной конвертации криптовалют в фиат (и обратно)Корпоративные карты и мультивалютные сч

**← LEAD:**
Ринат, добрый день. 

Спасибо за email. Для Schooly это скорее всего будет неактуально. 

Но это возможно станет интересным для некоторых других моих проектов, но чуть позже. 

Я бы сохранил ваши контакты. 

Спасибо. ANTONCo-founder & CEOSchooly.
Book a call

On Thu, 31 Jul 2025 at 19:52, Rinat Khatipov <rinat.k@cronareach.com> wrote:

  
  
    
    
     
      
    
  
  
  
  Антон,

**→ US:**
Антон, здравствуйте!Спасибо, что нашли время ответить, рад знакомству!Возможно, могли бы дать мне свой контакт в ТГ или WA - мы бы Вам написали чтобы быть на связи?Или сами напишите вот сюда на ТГ: @BrrrutТакже прикрепляю презентацию для Вашего ознакомления с нашим решениемИ подскажите, пожалуйста, когда примерно может быть актуально для Вас чтобы я вернулся когда скажете - и напомнил о себе? )С у

**← LEAD:**
Взаимно :)
В Телеге сообщения обычно теряются. Поэтому лучше написать на anton@cida.io
Спасибо. Best regards, 
Anton
Co-founder
Schooly.

On Fri, 1 Aug 2025 at 12:09 am, Rinat Khatipov <rinat.k@cronareach.com> wrote:
Антон, здравствуйте!Спасибо, что нашли время ответить, рад знакомству!Возможно, могли бы дать мне свой контакт в ТГ или WA - мы бы Вам написали чтобы быть на связи?Или сами напишите в

**→ US:**
Антон, благодарюМой коллега Евгений (в копии) напишет Вам на почту сейчас - он у нас отвечает за lead nurturing, i.e. пинги потенциальных клиентов )Вам хорошего вечера пятницы и выходных!С уважением,Ринат

**→ US:**
Антон, доброе утро!Решил вернуться к Вам по случаю окончания сезона отпусков )С Вашего позволения, напомню коротко о наших основных сервисах:- Корпоративные картыВыпуск физических и виртуальных карт для вашей командыКлючевая особенность: возможность их пополнения напрямую с криптовалютного балансаИдеально подходит для оплаты рекламных кабинетов, подписок и других корпоративных расходов- Мультивалю

---

## 10. KEY METRICS

| Metric | Value |
|--------|-------|
| Total conversations analyzed | 36,192 |
| Warm/qualified leads | 2,800 (7.7%) |
| Response rate (interested+meeting+question) | 7.7% |
| Email conversations | 34,950 |
| LinkedIn conversations | 1,036 |
| Avg. warm lead conversion to approved | ~1% |
