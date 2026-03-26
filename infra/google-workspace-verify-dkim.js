// 1. Gets verification tokens from Google Workspace, adds TXT records to Namecheap, triggers verification
// 2. Reports DKIM status (manual step needed via Admin Console)
//
// Usage:
//   node google-workspace-verify-dkim.js --domains-file crona-domains.txt

const fs = require('fs');
const path = require('path');
const { google } = require('googleapis');

const NAMECHEAP_API_KEY   = 'f3335861b92247779364649ae2beb014';
const NAMECHEAP_API_USER  = 'decaster3';
const NAMECHEAP_CLIENT_IP = '150.241.224.134';

const OAUTH_CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');
const TOKEN_FILE             = path.join(__dirname, 'google-oauth-token.json');

const SCOPES = ['https://www.googleapis.com/auth/admin.directory.domain'];

// ── Args ──────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const getArg = (name) => { const i = args.indexOf(`--${name}`); return i !== -1 ? args[i + 1] : null; };

const domainsFile = getArg('domains-file');
const customerId  = getArg('customer') || 'my_customer';

if (!domainsFile) {
  console.error('Usage: node google-workspace-verify-dkim.js --domains-file domains.txt');
  process.exit(1);
}

const domains = fs.readFileSync(domainsFile, 'utf8')
  .split('\n').map(d => d.trim()).filter(Boolean);

console.log(`Domains to process: ${domains.length}\n`);

// ── OAuth ─────────────────────────────────────────────────────────────────────

async function getAuthClient() {
  const creds = JSON.parse(fs.readFileSync(OAUTH_CREDENTIALS_FILE));
  const { client_id, client_secret } = creds.installed;
  const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, 'http://localhost:3000');

  if (!fs.existsSync(TOKEN_FILE)) {
    console.error('No OAuth token found. Run google-workspace-add-domains.js first.');
    process.exit(1);
  }

  const token = JSON.parse(fs.readFileSync(TOKEN_FILE));
  oAuth2Client.setCredentials(token);
  return oAuth2Client;
}

// ── Namecheap helpers ─────────────────────────────────────────────────────────

function splitDomain(domain) {
  const lastDot = domain.lastIndexOf('.');
  return { sld: domain.substring(0, lastDot), tld: domain.substring(lastDot + 1) };
}

async function getExistingRecords(domain) {
  const { sld, tld } = splitDomain(domain);
  const url = `https://api.namecheap.com/xml.response?ApiUser=${NAMECHEAP_API_USER}&ApiKey=${NAMECHEAP_API_KEY}&UserName=${NAMECHEAP_API_USER}&ClientIp=${NAMECHEAP_CLIENT_IP}&Command=namecheap.domains.dns.getHosts&SLD=${sld}&TLD=${tld}`;
  const resp = await fetch(url);
  const xml = await resp.text();
  const hostMatches = [...xml.matchAll(/<host\s([^/]*?)\/>/gi)];
  return hostMatches.map(m => {
    const attr = (name) => { const r = new RegExp(`${name}="([^"]*?)"`, 'i'); const x = m[1].match(r); return x ? x[1] : ''; };
    return { Name: attr('Name'), Type: attr('Type'), Address: attr('Address'), MXPref: attr('MXPref') || '10', TTL: attr('TTL') || '1800' };
  });
}

async function addTxtRecord(domain, host, value) {
  const { sld, tld } = splitDomain(domain);
  const existing = await getExistingRecords(domain);

  // Remove old record with same host+type if exists
  const filtered = existing.filter(h => !(h.Name.toLowerCase() === host.toLowerCase() && h.Type === 'TXT'));

  let params = '';
  let idx = 1;
  for (const h of filtered) {
    params += `&HostName${idx}=${encodeURIComponent(h.Name)}&RecordType${idx}=${h.Type}&Address${idx}=${encodeURIComponent(h.Address)}&MXPref${idx}=${h.MXPref}&TTL${idx}=${h.TTL}`;
    idx++;
  }
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

  const results = {
    alreadyVerified: [],
    tokenAdded: [],       // TXT added, waiting for propagation + verify
    noToken: [],          // domain in workspace but no token returned
    failed: [],
  };

  for (const domain of domains) {
    process.stdout.write(`${domain} ... `);

    try {
      const res = await adminDir.domains.get({ customer: customerId, domainName: domain });
      const data = res.data;

      if (data.verified) {
        console.log('✓ already verified');
        results.alreadyVerified.push(domain);
        continue;
      }

      // Get verification token — it's in verificationToken or domainAliases[0].verificationToken
      const token = data.verificationToken || data.domainAliases?.[0]?.verificationToken;

      if (!token) {
        console.log('⚠ not verified, no token returned');
        results.noToken.push(domain);
        continue;
      }

      // Add TXT record to Namecheap
      await addTxtRecord(domain, '@', token);
      console.log(`TXT added (${token.substring(0, 30)}...)`);
      results.tokenAdded.push(domain);

    } catch (e) {
      console.log(`FAILED: ${e.message}`);
      results.failed.push({ domain, error: e.message });
    }

    await new Promise(r => setTimeout(r, 600));
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`Already verified:  ${results.alreadyVerified.length}`);
  console.log(`TXT added:         ${results.tokenAdded.length}`);
  console.log(`No token:          ${results.noToken.length}`);
  console.log(`Failed:            ${results.failed.length}`);

  if (results.noToken.length) {
    console.log('\nDomains with no token (need manual check in Admin Console):');
    results.noToken.forEach(d => console.log(`  - ${d}`));
  }
  if (results.failed.length) {
    results.failed.forEach(f => console.log(`  - ${f.domain}: ${f.error}`));
  }

  if (results.tokenAdded.length > 0) {
    console.log(`\n⏳ TXT records added for ${results.tokenAdded.length} domains.`);
    console.log('DNS propagation takes 5-30 min. After that run with --verify-only to confirm.');
  }

  console.log('\n──────────────────────────────────────────');
  console.log('DKIM: No public Google API for DKIM key generation.');
  console.log('Must be done in Admin Console → Apps → Google Workspace → Gmail → Authenticate email');
  console.log('Select each domain → Generate new record → copy DNS value → add to Namecheap as:');
  console.log('  TXT record, host: google._domainkey, value: <from Google>');
}

main().catch(console.error);
