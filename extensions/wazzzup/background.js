// ── Wazzzup Background Service Worker ──
// Orchestrates: navigate WA tab → inject content script → send message

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'sendMessage') {
    handleSendMessage(request.phone, request.message)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // async
  }
});

async function handleSendMessage(phone, message) {
  // 1. Find the WhatsApp Web tab
  const tabs = await chrome.tabs.query({ url: 'https://web.whatsapp.com/*' });
  if (!tabs || tabs.length === 0) {
    return { success: false, error: 'WhatsApp Web not open' };
  }

  const tab = tabs[0];

  // 2. Navigate the tab to the send URL
  const sendUrl = `https://web.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(message)}`;

  await chrome.tabs.update(tab.id, { url: sendUrl, active: true });

  // 3. Wait for the page to finish loading
  await waitForTabLoad(tab.id);

  // 4. Give WhatsApp extra time to render the chat UI
  await sleep(3000);

  // 5. Inject the content script fresh (previous one died with navigation)
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    });
  } catch (err) {
    return { success: false, error: 'Failed to inject script: ' + err.message };
  }

  // 6. Small delay for script to initialize
  await sleep(500);

  // 7. Tell the content script to click send
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { action: 'clickSend' });
    return response;
  } catch (err) {
    return { success: false, error: 'Content script error: ' + err.message };
  }
}

function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    // Set a max timeout
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 20000);

    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timeout);
        resolve();
      }
    }

    chrome.tabs.onUpdated.addListener(listener);
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
