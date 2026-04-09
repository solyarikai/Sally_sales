# Classify Prompts — Format Rules

## Правило: никакого OUTPUT FORMAT в classify промптах

Backend (`company_search_service.py`) **автоматически** оборачивает любой `custom_system_prompt` следующей инструкцией:

```
Respond ONLY with valid JSON in this exact format (no markdown, no text outside JSON):
{
  "is_target": true,
  "confidence": 0.0,
  "segment": "SEGMENT_NAME or NOT_A_MATCH",
  "reasoning": "1-2 sentence explanation"
}
```

Если промпт **сам** описывает формат вывода (pipe-format, другой JSON, примеры ответов) — GPT получает конфликтующие инструкции и иногда следует одному, иногда другому. Результат: parsing errors → `is_target=false`, потеря targets.

## Что писать в промпт

✅ **Можно и нужно:**
- Описание продукта (что такое OnSocial, зачем он)
- Определения сегментов (SOCIAL_COMMERCE, INFLUENCER_PLATFORMS, ...)
- Правила включения / исключения (KEY TEST, CONFLICT RESOLUTION)
- Примеры компаний-мишеней

❌ **Нельзя:**
- `== OUTPUT FORMAT ==` секции
- Pipe-format примеры (`SEGMENT | 0.9 | reasoning`)
- Любые инструкции про формат ответа
- Примеры JSON ответов (backend уже их добавляет)

## Backend JSON schema

Поля которые backend ожидает от GPT:
```json
{
  "is_target": true,
  "confidence": 0.85,
  "segment": "SOCIAL_COMMERCE",
  "reasoning": "one-line explanation"
}
```

`segment` нормализуется: `segment` → `matched_segment` (legacy alias поддерживается).
`is_target: true` автоматически если `confidence >= 0.6`.

## Файл: backend/app/services/company_search_service.py

Wrapper добавляется в функции `analyze_company()` при `custom_system_prompt != None`.
Fallback pipe-parser добавлен (2026-04-10) на случай edge cases, но основной путь — JSON.
