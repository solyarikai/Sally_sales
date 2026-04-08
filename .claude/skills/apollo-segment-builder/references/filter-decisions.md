# Apollo Filter Decision Knowledge Base

> Накопленная база знаний о том, как принимать решения при сборке Apollo-фильтров.
> Источник: реальные кампании OnSocial, данные Sally, итерации v1→v5.
> Обновляй этот файл после каждого нового сегмента — он становится умнее с каждым запуском.

---

## 1. Geography

### Ключевое правило
Apollo не принимает "ALL GEO" как параметр — нужен явный список стран. Это не баг, это ограничение API.

### Стандартные блоки стран

| Блок | Страны | Когда использовать |
|------|--------|-------------------|
| **Western Core** | US, UK, DE, NL, FR, CA, AU, ES, IT, SE, DK, BE | Базовый набор, проверенные рынки с высокой конвертацией |
| **APAC+MENA** | IN, SG, JP, KR, AE | Добавлять если сегмент глобальный или связан с Азией |
| **LatAm+IL** | BR, MX, IL | Добавлять при маленьком TAM или если есть LATAM-сигнал |
| **Full Global** | Все 20 стран | При TAM < 500 компаний — нет смысла резать |

### Решения по сегментам

**INFLUENCER_PLATFORMS (v3):** Western Core (12) → v4 расширили до Full Global (20).
Причина: в v3 пропускали хорошие компании из APAC и MENA. Расширение дало +2x охват.

**AFFILIATE_PERFORMANCE (v3→v4):** Аналогично — Western Core → Full Global.

**IM_FIRST_AGENCIES (v3→v4):** Western Core → Full Global.
Примечание: Швеция убрана из приоритета в v3 из-за микро-агентств (BrandNation, Yagency = "not a fit"), но в v4 оставили в Full Global т.к. фильтр по размеру (10+) отсекает микро.

**SOCIAL_COMMERCE (v5):** Full Global (20) сразу.
Причина: TAM ~100-300 компаний глобально, live shopping сильнее всего в APAC — нет смысла резать.

### Правило принятия решения
- TAM < 500 компаний → Full Global (20)
- TAM 500-2000 → Western Core + APAC+MENA (17)
- TAM > 2000 → Western Core (12), можно расширить позже
- Есть явный APAC-сигнал в сегменте → всегда добавляй APAC

---

## 2. Company Size

### Справка по сегментам

| Сегмент | Размер | Обоснование |
|---------|--------|-------------|
| INFLUENCER_PLATFORMS | 5–5,000 | impact.com (1K-5K) = лучший лид Sally. Не резать верхнюю границу. |
| AFFILIATE_PERFORMANCE | 20–5,000 | Нижняя 20: мелкие аффилиаты не имеют продукта для API. |
| IM_FIRST_AGENCIES | 10–500 | Brighter Click (10-50) = strong fit. Выше 500 = холдинги (WPP, Omnicom = 0 конверсий). |
| SOCIAL_COMMERCE | 20–5,000 | Bazaarvoice (1K-5K), LTK (500-1K) = core ICP. Firework, ShopMy (50-200) тоже. |

### Правила принятия решения

**Нижняя граница:**
- SaaS/платформы: 5-20 сотрудников (стартапы с продуктом уже могут платить за API)
- Агентства: 10+ (меньше = фрилансер, нет бюджета)
- Marketplace/Commerce: 20+ (нужна команда для интеграции)

**Верхняя граница:**
- 5,000 — универсальный максимум для большинства сегментов
- 500 — только для агентств (выше = холдинги с бесконечным сейлз-циклом)
- Не режь верхнюю границу по умолчанию — большие компании часто лучшие лиды

**Формат JSON:**
- `["20,5000"]` — один диапазон (рекомендуется)
- `["10,50", "51,200", "201,500"]` — несколько диапазонов (если нужна разная логика по размеру)

---

## 3. Industry

### Стандартные комбинации

| Комбинация | Индустрии | Для каких сегментов |
|-----------|-----------|---------------------|
| **Tech** | Computer Software, Internet, Information Technology | SaaS, API-платформы |
| **Tech+Marketing** | + Marketing & Advertising, Online Media | Если компании описывают себя как "маркетинг" |
| **Tech+Commerce** | + E-commerce, Retail | Если сегмент связан с продажами/ритейлом |
| **Agency-only** | Marketing & Advertising ONLY | Строго для агентств — намеренно узко |

### Решения по сегментам

**INFLUENCER_PLATFORMS:** Tech+Marketing (без E-commerce). Influencer SaaS-платформы — это Software/Internet, иногда Marketing. E-commerce не добавляли т.к. тянул бы ритейл-бренды.

**AFFILIATE_PERFORMANCE:** Tech+Marketing+E-commerce. Affiliate сети часто в E-commerce. impact.com = Computer Software.

**IM_FIRST_AGENCIES:** Только Marketing & Advertising. Намеренно узко — PR-фирмы (Public Relations) дали 0 конверсий у Sally. Не добавляй PR&Comms в этот сегмент никогда.

**SOCIAL_COMMERCE:** Tech+Marketing+Commerce+Retail. Live shopping платформы могут быть в Retail (Bazaarvoice) или E-commerce, не только в Software.

### Чего избегать
- **Public Relations & Communications** → 0 конверсий у Sally, не добавляй
- **Financial Services** → не ICP для creator data
- **Retail** — добавлять только если сегмент буквально про e-commerce/live shopping

---

## 4. Company Keywords (keyword_tags)

### Принципы подбора

**Точность vs охват:**
- Слишком узко (5-8 keywords) → пропустим половину TAM
- Слишком широко (30+ keywords) → overlap с другими сегментами, шум
- Оптимум: 15-25 keywords для большинства сегментов

**Правило синонимов:** Для каждого core-термина добавляй 1-2 синонима.
Пример: "influencer marketing platform" → + "creator marketing platform" + "influencer platform"

**Правило overlap:** Перед финализацией — сверь с keyword_tags соседних сегментов.
Если keyword уже есть в другом сегменте, это не обязательно плохо (компании могут попасть в оба), но нужно убедиться что messaging для них разный.

### Эволюция v3 → v4 (чему научились)

**INFLUENCER_PLATFORMS v3 → v4:** Добавили смежные термины (earned media, digital PR platform, media monitoring, creator CRM, sentiment analysis). Причина: компании которые нужны OnSocial не всегда называют себя "influencer marketing" — они могут говорить "brand intelligence" или "social listening".

**IM_FIRST_AGENCIES v3 → v4:** УБРАЛИ "social media agency", "content marketing agency", "Instagram marketing". Эти keywords тянули тысячи generic SMM-агентств с 0 конверсий.

**Ключевой урок:** Широкие generic keywords (social media, content marketing) = шум. Специфичные нишевые keywords = качество.

### Проверочный список для новых keywords
- [ ] Этот keyword однозначно описывает ICP сегмента?
- [ ] Есть ли overlap с keyword_tags других сегментов? (если да — ок, но зафиксируй)
- [ ] Не слишком ли generic? (social media, content = обычно слишком широко)
- [ ] Есть ли синонимы которые компании реально используют?

---

## 5. Excluded Company Keywords

### Стандартный набор (всегда, для всех сегментов)

```
recruitment, staffing, accounting, legal, healthcare,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant, SEO only, PPC only, print,
antivirus, cybersecurity, IT infrastructure, ERP, payroll
```

Эти exclusions универсальны — никогда не убирай их.

### Сегмент-специфичные exclusions

| Сегмент | Дополнительные exclusions | Причина |
|---------|--------------------------|---------|
| IM_FIRST_AGENCIES | PR agency, public relations, crisis comms, branding only, market research, consulting, modelling agency, event management only, photography/video studio only | PR и consulting = 0 конверсий у Sally |
| AFFILIATE_PERFORMANCE | affiliate agency, media buying agency, banking, crypto exchange | Agency ≠ platform; fintech тянет банки |
| SOCIAL_COMMERCE | e-commerce platform, online store builder, shopping cart, payment processing, dropshipping, affiliate network, video streaming platform, live streaming entertainment, gaming streaming, sports streaming | Shopify-клоны и Twitch-подобные — не ICP |

### Правило для новых сегментов
Спроси: "Какие типы компаний могут случайно попасть по нашим keywords, но не являются ICP?"
Для каждого такого типа — добавь 1-2 exclusion keyword.

---

## 6. Job Titles (People Filters)

### Базовый набор (всегда включается)

```
CTO, VP Engineering, VP of Engineering, Head of Engineering,
VP Product, Head of Product, Chief Product Officer,
Director of Engineering, Director of Product,
Co-Founder, Founder, CEO, COO
```

Это DMs для API/data продуктов в SaaS-компаниях. Работает для большинства сегментов.

### Сегмент-специфичные добавления

| Сегмент | Дополнительные титулы | Обоснование |
|---------|----------------------|-------------|
| AFFILIATE_PERFORMANCE | VP/Head/Director of Partnerships, VP/Head of Growth | Partnerships решает про affiliate интеграции |
| IM_FIRST_AGENCIES | CEO, Managing Director, Managing Partner, Head of Influencer Marketing, Head of Talent | Агентства = другая структура, нет CTO |
| SOCIAL_COMMERCE | Head of Marketplace, VP Commerce, Director of Marketplace, Head of Partnerships, VP Partnerships | Marketplace quality = уникальный buyer |

### Правило: кто реально покупает?

**Для SaaS/платформ:** CTO и VP Product решают про API-интеграцию.
**Для агентств:** CEO/Founder и Head of [core service] — нет технического DM.
**Для marketplace/commerce:** + Head of Marketplace, VP Commerce — они болеют за качество продавцов/создателей.
**Для partnerships:** + VP/Head of Partnerships — если продукт = партнёрская программа.

### Кого всегда исключать

```
Intern, Junior, Assistant, Student, Freelance,
Marketing Manager, Sales Representative, Account Executive,
Account Manager, Customer Success, Support, HR, Recruiter,
Content Writer, Designer, Social Media Manager
```

**Сегмент-специфичные exclusions:**
- Affiliate/performance сегменты: + "Affiliate Manager", "Partner Manager" (execution, не DM)
- Agency сегменты: + "Campaign Manager", "Campaign Coordinator", "Media Planner", "Community Manager"

### Management Level

Единый для всех сегментов (v4):
`c_suite, vp, director, owner, head, partner, founder`

В v3 был разный — в v4 унифицировали. Не менять.

---

## 7. Validated Data от Sally

Эти данные подтверждены реальными результатами кампаний OnSocial. Используй для калибровки решений.

### Сильные лиды (конвертировались)

| Компания | Сегмент | Размер | Контакт | Сигнал |
|----------|---------|--------|---------|--------|
| impact.com | AFFPERF | 1K-5K | Sr. Director of Engineering (Johan Venter) | Запросил walkthrough |
| The Shelf | INFPLAT | 50-200 | — | Сильный fit |
| Brighter Click | IMAGENCY | 10-50 | Founder | Strong fit |
| GameInfluencer | IMAGENCY | 50-200 | CEO | Engaged |
| MediaLabel | INFPLAT | — | — | Validated |
| Peersway | INFPLAT | — | — | Validated |

### Провалы (не конвертировались, объяснение)

| Компания | Причина провала | Вывод для фильтров |
|----------|----------------|-------------------|
| WPP, Omnicom, HAVAS, Mindshare | Слишком крупные холдинги (10K+) | Cap agencies at 500 employees |
| BrandNation, Yagency (SE) | "Too small, cannot afford" | Min 10 employees for agencies |
| United Influencers | "Not a need" | Добавлен в blacklist |
| Social Media Examiner | Медиа-компания, не buyer | Исключать медиа из IMAGENCY |
| Croud | "Remove from mailing list" | Добавлен в blacklist |
| PR-агентства в целом | 0 конверсий | Никогда не таргетировать PR |
| Generic SMM-агентства | 0 конверсий | Убрать "social media agency" из keywords |

### Случайные попадания (были в кампании с неправильным messaging)

Bazaarvoice, LTK, ShopMy — попали в INFPLAT/AFFPERF через широкие фильтры, но получили generic messaging. Это и стало причиной создания отдельного сегмента SOCIAL_COMMERCE.

**Урок:** Если компания попадает в два сегмента — она должна получать messaging того сегмента, который точнее описывает её боль.

---

## 8. TAM-ориентиры

| TAM (компании) | Стратегия |
|----------------|-----------|
| < 200 | Full Global, максимум keywords, не резать размер |
| 200–1,000 | Full Global или Western+APAC, средний набор keywords |
| 1,000–5,000 | Western Core, можно сужать keywords для точности |
| > 5,000 | Можно запускать частями по гео или sub-сегментам |

Оценивай TAM перед финализацией: `python3 universal_pipeline.py --mode apollo --dry-run` или Apollo UI.

---

## 9. Чеклист перед запуском пайплайна

После генерации фильтров — проверь:

- [ ] **25-company sample:** Запусти Apollo, возьми первые 25 компаний. Вручную проверь: >70% соответствуют ICP?
- [ ] **Overlap-проверка:** Есть ли компании которые одновременно попадут в несколько сегментов? Если да — они получат дублирующиеся письма. Добавь exclusion или смирись (если messaging разный).
- [ ] **Sally blacklist:** Прогони через blacklist (competitors + negative responders + active pipeline)
- [ ] **Classify prompt:** Добавлен ли новый сегмент в gathering_prompts (БД)?
- [ ] **kb_segments:** Добавлена ли запись в БД для нового сегмента?
- [ ] **Email sequence:** Есть ли markdown-файл с текстами для этого сегмента?

---

## 10. Как обновлять этот файл

После каждого нового сегмента добавляй:
1. Решение по Geography → в таблицу раздела 1
2. Решение по Size → в таблицу раздела 2
3. Решение по Industry → в таблицу раздела 3
4. Ключевые keywords и почему → в раздел 4
5. Сегмент-специфичные exclusions → в таблицу раздела 5
6. Дополнительные титулы → в таблицу раздела 6
7. Результаты первого прогона → в раздел 7 (Validated Data)

Чем больше реальных данных — тем точнее будут автоматические решения.
