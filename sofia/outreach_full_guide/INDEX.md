# Outreach Knowledge Base — Быстрый индекс

> Это быстрый индекс базы знаний. Для деталей → смотри `outreach-knowledge-base_ru.md` или `outreach-knowledge-base.md`

## 🚀 Как пользоваться этой базой

1. **Знаешь что ищешь?** → Ищи в этом индексе (Ctrl+F)
2. **Нужна вся информация?** → Загрузи `outreach-knowledge-base_ru.md`
3. **Нужна деталь?** → Используй `grep "keyword" outreach-knowledge-base_ru.md`

---

## 📑 Основные разделы

### 1️⃣ Сбор базы контактов
| Что нужно | Инструмент | Статус | Примечание |
|-----------|-----------|--------|-----------|
| Основной поиск | Apollo.io | ✅ Основной | Максимум фильтров |
| Сегментация | Crona | ✅ Работает | После Apollo (4000 кредитов) |
| Финтех/SaaS | Clay | ✅ | Данные + автоматизация |
| Веб-скрепинг | Apify, Outscraper | ✅ | Конкретные сайты |
| Обогащение | Hunter.io, Clearbit | ✅ | Email валидация |

**Быстрый флоу**: Apollo → экспорт CSV → Crona сегментация → готовые контакты

### 2️⃣ Написание секвенса
| Фаза | Что делать | Инструмент | Результат |
|------|-----------|-----------|----------|
| 1 | Информация о клиенте | Google, LinkedIn | ICP, боли, контекст |
| 2 | Анализ проекта (JTBD) | Claude | 3-4 основные проблемы |
| 3 | Email 1, 2, 3 | Claude (промпты) | Готовый текст для Smartlead |

**Ключевой промпт**: [есть в базе знаний]

### 3️⃣ Email-аутрич
| Шаг | Инструмент | Действие |
|-----|-----------|---------|
| Валидация | Email Validation API | Проверка перед отправкой |
| Почтовые ящики | Smartlead | Создание + настройка |
| Кампания | Smartlead | Запуск + tracking |
| Ответы | Sheets + Zapier | Автоматический импорт |

### 4️⃣ LinkedIn-аутрич
- **Setup**: SSI score, нужен реальный профиль
- **Автоматизация**: Getsales → Google Sheets (синхронизация)

### 5️⃣ Telegram-аутрич
- **Бот**: SpamBot или собственный
- **Рассылка**: Автоматизированная отправка по списку

---

## 🎯 Частые вопросы

**Q: Как найти контакты для [индустрия]?**
→ Apollo фильтры: industry + headcount + geo → экспорт

**Q: Как быстро проверить ICP?**
→ Apollo filters → экспорт 50-100 контактов → быстрый анализ вручную

**Q: Какой порядок: Email или LinkedIn?**
→ Email первый (выше CR), LinkedIn как backup/follow-up

**Q: Можно ли автоматизировать всё?**
→ Нет полной автоматизации; рекомендуется гибридный подход (50% auto, 50% ручная настройка)

**Q: Как не попасть в спам?**
→ Смотри "Лучшие практики" (email разминка, персонализация, валидация)

---

## 📚 Ссылки на полные гайды

- **Apollo**: `grep "Apollo" outreach-knowledge-base_ru.md`
- **Crona**: `grep "Crona" outreach-knowledge-base_ru.md`
- **Smartlead**: `grep "Smartlead" outreach-knowledge-base_ru.md`
- **Sequence Writing**: `grep "Email 1\|Email 2\|Email 3" outreach-knowledge-base_ru.md`

---

## 🔧 Команды для быстрого поиска

```bash
# Ищешь информацию о сегменте?
grep -i "segment\|сегмент" outreach-knowledge-base_ru.md

# Ищешь лучшие практики?
grep -i "best practice\|ошибка\|mistake" outreach-knowledge-base_ru.md

# Ищешь промпты для Claude?
grep -i "prompt\|промпт" outreach-knowledge-base_ru.md

# Ищешь информацию по инструменту?
grep -i "apollo\|crona\|smartlead\|clay" outreach-knowledge-base_ru.md
```

---

## 📊 Структура основного файла

```
outreach-knowledge-base_ru.md
├── 1. Сбор базы контактов
│   ├── Apollo
│   ├── Crona
│   ├── Clay, Apify, Outscraper
│   ├── Обогащение и валидация
│   └── Русскоязычные контакты
├── 2. Написание секвенса
│   ├── JTBD анализ
│   ├── Prompts для Claude
│   └── Email templates
├── 3. Email Setup
├── 4. LinkedIn Setup
├── 5. Telegram Setup
├── 6. Best Practices
└── 7. Common Mistakes
```

---

**Версия**: 1.0 | **Дата**: 2026-03-13 | **Язык**: RU + EN доступны
