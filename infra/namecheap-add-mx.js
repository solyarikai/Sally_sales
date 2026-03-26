// Adds ASPMX.L.GOOGLE.COM MX record to all crona domains (preserving existing records)
// Used for Google Workspace MX-based domain verification
//
// Usage: node namecheap-add-mx.js --domains-file crona-domains.txt

const fs = require('fs');
const path = require('path');

const NCKEY = 'f3335861b92247779364649ae2beb014';
const NCU   = 'decaster3';
const NCIP  = '150.241.224.134';

const args = process.argv.slice(2);
const getArg = n => { const i = args.indexOf('--'+n); return i !== -1 ? args[i+1] : null; };
const domainsFile = getArg('domains-file');
if (!domainsFile) { console.error('Usage: node namecheap-add-mx.js --domains-file domains.txt'); process.exit(1); }

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log('Domains:', domains.length);

function split(domain) {
  const i = domain.lastIndexOf('.');
  return { sld: domain.substring(0, i), tld: domain.substring(i + 1) };
}

async function ncGet(domain) {
  const { sld, tld } = split(domain);
  const xml = await fetch(`https://api.namecheap.com/xml.response?ApiUser=${NCU}&ApiKey=${NCKEY}&UserName=${NCU}&ClientIp=${NCIP}&Command=namecheap.domains.dns.getHosts&SLD=${sld}&TLD=${tld}`).then(r => r.text());
  return [...xml.matchAll(/<host\s([^/]*?)\/>/gi)].map(m => {
    const a = n => { const x = m[1].match(new RegExp(`${n}="([^"]*?)"`, 'i')); return x ? x[1] : ''; };
    return { Name: a('Name'), Type: a('Type'), Address: a('Address'), MXPref: a('MXPref') || '10', TTL: a('TTL') || '1800' };
  });
}

async function ncSet(domain, records) {
  const { sld, tld } = split(domain);
  let params = '', idx = 1;
  for (const h of records) {
    params += `&HostName${idx}=${encodeURIComponent(h.Name)}&RecordType${idx}=${h.Type}&Address${idx}=${encodeURIComponent(h.Address)}&MXPref${idx}=${h.MXPref}&TTL${idx}=${h.TTL}`;
    idx++;
  }
  const xml = await fetch(`https://api.namecheap.com/xml.response?ApiUser=${NCU}&ApiKey=${NCKEY}&UserName=${NCU}&ClientIp=${NCIP}&Command=namecheap.domains.dns.setHosts&SLD=${sld}&TLD=${tld}${params}`).then(r => r.text());
  if (!xml.includes('Status="OK"')) {
    const e = xml.match(/<Error[^>]*>([^<]+)<\/Error>/);
    throw new Error(e ? e[1] : 'Namecheap error');
  }
}

(async () => {
  const ok = [], fail = [];
  for (const domain of domains) {
    process.stdout.write(`${domain} ... `);
    try {
      const existing = await ncGet(domain);
      const filtered = existing.filter(h => h.Type !== 'MX');
      const records = [
        { Name: '@', Type: 'MX', Address: 'ASPMX.L.GOOGLE.COM', MXPref: '1', TTL: '1800' },
        ...filtered,
      ];
      await ncSet(domain, records);
      console.log('OK');
      ok.push(domain);
    } catch (e) {
      console.log('FAIL:', e.message);
      fail.push(domain);
    }
    await new Promise(r => setTimeout(r, 600));
  }
  console.log(`\nOK: ${ok.length}  FAIL: ${fail.length}`);
})();
