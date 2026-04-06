// Fetches Instantly inbox placement test results for OnSocial and sends to Slack
// Mailboxes with deliverability < 80% are listed; passing tests get "все ящики здоровые"
//
// Usage:
//   node instantly-spam-report-onsocial.js

const API_KEY = 'OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OmlTb0RjaU5ZdVlFcQ==';
const headers = { 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' };

const TESTS = [
  { id: '019d61f5-fbab-721d-99f6-31b3b76592ad', name: 'Onsocial', webhook: 'https://hooks.slack.com/services/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' },
];

async function getAnalytics(testId) {
  let items = [], next = null;
  do {
    const url = 'https://api.instantly.ai/api/v2/inbox-placement-analytics?test_id=' + testId + '&limit=100' + (next ? '&starting_after=' + next : '');
    const d = await fetch(url, { headers }).then(r => r.json());
    items.push(...(d.items || []));
    next = d.next_starting_after;
  } while (next);
  return items;
}

function getMailboxStats(items) {
  const byEmail = {};
  for (const r of items) {
    if (!byEmail[r.sender_email]) byEmail[r.sender_email] = { total: 0, spam: 0 };
    byEmail[r.sender_email].total++;
    if (r.is_spam) byEmail[r.sender_email].spam++;
  }
  return Object.entries(byEmail).map(([email, s]) => ({
    email,
    deliverability: Math.round((1 - s.spam / s.total) * 100),
  }));
}

async function sendSlack(webhook, testId, stats) {
  const date = new Date().toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const link = 'https://app.instantly.ai/app/inbox-placement-tests/' + testId;
  const total = stats.length;
  const bad = stats.filter(s => s.deliverability < 80);
  const good = stats.filter(s => s.deliverability >= 80);

  let text = '*OnSocial - Inbox Placement Report*\n' + date + '\n\n';

  if (bad.length > 0) {
    text += ':warning: *Проблемные ящики (' + bad.length + ' из ' + total + '):*\n';
    for (const s of bad.sort((a, b) => a.deliverability - b.deliverability)) {
      text += '  ' + s.email + ' - ' + s.deliverability + '%\n';
    }
  }

  const warn = good.filter(s => s.deliverability < 100);
  if (warn.length > 0) {
    text += '\n:eyes: *Ящики < 100% (но выше 80%):*\n';
    for (const s of warn.sort((a, b) => a.deliverability - b.deliverability)) {
      text += '  ' + s.email + ' - ' + s.deliverability + '%\n';
    }
  }

  const perfect = good.filter(s => s.deliverability === 100);
  if (perfect.length > 0) {
    text += '\n:white_check_mark: Здоровые ящики: ' + perfect.length + ' из ' + total + '\n';
  }

  if (total === 0) {
    text += 'Нет данных по ящикам\n';
  }

  text += '\n<' + link + '|Открыть в Instantly>';

  const r = await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  return r.ok;
}

(async () => {
  for (const t of TESTS) {
    const items = await getAnalytics(t.id);
    const stats = getMailboxStats(items);
    const bad = stats.filter(s => s.deliverability < 80);
    const ok = await sendSlack(t.webhook, t.id, stats);
    const status = bad.length > 0 ? bad.length + ' ящиков < 80%' : 'все OK';
    console.log(t.name + ': ' + (ok ? 'отправлено' : 'ОШИБКА') + ' — ' + status);
  }
})();
