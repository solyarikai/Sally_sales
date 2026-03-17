# Wazzzup — Architecture & Approach

## How It Works

Wazzzup sends WhatsApp messages by hooking into WhatsApp Web's internal JavaScript modules via **wppconnect-team/wa-js** (v3.22.1). No URL navigation, no DOM clicks, no page reloads.

### Core Call
```js
await window.WPP.chat.sendTextMessage(`${phone}@c.us`, message, { createChat: true })
```

This calls WhatsApp's internal webpack functions directly — the same functions the web client uses.

## Architecture

```
┌─────────────┐     chrome.runtime      ┌──────────────┐     chrome.tabs      ┌──────────────┐
│   popup.js  │ ──────────────────────→  │ background.js│ ──────────────────→  │  content.js  │
│  (UI window)│ ←──────────────────────  │  (service    │ ←──────────────────  │  (WA page)   │
│             │     sendResponse         │   worker)    │    sendResponse      │              │
└─────────────┘                          └──────────────┘                      └──────┬───────┘
                                                                                      │ window.postMessage
                                                                               ┌──────▼───────┐
                                                                               │  inject.js   │
                                                                               │  (page ctx)  │
                                                                               │  window.WPP  │
                                                                               └──────────────┘
```

### Files

| File | Context | Purpose |
|------|---------|---------|
| `popup.html/js/css` | Extension popup window | UI: contacts, template, send config, log |
| `background.js` | Service worker | Opens popup as persistent window, routes messages |
| `content.js` | Content script (WA page) | Injects wa-js + inject.js, bridges messages |
| `wa-js.js` | Page context (injected) | wppconnect-team/wa-js v3.22.1 — hooks into WA internals |
| `inject.js` | Page context (injected) | Receives commands via postMessage, calls WPP API |

### Message Flow (send one message)

1. **popup.js** → `chrome.runtime.sendMessage({action: 'sendMessage', phone, message})`
2. **background.js** → finds WA tab → `chrome.tabs.sendMessage(tabId, ...)`
3. **content.js** → `window.postMessage({source: 'wazzzup-content', action: 'sendMessage', ...})`
4. **inject.js** → `WPP.chat.sendTextMessage(phone + '@c.us', message, {createChat: true})`
5. Response flows back the same chain

### Phone Number Format

- Strip `+` prefix and all spaces/dashes
- Append `@c.us` for individual chats, `@g.us` for groups
- Examples: `79643856156@c.us`, `436609273668@c.us`

### LID Migration

Newer WhatsApp accounts use LID (Linked Identity) instead of phone-based addresses. The inject script auto-detects this via `WPP.conn.getMigrationState()` and resolves the LID before sending.

## wa-js Library

- **Source**: [wppconnect-team/wa-js](https://github.com/AzizKHAN030/wa-js) (fork used by WADesk)
- **Version**: 3.22.1
- **Size**: 492KB
- **How it works**: Injects into the page as a `<script>` tag. Self-initializes by finding WhatsApp Web's webpack modules and patching into them. Exposes `window.WPP` global with clean APIs.
- **No API key needed** — runs entirely client-side, piggybacks on the logged-in WA Web session.

### Key WPP APIs

```js
// Send text
WPP.chat.sendTextMessage(chatId, text, { createChat: true })

// Send file/image
WPP.chat.sendFileMessage(chatId, file, { type: 'image', caption: '...' })

// Check if number exists on WhatsApp
WPP.contact.queryExists('79643856156@c.us')

// Get own user ID
WPP.conn.getMyUserId()

// Readiness check
WPP.isFullReady  // boolean
```

## Popup Persistence

The popup opens as a separate Chrome window (`chrome.windows.create`) instead of the default dropdown popup. This ensures the sending loop survives clicking away — the window stays open until explicitly closed.

## CSV Parsing

Supports proper RFC 4180 CSV parsing:
- Quoted fields with commas and newlines inside
- Auto-detects delimiter (comma, tab, semicolon)
- Header row defines variable names: `Phone,Name,Company,...`
- All non-phone columns become `{{variable}}` placeholders in templates
- Dynamic chips in Compose tab update based on CSV headers

## Test CSV

See `test_contacts.csv` — 3 contacts for testing:
```
Phone,Name
79643856156,Test message 1 - Petr RU
79600722199,Test message 2 - Adele RU
436609273668,Test message 3 - Austria
```

Template: `hi {{name}}` → sends personalized messages to each contact.

## Reverse-Engineered From

"Free WhatsApp Bulk Sender" (Chrome Web Store ID: `amokpeafejimkmcjjhbehganpgidcbif`).
Key insight: the entire sending capability comes from one library (wa-js). The extension is just a UI + queue manager around it.
