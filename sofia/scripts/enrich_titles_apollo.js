/**
 * Enrich job titles for leads without titles via Apollo internal API.
 *
 * Usage:
 *   node enrich_titles_apollo.js
 *   node enrich_titles_apollo.js --batch-size 5 --delay 1500
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');


puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS  = 'UQdzDShCjAi5Nil!!';
const SESSION_FILE = path.join(__dirname, 'data', 'apollo_session.json');

const INPUT_CSV  = path.join(__dirname, 'data', 'imsaas_no_title.csv');
const OUTPUT_CSV = path.join(__dirname, 'data', 'imsaas_enriched_titles.csv');

const args       = process.argv.slice(2);
const getArg     = (f) => { const i = args.indexOf(f); return i >= 0 && args[i+1] ? args[i+1] : null; };
const BATCH_SIZE = parseInt(getArg('--batch-size') || '10');
const DELAY_MS   = parseInt(getArg('--delay')      || '1500');
const MAX_PAGES  = 3;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts()      { return new Date().toISOString().replace('T',' ').slice(0,19); }

// ── CSV ───────────────────────────────────────────────────────────────────────
function readLeads() {
  const content = fs.readFileSync(INPUT_CSV, 'utf-8');
  return csv.parse(content, { columns: true, skip_empty_lines: true, trim: true });
}

function writeCSV(rows) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const esc = v => `"${String(v||'').replace(/"/g,'""')}"`;
  const lines = [headers.join(','), ...rows.map(r => headers.map(h => esc(r[h])).join(','))];
  fs.writeFileSync(OUTPUT_CSV, lines.join('\n'), 'utf-8');
}

// ── Apollo login ──────────────────────────────────────────────────────────────
async function login(page) {
  await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  if (!page.url().includes('login')) {
    console.log(`[${ts()}] Session valid`);
    return;
  }

  console.log(`[${ts()}] Logging in...`);
  await page.waitForSelector('input[name="email"]', { timeout: 15000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 50 });
  await sleep(300);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 50 });
  await sleep(300);
  await page.keyboard.press('Enter');
  await sleep(6000);

  await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const cookies = await page.cookies();
  fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
  console.log(`[${ts()}] Logged in OK`);
}

// ── API call ──────────────────────────────────────────────────────────────────
async function searchDomains(page, domains, pageNum) {
  return page.evaluate(async (payload) => {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
      const res = await fetch('https://app.apollo.io/api/v1/mixed_people/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Csrf-Token': csrf },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      if (!res.ok) return { error: `HTTP ${res.status}`, status: res.status, preview: text.slice(0,100) };
      return JSON.parse(text);
    } catch(e) {
      return { error: e.message };
    }
  }, {
    q_organization_domains_list: domains,
    page: pageNum,
    per_page: 100,
    display_mode: 'explorer_mode',
    context: 'people-index-page',
    finder_version: 2,
  });
}

// ── Main ──────────────────────────────────────────────────────────────────────
(async () => {
  console.log(`[${ts()}] Enrich titles via Apollo`);

  const leads = readLeads();
  console.log(`[${ts()}] Loaded ${leads.length} leads`);

  // Index by email, group by domain
  const emailIndex = {};
  const domainMap  = {};
  for (const lead of leads) {
    const email = (lead.email || '').toLowerCase().trim();
    if (!email) continue;
    emailIndex[email] = lead;
    const domain = email.split('@')[1];
    if (domain) {
      domainMap[domain] = domainMap[domain] || [];
      domainMap[domain].push(email);
    }
  }

  const domains = Object.keys(domainMap);
  const totalBatches = Math.ceil(domains.length / BATCH_SIZE);
  console.log(`[${ts()}] Domains: ${domains.length}, Batches: ${totalBatches}`);

  // Launch browser
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36');

  // Load cookies
  if (fs.existsSync(SESSION_FILE)) {
    try {
      const cookies = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
      await page.setCookie(...cookies);
    } catch(e) {}
  }

  await login(page);

  const titleMap = {};
  let matched = 0;

  for (let i = 0; i < domains.length; i += BATCH_SIZE) {
    const batch   = domains.slice(i, i + BATCH_SIZE);
    const batchNo = Math.floor(i / BATCH_SIZE) + 1;

    for (let p = 1; p <= MAX_PAGES; p++) {
      process.stdout.write(`[${ts()}] [${batchNo}/${totalBatches}] p${p} `);

      const data = await searchDomains(page, batch, p);

      if (data.error) {
        console.log(`ERR: ${data.error}`);
        // If session expired, re-login
        if (data.status === 401 || data.status === 403) {
          await login(page);
        }
        await sleep(3000);
        break;
      }

      const people = data.people || [];
      let hit = 0;
      for (const person of people) {
        const em = (person.email || '').toLowerCase().trim();
        if (em && emailIndex[em] && !titleMap[em] && person.title) {
          titleMap[em] = person.title;
          hit++;
          matched++;
        }
      }
      console.log(`${people.length} results, ${hit} new titles (total: ${matched})`);

      if (people.length < 50) break; // last page
      await sleep(DELAY_MS);
    }

    await sleep(DELAY_MS);
  }

  await browser.close();
  console.log(`\n[${ts()}] Done. Matched ${matched} / ${leads.length}`);

  // Write output
  const output = leads.map(lead => ({
    ...lead,
    enriched_title: titleMap[(lead.email||'').toLowerCase().trim()] || '',
  }));
  writeCSV(output);

  const enriched   = output.filter(r => r.enriched_title).length;
  const still_empty = leads.length - enriched;
  console.log(`[${ts()}] Enriched: ${enriched} | Still empty: ${still_empty}`);
  console.log(`[${ts()}] Saved → ${OUTPUT_CSV}`);
})();
