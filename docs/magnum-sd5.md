# magnum-sd5: Inbox & Messaging Improvements

## Проблема

Inbox-чат в Telegram Outreach имел ряд UX-проблем:

1. **Textarea слишком высокий** — начальная высота текстового поля не совпадала с кнопками (шаблоны, отправка), визуально ломая layout.
2. **Скролл ломался при >6 строках** — при вводе длинного сообщения текст уезжал за границы, скролл работал только вниз.
3. **Нет форматирования текста** — невозможно было отправлять жирный, курсив, подчёркнутый текст и другие HTML-entities через горячие клавиши.
4. **Нельзя написать незнакомому контакту** — Inbox позволял только отвечать на существующие диалоги, но не начинать новые.

## Решение

### sd5.1 — Начальная высота textarea

Textarea заменён на `contentEditable` div с CSS-стилями, обеспечивающими компактную начальную высоту, совпадающую с кнопками (`min-height` через класс `inbox-editor`). Динамическое расширение по содержимому сохраняется нативно.

### sd5.2 — Корректный скролл при длинном тексте

`contentEditable` div с ограниченной максимальной высотой обеспечивает корректный скролл через CSS `overflow-y: auto`. При превышении max-height появляется скроллбар, текст не уезжает за границы контейнера. Отправка по `Enter`, перевод строки по `Shift+Enter`.

### sd5.3 — Форматирование через горячие клавиши

Реализовано два механизма форматирования:

**Горячие клавиши** (`handleEditorKeyDown`):

| Комбинация | Эффект |
|---|---|
| `Ctrl+B` | Жирный |
| `Ctrl+I` | Курсив |
| `Ctrl+U` | Подчёркнутый |
| `Ctrl+K` | Ссылка (custom popup для ввода URL) |
| `Ctrl+Shift+X` | Зачёркнутый |
| `Ctrl+Shift+>` | Цитата (`blockquote`) |
| `Ctrl+Shift+M` | Моноширинный (`code`) |
| `Ctrl+Shift+P` | Спойлер (`tg-spoiler`) |

**Toolbar-кнопки** — визуальная панель под редактором дублирует все горячие клавиши.

Форматирование работает через `document.execCommand` для стандартных операций (bold, italic, underline, strikethrough) и утилиту `wrapSelectionWith()` для Telegram-специфичных тегов (blockquote, code, tg-spoiler). Поддерживает toggle — повторное нажатие снимает форматирование.

При отправке HTML из `contentEditable` конвертируется в Telegram HTML-entities через `htmlToTgHtml()`.

**Дополнительные фиксы** (после первичной реализации):
- Toggle для code/quote — повторное нажатие корректно снимает обёртку
- Custom link popup — вместо `prompt()` используется inline-popup для ввода URL
- CSS-стили для ссылок внутри редактора (`frontend/src/index.css`)

### sd5.4 — Новый диалог с незнакомым контактом

Кнопка «New Chat» доступна при фильтре по конкретному аккаунту. Флоу:

1. Нажать «New Chat» -> открывается модальное окно
2. Ввести `@username` (символ `@` автоматически удаляется)
3. «Start Chat» -> бэкенд резолвит username через Telegram API, создаёт `TgInboxDialog`
4. Диалог появляется в списке, можно сразу отправить сообщение

Backend endpoint: `POST /api/tg-outreach/inbox/new-chat`
- Принимает: `{ account_id: number, username: string }`
- Резолвит username через активную Telegram-сессию аккаунта
- Если диалог уже существует — возвращает его (с `is_new: false`)
- Автоматически создаёт `TgAccount` если его нет для DM-аккаунта (фикс: многие DM-аккаунты не имели соответствующего `TgAccount`, что приводило к ошибке "No outreach account found")

## Изменённые файлы

- `frontend/src/pages/TelegramOutreachPage.tsx` — contentEditable-редактор вместо textarea, `wrapSelectionWith()` для форматирования, `handleEditorKeyDown` для горячих клавиш, formatting toolbar, New Chat модальное окно и `handleNewChat()`, toggle fix для code/quote, custom link popup
- `frontend/src/api/telegramOutreach.ts` — метод `createNewChat()` для API вызова
- `frontend/src/index.css` — CSS-стили для ссылок в contentEditable-редакторе
- `backend/app/api/telegram_outreach.py` — endpoint `POST /inbox/new-chat` с резолвингом username и созданием диалога, авто-создание `TgAccount`
- `backend/app/services/inbox_sync_service.py` — авто-создание `TgAccount` при inbox sync для DM-аккаунтов без outreach-записи

## Использование

### Отправка сообщения
- Ввести текст в редактор -> `Enter` для отправки
- `Shift+Enter` для перевода строки

### Форматирование
1. Выделить текст в редакторе
2. Нажать горячую клавишу (например `Ctrl+B`) или кнопку на панели
3. Текст визуально форматируется в редакторе
4. При отправке HTML конвертируется в Telegram-совместимый формат

### Новый чат
1. Выбрать аккаунт в фильтре (обязательно)
2. Нажать кнопку «New Chat» в хедере списка диалогов
3. Ввести username контакта -> «Start Chat»
4. Диалог откроется автоматически
