/**
 * Apollo Fintech Funded Companies — Quick Export
 *
 * Uses Apollo internal API (session cookies, free) to export
 * fintech companies that recently received funding (Seed/A/B).
 *
 * Usage:
 *   node scripts/apollo_fintech_funded.js
 *   node scripts/apollo_fintech_funded.js --max-pages 5
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const SESSION_FILE = path.join(__dirname, 'data', 'apollo_session.json');
const OUT_FILE = path.join(__dirname, '..', 'gathering-data', 'fintech_funded_companies.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// Parse args
let maxPages = 1;
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === '--max-pages' && process.argv[i + 1]) {
    maxPages = parseInt(process.argv[i + 1]) || 1;
  }
}

async function login(page) {
  console.log(`[${ts()}] Logging into Apollo...`);

  // Load saved cookies
  if (fs.existsSync(SESSION_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
    await page.setCookie(...cookies);
    console.log(`[${ts()}] Loaded ${cookies.length} saved cookies`);
  }

  await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies') || url.includes('/sequences')) {
    console.log(`[${ts()}] Already logged in`);
    return;
  }

  // Need to login
  console.log(`[${ts()}] Entering credentials...`);
  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 30 });
  await sleep(500);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 30 });
  await sleep(500);
  await page.click('button[type="submit"]');
  await sleep(5000);

  for (let i = 0; i < 30; i++) {
    const u = page.url();
    if (u.includes('/people') || u.includes('/home') || u.includes('/companies') || u.includes('/sequences')) {
      console.log(`[${ts()}] Login successful`);
      // Save cookies
      const cookies = await page.cookies();
      fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
      return;
    }
    await sleep(2000);
  }
  throw new Error('Login failed — stuck at: ' + page.url());
}

async function searchCompanies(page, params) {
  return page.evaluate(async (searchParams) => {
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.content : '';
      const res = await fetch('https://app.apollo.io/api/v1/mixed_companies/search', {
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
  }, params);
}

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  try {
    await login(page);

    // Navigate to companies page for proper context
    await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(2000);

    const allCompanies = [];

    for (let pageNum = 1; pageNum <= maxPages; pageNum++) {
      const params = {
        // Fintech keywords
        q_organization_keyword_tags: ['fintech', 'neobank', 'payments', 'blockchain', 'crypto', 'digital wallet', 'BaaS', 'payment platform'],
        // Target countries
        organization_locations: ['United Kingdom', 'Germany', 'Netherlands', 'United Arab Emirates', 'Singapore', 'Estonia', 'Lithuania', 'Poland'],
        // 11-200 employees
        organization_num_employees_ranges: ['11,50', '51,200'],
        // Funding filter: Seed, Series A, Series B
        organization_latest_funding_stage_cd: ['seed', 'series_a', 'series_b'],
        sort_by_field: '[none]',
        sort_ascending: false,
        page: pageNum,
        per_page: 25,
        display_mode: 'explorer_mode',
        context: 'companies-index-page',
        finder_version: 2,
      };

      console.log(`[${ts()}] Fetching page ${pageNum}...`);
      const result = await searchCompanies(page, params);

      if (result.error) {
        console.log(`[${ts()}] ERROR: ${result.error}`);
        break;
      }

      const accounts = result.accounts || [];
      const totalEntries = result.pagination?.total_entries || 0;

      if (pageNum === 1) {
        console.log(`[${ts()}] Total available: ${totalEntries} companies`);
      }

      if (accounts.length === 0) break;

      for (const acc of accounts) {
        allCompanies.push({
          domain: acc.domain || acc.website_url || '',
          name: acc.name || '',
          linkedin_url: acc.linkedin_url || '',
          estimated_num_employees: acc.estimated_num_employees || null,
          industries: acc.industries || [],
          city: acc.city || '',
          country: acc.country || '',
          latest_funding_stage: acc.latest_funding_stage || '',
          latest_funding_amount: acc.latest_funding_amount || null,
          total_funding: acc.total_funding || null,
          keywords: acc.keywords || [],
        });
      }

      console.log(`[${ts()}] Page ${pageNum}: ${accounts.length} companies (total: ${allCompanies.length})`);

      if (accounts.length < 25) break;
      await sleep(800 + Math.random() * 500);
    }

    // Dedup by domain
    const seen = new Set();
    const unique = allCompanies.filter(c => {
      const d = (c.domain || '').toLowerCase().replace(/^www\./, '');
      if (!d || seen.has(d)) return false;
      seen.add(d);
      return true;
    });

    // Save
    const outDir = path.dirname(OUT_FILE);
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(OUT_FILE, JSON.stringify(unique, null, 2));

    console.log(`\n[${ts()}] DONE: ${unique.length} unique companies saved to ${OUT_FILE}`);

    // Print summary
    for (const c of unique) {
      const emp = c.estimated_num_employees || '?';
      const funding = c.latest_funding_stage || '?';
      console.log(`  ${(c.domain || '').padEnd(35)} | ${(c.name || '').padEnd(30)} | ${String(emp).padStart(5)} emp | ${c.country || '?'} | ${funding}`);
    }

  } catch (e) {
    console.error(`[${ts()}] FATAL: ${e.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
