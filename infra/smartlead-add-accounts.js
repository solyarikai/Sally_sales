// Adds 50 Google Workspace mailboxes to Smartlead
// petr@ and rinat@ on all 25 crona domains
// Usage: node smartlead-add-accounts.js --domains-file crona-domains.txt

const fs = require('fs');
const path = require('path');

const API_KEY = 'eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5';
const BASE    = 'https://server.smartlead.ai/api/v1';

const args = process.argv.slice(2);
const getArg = n => { const i = args.indexOf('--' + n); return i !== -1 ? args[i + 1] : null; };
const domainsFile = getArg('domains-file');
if (!domainsFile) { console.error('Usage: node smartlead-add-accounts.js --domains-file domains.txt'); process.exit(1); }

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log(`Domains: ${domains.length}, accounts to add: ${domains.length * 2}\n`);

const PASSWORD = 'SallySuper777';

const USERS = [
  { login: 'petr',  name: 'Petr Petrov' },
  { login: 'rinat', name: 'Rinat Khatipov' },
];

async function addAccount(email, name) {
  const res = await fetch(`${BASE}/email-accounts/save?api_key=${API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from_name:      name,
      from_email:     email,
      user_name:      email,
      password:       PASSWORD,
      smtp_host: 'smtp.gmail.com',
      smtp_port: 587,
      imap_host: 'imap.gmail.com',
      imap_port: 993,
      max_email_per_day: 30,
      warmup_enabled: true,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || data.error || res.status);
  return data;
}

(async () => {
  const results = { added: [], failed: [] };

  for (const domain of domains) {
    for (const user of USERS) {
      const email = `${user.login}@${domain}`;
      process.stdout.write(`${email} ... `);
      try {
        const data = await addAccount(email, user.name);
        const id = data.id || data.email_account_id || '?';
        console.log(`OK (id: ${id})`);
        results.added.push({ email, id });
      } catch (e) {
        console.log(`FAIL: ${e.message}`);
        results.failed.push({ email, error: e.message });
      }
      await new Promise(r => setTimeout(r, 300));
    }
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`Added:  ${results.added.length}`);
  console.log(`Failed: ${results.failed.length}`);
  if (results.failed.length) results.failed.forEach(f => console.log(`  - ${f.email}: ${f.error}`));
})();
