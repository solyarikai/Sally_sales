# ⚡ A/B Test Analysis — Quick Start Guide

## 📌 У нас есть

✅ **4 кампании IM-FIRST AGENCIES** в SmartLead  
✅ **Полная документация A/B вариантов** (5 шагов × 5 вариантов)  
✅ **Базовые метрики**: Sent, Replied, Response Rate %  
✅ **Автоматизированный анализ**: Python скрипт для SmartLead API  

---

## 🚀 Как запустить анализ

### 1. На Hetzner (recommended)

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && \
  python3 sofia/scripts/smartlead_im_agencies_ab_analysis.py"
```

**Что будет**:
- ✓ Подключится к SmartLead API (нужен SMARTLEAD_API_KEY в .env)
- ✓ Получит статистику по всем 4 кампаниям
- ✓ Выведет людей с положительными ответами
- ✓ Сохранит результаты в JSON файл с датой/временем

**Output**: `sofia/projects/OnSocial/hub/im_agencies_ab_analysis_YYYYMMDD_HHMMSS.json`

---

### 2. Локально (для просмотра)

Если нужно просто посмотреть варианты без запуска API:

```bash
# Посмотреть полный анализ с таблицами
cat sofia/projects/OnSocial/hub/IM_FIRST_AGENCIES_AB_TEST_ANALYSIS.md

# Посмотреть исходные последовательности
cat sofia/projects/OnSocial/docs/smartlead_sequences_2026-03-26.md | grep -A 50 "IM-FIRST AGENCIES"
```

---

## 📊 Текущие результаты (по состоянию на 2026-03-26)

| Кампания | Дата | Отправлено | Ответов | % |
|----------|------|-----------|---------|---|
| 🇮🇳 India | 2026-03-20 | 383 | **3** | **0.8%** ← Лучше |
| 🌍 Global | 2026-03-17 | 290 | 1 | 0.3% |
| 🇪🇺 Europe | 2026-03-20 | 559 | 0 | 0.0% |
| 🌎 Americas | 2026-03-23 | 338 | 0 | 0.0% |

**Вывод**: India выигрывает (0.8% vs 0.3%), но Europe и Americas — 0%.

---

## 🎯 Главные разницы между A/B вариантами

### Раунд 1: Opener (Step 1)

**Global + Americas** (97 слов):
```
Hi {{first_name}},

How does {{company_name}} verify creator audiences before signing deals? 
We helped an agency catch a creator with 60% fake followers before a €40K contract was signed.

450M+ profiles, credibility scoring, city-level demographics, all via API.
Can I pull the breakdown for a creator you're currently evaluating? 10 min.
```

**Europe** (68 слов) — *Concise, no case study*:
```
Hi {{first_name}},

How does {{company_name}} currently verify creator audiences before signing?

We helped an agency catch a creator with 60% fake followers before a €40K deal.

450M+ profiles with credibility scoring, city-level demographics, all via API.
15 min walkthrough?
```

**Гипотеза**: Детальный opener (Global) может работать лучше, чем сокращённый (Europe).

---

### Раунд 2: Competitor Comparison (Step 2)

**Global** — Детальное сравнение:
```
Most agencies we talk to are moving off HypeAuditor or frustrated 
with Kolsquare's coverage outside Western Europe.

What's different with us:
- Credibility breakdown: real / mass followers / bots
- City-level demographics, real-time
- Creator overlap across your client's shortlist
```

**Europe** — Краткое, гео-ориентированное:
```
Most agencies using HypeAuditor or Kolsquare are hitting coverage 
limits outside Western Europe.

Different angle: 450M+ profiles with credibility breakdown...
```

**Гипотеза**: Конкретные конкуренты (HypeAuditor) + bullet points работают лучше.

---

### Раунд 3: CTA (Step 5)

**Global**:
```
Trying to get on your radar before we approach from a different angle.
Do you have 10 minutes for a quick demo?
Or would a walkthrough with your team be better?
```

**Europe**:
```
Last touch: are you interested in seeing a live demo, 
or would docs + pricing be more useful?
```

---

## 💡 Рекомендации

### Приоритет 1: Почему India работает лучше?

**Сделать**:
1. Запустить скрипт на Hetzner, чтобы получить полные данные India sequence
2. Посмотреть, какой шаг ответ произошёл (Step 1, 2, 3, 4 или 5?)
3. Если India использует другой opener/hook, клонировать в Global

```bash
# После запуска скрипта на Hetzner смотреть:
cat sofia/projects/OnSocial/hub/im_agencies_ab_analysis_*.json | jq '.campaigns[] | select(.campaign_id == 3063527)'
```

---

### Приоритет 2: Оживить Europe (0% → ?)

**Гипотеза**: Европейцы ценят краткость, но нашему сокращённому версию не хватает доказательств.

**Test**:
- Взять Europe список
- Отправить им Global sequence (с полной case study)
- Сравнить reply %

---

### Приоритет 3: Americas Debug (0% → ?)

**Гипотеза**: Может быть список, может быть timing.

**Действия**:
1. Проверить: когда последний контакт с этим списком был?
2. Проверить: есть ли overlaps с предыдущими кампаниями (которые уже слышали о нас)?
3. Если да — это список fatigue, нужны новые контакты

---

## 📝 Как интерпретировать результаты

### Metrics

- **Sent**: Сколько писем отправлено
- **Replied**: Сколько лидов ответили хотя бы один раз
- **Response Rate %**: (Replied / Sent) × 100
- **Opened/Clicked**: Есть в SmartLead, но не в нашем CSV

### Что считается A/B тестом

**A** = Один вариант последовательности  
**B** = Другой вариант (отличается 1+ шагом)

У нас есть:
- **A vs B (Step 1 Opener)**: Global vs Europe
- **A vs B (Step 2 Hook)**: Detailed vs Brief
- **A vs B (Step 5 CTA)**: Multiple options vs preference ask

---

## 🔧 Инструменты

| Инструмент | Где | Что делает |
|------------|-----|----------|
| `smartlead_im_agencies_ab_analysis.py` | `sofia/scripts/` | Автозагрузка данных из SmartLead API |
| `IM_FIRST_AGENCIES_AB_TEST_ANALYSIS.md` | этот каталог | Полный анализ с гипотезами |
| `smartlead_sequences_2026-03-26.md` | `sofia/projects/OnSocial/docs/` | Исходные тексты сиквенсов |
| SmartLead Dashboard | https://app.smartlead.ai | Ручная проверка статистики |

---

## ❓ FAQ

**Q: Когда запустить анализ?**  
A: Лучше через 7-14 дней после отправки (дать лидам время ответить). Americas кампания молодая, дайте ей время.

**Q: Какой sample size нужен для valid выводов?**  
A: Минимум 30-50 replies per variant. Сейчас есть только 1-3. Нужно масштабировать.

**Q: Как заскейлить?**  
A: Скопировать лучший вариант на новый список с 500-1000 новых лидов.

**Q: Что если результаты статистически не значимы?**  
A: Значит, нужна бо́льшая выборка. Or различия слишком малы чтобы сделать вывод.

---

## 🎬 Next Steps

1. ✅ **Сегодня**: Посмотреть этот документ
2. 🚀 **Завтра**: Запустить анализ на Hetzner
3. 📊 **На неделе**: Выбрать один hypothesis для теста
4. 🎯 **На 2 неделе**: Запустить новую кампанию с test variant на 500 leads
5. 📈 **Через 2 недели**: Собрать результаты, сравнить

---

## 📞 Контакты

**Questions на**:
- SmartLead API: `sofia/mcp/smartlead-mcp/server.py`
- Sequences: `sofia/projects/OnSocial/docs/smartlead_sequences_2026-03-26.md`
- Analysis: этот файл

---

**Последнее обновление**: 2026-04-02
