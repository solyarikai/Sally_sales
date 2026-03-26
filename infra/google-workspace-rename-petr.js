// Renames all petr@* users from "Petr Petrov" → "Petr Nikolaev" across all domains in a file
// Usage: node google-workspace-rename-petr.js --domains-file crona-domains.txt

const fs = require('fs');
const path = require('path');
const { google } = require('googleapis');

const TOKEN_FILE       = path.join(__dirname, 'google-oauth-token.json');
const CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');

const args = process.argv.slice(2);
const getArg = n => { const i = args.indexOf('--' + n); return i !== -1 ? args[i + 1] : null; };
const domainsFile = getArg('domains-file');
if (!domainsFile) {
  console.error('Usage: node google-workspace-rename-petr.js --domains-file domains.txt');
  process.exit(1);
}

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log(`Domains: ${domains.length}, users to rename: ${domains.length}\n`);

async function getAuthClient() {
  const creds = JSON.parse(fs.readFileSync(CREDENTIALS_FILE));
  const { client_id, client_secret } = creds.installed;
  const auth = new google.auth.OAuth2(client_id, client_secret, 'http://localhost:3000');
  auth.setCredentials(JSON.parse(fs.readFileSync(TOKEN_FILE)));
  return auth;
}

(async () => {
  const auth = await getAuthClient();
  const adminDir = google.admin({ version: 'directory_v1', auth });

  const results = { updated: [], notFound: [], failed: [] };

  for (const domain of domains) {
    const email = `petr@${domain}`;
    process.stdout.write(`${email} ... `);

    try {
      await adminDir.users.update({
        userKey: email,
        requestBody: {
          name: { givenName: 'Petr', familyName: 'Nikolaev' },
        },
      });
      console.log('updated');
      results.updated.push(email);
    } catch (e) {
      const msg = e.response?.data?.error?.message || e.message;
      if (e.response?.status === 404) {
        console.log('not found');
        results.notFound.push(email);
      } else {
        console.log('FAILED:', msg);
        results.failed.push({ email, error: msg });
      }
    }

    await new Promise(r => setTimeout(r, 300));
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`Updated:   ${results.updated.length}`);
  console.log(`Not found: ${results.notFound.length}`);
  console.log(`Failed:    ${results.failed.length}`);
  if (results.failed.length) results.failed.forEach(f => console.log(`  - ${f.email}: ${f.error}`));
})();
