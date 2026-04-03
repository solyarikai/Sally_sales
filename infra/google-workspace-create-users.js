// Creates 2 users per domain: petr@domain.com and rinat@domain.com
// Usage: node google-workspace-create-users.js --domains-file crona-domains.txt

const fs = require('fs');
const path = require('path');
const { google } = require('googleapis');

const TOKEN_FILE       = path.join(__dirname, 'google-oauth-token.json');
const CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');

const args = process.argv.slice(2);
const getArg = n => { const i = args.indexOf('--' + n); return i !== -1 ? args[i + 1] : null; };
const domainsFile = getArg('domains-file');
if (!domainsFile) { console.error('Usage: node google-workspace-create-users.js --domains-file domains.txt'); process.exit(1); }

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log(`Domains: ${domains.length}, users to create: ${domains.length * 2}\n`);

const PASSWORD = 'SallySuper777';

const RINAT_PHOTO = fs.readFileSync('C:\\Users\\Artem\\Downloads\\T051RLPQ5AP-U05RJEFTJ90-5e0acd07545b-192.png');
const PETR_PHOTO  = fs.readFileSync('C:\\Users\\Artem\\Downloads\\T051RLPQ5AP-U05S7E6MUGY-3d6ba346c70e-192 (1).png');

function toUrlSafeBase64(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

const USERS = [
  { login: 'petr',  givenName: 'Petr',  familyName: 'Nikolaev', photo: PETR_PHOTO },
  { login: 'rinat', givenName: 'Rinat', familyName: 'Khatipov', photo: RINAT_PHOTO },
];

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

  const results = { created: [], alreadyExists: [], failed: [] };

  for (const domain of domains) {
    for (const user of USERS) {
      const email = `${user.login}@${domain}`;
      process.stdout.write(`${email} ... `);

      let skip = false;
      try {
        await adminDir.users.insert({
          requestBody: {
            primaryEmail: email,
            name: { givenName: user.givenName, familyName: user.familyName },
            password: PASSWORD,
            changePasswordAtNextLogin: false,
          },
        });
        console.log('created');
        results.created.push(email);
      } catch (e) {
        const msg = e.response?.data?.error?.message || e.message;
        if (msg.includes('Entity already exists') || e.response?.status === 409) {
          console.log('already exists');
          results.alreadyExists.push(email);
        } else {
          console.log('FAILED:', msg);
          results.failed.push({ email, error: msg });
          skip = true;
        }
      }

      if (!skip) {
        try {
          await adminDir.users.photos.update({
            userKey: email,
            requestBody: {
              photoData: toUrlSafeBase64(user.photo),
              mimeType: 'IMAGE/PNG',
              width: 192,
              height: 192,
            },
          });
          console.log(`  avatar OK`);
        } catch (e) {
          console.log(`  avatar FAILED: ${e.response?.data?.error?.message || e.message}`);
        }
      }

      await new Promise(r => setTimeout(r, 400));
    }
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`Created:       ${results.created.length}`);
  console.log(`Already exist: ${results.alreadyExists.length}`);
  console.log(`Failed:        ${results.failed.length}`);
  if (results.failed.length) results.failed.forEach(f => console.log(`  - ${f.email}: ${f.error}`));
  console.log(`\nPassword: ${PASSWORD}`);
})();
