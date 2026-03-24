# Telegram DM Inbox — Issues & Solutions

## Status: MVP deployed at http://46.62.210.24/telegram-inbox

---

## RESOLVED Issues

### 1. TypeScript build failure — wrong theme tokens (2026-03-25 00:15)
**Problem:** Used `t.text`, `t.textMuted`, `t.border`, `t.accent`, `t.bgApp` which don't exist in `themeColors()`.
**Fix:** Mapped to actual tokens: `t.text1`, `t.text4`, `t.divider`, `t.btnPrimaryBg`, `t.pageBg`.
**Commit:** `af273b3`

### 2. Unused import — useCallback (2026-03-25 00:20)
**Problem:** TypeScript strict mode rejected unused import.
**Fix:** Removed `useCallback` from imports.
**Commit:** `da5ce88`

### 3. Alembic multiple heads (2026-03-25 00:25)
**Problem:** Migration had `down_revision = None`, creating a branch.
**Fix:** Set `down_revision = "j1_remove_placeholder_emails"`.
**Commit:** `1fd2e06`

### 4. RAR support missing (2026-03-25 00:30)
**Problem:** Upload endpoint only accepted ZIP. User's tdata is in RAR format (`MultiAccount (38).rar`).
**Fix:** Added RAR extraction via `unar` (installed in Docker), updated frontend to accept `.rar`.
**Commit:** `c647660`, `9e14d17`

### 5. `unrar` package not available in Debian bookworm (2026-03-25 00:35)
**Problem:** Docker build failed — `unrar` not in Debian repos.
**Fix:** Used `unar` (from `unar` package) instead, which is available.
**Commit:** `9e14d17`

---

## KNOWN Issues (to resolve)

### 6. TGConvertor may not handle multi-account tdata
**Problem:** The RAR `MultiAccount (38).rar` likely contains tdata for MULTIPLE accounts. `TGConvertor.SessionManager.from_tdata_folder()` may only extract the first account.
**Solution plan:** After extraction, scan for multiple account directories inside tdata (hex-named subdirectories). Convert each separately. Return list of accounts instead of one.
**Priority:** HIGH — blocks testing with the user's actual file.

### 7. No browser-based testing done yet
**Problem:** Page deployed but not visually verified via browser.
**Solution plan:** Use Puppeteer or manual browser access to screenshot the page at `http://46.62.210.24/telegram-inbox`.
**Priority:** HIGH

### 8. Send button visible but SENDING IS PROHIBITED
**Problem:** MVP has a send button and send endpoint. User explicitly said "DON'T SEND ANYTHING FROM ANY ACCOUNT".
**Solution plan:** Add a safety guard — disable send in production unless explicitly enabled. Consider removing send button entirely for now or showing "READ ONLY" mode.
**Priority:** MEDIUM — safety concern.

### 9. No project assignment UI
**Problem:** Account-to-project assignment exists in API but no dropdown in the UI yet.
**Solution plan:** Add project dropdown per account in the left panel.
**Priority:** LOW — not blocking MVP.

### 10. No real-time message updates
**Problem:** New incoming messages only appear after manual page reload.
**Solution plan:** Phase 2 — add Telethon event handlers for real-time DM detection + WebSocket/polling to frontend.
**Priority:** LOW — acceptable for MVP.
