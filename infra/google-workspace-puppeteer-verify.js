// Automates Google Workspace Admin Console to get domain verification tokens,
// then adds TXT records to Namecheap for all unverified domains.
//
// Strategy: intercept XHR/fetch responses from Admin Console internal APIs
// which contain the google-site-verification token for each domain.
//
// Usage:
//   node google-workspace-puppeteer-verify.js --domains-file crona-domains.txt

const fs = require('fs');
const os = require('os');
const path = require('path');
const { exec, execSync } = require('child_process');
const puppeteer = require('puppeteer');

const NAMECHEAP_API_KEY   = 'f3335861b92247779364649ae2beb014';
const NAMECHEAP_API_USER  = 'decaster3';
const NAMECHEAP_CLIENT_IP = '150.241.224.134';

const args = process.argv.slice(2);
const getArg = (name) => { const i = args.indexOf(`--${name}`); return i !== -1 ? args[i + 1] : null; };
const domainsFile = getArg('domains-file');

if (!domainsFile) {
  console.error('Usage: node google-workspace-puppeteer-verify.js --domains-file domains.txt');
  process.exit(1);
}

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log(`Domains: ${domains.length}`);

// ── Namecheap ─────────────────────────────────────────────────────────────────

function splitDomain(d) { const i = d.lastIndexOf('.'); return { sld: d.substring(0, i), tld: d.substring(i + 1) }; }

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
  const filtered = existing.filter(h => !(h.Name.toLowerCase() === host.toLowerCase() && h.Type === 'TXT' && h.Address.includes('google-site-verification')));

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

// ── Token extraction ──────────────────────────────────────────────────────────

function extractToken(text) {
  // Matches google-site-verification=XXXXX in any format
  const m = text.match(/google-site-verification[=:\s\\"']+([A-Za-z0-9_\-]{20,})/i);
  return m ? `google-site-verification=${m[1]}` : null;
}

// Navigate to domain page and intercept all responses to find the token
async function getTokenForDomain(page, domain) {
  return new Promise(async (resolve) => {
    let token = null;
    const responseHandler = async (response) => {
      if (token) return;
      try {
        const url = response.url();
        // Only check relevant URLs
        if (!url.includes('google') && !url.includes('admin')) return;
        const ct = response.headers()['content-type'] || '';
        if (!ct.includes('json') && !ct.includes('text') && !ct.includes('javascript')) return;
        const text = await response.text();
        const found = extractToken(text);
        if (found) {
          token = found;
          resolve(token);
        }
      } catch (_) {}
    };

    page.on('response', responseHandler);

    // Navigate to domain-specific verification page
    // Try multiple URL patterns that Admin Console uses
    const urls = [
      `https://admin.google.com/ac/domains/verify?domainName=${encodeURIComponent(domain)}`,
      `https://admin.google.com/ac/domains/${encodeURIComponent(domain)}/verify`,
    ];

    for (const url of urls) {
      if (token) break;
      try {
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 20000 });
        await new Promise(r => setTimeout(r, 2000));
        // Also check page HTML directly
        if (!token) {
          const content = await page.content();
          token = extractToken(content);
          if (token) { resolve(token); break; }
        }
      } catch (_) {}
    }

    // If still no token, go to main domains list and click the domain
    if (!token) {
      try {
        await page.goto('https://admin.google.com/ac/domains/home', { waitUntil: 'networkidle2', timeout: 20000 });
        await new Promise(r => setTimeout(r, 2000));

        // Click on the domain row
        const clicked = await page.evaluate((targetDomain) => {
          // Search through all text nodes
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            if (node.textContent.trim() === targetDomain) {
              // Click parent element
              let el = node.parentElement;
              for (let i = 0; i < 5; i++) {
                if (el.tagName === 'TR' || el.tagName === 'A' || el.getAttribute('role') === 'row') {
                  el.click();
                  return true;
                }
                el = el.parentElement;
                if (!el) break;
              }
              node.parentElement.click();
              return true;
            }
          }
          return false;
        }, domain);

        if (clicked) {
          await new Promise(r => setTimeout(r, 3000));
          const content = await page.content();
          token = extractToken(content);
          if (token) resolve(token);
        }
      } catch (_) {}
    }

    page.off('response', responseHandler);

    // Timeout fallback
    setTimeout(() => resolve(null), 25000);
  });
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  console.log('\nLaunching browser...\n');

  const userDataDir = path.join(os.tmpdir(), `chrome_admin_${Date.now()}_${Math.random().toString(36).slice(2)}`);
  fs.mkdirSync(userDataDir, { recursive: true });

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    userDataDir,
    pipe: true,
    args: ['--no-sandbox', '--no-first-run', '--no-default-browser-check', '--start-maximized'],
    defaultViewport: null,
  });

  const page = await browser.newPage();

  // Enable request interception for all content types
  await page.setRequestInterception(false);

  // Navigate to Admin Console
  await page.goto('https://admin.google.com/ac/domains/home', { waitUntil: 'networkidle2', timeout: 30000 });

  // Wait for login if redirected
  if (!page.url().includes('admin.google.com/ac')) {
    console.log('⚠ Please log in to Google Admin Console in the browser window.');
    console.log('Waiting up to 2 minutes...\n');
    await page.waitForFunction(
      () => window.location.href.includes('admin.google.com/ac'),
      { timeout: 120000, polling: 1000 }
    );
    console.log('✓ Logged in\n');
  }

  await new Promise(r => setTimeout(r, 2000));

  const results = { tokenAdded: [], noToken: [], ncFailed: [] };

  for (const domain of domains) {
    process.stdout.write(`${domain} ... `);

    const token = await getTokenForDomain(page, domain);

    if (!token) {
      console.log('⚠ token not found');
      results.noToken.push(domain);
      continue;
    }

    console.log(`token found`);

    try {
      await ncAddTxt(domain, '@', token);
      console.log(`  ✓ TXT → Namecheap`);
      results.tokenAdded.push({ domain, token });
    } catch (e) {
      console.log(`  ✗ Namecheap: ${e.message}`);
      results.ncFailed.push({ domain, token, error: e.message });
    }

    await new Promise(r => setTimeout(r, 800));
  }

  // Save all found tokens for reference
  const outputFile = path.join(__dirname, 'verify-tokens.json');
  fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
  console.log(`\nTokens saved to ${outputFile}`);

  console.log('\n══════════════════════════════════════════');
  console.log(`TXT added: ${results.tokenAdded.length}`);
  console.log(`No token:  ${results.noToken.length}`);
  console.log(`NC failed: ${results.ncFailed.length}`);

  if (results.noToken.length > 0) {
    console.log('\nDomains where token was NOT found — manual check needed:');
    results.noToken.forEach(d => console.log(`  - ${d}`));
  }
  if (results.tokenAdded.length > 0) {
    console.log('\n⏳ Wait 5–30 min for DNS propagation, then Google auto-verifies.');
  }

  await browser.close();
  console.log('\nDone.');
}

main().catch(e => { console.error(e); process.exit(1); });
