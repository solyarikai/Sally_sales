/**
 * Apollo Fintech Funded — People Export
 *
 * Exports decision-makers from recently funded fintech companies.
 * Uses Apollo internal People API via session cookies (free).
 *
 * Usage:
 *   node scripts/apollo_fintech_funded_people.js
 *   node scripts/apollo_fintech_funded_people.js --max-pages 30
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const SESSION_FILE = path.join(__dirname, 'data', 'apollo_session.json');
const OUT_FILE = path.join(__dirname, '..', 'gathering-data', 'fintech_funded_people.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// Parse args
let maxPages = 25;
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === '--max-pages' && process.argv[i + 1]) {
    maxPages = parseInt(process.argv[i + 1]) || 25;
  }
}

// Titles relevant for selling dev outsourcing services
const PERSON_TITLES = [
  'CTO',
  'Chief Technology Officer',
  'VP Engineering',
  'VP of Engineering',
  'Head of Engineering',
  'Engineering Director',
  'Director of Engineering',
  'Head of Development',
  'Head of Product',
  'VP Product',
  'VP of Product',
  'Chief Product Officer',
  'CPO',
  'CEO',
  'Founder',
  'Co-Founder',
  'COO',
];

async function login(page) {
  console.log(`[${ts()}] Logging into Apollo...`);

  if (fs.existsSync(SESSION_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
    await page.setCookie(...cookies);
    console.log(`[${ts()}] Loaded saved cookies`);
  }

  await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies') || url.includes('/sequences')) {
    console.log(`[${ts()}] Already logged in`);
    return;
  }

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
      const cookies = await page.cookies();
      fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
      return;
    }
    await sleep(2000);
  }
  throw new Error('Login failed — stuck at: ' + page.url());
}

async function searchPeople(page, params) {
  return page.evaluate(async (searchParams) => {
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
    await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(2000);

    const allPeople = [];
    let totalEntries = 0;

    for (let pageNum = 1; pageNum <= maxPages; pageNum++) {
      const params = {
        // Company filters
        q_organization_keyword_tags: ['fintech', 'neobank', 'payments', 'blockchain', 'crypto', 'digital wallet', 'BaaS', 'payment platform'],
        organization_locations: ['United Kingdom', 'Germany', 'Netherlands', 'United Arab Emirates', 'Singapore', 'Estonia', 'Lithuania', 'Poland', 'Czech Republic', 'Cyprus'],
        organization_num_employees_ranges: ['11,50', '51,200'],
        organization_latest_funding_stage_cd: ['seed', 'series_a', 'series_b', 'series_c'],
        // People filters — titles for selling dev services
        person_titles: PERSON_TITLES,
        // Pagination
        page: pageNum,
        per_page: 25,
        display_mode: 'explorer_mode',
        context: 'people-index-page',
        finder_version: 2,
      };

      const result = await searchPeople(page, params);

      if (result.error) {
        console.log(`[${ts()}] p${pageNum} ERROR: ${result.error}`);
        if (result.status === 422 || result.status === 429) {
          console.log(`[${ts()}] Rate limited or invalid request, stopping.`);
          break;
        }
        await sleep(5000);
        continue;
      }

      const people = result.people || [];
      totalEntries = result.pagination?.total_entries || totalEntries;

      if (pageNum === 1) {
        console.log(`[${ts()}] Total available: ${totalEntries} people`);
      }

      if (people.length === 0) break;

      for (const p of people) {
        const org = p.organization || {};
        allPeople.push({
          name: p.name || '',
          title: p.title || '',
          linkedin_url: p.linkedin_url || '',
          city: p.city || '',
          country: p.country || '',
          company_name: org.name || p.organization_name || '',
          company_domain: org.primary_domain || org.domain || p.organization?.website_url || '',
          company_linkedin: org.linkedin_url || '',
          company_employees: org.estimated_num_employees || null,
          company_industry: org.industry || '',
          company_country: org.country || '',
          company_funding_stage: org.latest_funding_stage || '',
          company_total_funding: org.total_funding || null,
        });
      }

      if (pageNum % 5 === 0 || pageNum === 1) {
        console.log(`[${ts()}] Page ${pageNum}/${Math.ceil(totalEntries / 25)}: +${people.length} people (total: ${allPeople.length})`);
      }

      if (people.length === 0) break;
      if (pageNum >= (result.pagination?.total_pages || Infinity)) break;

      await sleep(800 + Math.random() * 500);
    }

    // Dedup by linkedin_url or name+company
    const seen = new Set();
    const unique = allPeople.filter(p => {
      const key = p.linkedin_url || `${p.name}__${p.company_domain}`.toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Save
    const outDir = path.dirname(OUT_FILE);
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(OUT_FILE, JSON.stringify(unique, null, 2));

    console.log(`\n[${ts()}] DONE: ${unique.length} unique people from ${new Set(unique.map(p => p.company_domain)).size} companies`);
    console.log(`[${ts()}] Saved to ${OUT_FILE}`);

    // Print summary
    console.log(`\n${'─'.repeat(130)}`);
    console.log(`${'Name'.padEnd(25)} | ${'Title'.padEnd(30)} | ${'Company'.padEnd(25)} | ${'Domain'.padEnd(25)} | ${'Country'.padEnd(12)} | Funding`);
    console.log(`${'─'.repeat(130)}`);
    for (const p of unique.slice(0, 50)) {
      console.log(
        `${(p.name || '').substring(0, 24).padEnd(25)} | ` +
        `${(p.title || '').substring(0, 29).padEnd(30)} | ` +
        `${(p.company_name || '').substring(0, 24).padEnd(25)} | ` +
        `${(p.company_domain || '').substring(0, 24).padEnd(25)} | ` +
        `${(p.company_country || '').substring(0, 11).padEnd(12)} | ` +
        `${p.company_funding_stage || '?'}`
      );
    }
    if (unique.length > 50) console.log(`  ... and ${unique.length - 50} more`);

  } catch (e) {
    console.error(`[${ts()}] FATAL: ${e.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
