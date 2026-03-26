// Adds domains to Google Workspace and creates Namecheap TXT verification records
// Flow: OAuth login (one-time, browser) → add domains → get tokens → add TXT → verify
//
// Usage:
//   node google-workspace-add-domains.js --customer CUSTOMER_ID --domains-file crona-domains.txt
//   node google-workspace-add-domains.js --customer my_customer --domains-file crona-domains.txt
//
// CUSTOMER_ID: "my_customer" works if you're the primary domain admin,
//              or get it from Admin Console → Account → Account settings

const fs = require('fs');
const http = require('http');
const path = require('path');
const { google } = require('googleapis');

// ── Config ────────────────────────────────────────────────────────────────────

const NAMECHEAP_API_KEY  = 'f3335861b92247779364649ae2beb014';
const NAMECHEAP_API_USER = 'decaster3';
const NAMECHEAP_CLIENT_IP = '150.241.224.134';

const OAUTH_CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');
const TOKEN_FILE = path.join(__dirname, 'google-oauth-token.json');

const SCOPES = [
  'https://www.googleapis.com/auth/admin.directory.domain',
];

// ── Args ──────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const getArg = (name) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 ? args[i + 1] : null;
};

const customerId  = getArg('customer') || 'my_customer';
const domainsFile = getArg('domains-file');
const onlyAdd     = args.includes('--only-add');     // skip verify step
const onlyVerify  = args.includes('--only-verify');  // skip add step

if (!domainsFile) {
  console.error('Usage: node google-workspace-add-domains.js --customer my_customer --domains-file domains.txt');
  process.exit(1);
}

const domains = fs.readFileSync(domainsFile, 'utf8')
  .split('\n').map(d => d.trim()).filter(Boolean);

console.log(`Domains to process: ${domains.length}`);

// ── OAuth ─────────────────────────────────────────────────────────────────────

async function getAuthClient() {
  const creds = JSON.parse(fs.readFileSync(OAUTH_CREDENTIALS_FILE));
  const { client_id, client_secret, redirect_uris } = creds.installed;

  const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, 'http://localhost:3000');

  // Reuse saved token if available
  if (fs.existsSync(TOKEN_FILE)) {
    const token = JSON.parse(fs.readFileSync(TOKEN_FILE));
    oAuth2Client.setCredentials(token);
    console.log('Using saved OAuth token.');
    return oAuth2Client;
  }

  // First-time: open browser for consent
  const authUrl = oAuth2Client.generateAuthUrl({ access_type: 'offline', scope: SCOPES });
  console.log('\nOpening browser for Google OAuth consent...');
  console.log('If browser does not open, go to:\n', authUrl);

  try { (await import('open')).default(authUrl); } catch (_) {}

  const code = await new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, 'http://localhost:3000');
      const code = url.searchParams.get('code');
      if (!code) { res.end('Waiting...'); return; }
      res.end('<h1>Auth complete. You can close this tab.</h1>');
      server.close();
      resolve(code);
    });
    server.listen(3000);
    console.log('Waiting for OAuth callback on http://localhost:3000 ...');
  });

  const { tokens } = await oAuth2Client.getToken(code);
  oAuth2Client.setCredentials(tokens);
  fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokens));
  console.log('Token saved to', TOKEN_FILE);
  return oAuth2Client;
}

// ── Namecheap TXT helper ──────────────────────────────────────────────────────

async function addTxtRecord(domain, host, value) {
  const lastDot = domain.lastIndexOf('.');
  const sld = domain.substring(0, lastDot);
  const tld = domain.substring(lastDot + 1);

  // First get existing records so we don't overwrite them
  const getUrl = `https://api.namecheap.com/xml.response?ApiUser=${NAMECHEAP_API_USER}&ApiKey=${NAMECHEAP_API_KEY}&UserName=${NAMECHEAP_API_USER}&ClientIp=${NAMECHEAP_CLIENT_IP}&Command=namecheap.domains.dns.getHosts&SLD=${sld}&TLD=${tld}`;

  const getResp = await fetch(getUrl);
  const getXml = await getResp.text();

  // Parse existing hosts
  const hostMatches = [...getXml.matchAll(/<host\s([^/]*?)\/>/g)];
  const existingHosts = hostMatches.map((m, i) => {
    const attr = (name) => { const r = new RegExp(`${name}="([^"]*?)"`); const x = m[1].match(r); return x ? x[1] : ''; };
    return { Name: attr('Name'), Type: attr('Type'), Address: attr('Address'), MXPref: attr('MXPref') || '10', TTL: attr('TTL') || '1800' };
  });

  // Build setHosts params with existing + new TXT
  let params = '';
  let idx = 1;

  for (const h of existingHosts) {
    params += `&HostName${idx}=${encodeURIComponent(h.Name)}&RecordType${idx}=${h.Type}&Address${idx}=${encodeURIComponent(h.Address)}&MXPref${idx}=${h.MXPref}&TTL${idx}=${h.TTL}`;
    idx++;
  }

  // Add the new TXT record
  params += `&HostName${idx}=${encodeURIComponent(host)}&RecordType${idx}=TXT&Address${idx}=${encodeURIComponent(value)}&TTL${idx}=1800`;

  const setUrl = `https://api.namecheap.com/xml.response?ApiUser=${NAMECHEAP_API_USER}&ApiKey=${NAMECHEAP_API_KEY}&UserName=${NAMECHEAP_API_USER}&ClientIp=${NAMECHEAP_CLIENT_IP}&Command=namecheap.domains.dns.setHosts&SLD=${sld}&TLD=${tld}${params}`;

  const setResp = await fetch(setUrl);
  const setXml = await setResp.text();

  if (setXml.includes('Status="OK"')) return true;
  const errMatch = setXml.match(/<Error[^>]*>([^<]+)<\/Error>/);
  throw new Error(errMatch ? errMatch[1] : 'Unknown Namecheap error');
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const auth = await getAuthClient();
  const adminDir = google.admin({ version: 'directory_v1', auth });

  const results = { added: [], alreadyExists: [], verified: [], failed: [] };

  for (const domain of domains) {
    console.log(`\n── ${domain} ──`);

    // Step 1: Add domain to Google Workspace
    if (!onlyVerify) {
      try {
        const res = await adminDir.domains.insert({
          customer: customerId,
          requestBody: { domainName: domain },
        });
        const token = res.data.domainAliases?.[0]?.verificationToken || res.data.verificationToken;
        console.log(`  Added. Verification token: ${token}`);
        results.added.push({ domain, token });

        // Create TXT record on Namecheap
        if (token) {
          try {
            await addTxtRecord(domain, '@', token);
            console.log(`  TXT record created on Namecheap.`);
          } catch (e) {
            console.log(`  WARNING: Failed to add TXT record: ${e.message}`);
          }
        }
      } catch (e) {
        if (e.code === 409 || e.message?.includes('already exists')) {
          console.log(`  Already exists in Workspace.`);
          results.alreadyExists.push(domain);
        } else {
          console.log(`  FAILED to add: ${e.message}`);
          results.failed.push({ domain, error: e.message });
          continue;
        }
      }
    }

    // Step 2: Verify domain
    if (!onlyAdd) {
      await new Promise(r => setTimeout(r, 2000)); // small delay for DNS
      try {
        await adminDir.domains.get({ customer: customerId, domainName: domain });
        console.log(`  Verification triggered.`);
        results.verified.push(domain);
      } catch (e) {
        console.log(`  Verify: ${e.message}`);
      }
    }

    await new Promise(r => setTimeout(r, 500));
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`Added:         ${results.added.length}`);
  console.log(`Already exist: ${results.alreadyExists.length}`);
  console.log(`Failed:        ${results.failed.length}`);
  if (results.failed.length) results.failed.forEach(f => console.log(`  - ${f.domain}: ${f.error}`));
}

main().catch(console.error);
