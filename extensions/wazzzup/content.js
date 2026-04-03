// ── Wazzzup Content Script — runs on web.whatsapp.com ──
// Injects wa-js.js + inject.js into the page, bridges messages between background and inject.

// Guard against multiple injections
if (!window._wazzzupInit) {
  window._wazzzupInit = true;

  // ── Step 1: Inject wa-js.js into the page context ──
  function injectScript(file) {
    return new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = chrome.runtime.getURL(file);
      script.onload = () => { script.remove(); resolve(); };
      script.onerror = () => { script.remove(); resolve(); };
      (document.head || document.documentElement).appendChild(script);
    });
  }

  async function init() {
    // Inject wa-js library (creates window.WPP)
    await injectScript('wa-js.js');
    // Inject our message handler
    await injectScript('inject.js');

    // Poll until WPP is ready
    let ready = false;
    for (let i = 0; i < 60; i++) { // up to 30 seconds
      ready = await checkReady();
      if (ready) break;
      await sleep(500);
    }
    console.log('[Wazzzup] WPP ready:', ready);
  }

  init();

  // ── Step 2: Message bridge ──
  // Background → content script → inject.js (page context) → back
  const pendingRequests = new Map();
  let msgId = 0;

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'sendMessage') {
      sendToPage('sendMessage', request.phone, request.message)
        .then(sendResponse)
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true; // async
    }
    if (request.action === 'checkReady') {
      checkReady().then(ready => sendResponse({ ready }));
      return true;
    }
  });

  // Listen for responses from inject.js
  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data || event.data.source !== 'wazzzup-inject') return;
    const { id, success, error } = event.data;
    const pending = pendingRequests.get(id);
    if (pending) {
      pendingRequests.delete(id);
      pending.resolve({ success, error: error || null });
    }
  });

  function sendToPage(action, phone, message) {
    return new Promise((resolve, reject) => {
      const id = ++msgId;
      const timeout = setTimeout(() => {
        pendingRequests.delete(id);
        resolve({ success: false, error: 'Timeout waiting for WPP response' });
      }, 20000);

      pendingRequests.set(id, {
        resolve: (result) => { clearTimeout(timeout); resolve(result); }
      });

      window.postMessage({
        source: 'wazzzup-content',
        id,
        action,
        phone,
        message
      }, '*');
    });
  }

  function checkReady() {
    return new Promise((resolve) => {
      const id = ++msgId;
      const timeout = setTimeout(() => {
        pendingRequests.delete(id);
        resolve(false);
      }, 2000);

      pendingRequests.set(id, {
        resolve: (result) => { clearTimeout(timeout); resolve(result.success); }
      });

      window.postMessage({
        source: 'wazzzup-content',
        id,
        action: 'checkReady'
      }, '*');
    });
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
}
