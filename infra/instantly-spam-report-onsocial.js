// Fetches Instantly inbox placement test results for OnSocial and sends to Slack
// Mailboxes with deliverability < 80% are listed; passing tests get "все ящики здоровые"
//
// Usage:
//   node instantly-spam-report-onsocial.js

const API_KEY = 'OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OmlTb0RjaU5ZdVlFcQ==';
const headers = { 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' };

const TESTS = [
  { id: '019d2070-3de6-7d11-a73c-d20bc09ef3ac', name: 'Onsocial', webhook: 'https://hooks.slack.com/services/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' },
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

function getBadMailboxes(items) {
  const byEmail = {};
  for (const r of items) {
    if (!byEmail[r.sender_email]) byEmail[r.sender_email] = { total: 0, spam: 0 };
    byEmail[r.sender_email].total++;
    if (r.is_spam) byEmail[r.sender_email].spam++;
  }
  return Object.entries(byEmail)
    .filter(([, s]) => (1 - s.spam / s.total) < 0.8)
    .map(([email]) => email);
}

async function sendSlack(webhook, testId, badEmails) {
  const link = 'https://app.instantly.ai/app/inbox-placement-tests/' + testId;
  const body = badEmails.length > 0 ? badEmails.join('\n') : 'все ящики здоровые';
  const r = await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: link + '\n\n' + body }),
  });
  return r.ok;
}

(async () => {
  for (const t of TESTS) {
    const items = await getAnalytics(t.id);
    const bad = getBadMailboxes(items);
    const ok = await sendSlack(t.webhook, t.id, bad);
    const status = bad.length > 0 ? bad.length + ' ящиков < 80%' : 'все OK';
    console.log(t.name + ': ' + (ok ? 'отправлено' : 'ОШИБКА') + ' — ' + status);
  }
})();
