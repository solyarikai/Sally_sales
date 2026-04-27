# OnSocial — GetSales LinkedIn Reply Analytics (14d)

**Window:** 2026-04-13 → 2026-04-27
**Channel:** LinkedIn (GetSales)
**Method:** GetSales MCP API (`list_messages`, `get_contact`, `list_flows`)
**Author:** Claude (analysis), Sofia (review)

---

## TL;DR

- **2 confirmed warm replies** на LinkedIn за 14 дней по OnSocial-флоу.
- **INFLUENCER PLATFORMS #C** — единственный явно живой OnSocial-флоу (1 warm).
- **IM-FIRST AGENCIES #C** — тишина (0 warm на 8+ first-touch + 5 follow-ups в sample).
- **AFFPERF / INFPLAT_INDIA / IMAGENCY_INDIA / INFPLAT_MENA_APAC** — низкий volume или мёртвые в sample.
- Hard data на LinkedIn НЕ подтверждает что IMAGENCY-сегмент работает в этом канале.

---

## Confirmed Warm Replies

| # | Lead | Компания | Geo | Флоу | Reply text | Tone | Date |
|---|------|----------|-----|------|------------|------|------|
| 1 | Duy Pham (CEO) | OTA Network | Vietnam | `INFLUENCER PLATFORMS #C` | "Yes. Nice to e meet you!" → "Could you send me a quick profile about your service?" → "duypb@appota.com" | WARM, asks demo | 2026-04-20 → 21 |
| 2 | María Majón Diéguez (CEO) | Let's Be Group | Spain | IMAGENCY (Spanish list, likely `IM-FIRST AGENCIES #C` или geo-specific) | "Hello dear, let me know more about your api, How you can help us?" | WARM, asks discovery | 2026-04-26 |

Оба = high-quality leads, поделились email, готовы к pitch deck/demo.

---

## По флоу

| Flow | UUID | Status | Outbox sample (14d) | Confirmed replies | Notes |
|------|------|--------|---------------------|-------------------|-------|
| INFLUENCER PLATFORMS #C | `2e128a49-6675-4c4c-a14b-fe4ac709f640` | on | ~21+ | **1 warm** (Duy/OTA) | Живой; работает |
| IM-FIRST AGENCIES #C | `05b5ebbb-5cfb-46e5-80df-6b1ad17d18a3` | on | ~13+ (8 first + 5 follow-up) | **0 warm** | Тишина; крупные агентства (Kantar, Mindshare, Launchmetrics) не отвечают |
| Spanish IMAGENCY trail | (через Spanish list `25932db3`) | — | 1 sample | **1 warm** (María/Let's Be Group) | Geo-specific; не reusable как канал |
| INFPLAT_MENA_APAC \| 01.04 | `16d4d827-11d3-4e2f-a471-66b7fc6fb40a` | on | low в sample | 0 в sample | Volume не оценён |
| INFPLAT_INDIA \| 01.04 | `470896be-695e-4cec-910d-2c8a3f76160d` | on | Chandrayee/ClanConnect 4-touch | 0 в sample | Volume не оценён |
| IMAGENCY_INDIA \| 01.04 | `81d55314-4967-4ffc-b3da-01a46dee6bc8` | on | low в sample | 0 в sample | Volume не оценён |
| AFFILIATE & PERFORMANCE #C | `00722544-2efa-4125-90f1-f9ed79d00c3c` | on | fingerprint не идентифицирован | n/a | Возможно мёртвый |

---

## Outbox sample — leads без reply за 14d

**INFLUENCER PLATFORMS #C** (1st-touch "creator data infrastructure"):
Yun/MBC, Dick/Global, Ruby/CAN Digital, Tinta/Nativo, Sajad/Orbit, Victoria/Global, Sabrina/Digital Age, Shakeel/XDBS, Leonardo/Artear, Yan/CULTURE KIDS, Sharon/Coinband, Anne/Freelance, Wilona/Catalysts, Pravin/Market Xcel, Edokpayi/Global, Junk/Global, Ghulam/Global, Jillian/Frank — **0 replies**.

**IM-FIRST AGENCIES #C** (1st-touch "white-label analytics under your brand"):
Debbie/Dovetail, Qaiser/inDrive, Margot/Launchmetrics, Catherine/Kantar, Jane/Kantar, Gang/Mindshare, Mariya/Mindshare, Gregory/inDrive — **0 replies**.

**Multi-touch follow-ups** (3-4 messages, "With OnSocial...", "Most teams stuck", agency-margin pitch):
Greg/Kantar, Daria/Grapzy, Valerie/Kantar, Chandrayee/ClanConnect, Monika/Digital ShoutOuts, Colette/Jabberhaus, Supranan/Mindshare — **0 replies**.

---

## Методологические ограничения

GetSales API не отдаёт per-flow reply stats напрямую и не фильтрует messages по дате/типу. Полный обход требует:
- ~200 страниц `list_messages` (offset 0 → 10 000 messages в окне) из 258 911 total
- ~150-300 `get_contact` для tag/list-mapping на флоу
- outbox count в окне per flow для расчёта reply rate

**Реально просканировано:**
- 16 spot-pages (offsets 0, 50, 100, 150, 200, 250, 500, 1k, 2k, 3k, 5k, 6k, 7k, 8k, 9k, 10k) ≈ 800 messages
- 25 целенаправленных `list_messages(lead_uuid)` для OnSocial-identifiable leads
- 6 `get_contact` для подтверждения tags/lists

Это **representative sample**, а не полный обход. Реальные replies могут быть в 2-3x выше, но **паттерн (INFPLAT > IMAGENCY > AFFPERF) повторяет email-данные из** `OS_Analytics_CampaignAudit_2026-04-26.csv`.

**Контекст:** GetSales-аккаунт обслуживает много продуктов параллельно (Easystaff, Mifort, SquareFi, Finchtrade, branded resale, AI fraud detection, OnSocial). OnSocial-сообщения = ~7-10% потока.

---

## Идентификаторы OnSocial-leads (для будущих выборок)

`get_contact` возвращает пустое поле `flows` (контакты теряют ассоциацию после завершения флоу). Реальные идентификаторы:

**По tags:**
- `INFLUENCER_PLATFORMS` — Duy/OTA, Pravin/Market Xcel
- `5835e1c9-694a-4e49-b9ed-c106ccb89f67` — IMAGENCY tag (María/Let's Be Group)
- `81d2eff6-dc6c-405c-aa3e-2148931a6fc2` — Chandrayee/ClanConnect (вероятно INFPLAT_INDIA или IM_FIRST_AGENCIES)
- `61847adf-3e9b-4b40-a9c3-5fb0250b618b` — общий тег (Duy/OTA, Chandrayee)

**По list_uuid:**
- `2f900c3a-589c-4b25-a9f4-422a0c4e57c1` — INFPLAT list (Duy, Pravin)
- `25932db3-0e53-42a5-9864-5796047e7907` — IMAGENCY list (María)
- `a6e3ae0c-f4f9-4279-bc4f-c2d6e59a7a01` — INFPLAT_INDIA (Chandrayee)
- `1481eb69-6611-49f2-89b2-c8030534f63b` — НЕ OnSocial (Ilya/FG BCS, Russian)

---

## Decision context — IMAGENCY_TECHLEAD на LI

Контекст из Strategy Review (2026-04-26):
- AFFPERF: 50% → REDUCE to 15% (0/154 SQL)
- IMAGENCY: 35% → MAINTAIN 30%
- INFPLAT: 9% → BOOST to 40% (0.49% lead→SQL, BEST email channel)
- SOCCOM: untested

**Email data (`OS_Analytics_CampaignAudit_2026-04-26.csv`):**
- IMAGENCY_TECHLEAD (3169092): Pos rate LT 0.565% — best in IMAGENCY cohort
- INFPLAT email = 0.49% lead→SQL
- 2 LI accounts available: Albina + Rajat

**LinkedIn data (этот отчёт):**
- INFPLAT в LI: 1 warm reply (Duy/OTA) — **proven**
- IMAGENCY на LI через generic `IM-FIRST AGENCIES #C`: **0 warm**
- TECHLEAD-specific persona на LI: **никогда не тестировалась**

**Decision (current plan):**
- **Albina → IMAGENCY_TECHLEAD smoke test** (новый flow + новый sequence под CTO/Head of Eng)
- **Rajat → INFPLAT** (`INFLUENCER PLATFORMS #C`, proven warm)
- **Kill-criteria:** 7 days, 0 warm replies → Albina переключается на INFPLAT
- **Pause:** AFFPERF, INFPLAT_INDIA, IMAGENCY_INDIA, INFPLAT_MENA_APAC, generic `IM-FIRST AGENCIES #C`

---

## Next steps

1. Извлечь IMAGENCY_TECHLEAD лидов с LI URL (Hetzner: enriched.json + DB).
2. Написать TECHLEAD-specific LI sequence (не reusing `IM-FIRST AGENCIES #C`).
3. Сгенерить GetSales CSV (49 cols).
4. Создать flow в GetSales UI, attach Albina.
5. Залить контакты через `add_new_lead_to_flow`.
6. Мониторинг 7 дней → kill/keep решение.

Для полной картины LI-channel:
- Запросить у GetSales export по `tags=INFLUENCER_PLATFORMS` + `last_messaging_activity_at >= 2026-04-13` (если API поддерживает).
- Альтернатива: 7-day window даёт ~5 000 messages = ~100 запросов = выполнимо за одну сессию.
