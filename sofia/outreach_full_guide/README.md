# 📚 Outreach Knowledge Base — Инструкция

## 🎯 Для чего эта папка

Полная база знаний по B2B-аутричу с готовыми процессами, промптами и лучшими практиками.

## 📖 Что здесь

| Файл | Для чего | Когда читать |
|------|---------|------------|
| `INDEX.md` | Быстрый индекс и команды | Быстрый поиск или первый раз |
| `outreach-knowledge-base_ru.md` | Полная база (RU) | Нужна полная информация |
| `outreach-knowledge-base.md` | Полная база (EN) | Предпочитаешь английский |

## 🚀 Быстрый старт

### Сценарий 1: Нужен быстрый ответ на вопрос
1. Открой `INDEX.md`
2. Ищи по таблице (Ctrl+F)
3. Читай нужный раздел

### Сценарий 2: Нужна деталь (напр., как использовать Apollo)
1. Используй команду из `INDEX.md`:
   ```bash
   grep -i "apollo" "outreach-knowledge-base_ru.md" | head -50
   ```
2. Прочитай результаты

### Сценарий 3: Нужен готовый процесс (напр., написать email)
1. Открой `outreach-knowledge-base_ru.md`
2. Найди раздел "2. Написание секвенса"
3. Скопируй Claude prompts
4. Используй для своего проекта

---

## 📋 Основные процессы

### 1️⃣ Сбор контактов (2-3 часа)
```
Apollo (поиск и фильтры)
  → CSV экспорт
    → Crona (сегментация)
      → готовые контакты с данными
```
**Документация**: Section 1 в `outreach-knowledge-base_ru.md`

### 2️⃣ Написание email-секвенса (1-2 часа)
```
Информация о клиенте (Google + LinkedIn)
  → Claude JTBD анализ
    → Claude Email 1, 2, 3 prompts
      → готовые тексты для Smartlead
```
**Документация**: Section 2 в `outreach-knowledge-base_ru.md`

### 3️⃣ Email-кампания (0.5 часа + автоматизация)
```
Email валидация
  → Smartlead кампания (отправка)
    → Tracking и ответы
      → Sheets (автоматический импорт)
```
**Документация**: Section 3 в `outreach-knowledge-base_ru.md`

---

## 🔍 Как искать в базе

### Вариант 1: grep (самый быстрый)
```bash
# Ищешь информацию об Apollo
grep -i "apollo" "outreach-knowledge-base_ru.md"

# Ищешь лучшие практики
grep -i "best practice\|ошибка" "outreach-knowledge-base_ru.md"

# Ищешь промпты для Claude
grep -i "prompt\|напиши" "outreach-knowledge-base_ru.md"
```

### Вариант 2: Ctrl+F в файле
1. Открой `outreach-knowledge-base_ru.md`
2. Ctrl+F → введи ключевое слово
3. Читай нужный раздел

### Вариант 3: INDEX.md таблица
1. Открой `INDEX.md`
2. Найди нужный раздел
3. Нажми на ссылку (если есть)

---

## 💡 Лучшие практики по экономии контекста

Для Claude:

1. **Не загружай весь файл, если ищешь одно** → используй `grep`
2. **Используй INDEX.md для навигации** → там уже ссылки и таблицы
3. **Загружай полный файл только когда нужен полный контекст** (например, вся стратегия аутрича)
4. **Ищи по ключевым словам** → экономит в 10+ раз контекст

---

## 📊 Частые вопросы

### Где найти промпты для email?
→ `outreach-knowledge-base_ru.md`, раздел "Phase 3: Sequence Creation"

### Как не попасть в спам?
→ `outreach-knowledge-base_ru.md`, раздел "Best Practices"

### Какой порядок: Email или LinkedIn?
→ Email первый (выше CR). LinkedIn как follow-up. Смотри раздел "4. LinkedIn Setup"

### Где взять список контактов?
→ Apollo → фильтры (смотри "1. Collecting a Database of Contacts")

### Как автоматизировать?
→ Smartlead (email), Getsales (LinkedIn). Полная автоматизация невозможна, работает гибридный подход.

---

## 📞 Контакты инструментов

| Инструмент | Зачем | Статус |
|-----------|-------|--------|
| Apollo | Поиск контактов | ✅ |
| Crona | Сегментация (sofia.kamyshenko@gmail.com) | ✅ 4000 кредитов |
| Smartlead | Email кампании | ✅ |
| Clay | Данные + автоматизация | ✅ |
| Getsales | LinkedIn автоматизация | ✅ |
| Hunter.io | Валидация email | ✅ |

---

## 🔗 Ссылки

- **Полная база RU**: `outreach-knowledge-base_ru.md`
- **Полная база EN**: `outreach-knowledge-base.md`
- **Быстрый индекс**: `INDEX.md`
- **Память Claude**: `/Users/user/.claude/projects/.../memory/outreach-kb.md`

---

**Версия**: 1.0 | **Дата**: 2026-03-13
