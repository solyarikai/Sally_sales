// Re-verifies unverified Google Workspace domains:
// delete → re-insert (gets fresh token) → add TXT to Namecheap → done
//
// Usage:
//   node google-workspace-reverify.js --domains-file crona-domains.txt

const fs = require('fs');
const path = require('path');
const { google } = require('googleapis');

const NAMECHEAP_API_KEY   = 'f3335861b92247779364649ae2beb014';
const NAMECHEAP_API_USER  = 'decaster3';
const NAMECHEAP_CLIENT_IP = '150.241.224.134';

const OAUTH_CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');
const TOKEN_FILE             = path.join(__dirname, 'google-oauth-token.json');

const args = process.argv.slice(2);
const getArg = (name) => { const i = args.indexOf(`--${name}`); return i !== -1 ? args[i + 1] : null; };
const domainsFile = getArg('domains-file');
const customerId  = getArg('customer') || 'my_customer';

if (!domainsFile) { console.error('Usage: node google-workspace-reverify.js --domains-file domains.txt'); process.exit(1); }

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log(`Domains: ${domains.length}\n`);

async function getAuthClient() {
  const creds = JSON.parse(fs.readFileSync(OAUTH_CREDENTIALS_FILE));
  const { client_id, client_secret } = creds.installed;
  const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, 'http://localhost:3000');
  oAuth2Client.setCredentials(JSON.parse(fs.readFileSync(TOKEN_FILE)));
  return oAuth2Client;
}

function splitDomain(domain) {
  const i = domain.lastIndexOf('.');
  return { sld: domain.substring(0, i), tld: domain.substring(i + 1) };
}

async function ncGetRecords(domain) {
  const { sld, tld } = splitDomain(domain);
  const url = `https://api.namecheap.com/xml.response?ApiUser=${NAMECHEAP_API_USER}&ApiKey=${NAMECHEAP_API_KEY}&UserName=${NAMECHEAP_API_USER}&ClientIp=${NAMECHEAP_CLIENT_IP}&Command=namecheap.domains.dns.getHosts&SLD=${sld}&TLD=${tld}`;
  const xml = await (await fetch(url)).text();
  return [...xml.matchAll(/<host\s([^/]*?)\/>/gi)].map(m => {
    const a = (n) => { const x = m[1].match(new RegExp(`${n}="([^"]*?)"`, 'i')); return x ? x[1] : ''; };
    return { Name: a('Name'), Type: a('Type'), Address: a('Address'), MXPref: a('MXPref') || '10', TTL: a('TTL') || '1800' };
  });
}

async function ncAddTxt(domain, host, value) {
  const { sld, tld } = splitDomain(domain);
  const existing = await ncGetRecords(domain);
  const filtered = existing.filter(h => !(h.Name.toLowerCase() === host.toLowerCase() && h.Type === 'TXT'));

  let params = '', idx = 1;
  for (const h of filtered) {
    params += `&HostName${idx}=${encodeURIComponent(h.Name)}&RecordType${idx}=${h.Type}&Address${idx}=${encodeURIComponent(h.Address)}&MXPref${idx}=${h.MXPref}&TTL${idx}=${h.TTL}`;
    idx++;
  }
  params += `&HostName${idx}=${encodeURIComponent(host)}&RecordType${idx}=TXT&Address${idx}=${encodeURIComponent(value)}&TTL${idx}=1800`;

  const xml = await (await fetch(
    `https://api.namecheap.com/xml.response?ApiUser=${NAMECHEAP_API_USER}&ApiKey=${NAMECHEAP_API_KEY}&UserName=${NAMECHEAP_API_USER}&ClientIp=${NAMECHEAP_CLIENT_IP}&Command=namecheap.domains.dns.setHosts&SLD=${sld}&TLD=${tld}${params}`
  )).text();
  if (!xml.includes('Status="OK"')) {
    const e = xml.match(/<Error[^>]*>([^<]+)<\/Error>/);
    throw new Error(e ? e[1] : 'Namecheap error');
  }
}

async function main() {
  const auth = await getAuthClient();
  const adminDir = google.admin({ version: 'directory_v1', auth });

  const results = { alreadyVerified: [], tokenAdded: [], failed: [] };

  for (const domain of domains) {
    process.stdout.write(`${domain} ... `);

    try {
      // Check current status
      const res = await adminDir.domains.get({ customer: customerId, domainName: domain });

      if (res.data.verified) {
        console.log('✓ already verified, skipping');
        results.alreadyVerified.push(domain);
        await new Promise(r => setTimeout(r, 300));
        continue;
      }

      // Delete → re-insert to get a fresh verification token
      await adminDir.domains.delete({ customer: customerId, domainName: domain });
      await new Promise(r => setTimeout(r, 1000));

      const insertRes = await adminDir.domains.insert({
        customer: customerId,
        requestBody: { domainName: domain },
      });

      const token = insertRes.data.verificationToken || insertRes.data.domainAliases?.[0]?.verificationToken;

      if (!token) {
        console.log('⚠ no token after re-insert');
        results.failed.push({ domain, error: 'no token after insert' });
        continue;
      }

      // Add TXT to Namecheap (preserving existing records)
      await ncAddTxt(domain, '@', token);
      console.log(`✓ TXT added (token: ${token.substring(0, 40)}...)`);
      results.tokenAdded.push(domain);

    } catch (e) {
      const msg = e.response?.data?.error?.message || e.message;
      console.log(`FAILED: ${msg}`);
      results.failed.push({ domain, error: msg });
    }

    await new Promise(r => setTimeout(r, 800));
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`Already verified: ${results.alreadyVerified.length}`);
  console.log(`TXT added:        ${results.tokenAdded.length}`);
  console.log(`Failed:           ${results.failed.length}`);
  if (results.failed.length) results.failed.forEach(f => console.log(`  - ${f.domain}: ${f.error}`));

  if (results.tokenAdded.length > 0) {
    console.log('\n⏳ DNS propagation takes 5–30 min.');
    console.log('After that Google auto-verifies, or check in Admin Console → Domains.');
  }
}

main().catch(console.error);
