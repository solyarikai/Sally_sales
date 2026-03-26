const NCKEY = 'f3335861b92247779364649ae2beb014';
const NCU   = 'decaster3';
const NCIP  = '150.241.224.134';

const records = [
  { domain: 'cronaoutreach.com', token: 'google-site-verification=3dnwHjethh_lxrinmoKsH3lLxkySHNi0FczN-k_nIIY' },
  { domain: 'cronaplatform.com', token: 'google-site-verification=yRnfs3Loi-fuAM13Kaw689_bI_FZtv1Vre8KQKo6Jh8' },
  { domain: 'cronapulse.com',    token: 'google-site-verification=khyAgjyVyo5LqUDaii1nrg47k3d7-3d2sCaQcYwMfoE' },
  { domain: 'cronascout.com',    token: 'google-site-verification=NXBw43rcX2BzS9vYYZVT0aGGVv4nJpHkY27br3hgRjM' },
  { domain: 'cronasuite.com',    token: 'google-site-verification=PUtMfDZ8Q7JFKc2EyHxBWYPjCEcb7dF9ixcyuvDRQ-A' },
];

function split(domain) { const i = domain.lastIndexOf('.'); return { sld: domain.substring(0, i), tld: domain.substring(i+1) }; }

async function ncGet(domain) {
  const { sld, tld } = split(domain);
  const xml = await fetch(`https://api.namecheap.com/xml.response?ApiUser=${NCU}&ApiKey=${NCKEY}&UserName=${NCU}&ClientIp=${NCIP}&Command=namecheap.domains.dns.getHosts&SLD=${sld}&TLD=${tld}`).then(r => r.text());
  return [...xml.matchAll(/<host\s([^/]*?)\/>/gi)].map(m => {
    const a = n => { const x = m[1].match(new RegExp(`${n}="([^"]*?)"`, 'i')); return x ? x[1] : ''; };
    return { Name: a('Name'), Type: a('Type'), Address: a('Address'), MXPref: a('MXPref') || '10', TTL: a('TTL') || '1800' };
  });
}

async function ncAddTxt(domain, value) {
  const { sld, tld } = split(domain);
  const existing = await ncGet(domain);
  const filtered = existing.filter(h => !(h.Name === '@' && h.Type === 'TXT' && h.Address.includes('google-site-verification')));
  const allRecords = [...filtered, { Name: '@', Type: 'TXT', Address: value, MXPref: '10', TTL: '1800' }];
  let params = '', idx = 1;
  for (const h of allRecords) {
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
  for (const { domain, token } of records) {
    process.stdout.write(`${domain} ... `);
    try {
      await ncAddTxt(domain, token);
      console.log('OK');
    } catch(e) {
      console.log('FAIL:', e.message);
    }
    await new Promise(r => setTimeout(r, 600));
  }
})();
