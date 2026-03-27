---
name: whisper-transcribe
description: Транскрибирует аудио или видео файл в текст с помощью локального Whisper. Используй когда пользователь говорит "транскрибируй", "расшифруй", "переведи аудио в текст", "сделай текст из записи", или даёт путь к .mp3/.mp4/.wav/.m4a/.ogg файлу.
---

# Whisper Transcribe

Whisper установлен по пути: `/Users/user/Library/Python/3.14/bin/whisper`

## Инструкции

**Шаг 1 — Уточни параметры** (если не указаны):
- Путь к аудио/видео файлу
- Язык (по умолчанию: `ru` для русского, `en` для английского; если неизвестен — не указывай, Whisper определит сам)
- Куда сохранить результат (по умолчанию: рядом с исходным файлом)
- Формат вывода: `txt` (чистый текст), `srt` (субтитры), `vtt`, `json` (по умолчанию: `txt`)

**Шаг 2 — Запусти команду**

Базовая транскрипция:
```bash
/Users/user/Library/Python/3.14/bin/whisper "<путь_к_файлу>" --model turbo --language ru --output_format txt --output_dir "<папка_назначения>"
```

Транскрипция с авто-определением языка:
```bash
/Users/user/Library/Python/3.14/bin/whisper "<путь_к_файлу>" --model turbo --output_format txt --output_dir "<папка_назначения>"
```

Перевод на английский (любой язык → English):
```bash
/Users/user/Library/Python/3.14/bin/whisper "<путь_к_файлу>" --model turbo --task translate --output_format txt --output_dir "<папка_назначения>"
```

**Шаг 3 — Сохрани и покажи результат**

После завершения:
1. Прочитай полученный `.txt` файл из папки назначения
2. Покажи транскрипт пользователю
3. Если нужно — предложи сохранить в `sofia/transcripts/[имя_файла].txt`

## Параметры модели

| Модель | Скорость | Качество | Когда использовать |
|--------|----------|----------|--------------------|
| `tiny` | Очень быстро | Низкое | Черновая расшифровка |
| `base` | Быстро | Среднее | Короткие записи |
| `small` | Средне | Хорошее | Обычные записи |
| `medium` | Медленно | Высокое | Важные записи |
| `turbo` | Быстро | Высокое | **По умолчанию** |
| `large` | Медленно | Лучшее | Максимальное качество |

## Примеры

**Расшифровать звонок на русском:**
```bash
/Users/user/Library/Python/3.14/bin/whisper "~/Downloads/call.mp3" --model turbo --language ru --output_format txt --output_dir ~/Downloads
```

**Субтитры к видео:**
```bash
/Users/user/Library/Python/3.14/bin/whisper "~/Downloads/video.mp4" --model turbo --output_format srt --output_dir ~/Downloads
```

**Несколько файлов сразу:**
```bash
/Users/user/Library/Python/3.14/bin/whisper file1.mp3 file2.mp4 --model turbo --language ru --output_format txt --output_dir ./transcripts
```

## Поддерживаемые форматы

`.mp3` · `.mp4` · `.wav` · `.m4a` · `.ogg` · `.flac` · `.webm` · `.mkv` · `.avi`

## Заметки

- Если файл большой (>30 мин), транскрипция может занять несколько минут
- Модель `turbo` — лучший баланс скорости и качества
- Для коротких клипов (<5 мин) можно использовать `small` — быстрее
- Результат сохраняется с тем же именем файла, но с расширением `.txt` / `.srt` и т.д.
