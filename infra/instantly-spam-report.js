// Fetches Instantly inbox placement test results and sends to Slack
// Mailboxes with deliverability < 80% are listed; passing tests get "все ящики здоровые"
//
// Usage:
//   node instantly-spam-report.js

const API_KEY = 'OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OnJoWER1SGpuakVodA==';
const headers = { 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' };

const WEBHOOKS = {
  squarefi:   'https://hooks.slack.com/services/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',
  easyglobal: 'https://hooks.slack.com/services/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',
  palark:     'https://hooks.slack.com/services/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',
  easystaff:  'https://hooks.slack.com/services/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',
  tfp:        'https://hooks.slack.com/services/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',
  onsocial:   'https://hooks.slack.com/services/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',
  rizzult:    'https://hooks.slack.com/services/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',
  inxy:       'https://hooks.slack.com/services/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',
  mifort:     'https://hooks.slack.com/services/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',
  internal:   'https://hooks.slack.com/services/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',
  paybis:     'https://hooks.slack.com/services/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',
  gwc:        'https://hooks.slack.com/services/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',
};

const TESTS = [
  { id: '019d207b-821b-7274-9ebc-3c7620530cba', name: 'GWC',       webhook: WEBHOOKS.gwc },
  { id: '019d2070-412e-7c72-a9c2-fa50e1669917', name: 'Rizzult',   webhook: WEBHOOKS.rizzult },
  { id: '019d2070-3de6-7d11-a73c-d20bc09ef3ac', name: 'Onsocial',  webhook: WEBHOOKS.onsocial },
  { id: '019d2070-3b79-79c1-a42f-6cb435fd8138', name: 'Paybis',    webhook: WEBHOOKS.paybis },
  { id: '019d2070-3830-7a4d-ad00-2741c8ff7321', name: 'Delyrio',   webhook: WEBHOOKS.easystaff },
  { id: '019d2070-3516-73f7-b589-0725857ea7c4', name: 'Easystaff', webhook: WEBHOOKS.easystaff },
  { id: '019d2070-328e-757e-a790-146457464dac', name: 'TFP',        webhook: WEBHOOKS.tfp },
  { id: '019d2070-2f8a-7ae2-ac83-4f0f334ab206', name: 'Maincard',  webhook: WEBHOOKS.easystaff },
  { id: '019d2070-2c1a-7c32-968f-32fbbdc8702b', name: 'Internal',  webhook: WEBHOOKS.internal },
  { id: '019d2070-28c1-740d-b399-26de9675adad', name: 'EasyGlobal', webhook: WEBHOOKS.easyglobal },
  { id: '019d2070-2558-787b-9f10-d0469402b766', name: 'Squarefi',  webhook: WEBHOOKS.squarefi },
  { id: '019d2070-2247-71bd-92cc-9ffea3e4245e', name: 'Inxy',      webhook: WEBHOOKS.inxy },
  { id: '019d2070-1ed8-7a6c-93f0-6c71f30991c8', name: 'Palark',    webhook: WEBHOOKS.palark },
  { id: '019d206f-d362-716e-9f50-07643f729bda', name: 'Mifort',    webhook: WEBHOOKS.mifort },
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
