# Telegram DM Inbox — Issues & Solutions

## Status: WORKING at http://46.62.210.24/telegram-inbox
- 15 accounts imported from MultiAccount (38).rar
- All 15 connected, dialogs loading, conversations readable
- Read-only mode (send disabled)

---

## RESOLVED

### 1. Wrong theme tokens (2026-03-25 00:15)
Used `t.text`, `t.textMuted` etc. → Fixed to `t.text1`, `t.text4`, `t.divider`, `t.btnPrimaryBg`, `t.pageBg`.

### 2. Unused imports (2026-03-25 00:20)
TypeScript strict mode. Removed `useCallback`, `Send`.

### 3. Alembic multiple heads (2026-03-25 00:25)
`down_revision = None` → `"j1_remove_placeholder_emails"`.

### 4. RAR support (2026-03-25 00:30)
Only ZIP accepted. Added RAR via `unar` (not `unrar`, unavailable in Debian bookworm).

### 5. TGConvertor import path (2026-03-25 00:40)
`TGConvertor.manager.manager` wrong → `TGConvertor` (top-level).

### 6. opentele missing dependency (2026-03-25 00:45)
TGConvertor[tdata] needs opentele. Added to requirements.txt.

### 7. opentele infinite recursion (2026-03-25 01:00)
`TDesktop.api.setter` ↔ `Account.api.setter` infinite loop with 15 accounts.
**Fix:** Monkey-patched both setters with recursion guard.

### 8. opentele kMaxAccounts=3 limit (2026-03-25 01:05)
Only loaded 3 of 15 accounts. Kotatogram supports 100.
**Fix:** Patched `TDesktop.kMaxAccounts = 100` before loading.

### 9. opentele ToTelethon broken (2026-03-25 01:10)
`auth_session` local variable error in opentele's converter.
**Fix:** Built StringSession manually from raw auth keys + DC addresses.

### 10. Timezone naive/aware mismatch (2026-03-25 01:20)
`datetime.now(timezone.utc)` into `DateTime` column (no timezone). → `datetime.utcnow()`.

### 11. Frontend upload timeout (2026-03-25 01:25)
Default axios timeout too short for 15-account import (~60s).
**Fix:** Set `timeout: 120000` on upload request.

---

## REMAINING (minor)

### 12. FloodWait when switching accounts rapidly
Clicking between accounts fast triggers Telegram rate limits on `get_dialogs`.
**Plan:** Add per-account dialog caching + debounce on account click.

### 13. No project assignment UI
Account-to-project dropdown not in UI yet.
**Plan:** Add project selector dropdown per account in left panel.

### 14. Empty text shows "Upload a tdata ZIP" not "ZIP or RAR"
Minor copy issue in the empty state text.

### 15. No real-time incoming message detection
Messages only show on manual load.
**Plan:** Phase 2 — Telethon event handlers + polling.
