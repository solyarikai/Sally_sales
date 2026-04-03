// ── Wazzzup Background Service Worker ──
// Opens popup as persistent window, routes messages to content script on WA tab.
// No URL navigation — wa-js handles everything via WhatsApp's internal API.

// ── Popup as persistent window ──
chrome.action.onClicked.addListener(async () => {
  const windows = await chrome.windows.getAll({ populate: true });
  for (const win of windows) {
    if (win.type === 'popup' && win.tabs?.some(t => t.url?.includes('popup.html'))) {
      await chrome.windows.update(win.id, { focused: true });
      return;
    }
  }
  await chrome.windows.create({
    url: 'popup.html',
    type: 'popup',
    width: 400,
    height: 650
  });
});

// ── Message routing: popup → background → content script on WA tab ──
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'sendMessage') {
    routeToWhatsApp(request)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

async function routeToWhatsApp(request) {
  const tabs = await chrome.tabs.query({ url: 'https://web.whatsapp.com/*' });
  if (!tabs || tabs.length === 0) {
    return { success: false, error: 'WhatsApp Web not open' };
  }

  try {
    const response = await chrome.tabs.sendMessage(tabs[0].id, {
      action: 'sendMessage',
      phone: request.phone,
      message: request.message
    });
    return response;
  } catch (err) {
    return { success: false, error: 'Content script not ready: ' + err.message };
  }
}
