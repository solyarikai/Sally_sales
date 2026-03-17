// ── Wazzzup Inject Script ──
// Runs in the PAGE context (not content script) — has access to window.WPP
// Communicates with content.js via window.postMessage

window.addEventListener('message', async (event) => {
  if (event.source !== window || !event.data || event.data.source !== 'wazzzup-content') return;

  const { id, action, phone, message } = event.data;

  if (action === 'checkReady') {
    const ready = !!(window.WPP && window.WPP.isFullReady);
    window.postMessage({ source: 'wazzzup-inject', id, success: ready }, '*');
    return;
  }

  if (action === 'sendMessage') {
    try {
      let receiver = `${phone}@c.us`;

      // Handle LID migration (newer WhatsApp accounts)
      try {
        const migrationState = window.WPP.conn.getMigrationState();
        if (migrationState && migrationState.isLidMigrated && !receiver.includes('@lid')) {
          const chatBaseInfo = await window.WPP.contact.queryExists(receiver);
          if (chatBaseInfo && chatBaseInfo.lid) {
            receiver = chatBaseInfo.lid._serialized || receiver;
          }
        }
      } catch (e) { /* older WA versions without LID — ignore */ }

      await window.WPP.chat.sendTextMessage(receiver, message, {
        createChat: true,
        linkPreview: false
      });

      window.postMessage({ source: 'wazzzup-inject', id, success: true }, '*');
    } catch (err) {
      window.postMessage({ source: 'wazzzup-inject', id, success: false, error: err.message || String(err) }, '*');
    }
    return;
  }
});
