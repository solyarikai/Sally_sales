# Git Auto-Sync Setup for Claude Code

Вставь это в Claude Code как промпт — он всё настроит автоматически.

---

## Промпт для вставки:

```
Настрой мне автоматический git sync для командной работы. Нужно:

1. Создай файл ~/.claude/hooks/auto_git_sync.sh — auto commit + push после каждого Edit/Write:
   - Определяет файл из tool_input.file_path
   - Находит git root
   - Формирует описательный commit message: "auto: update/add [тип] [путь]"
   - Типы: .py→script, .sh→shell script, .csv→data, .md→docs, .json→config
   - git add + commit + push (--no-verify, в фоне)

2. Создай файл ~/.claude/hooks/auto_git_pull.sh — auto pull с кулдауном 2 минуты:
   - Определяет cwd из tool_input.file_path или из поля cwd
   - Находит git root
   - Кулдаун через /tmp/git_pull_cooldown_[hash] — не чаще раза в 2 минуты
   - Stash локальных изменений перед pull, stash pop после
   - git pull --rebase
   - Сообщает только если были новые изменения

3. Оба файла chmod +x

4. Добавь в ~/.claude/settings.json хуки:
   - SessionStart → auto_git_pull.sh
   - PreToolUse matcher "Edit|Write" → auto_git_pull.sh
   - PostToolUse matcher "Edit|Write" → auto_git_sync.sh

Не трогай существующие хуки — добавь новые в дополнение.
```
