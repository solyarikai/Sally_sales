// ✅ РАБОЧИЙ СКРИПТ (проверен 2026-03-26)
// Включает DKIM для списка доменов через Google Workspace Admin Console.
// Для каждого домена: выбирает домен → "Создать новую запись" → "Создать" →
//   добавляет TXT-запись google._domainkey в Namecheap → нажимает "Включить аутентификацию".
//
// Требования:
//   - Закрыть Chrome перед запуском (иначе конфликт ProcessSingleton)
//   - Залогиниться в Google Admin Console в открывшемся окне (1 раз)
//   - Admin Console должна быть на русском языке (ищет кнопки "Создать", "Включить аутентификацию")
//
// Запуск:
//   cd infra && node google-workspace-enable-dkim.js --domains-file crona-domains.txt
//
// Результат сохраняется в dkim-results.json

const fs   = require('fs');
const os   = require('os');
const path = require('path');
const puppeteer = require('puppeteer');

const NAMECHEAP_API_KEY   = 'f3335861b92247779364649ae2beb014';
const NAMECHEAP_API_USER  = 'decaster3';
const NAMECHEAP_CLIENT_IP = '150.241.224.134';

const args    = process.argv.slice(2);
const getArg  = (n) => { const i = args.indexOf(`--${n}`); return i !== -1 ? args[i + 1] : null; };
const domainsFile = getArg('domains-file');

if (!domainsFile) {
  console.error('Usage: node google-workspace-enable-dkim.js --domains-file domains.txt');
  process.exit(1);
}

const domains = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
console.log(`Domains: ${domains.length}\n`);

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
  // Remove old google._domainkey if present
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

// ── DKIM key extraction ───────────────────────────────────────────────────────

// Finds "v=DKIM1; k=rsa; p=..." in page text/network responses
function extractDkimKey(text) {
  // Match full DKIM value: v=DKIM1; k=rsa; p=<key>
  const m = text.match(/v=DKIM1[^"'<]{10,}/);
  return m ? m[0].replace(/\\n/g, '').replace(/\s+/g, ' ').trim() : null;
}

// ── DKIM flow for one domain ──────────────────────────────────────────────────

async function processDomain(page, domain) {
  const DKIM_URL = 'https://admin.google.com/ac/apps/gmail/authenticateemail';

  // Navigate to DKIM page — use 'load' to avoid frame detach on SPA redirects
  try {
    await page.goto(DKIM_URL, { waitUntil: 'load', timeout: 30000 });
  } catch (_) { /* ignore navigation errors from SPA redirects */ }
  await page.waitForFunction(
    () => window.location.href.includes('authenticateemail'),
    { timeout: 30000, polling: 500 }
  );
  await new Promise(r => setTimeout(r, 2000));

  // ── Select domain from dropdown ───────────────────────────────────────────
  // 1. Try native <select>
  const selected = await page.evaluate((targetDomain) => {
    for (const sel of document.querySelectorAll('select')) {
      for (const opt of sel.options) {
        if (opt.text.trim().toLowerCase() === targetDomain.toLowerCase() ||
            opt.value.trim().toLowerCase() === targetDomain.toLowerCase()) {
          sel.value = opt.value;
          sel.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }
      }
    }
    return false;
  }, domain);

  if (!selected) {
    // 2. Click Angular Material dropdown trigger via evaluate (more reliable)
    const clicked = await page.evaluate(() => {
      const t = document.querySelector('[role="combobox"], [role="listbox"], mat-select, .mat-select');
      if (t) { t.click(); return true; }
      return false;
    });
    if (!clicked) return { status: 'no_dropdown', dkimKey: null };

    // 3. Wait for overlay options and click the matching domain via element handle
    try {
      await page.waitForSelector(
        '[role="option"], mat-option, .mat-option, .mdc-list-item__primary-text',
        { timeout: 5000 }
      );
    } catch (_) { return { status: 'no_dropdown', dkimKey: null }; }

    const optionClicked = await page.evaluate((targetDomain) => {
      const options = document.querySelectorAll('[role="option"], mat-option, .mat-option');
      for (const opt of options) {
        if (opt.textContent.trim().toLowerCase().includes(targetDomain.toLowerCase())) {
          opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
          opt.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
          opt.click();
          return opt.textContent.trim();
        }
      }
      return null;
    }, domain);
    if (!optionClicked) return { status: 'no_dropdown', dkimKey: null };
    process.stdout.write(`[selected: ${optionClicked}] `);
  }

  await new Promise(r => setTimeout(r, 2000));

  // ── Extract existing DKIM key if already shown ────────────────────────────
  let dkimKey = await page.evaluate(() => {
    // Check input/textarea values first
    for (const el of document.querySelectorAll('input, textarea')) {
      if ((el.value || '').includes('v=DKIM1')) return el.value;
    }
    // Then full textContent of body (catches spans, divs, etc.)
    const m = document.body.textContent.match(/v=DKIM1[^<]{10,}/);
    return m ? m[0].replace(/\s+/g, ' ').trim() : null;
  });

  if (!dkimKey) {
    // ── Click "Создать новую запись" / "Generate new record" ─────────────
    const generated = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button, [role="button"], a')];
      const target = btns.find(b => {
        const t = b.textContent.trim().toLowerCase();
        return t.includes('создать') || t.includes('generate');
      });
      if (target) { target.click(); return target.textContent.trim(); }
      return null;
    });

    if (!generated) return { status: 'no_key', dkimKey: null };

    // After "Создать новую запись" a dialog appears — click "Создать" to confirm defaults
    await new Promise(r => setTimeout(r, 2000));
    const confirmed = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button, [role="button"]')];
      const confirm = btns.find(b => {
        const t = b.textContent.trim().toLowerCase();
        return t === 'создать' || t === 'create';
      });
      if (confirm) { confirm.click(); return confirm.textContent.trim(); }
      return null;
    });

    // Wait for key to appear in DOM
    try {
      await page.waitForFunction(
        () => {
          for (const el of document.querySelectorAll('input, textarea')) {
            if ((el.value || '').includes('v=DKIM1')) return true;
          }
          return document.body.innerText.includes('v=DKIM1');
        },
        { timeout: 15000, polling: 500 }
      );
    } catch (_) { /* key may appear via network interception below */ }

    dkimKey = await page.evaluate(() => {
      for (const el of document.querySelectorAll('input, textarea')) {
        if ((el.value || '').includes('v=DKIM1')) return el.value;
      }
      const m = document.body.textContent.match(/v=DKIM1[^<]{10,}/);
      return m ? m[0].replace(/\s+/g, ' ').trim() : null;
    });
  }

  if (!dkimKey) return { status: 'no_key', dkimKey: null };

  // ── Click "Включить аутентификацию" / "Start authentication" ─────────────
  const started = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button, [role="button"]')];
    const target = btns.find(b => {
      const t = b.textContent.trim().toLowerCase();
      return t.includes('включить') || t.includes('start authentication') || t.includes('turn on');
    });
    if (target) { target.click(); return true; }
    return false;
  });

  return { status: started ? 'started' : 'key_found_no_button', dkimKey };
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const userDataDir = path.join(os.tmpdir(), `chrome_dkim_${Date.now()}`);
  fs.mkdirSync(userDataDir, { recursive: true });

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: require('puppeteer').executablePath(),
    userDataDir,
    pipe: true,
    args: ['--no-sandbox', '--no-first-run', '--no-default-browser-check', '--start-maximized'],
    defaultViewport: null,
  });

  const page = await browser.newPage();

  // Navigate to Admin Console — wait for login
  await page.goto('https://admin.google.com/ac/apps/gmail/authenticateemail', { waitUntil: 'networkidle2', timeout: 30000 });

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

  const results = { done: [], keyOnly: [], noKey: [], ncFailed: [], noDropdown: [] };

  for (const domain of domains) {
    process.stdout.write(`${domain} ... `);

    try {
      const { status, dkimKey } = await processDomain(page, domain);

      if (status === 'no_dropdown') {
        console.log('⚠ domain dropdown not found');
        results.noDropdown.push(domain);
        continue;
      }

      if (status === 'no_key') {
        console.log('⚠ DKIM key not found on page');
        results.noKey.push(domain);
        continue;
      }

      // Add TXT to Namecheap
      try {
        await ncAddTxt(domain, 'google._domainkey', dkimKey);
        console.log(`✓ TXT → Namecheap`);
      } catch (e) {
        console.log(`✗ Namecheap: ${e.message}`);
        results.ncFailed.push({ domain, dkimKey, error: e.message });
        continue;
      }

      if (status === 'started') {
        console.log(`  ✓ DKIM authentication started`);
        results.done.push(domain);
      } else {
        console.log(`  ⚠ key added to DNS but "Start authentication" button not found — check manually`);
        results.keyOnly.push(domain);
      }

    } catch (e) {
      console.log(`FAILED: ${e.message}`);
      results.noKey.push(domain);
    }

    await new Promise(r => setTimeout(r, 1000));
  }

  console.log('\n══════════════════════════════════════════');
  console.log(`DKIM enabled:       ${results.done.length}`);
  console.log(`Key added (manual): ${results.keyOnly.length}`);
  console.log(`No key found:       ${results.noKey.length}`);
  console.log(`No dropdown:        ${results.noDropdown.length}`);
  console.log(`Namecheap failed:   ${results.ncFailed.length}`);

  if (results.noKey.length + results.noDropdown.length > 0) {
    console.log('\n⚠ These domains need manual check in Admin Console → Apps → Gmail → Authenticate email:');
    [...results.noKey, ...results.noDropdown].forEach(d => console.log(`  - ${d}`));
  }
  if (results.keyOnly.length > 0) {
    console.log('\nDNS TXT added but "Start authentication" was not clicked — do it manually for:');
    results.keyOnly.forEach(d => console.log(`  - ${d}`));
  }

  // Save log
  const logFile = path.join(__dirname, 'dkim-results.json');
  fs.writeFileSync(logFile, JSON.stringify(results, null, 2));
  console.log(`\nLog saved to ${logFile}`);

  await browser.close();
  console.log('Done.');
}

main().catch(e => { console.error(e); process.exit(1); });
