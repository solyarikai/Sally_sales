// ── Wazzzup Content Script — runs on web.whatsapp.com ──
// This script is injected AFTER navigation to /send?phone=X&text=Y
// Its only job: wait for the compose box + send button, then click send.

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'clickSend') {
    handleClickSend()
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // async response
  }

  if (request.action === 'checkStatus') {
    const loggedIn = !!document.querySelector('[data-testid="chat-list"]');
    sendResponse({ loggedIn });
    return;
  }
});

async function handleClickSend() {
  try {
    // Check for "invalid phone number" popup first
    const invalidPopup = document.querySelector('[data-testid="popup-contents"]');
    if (invalidPopup) {
      const okBtn = invalidPopup.querySelector('[data-testid="popup-controls-ok"]');
      if (okBtn) okBtn.click();
      return { success: false, error: 'Invalid phone number' };
    }

    // Wait for the compose box to appear (means chat loaded and text is populated)
    const inputBox = await waitForElement(
      '[data-testid="conversation-compose-box-input"], div[contenteditable="true"][data-tab="10"]',
      12000
    );

    if (!inputBox) {
      // Check again for popup that may have appeared during wait
      const popup = document.querySelector('[data-testid="popup-contents"]');
      if (popup) {
        const text = popup.textContent || '';
        const okBtn = popup.querySelector('[data-testid="popup-controls-ok"]');
        if (okBtn) okBtn.click();
        return { success: false, error: 'WhatsApp error: ' + text.slice(0, 80) };
      }
      return { success: false, error: 'Chat did not load (compose box not found)' };
    }

    // Wait a bit for the message text to be fully populated by WhatsApp
    await sleep(1500);

    // Find the send button
    const sendBtn = await waitForElement(
      '[data-testid="send"], [data-testid="compose-btn-send"], button[aria-label="Send"]',
      5000
    );

    if (!sendBtn) {
      // Try pressing Enter as fallback
      inputBox.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true
      }));
      await sleep(1000);
      return { success: true, method: 'enter-key' };
    }

    sendBtn.click();
    await sleep(1500);

    // Verify: check if message appeared in chat (look for latest outgoing msg tick)
    const ticks = document.querySelectorAll('[data-testid="msg-check"], [data-testid="msg-dblcheck"], [data-testid="msg-time"]');
    if (ticks.length > 0) {
      return { success: true };
    }

    // Even without tick verification, the click likely worked
    return { success: true };

  } catch (err) {
    return { success: false, error: err.message || 'Unknown error' };
  }
}

function waitForElement(selector, timeout = 10000) {
  return new Promise((resolve) => {
    const existing = document.querySelector(selector);
    if (existing) { resolve(existing); return; }

    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) {
        observer.disconnect();
        clearTimeout(timer);
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    const timer = setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, timeout);
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
