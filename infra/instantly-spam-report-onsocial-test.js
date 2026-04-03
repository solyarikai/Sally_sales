// Test script for OnSocial Instantly spam report
// Checks: 1) Instantly API key works, 2) Slack webhook accepts messages

const API_KEY = 'OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OmlTb0RjaU5ZdVlFcQ==';
const TEST_ID = '019d2070-3de6-7d11-a73c-d20bc09ef3ac';
const SLACK_WEBHOOK = 'https://hooks.slack.com/services/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';
const headers = { 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' };

async function testInstantly() {
  const url = 'https://api.instantly.ai/api/v2/inbox-placement-analytics?test_id=' + TEST_ID + '&limit=1';
  const r = await fetch(url, { headers });
  if (r.ok) {
    console.log('[OK] Instantly API — ключ работает, статус ' + r.status);
  } else {
    const body = await r.text();
    console.log('[FAIL] Instantly API — статус ' + r.status + ': ' + body);
  }
}

async function testSlack() {
  const r = await fetch(SLACK_WEBHOOK, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: '[TEST] OnSocial spam report — проверка подключения' }),
  });
  if (r.ok) {
    console.log('[OK] Slack webhook — сообщение отправлено');
  } else {
    console.log('[FAIL] Slack webhook — статус ' + r.status);
  }
}

(async () => {
  await testInstantly();
  await testSlack();
})();
