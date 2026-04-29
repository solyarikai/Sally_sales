# SmartLead — Formatting Rules

When writing email sequences (markdown files or GOD_SEQUENCE):
- **No em dashes** (`---`). Use regular dash (`-`). Em dashes break in some email clients.
- **Line breaks**: SmartLead API ignores `\n`. Use `<br>` for line breaks, `<br><br>` for paragraph breaks.
- Pipeline scripts auto-convert `\n` -> `<br>` and `---` -> `-` when uploading, but markdown source files should be clean.
- **A/B variants**: SmartLead API doesn't support variants. Add B variants manually in SmartLead UI.
- **Activation**: NEVER activate campaigns via API. Only manually in SmartLead UI.
- **delay_in_days** is relative to the previous email, not absolute from step 1.
- **POST /sequences** replaces ALL sequences — always send the full list, not just new ones.
