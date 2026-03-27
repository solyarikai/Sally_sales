---
name: Google Sheets — организация и нейминг
description: Результаты сессии по наведению порядка в Google Sheets: ~85 таблиц переименованы, введена система нейминга, задокументированы правила
type: project
---

## Что сделано (Mar 25, 2026)

Провели полную реорганизацию Google Sheets для проекта OnSocial.

**Why:** ~100 таблиц с хаотичными названиями (US 10-15, Untitled, Companies_affperf_round2) — невозможно ориентироваться.

**How to apply:** При создании любой новой таблицы — следовать конвенции ниже. Гайд лежит в `projects/OnSocial/docs/google-sheets-naming.md`.

---

## Система нейминга

Формула: `[ПРОЕКТ] | [ТИП] | [СЕГМЕНТ] — [ДАТА]`

**Проекты:** `OS` (OnSocial), `Sally` (внутренние), `Ops` (общие без проекта)

**Типы:**
- `Leads` — финальные лиды с email, готовые к кампании
- `Targets` — компании до обогащения (вход в пайплайн)
- `Import` — сырые экспорты из Apollo / Clay / Findymail / GetSales / Crona / SmartLead
- `Archive` — снимки истории (дата обязательна)
- `Analytics` — аналитика ответов, аудиты
- `Ops` — операционные (blacklist, exclusion lists, costs, master sheet)

**Сегменты:** `IMAGENCY`, `INFPLAT`, `AFFPERF`, `NFPLAT` + география через пробел

---

## Ключевые таблицы

| Название | ID | Что это |
|----------|-----|---------|
| `OnSocial <> Sally` | 1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E | Командный документ (не переименовывать — используется всей командой). ICP, сегменты, гипотезы, сиквенсы |
| `OS \| Ops \| Daily` | 1c0PpKPsZfxbPYUPTqEyVPfKPOffExwLhrCOUDk3-RKA | Ежедневный трекер |
| `OS \| Ops \| Blacklist` | 1drDBlOBr_BEeYd0Fv5292IbAfdTApLgITOht6PZHCU4 | Блэклист компаний |
| `OS \| Ops \| Exclusion List — Apollo` | 1O2xy9Huo0uaCErTq5Er_6xj0PQv8AXZc_DWC13einn8 | Основной список исключений Apollo |
| `OS \| Leads \| All` | 1Jia8Sor5V2cby3sORXZxuaSvM_vgWB-uMdazK6RZ5wA | Все лиды |
| `OS \| Leads \| Warm Replies` | 13gWosfj8NLgPNromOJyH2gs2yIuQT2TDoXeMXhG42xA | Тёплые ответы |

---

## Что осталось сделать вручную (Google Drive)

1. **Создать папки** в Google Drive:
   ```
   OnSocial/ → Leads/, Targets/, Import/, Archive/, Analytics/, Ops/
   Sally/ → Ops/, Templates/
   Operations/
   ```

2. **Удалить 5 таблиц** (мусор/дубли):
   - `1HLBva9zAb3` — Without Email 18 march (неполные данные)
   - `1zM44yiPns` — Sheet1 пустой
   - `1k6W38VPaLx` — LEADS IMAGENCY дубль
   - `1_ohQIAS1n` — INFPLAT EUROPE дубль
   - `1cwMRTe0wF` — INFPLAT AMERICAS дубль

3. **Одна таблица без прав** — `OS | Ops | Costs` (18YLqzx...) — 403, нужен владелец

---

## Документация

Полный гайд: `projects/OnSocial/docs/google-sheets-naming.md`
Краткая версия в CLAUDE.md: `magnum-opus/.claude/CLAUDE.md` (раздел "Google Sheets — нейминг и структура")
