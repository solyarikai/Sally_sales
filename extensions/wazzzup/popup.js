// ── State ──────────────────────────────────────────
let contacts = [];
let templates = {};
let sendLog = [];
let sending = false;
let paused = false;
let stopRequested = false;
let countdownInterval = null;

// ── DOM refs ──────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

// ── Init ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initTabs();
  initCompose();
  initContacts();
  initSend();
  initLog();
  await loadState();
  checkWhatsAppStatus();
});

// ── Tabs ──────────────────────────────────────────
function initTabs() {
  $$('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.tab').forEach(t => t.classList.remove('active'));
      $$('.tab-content').forEach(tc => tc.classList.remove('active'));
      tab.classList.add('active');
      $(`#tab-${tab.dataset.tab}`).classList.add('active');
      if (tab.dataset.tab === 'send') updateSendSummary();
    });
  });
}

// ── Compose Tab ───────────────────────────────────
function initCompose() {
  const tpl = $('#template');
  const charCount = $('#char-count');

  tpl.addEventListener('input', () => {
    charCount.textContent = tpl.value.length;
    updatePreview();
    saveState();
  });

  // Variable chips
  $$('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const v = chip.dataset.var;
      const start = tpl.selectionStart;
      const end = tpl.selectionEnd;
      tpl.value = tpl.value.slice(0, start) + v + tpl.value.slice(end);
      tpl.selectionStart = tpl.selectionEnd = start + v.length;
      tpl.focus();
      tpl.dispatchEvent(new Event('input'));
    });
  });

  // Save template
  $('#save-template').addEventListener('click', () => {
    const name = $('#template-name').value.trim();
    const body = tpl.value.trim();
    if (!name || !body) return;
    templates[name] = body;
    $('#template-name').value = '';
    renderSavedTemplates();
    saveState();
  });
}

function updatePreview() {
  const tpl = $('#template').value;
  const preview = $('#preview');
  if (!tpl.trim()) {
    preview.innerHTML = '<span class="preview-placeholder">Type a message above to see preview</span>';
    return;
  }
  const sample = { name: 'John', company: 'Acme Inc', custom1: 'VIP' };
  let msg = tpl;
  for (const [k, v] of Object.entries(sample)) {
    msg = msg.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
  }
  preview.textContent = msg;
}

function renderSavedTemplates() {
  const wrap = $('#saved-templates');
  wrap.innerHTML = '';
  for (const [name, body] of Object.entries(templates)) {
    const item = document.createElement('div');
    item.className = 'saved-item';
    item.innerHTML = `
      <span class="saved-item-name">${esc(name)}</span>
      <button class="saved-item-del" data-name="${esc(name)}">&times;</button>
    `;
    item.addEventListener('click', (e) => {
      if (e.target.classList.contains('saved-item-del')) {
        delete templates[e.target.dataset.name];
        renderSavedTemplates();
        saveState();
        return;
      }
      $('#template').value = body;
      $('#template').dispatchEvent(new Event('input'));
    });
    wrap.appendChild(item);
  }
}

// ── Contacts Tab ──────────────────────────────────
function initContacts() {
  const numbersEl = $('#numbers');

  numbersEl.addEventListener('input', () => {
    parseContacts();
    saveState();
  });

  $('#paste-clipboard').addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      numbersEl.value = (numbersEl.value ? numbersEl.value + '\n' : '') + text;
      numbersEl.dispatchEvent(new Event('input'));
    } catch (e) { /* clipboard denied */ }
  });

  $('#clear-numbers').addEventListener('click', () => {
    numbersEl.value = '';
    contacts = [];
    renderContactsTable();
    saveState();
  });

  // File import
  const dropZone = $('#drop-zone');
  const fileInput = $('#file-input');

  $('#browse-btn').addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) readFile(e.target.files[0]);
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) readFile(e.dataTransfer.files[0]);
  });

  $('#select-all').addEventListener('change', (e) => {
    contacts.forEach(c => c.selected = e.target.checked);
    renderContactsTable();
  });
}

function readFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const existing = $('#numbers').value;
    $('#numbers').value = (existing ? existing + '\n' : '') + e.target.result;
    parseContacts();
    saveState();
  };
  reader.readAsText(file);
}

function parseContacts() {
  const raw = $('#numbers').value.trim();
  if (!raw) { contacts = []; renderContactsTable(); return; }

  const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
  contacts = [];

  for (const line of lines) {
    if (/^(phone|number|tel)/i.test(line)) continue;

    const parts = line.split(/[,\t;]/).map(p => p.trim());
    let phone = parts[0] || '';

    phone = phone.replace(/[^\d+]/g, '');
    if (!phone || phone.length < 7) continue;
    if (!phone.startsWith('+')) phone = '+' + phone;

    contacts.push({
      phone,
      name: parts[1] || '',
      company: parts[2] || '',
      selected: true
    });
  }

  // Dedupe by phone
  const seen = new Set();
  contacts = contacts.filter(c => {
    if (seen.has(c.phone)) return false;
    seen.add(c.phone);
    return true;
  });

  renderContactsTable();
}

function renderContactsTable() {
  const body = $('#contacts-body');
  const noContacts = $('#no-contacts');
  const countEl = $('#contact-count');

  const selected = contacts.filter(c => c.selected);
  countEl.textContent = `${selected.length} / ${contacts.length} contacts`;

  if (contacts.length === 0) {
    body.innerHTML = '';
    noContacts.style.display = 'block';
    return;
  }

  noContacts.style.display = 'none';
  body.innerHTML = contacts.map((c, i) => `
    <tr>
      <td><input type="checkbox" data-idx="${i}" ${c.selected ? 'checked' : ''}></td>
      <td>${esc(c.phone)}</td>
      <td>${esc(c.name) || '<span style="color:var(--text-muted)">\u2014</span>'}</td>
      <td>${esc(c.company) || '<span style="color:var(--text-muted)">\u2014</span>'}</td>
      <td><button class="row-del" data-idx="${i}">&times;</button></td>
    </tr>
  `).join('');

  body.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', (e) => {
      contacts[+e.target.dataset.idx].selected = e.target.checked;
      renderContactsTable();
    });
  });

  body.querySelectorAll('.row-del').forEach(btn => {
    btn.addEventListener('click', (e) => {
      contacts.splice(+e.target.dataset.idx, 1);
      renderContactsTable();
      saveState();
    });
  });
}

// ── Send Tab ──────────────────────────────────────
function initSend() {
  // Update schedule preview on any config change
  const configInputs = ['#delay-min', '#delay-max', '#batch-size', '#batch-break', '#daily-limit', '#work-start', '#work-end'];
  configInputs.forEach(sel => {
    $(sel).addEventListener('input', () => {
      updateSchedulePreview();
      saveState();
    });
  });

  $('#daily-limit').addEventListener('input', () => {
    $('#daily-limit-display').textContent = $('#daily-limit').value;
  });

  $('#respect-hours').addEventListener('change', () => {
    updateSchedulePreview();
    saveState();
  });

  $('#start-btn').addEventListener('click', startSending);
  $('#stop-btn').addEventListener('click', () => { stopRequested = true; });
  $('#pause-btn').addEventListener('click', () => {
    paused = !paused;
    $('#pause-btn').textContent = paused ? 'Resume' : 'Pause';
  });

  updateSchedulePreview();
  updateDailySentCount();
}

function getConfig() {
  return {
    delayMin: Math.max(1, +$('#delay-min').value) * 60, // seconds
    delayMax: Math.max(1, +$('#delay-max').value) * 60,
    batchSize: Math.max(1, +$('#batch-size').value),
    batchBreak: Math.max(1, +$('#batch-break').value) * 60, // seconds
    dailyLimit: Math.max(1, +$('#daily-limit').value),
    workStart: +$('#work-start').value,
    workEnd: +$('#work-end').value,
    respectHours: $('#respect-hours').checked
  };
}

function randomDelay(minSec, maxSec) {
  // Ensure min < max
  if (minSec > maxSec) [minSec, maxSec] = [maxSec, minSec];
  return minSec + Math.random() * (maxSec - minSec);
}

function isWithinWorkingHours(config) {
  if (!config.respectHours) return true;
  const now = new Date();
  const hour = now.getHours();
  return hour >= config.workStart && hour < config.workEnd;
}

function getTodayKey() {
  return new Date().toISOString().slice(0, 10);
}

function getTodaySentCount() {
  const today = getTodayKey();
  return sendLog.filter(e => e.date === today && e.status === 'sent').length;
}

function updateDailySentCount() {
  const count = getTodaySentCount();
  $('#daily-sent').textContent = count;
  $('#daily-limit-display').textContent = $('#daily-limit').value;
}

function updateSchedulePreview() {
  const cfg = getConfig();
  const selected = contacts.filter(c => c.selected).length;
  const preview = $('#schedule-preview');

  if (selected === 0) {
    preview.innerHTML = '<p class="empty-state">Add contacts to see schedule</p>';
    return;
  }

  const dailyLimit = cfg.dailyLimit;
  const toSend = Math.min(selected, dailyLimit - getTodaySentCount());

  if (toSend <= 0) {
    preview.innerHTML = '<p class="empty-state">Daily limit reached. Resumes tomorrow.</p>';
    return;
  }

  const batches = Math.ceil(toSend / cfg.batchSize);
  const avgDelay = (cfg.delayMin + cfg.delayMax) / 2;
  const batchTime = (cfg.batchSize - 1) * avgDelay; // time within batch
  const totalTime = batches * batchTime + (batches - 1) * cfg.batchBreak;

  let lines = [];
  lines.push(`<div class="schedule-line"><span class="schedule-batch">${toSend} messages in ${batches} batch${batches > 1 ? 'es' : ''}</span></div>`);
  lines.push(`<div class="schedule-line"><span>${cfg.batchSize} msg/batch, ${cfg.delayMin/60}-${cfg.delayMax/60} min gaps</span></div>`);

  if (batches > 1) {
    lines.push(`<div class="schedule-line"><span>${cfg.batchBreak/60} min break between batches</span></div>`);
  }

  const hours = Math.floor(totalTime / 3600);
  const mins = Math.round((totalTime % 3600) / 60);
  const eta = hours > 0 ? `~${hours}h ${mins}m total` : `~${mins}m total`;
  lines.push(`<div class="schedule-line"><span class="schedule-time">${eta}</span></div>`);

  if (selected > dailyLimit) {
    const days = Math.ceil(selected / dailyLimit);
    lines.push(`<div class="schedule-line"><span class="schedule-time">${selected} contacts = ~${days} days at ${dailyLimit}/day</span></div>`);
  }

  preview.innerHTML = lines.join('');
}

function updateSendSummary() {
  const selected = contacts.filter(c => c.selected);
  $('#summary-contacts').textContent = selected.length;
  const tpl = $('#template').value.trim();
  $('#summary-template').textContent = tpl ? (tpl.length > 20 ? tpl.slice(0, 20) + '...' : tpl) : '--';

  updateSchedulePreview();
  updateDailySentCount();

  const canSend = selected.length > 0 && tpl;
  const btn = $('#start-btn');

  chrome.tabs.query({ url: 'https://web.whatsapp.com/*' }, (tabs) => {
    const onWA = tabs && tabs.length > 0;
    if (!canSend) {
      btn.disabled = true;
      btn.textContent = selected.length === 0 ? 'Add contacts first' : 'Write a message first';
    } else if (!onWA) {
      btn.disabled = true;
      btn.textContent = 'Open WhatsApp Web first';
    } else {
      btn.disabled = false;
      const remaining = Math.min(selected.length, getConfig().dailyLimit - getTodaySentCount());
      btn.textContent = remaining > 0 ? `Send to ${remaining} contacts today` : 'Daily limit reached';
      btn.disabled = remaining <= 0;
    }
  });
}

function showCountdown(seconds, label) {
  const nextAction = $('#next-action');
  nextAction.style.display = 'block';
  clearInterval(countdownInterval);

  let remaining = Math.round(seconds);

  const render = () => {
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    const timeStr = m > 0 ? `${m}m ${s}s` : `${s}s`;
    nextAction.innerHTML = `${label} <span class="countdown">${timeStr}</span>`;
  };

  render();
  countdownInterval = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(countdownInterval);
      nextAction.style.display = 'none';
    } else {
      render();
    }
  }, 1000);
}

async function startSending() {
  const selected = contacts.filter(c => c.selected);
  const tpl = $('#template').value.trim();
  if (!selected.length || !tpl) return;

  const cfg = getConfig();
  sending = true;
  paused = false;
  stopRequested = false;

  $('#start-btn').style.display = 'none';
  $('#stop-btn').style.display = 'block';
  $('#pause-btn').style.display = 'block';
  $('#progress-section').style.display = 'block';

  let sent = 0;
  let batchCount = 0;
  const todaySent = getTodaySentCount();
  const todayLimit = cfg.dailyLimit - todaySent;
  const total = Math.min(selected.length, todayLimit);

  for (let i = 0; i < selected.length; i++) {
    if (stopRequested) break;

    // Check daily limit
    if (getTodaySentCount() >= cfg.dailyLimit) {
      showCountdown(0, 'Daily limit reached. Stopping.');
      break;
    }

    // Check working hours
    if (cfg.respectHours && !isWithinWorkingHours(cfg)) {
      // Calculate seconds until work start
      const now = new Date();
      let nextStart = new Date(now);
      nextStart.setHours(cfg.workStart, 0, 0, 0);
      if (nextStart <= now) nextStart.setDate(nextStart.getDate() + 1);
      const waitSec = (nextStart - now) / 1000;

      showCountdown(waitSec, 'Outside working hours. Resuming in');

      while (!isWithinWorkingHours(cfg) && !stopRequested) {
        await sleep(10000); // check every 10s
      }
      if (stopRequested) break;
    }

    // Pause support
    while (paused && !stopRequested) {
      await sleep(500);
    }
    if (stopRequested) break;

    // Update progress
    const pct = Math.round((sent / total) * 100);
    $('#progress-bar').style.width = pct + '%';
    $('#progress-text').textContent = `${sent} / ${total}`;

    // Build personalized message (support both {var} and {{var}})
    const contact = selected[i];
    let msg = tpl;
    const vars = { name: contact.name || '', company: contact.company || '', custom1: contact.custom1 || '' };
    for (const [k, v] of Object.entries(vars)) {
      msg = msg.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
      msg = msg.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    }
    msg = msg.trim();

    // Send via content script
    const result = await sendMessage(contact.phone, msg);

    const entry = {
      phone: contact.phone,
      name: contact.name,
      message: msg,
      status: result.success ? 'sent' : 'failed',
      error: result.error || null,
      time: new Date().toLocaleTimeString(),
      date: getTodayKey()
    };
    sendLog.unshift(entry);
    renderLog();
    updateDailySentCount();
    saveState();

    sent++;
    batchCount++;

    // Check if we've completed a batch
    if (batchCount >= cfg.batchSize && sent < total && !stopRequested) {
      batchCount = 0;

      // Batch break with ±15% randomization
      const breakBase = cfg.batchBreak;
      const breakJitter = breakBase * 0.15;
      const breakDelay = breakBase + (Math.random() * 2 - 1) * breakJitter;

      showCountdown(breakDelay, 'Batch done. Next batch in');
      await sleepInterruptible(breakDelay * 1000);

      if (stopRequested) break;
    } else if (sent < total && !stopRequested) {
      // Normal inter-message delay (random within range)
      const delay = randomDelay(cfg.delayMin, cfg.delayMax);

      showCountdown(delay, 'Next message in');
      await sleepInterruptible(delay * 1000);
    }
  }

  // Done
  $('#progress-bar').style.width = '100%';
  $('#progress-text').textContent = `${sent} / ${total}`;
  clearInterval(countdownInterval);
  const nextAction = $('#next-action');
  nextAction.style.display = 'block';
  nextAction.innerHTML = stopRequested ? 'Stopped by user' : `Done! ${sent} messages sent today`;

  sending = false;
  $('#start-btn').style.display = 'block';
  $('#stop-btn').style.display = 'none';
  $('#pause-btn').style.display = 'none';
  $('#start-btn').textContent = 'Done! Send again?';
  $('#start-btn').disabled = false;
}

async function sleepInterruptible(ms) {
  const interval = 500;
  let elapsed = 0;
  while (elapsed < ms) {
    if (stopRequested) return;
    while (paused && !stopRequested) {
      await sleep(500);
    }
    if (stopRequested) return;
    await sleep(Math.min(interval, ms - elapsed));
    elapsed += interval;
  }
}

async function sendMessage(phone, message) {
  return new Promise((resolve) => {
    // Send to background service worker which handles navigation + injection
    chrome.runtime.sendMessage({
      action: 'sendMessage',
      phone: phone.replace('+', ''),
      message
    }, (response) => {
      if (chrome.runtime.lastError) {
        resolve({ success: false, error: chrome.runtime.lastError.message });
      } else {
        resolve(response || { success: false, error: 'No response' });
      }
    });
  });
}

// ── Log Tab ───────────────────────────────────────
function initLog() {
  $('#export-log').addEventListener('click', exportLog);
  $('#clear-log').addEventListener('click', () => {
    sendLog = [];
    renderLog();
    saveState();
  });
}

function renderLog() {
  const list = $('#log-list');
  const stats = {
    sent: sendLog.length,
    success: sendLog.filter(e => e.status === 'sent').length,
    failed: sendLog.filter(e => e.status === 'failed').length
  };

  $('#stat-sent').textContent = stats.sent;
  $('#stat-success').textContent = stats.success;
  $('#stat-failed').textContent = stats.failed;

  if (sendLog.length === 0) {
    list.innerHTML = '<p class="empty-state">No messages sent yet</p>';
    return;
  }

  list.innerHTML = sendLog.slice(0, 100).map(e => `
    <div class="log-entry-wrap">
      <div class="log-entry">
        <span class="log-icon">${e.status === 'sent' ? '\u2713' : '\u2717'}</span>
        <span class="log-phone">${esc(e.phone)}</span>
        <span class="log-time">${esc(e.name || '')}</span>
        <span class="log-status ${e.status === 'sent' ? 'log-status--ok' : 'log-status--fail'}">
          ${e.status === 'sent' ? 'Sent' : esc(e.error || 'Failed')}
        </span>
        <span class="log-time">${e.time}</span>
      </div>
      ${e.message ? `<div class="log-message">${esc(e.message.length > 80 ? e.message.slice(0, 80) + '...' : e.message)}</div>` : ''}
    </div>
  `).join('');
}

function exportLog() {
  if (sendLog.length === 0) return;
  const csv = 'phone,name,status,error,time,date,message\n' +
    sendLog.map(e =>
      `${e.phone},${csvEsc(e.name)},${e.status},${csvEsc(e.error || '')},${e.time},${e.date || ''},${csvEsc(e.message || '')}`
    ).join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `wazzzup-log-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── WhatsApp Status Check ─────────────────────────
function checkWhatsAppStatus() {
  chrome.tabs.query({ url: 'https://web.whatsapp.com/*' }, (tabs) => {
    const status = $('#wa-status');
    const text = status.querySelector('.status-text');
    if (tabs && tabs.length > 0) {
      status.classList.remove('status--disconnected');
      status.classList.add('status--connected');
      text.textContent = 'Connected';
    } else {
      status.classList.remove('status--connected');
      status.classList.add('status--disconnected');
      text.textContent = 'Not on WhatsApp';
    }
  });
}

// ── Persistence ───────────────────────────────────
async function saveState() {
  const state = {
    template: $('#template').value,
    numbers: $('#numbers').value,
    templates,
    sendLog: sendLog.slice(0, 500),
    delayMin: $('#delay-min').value,
    delayMax: $('#delay-max').value,
    batchSize: $('#batch-size').value,
    batchBreak: $('#batch-break').value,
    dailyLimit: $('#daily-limit').value,
    workStart: $('#work-start').value,
    workEnd: $('#work-end').value,
    respectHours: $('#respect-hours').checked
  };
  chrome.storage.local.set({ wazzzupState: state });
}

async function loadState() {
  return new Promise((resolve) => {
    chrome.storage.local.get('wazzzupState', (data) => {
      if (data.wazzzupState) {
        const s = data.wazzzupState;
        if (s.template) { $('#template').value = s.template; $('#template').dispatchEvent(new Event('input')); }
        if (s.numbers) { $('#numbers').value = s.numbers; parseContacts(); }
        if (s.templates) { templates = s.templates; renderSavedTemplates(); }
        if (s.sendLog) { sendLog = s.sendLog; renderLog(); }
        if (s.delayMin) $('#delay-min').value = s.delayMin;
        if (s.delayMax) $('#delay-max').value = s.delayMax;
        if (s.batchSize) $('#batch-size').value = s.batchSize;
        if (s.batchBreak) $('#batch-break').value = s.batchBreak;
        if (s.dailyLimit) { $('#daily-limit').value = s.dailyLimit; $('#daily-limit-display').textContent = s.dailyLimit; }
        if (s.workStart) $('#work-start').value = s.workStart;
        if (s.workEnd) $('#work-end').value = s.workEnd;
        if (s.respectHours !== undefined) $('#respect-hours').checked = s.respectHours;
      }
      updateDailySentCount();
      updateSchedulePreview();
      resolve();
    });
  });
}

// ── Helpers ───────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function csvEsc(s) {
  if (!s) return '';
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}
