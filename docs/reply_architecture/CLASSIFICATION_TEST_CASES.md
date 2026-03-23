# Reply Classification Test Cases

## Mandatory Process: Test Before Deploy

**NEVER push classification prompt changes without running ALL test cases first.**

```
1. Collect test case from operator feedback (Telegram screenshot, bug report)
2. Add to this file with: message, wrong label, correct label, language, context
3. Run ALL test cases against the CURRENT prompt → baseline accuracy
4. Make prompt change
5. Run ALL test cases against the NEW prompt → must be 100% accuracy
6. If any regression → iterate the prompt until ALL cases pass
7. Only then commit and deploy
```

**Target: 100% accuracy on ALL test cases below. No exceptions. No regressions.**

## How to Run Tests

```bash
# On Hetzner, inside the backend container:
docker exec leadgen-backend python -c "
from app.services.reply_processor import classify_reply
import asyncio, json

CASES = [
    # (message, subject, expected_category)
    ('Ill be on Singapore time Monday and Tuesday than back in Sydney on Wednesday', 'Re: resale', 'meeting_request'),
    ('Привет, вы сможете написать в тг greatagaincpa', 'LinkedIn conversation', 'interested'),
    ('Нам это нужно', 'LinkedIn conversation', 'interested'),
    ('Здравствуйте, Сергей! Давайте, расскажите)\nИ про фрилансеров тоже)', 'LinkedIn conversation', 'interested'),
    # Add all cases from below...
]

async def test():
    passed = 0
    failed = 0
    for msg, subj, expected in CASES:
        result = await classify_reply(subj, msg)
        cat = result.get('category', 'unknown')
        status = '✅' if cat == expected else '❌'
        if cat != expected:
            failed += 1
            print(f'{status} EXPECTED={expected} GOT={cat} | {msg[:60]}')
            print(f'   Reasoning: {result.get(\"reasoning\", \"\")}')
        else:
            passed += 1
            print(f'{status} {cat} | {msg[:60]}')
    print(f'\n{passed}/{passed+failed} passed ({100*passed/(passed+failed):.0f}%)')
    if failed:
        print(f'⚠️  {failed} FAILURES — DO NOT DEPLOY')
    else:
        print('✅ ALL PASSED — safe to deploy')

asyncio.run(test())
"
```

---

## Test Cases

### TC-001: Availability sharing → meeting_request
- **Date**: 2026-03-23
- **Source**: Telegram feedback from Агния
- **Lead**: Drew Bradford (drew@catenadigital.com.au)
- **Campaign**: Inxy - Luma 2
- **Message**: `Ill be on Singapore time Monday and Tuesday than back in Sydney on Wednesday`
- **Wrong label**: Other
- **Correct label**: meeting_request
- **Language**: English
- **Why misclassified**: Prompt defined meeting_request too narrowly — only "wants to schedule a call or meeting", didn't cover sharing availability/timezone
- **Fix applied**: Expanded meeting_request to include availability sharing, timezone, schedule, location

---

### TC-002: Sharing Telegram handle → interested
- **Date**: 2026-03-23
- **Source**: Telegram feedback from Агния
- **Lead**: Эрдем Ukhinov (erdem@royal.partners)
- **Campaign**: EasyStaff - Russian DM [>500 connects]
- **Message**: `Привет, вы сможете написать в тг greatagaincpa`
- **Wrong label**: Wrong Person
- **Correct label**: interested
- **Language**: Russian
- **Why misclassified**: "написать в тг [handle]" interpreted as redirecting to someone else. Actually sharing own Telegram to continue conversation.
- **Fix applied**: Added contact-sharing patterns (Telegram, WhatsApp, phone) to interested. Clarified wrong_person is ONLY for redirecting to a different person.

---

### TC-003: "We need this" (нужно vs не нужно) → interested
- **Date**: 2026-03-23
- **Source**: Telegram feedback from Агния
- **Lead**: Victoria Goldenberg (v.goldenberg@emcd.io)
- **Campaign**: EasyStaff - Russian DM [>500 connects]
- **Message**: `Нам это нужно`
- **Wrong label**: Not Interested
- **Correct label**: interested
- **Language**: Russian
- **Why misclassified**: AI confused "нужно" (need) with "не нужно" (don't need). Classic negation error — the word "нужно" appeared in not_interested examples.
- **Fix applied**: Added "нам это нужно", "это нужно" to interested examples. Added explicit rule: "нужно without не is POSITIVE". Intelligence service rescue for not_interested with positive "нужно" patterns.

---

### TC-004: "Давайте, расскажите" → interested
- **Date**: 2026-03-23
- **Source**: Telegram notification (correctly classified, included as positive test)
- **Lead**: Малик Ahmedov
- **Campaign**: EasyStaff - Russian DM [>500 connects]
- **Message**: `Добрый день!\nДа расскажите`
- **Wrong label**: n/a (correctly classified)
- **Correct label**: interested
- **Language**: Russian
- **Notes**: "Да расскажите" = "Yes, tell me about it" — already matches "давайте" pattern. Included as regression test.

---

## Template for New Cases

```
### TC-XXX: [Short description] → [correct_category]
- **Date**: YYYY-MM-DD
- **Source**: [Where the feedback came from]
- **Lead**: [Name] ([email])
- **Campaign**: [Campaign name]
- **Message**: `[exact message text]`
- **Wrong label**: [what the AI said]
- **Correct label**: [what it should be]
- **Language**: [English/Russian/other]
- **Why misclassified**: [Root cause analysis]
- **Fix applied**: [What was changed in the prompt/code]
```

---

## Prompt Change Log

| Date | Cases before | Accuracy before | Change | Cases after | Accuracy after |
|------|-------------|----------------|--------|-------------|---------------|
| 2026-03-23 | 0 | n/a | Initial: expanded meeting_request, added contact-sharing to interested | 3 | 100% (manual verification) |
| 2026-03-23 | 3 | 100% | Added "нужно" vs "не нужно" disambiguation | 4 | 100% (manual verification) |

---

## Rules for Maintaining This File

1. **Every classification bug report becomes a test case.** No exceptions.
2. **Run ALL cases before deploying prompt changes.** Even if you only changed one pattern.
3. **Never delete passing cases.** They are regression tests.
4. **Document the root cause.** "AI got confused" is not enough. WHY did it get confused?
5. **Include positive tests too.** Correctly classified cases prevent regressions.
6. **100% accuracy is the deploy gate.** 99% is not enough. Iterate the prompt until all pass.
7. **Test in both languages.** Russian and English patterns can interact unpredictably.
