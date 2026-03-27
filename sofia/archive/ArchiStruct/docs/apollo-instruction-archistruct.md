# Apollo Instruction — ArchiStruct

**Задача:** один широкий поиск → ~300–500 контактов → CSV → Crona сегментирует по 3 сегментам.

---

## Шаг 1 — Companies → применить фильтры

Левое меню → **Companies**

### Industry & Keywords

**Industry**

```
Architecture & Planning, Real Estate, Interior Design, Hospitality
```

**Company Keywords Contain ANY Of**

```
residential, villa, developer, luxury, architecture studio,
branded residence, co-living, hospitality, mixed-use, fit-out,
property developer, real estate development
```

**Excluded Company Keywords**

```
recruitment services, consulting, facility management,
mortgage, property portal, real estate brokerage,
real estate broker,
staffing, financial services
```

### Location

**Location:** United Arab Emirates

### Company Size

**# Employees:** 10–200

---

## Шаг 2 — Сохранить компании в список

1. Выбери 300–500 компаний
2. **Add to List** → назови `ArchiStruct_Wide`

---

## Шаг 3 — Найти людей внутри компаний

Открой список `ArchiStruct_Wide` → **Find People**

### Job Titles

```
Founder, CEO, Managing Director, Partner, Principal,
Development Director, Head of Design, Project Director
```

**Excluded Job Titles**

```
IT Director, HR Director, Finance Director,
Marketing Director, Sales Director, Accountant
```

### Management Level

- Owner
- C-Suite
- VP
- Director
- Partner

1. **Add to List** → `ArchiStruct_Contacts`

---

## Шаг 4 — Обогатить emails

Выбери всех → **Enrich → Enrich Emails** → дождись завершения

---

## Шаг 5 — Экспортировать CSV

Выбери все → **Export All Emails → Export Records** → сохрани файл

---

## Шаг 6 — Скинь CSV

CSV → Crona с segmentation prompt → разобьёт на 3 сегмента:

1. Международные архитектурные студии
2. Co-living & Branded Residence developers
3. Villa & Land Plot developers

---

**Следи за кредитами:** Settings → Billing and Credits → Credits Usage