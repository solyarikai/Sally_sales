// Generates backup verification codes for all users in a domains file
// Usage: node google-workspace-backup-codes.js --domains-file crona-domains.txt [--out backup-codes.csv]

const fs = require('fs');
const path = require('path');
const { google } = require('googleapis');

const TOKEN_FILE       = path.join(__dirname, 'google-oauth-token.json');
const CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');

const args = process.argv.slice(2);
const getArg = n => { const i = args.indexOf('--' + n); return i !== -1 ? args[i + 1] : null; };

const domainsFile = getArg('domains-file');
if (!domainsFile) {
  console.error('Usage: node google-workspace-backup-codes.js --domains-file domains.txt [--out backup-codes.csv]');
  process.exit(1);
}

const outFile = getArg('out') || domainsFile.replace(/\.txt$/, '') + '-backup-codes.csv';
const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
const USERS   = ['petr', 'rinat'];

console.log(`Domains: ${domains.length}, users: ${domains.length * USERS.length}\n`);

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

  const rows = ['Email,Code1,Code2,Code3,Code4,Code5,Code6,Code7,Code8,Code9,Code10'];
  const results = { ok: [], failed: [] };

  for (const domain of domains) {
    for (const login of USERS) {
      const email = `${login}@${domain}`;
      process.stdout.write(`${email} ... `);

      try {
        // Generate fresh backup codes (invalidates old ones)
        await adminDir.verificationCodes.generate({ userKey: email });

        // Retrieve the codes
        const { data } = await adminDir.verificationCodes.list({ userKey: email });
        const codes = (data.items || []).map(item => item.verificationCode);

        if (codes.length === 0) throw new Error('No codes returned');

        // Pad to 10 columns
        while (codes.length < 10) codes.push('');

        rows.push([email, ...codes].join(','));
        console.log(`OK (${codes.length} codes)`);
        results.ok.push(email);
      } catch (e) {
        const msg = e.response?.data?.error?.message || e.message;
        console.log(`FAIL: ${msg}`);
        results.failed.push({ email, error: msg });
        rows.push([email, `ERROR: ${msg}`].join(','));
      }

      await new Promise(r => setTimeout(r, 500));
    }
  }

  fs.writeFileSync(outFile, rows.join('\n'));
  console.log('\n══════════════════════════════════════════');
  console.log(`OK:     ${results.ok.length}`);
  console.log(`Failed: ${results.failed.length}`);
  if (results.failed.length) results.failed.forEach(f => console.log(`  - ${f.email}: ${f.error}`));
  console.log(`\nBackup codes saved to: ${outFile}`);
})();
