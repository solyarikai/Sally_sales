/**
 * Enrich job titles for leads without titles via Apollo internal API.
 *
 * Strategy:
 *   1. Read CSV with leads (no job title)
 *   2. Group leads by email domain
 *   3. For each domain batch, search Apollo people (no title filter, broad seniority)
 *   4. Match results back by email → fill job_title
 *   5. Export enriched CSV
 *
 * Usage:
 *   node enrich_titles_apollo.js --input data/imsaas_no_title.csv --output data/imsaas_enriched_titles.csv
 *   node enrich_titles_apollo.js --input data/imsaas_no_title.csv --output data/imsaas_enriched_titles.csv --headless
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const SESSION_FILE = path.join(__dirname, 'data', 'apollo_session.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// ── Args ──────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const get = (flag) => { const i = args.indexOf(flag); return i >= 0 && args[i+1] ? args[i+1] : null; };
const HEADLESS = args.includes('--headless');
const INPUT_CSV = get('--input') || path.join(__dirname, 'data', 'imsaas_no_title.csv');
const OUTPUT_CSV = get('--output') || path.join(__dirname, 'data', 'imsaas_enriched_titles.csv');
const BATCH_SIZE = parseInt(get('--batch-size') || '10');
const DELAY_MS = parseInt(get('--delay') || '1200');

// ── CSV parse/write ──────────────────────────────────────────────────────────
function parseCSV(content) {
  const lines = content.trim().split('\n');
  if (!lines.length) return [];
  const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g, '').trim());
  return lines.slice(1).map(line => {
    // Handle quoted fields with commas
    const values = [];
    let cur = '', inQ = false;
    for (const ch of line) {
      if (ch === '"') { inQ = !inQ; }
      else if (ch === ',' && !inQ) { values.push(cur.trim()); cur = ''; }
      else { cur += ch; }
    }
    values.push(cur.trim());
    const row = {};
    headers.forEach((h, i) => { row[h] = (values[i] || '').replace(/^"|"$/g, ''); });
    return row;
  });
}

function writeCSV(rows, filePath) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const escape = (v) => `"${String(v || '').replace(/"/g, '""')}"`;
  const lines = [headers.join(',')];
  for (const r of rows) {
    lines.push(headers.map(h => escape(r[h])).join(','));
  }
  fs.writeFileSync(filePath, lines.join('\n'), 'utf-8');
}

// ── Apollo login ──────────────────────────────────────────────────────────────
async function ensureLoggedIn(page) {
  await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  if (!page.url().includes('login')) {
    console.log(`[${ts()}] Already logged in`);
    return;
  }

  console.log(`[${ts()}] Logging in...`);
  await page.waitForSelector('input[name="email"]', { timeout: 15000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 40 });
  await sleep(300);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 40 });
  await sleep(300);
  await page.keyboard.press('Enter');
  await sleep(5000);

  await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const cookies = await page.cookies();
  fs.mkdirSync(path.dirname(SESSION_FILE), { recursive: true });
  fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
  console.log(`[${ts()}] Logged in, session saved`);
}

// ── Apollo internal API search ────────────────────────────────────────────────
async function searchByDomains(page, domains, pageNum = 1) {
  const results = await page.evaluate(async (searchParams) => {
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.content : '';
      const res = await fetch('https://app.apollo.io/api/v1/mixed_people/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Csrf-Token': csrfToken },
        credentials: 'include',
        body: JSON.stringify(searchParams),
      });
      if (!res.ok) return { error: `HTTP ${res.status}`, status: res.status };
      return await res.json();
    } catch (e) {
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
  return results;
}

// ── Main ──────────────────────────────────────────────────────────────────────
(async () => {
  console.log(`[${ts()}] Starting title enrichment`);
  console.log(`[${ts()}] Input:  ${INPUT_CSV}`);
  console.log(`[${ts()}] Output: ${OUTPUT_CSV}`);

  // Read input
  const content = fs.readFileSync(INPUT_CSV, 'utf-8');
  const leads = parseCSV(content);
  console.log(`[${ts()}] Loaded ${leads.length} leads`);

  // Build email → lead index, domain → emails map
  const emailIndex = {};
  const domainLeads = {};
  for (const lead of leads) {
    const email = lead.email?.toLowerCase().trim();
    if (!email) continue;
    emailIndex[email] = lead;
    const domain = email.split('@')[1];
    if (domain) {
      if (!domainLeads[domain]) domainLeads[domain] = [];
      domainLeads[domain].push(email);
    }
  }

  const uniqueDomains = Object.keys(domainLeads);
  console.log(`[${ts()}] Unique domains: ${uniqueDomains.length}`);
  console.log(`[${ts()}] Batch size: ${BATCH_SIZE} domains/request`);
  console.log(`[${ts()}] Total batches: ${Math.ceil(uniqueDomains.length / BATCH_SIZE)}`);

  // Launch browser
  const browser = await puppeteer.launch({
    headless: HEADLESS,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // Load session
  if (fs.existsSync(SESSION_FILE)) {
    try {
      const cookies = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
      await page.setCookie(...cookies);
      console.log(`[${ts()}] Loaded saved cookies`);
    } catch (e) {}
  }

  await ensureLoggedIn(page);

  // Process domains in batches
  const titleMap = {}; // email → title
  let matched = 0, batchNum = 0, totalBatches = Math.ceil(uniqueDomains.length / BATCH_SIZE);

  for (let i = 0; i < uniqueDomains.length; i += BATCH_SIZE) {
    const batch = uniqueDomains.slice(i, i + BATCH_SIZE);
    batchNum++;
    process.stdout.write(`[${ts()}] Batch ${batchNum}/${totalBatches} (${batch.slice(0,3).join(', ')}...) `);

    try {
      const data = await searchByDomains(page, batch);

      if (data.error) {
        console.log(`ERROR: ${data.error}`);
        await sleep(3000);
        continue;
      }

      const people = data.people || [];
      let batchMatched = 0;

      for (const p of people) {
        const pEmail = (p.email || '').toLowerCase().trim();
        if (pEmail && emailIndex[pEmail] && !emailIndex[pEmail]._enriched_title) {
          emailIndex[pEmail]._enriched_title = p.title || '';
          if (p.title) {
            titleMap[pEmail] = p.title;
            batchMatched++;
            matched++;
          }
        }
      }

      console.log(`→ ${people.length} people, ${batchMatched} matched`);
    } catch (e) {
      console.log(`ERROR: ${e.message}`);
    }

    await sleep(DELAY_MS);
  }

  await browser.close();

  console.log(`\n[${ts()}] Total matched: ${matched} / ${leads.length}`);

  // Write output — original leads with enriched title added
  const output = leads.map(lead => {
    const email = lead.email?.toLowerCase().trim();
    const title = titleMap[email] || '';
    return { ...lead, enriched_title: title };
  });

  fs.mkdirSync(path.dirname(OUTPUT_CSV), { recursive: true });
  writeCSV(output, OUTPUT_CSV);
  console.log(`[${ts()}] Saved → ${OUTPUT_CSV}`);

  // Stats
  const enriched = output.filter(r => r.enriched_title).length;
  const still_empty = output.filter(r => !r.enriched_title).length;
  console.log(`[${ts()}] Enriched: ${enriched}, Still no title: ${still_empty}`);
})();
