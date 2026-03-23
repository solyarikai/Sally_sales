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
      const accounts = result.accounts || [];
      totalEntries = result.pagination?.total_entries || totalEntries;

      // Build org lookup from accounts (has funding, employees, etc.)
      const orgMap = {};
      for (const acc of accounts) {
        const orgId = acc.organization_id || acc.id;
        if (orgId) orgMap[orgId] = acc;
      }

      if (pageNum === 1) {
        console.log(`[${ts()}] Total available: ${totalEntries} people (${accounts.length} accounts on page)`);
      }

      if (people.length === 0) break;

      for (const p of people) {
        // Match person to account by organization_id
        const orgId = p.organization_id || (p.organization || {}).id;
        const acc = orgMap[orgId] || {};
        const org = p.organization || {};
        allPeople.push({
          name: p.name || '',
          title: p.title || '',
          email: p.email || '',
          linkedin_url: p.linkedin_url || '',
          city: p.city || '',
          country: p.country || '',
          company_name: acc.name || org.name || p.organization_name || '',
          company_domain: acc.domain || acc.primary_domain || org.primary_domain || org.domain || '',
          company_linkedin: acc.linkedin_url || org.linkedin_url || '',
          company_employees: acc.estimated_num_employees || org.estimated_num_employees || null,
          company_industry: (acc.industries || []).join(', ') || org.industry || '',
          company_country: acc.country || org.country || '',
          company_funding_stage: acc.latest_funding_stage || org.latest_funding_stage || '',
          company_total_funding: acc.total_funding || org.total_funding || null,
          company_latest_funding_amount: acc.latest_funding_amount || null,
        });
      }

      if (pageNum % 5 === 0 || pageNum === 1) {
        console.log(`[${ts()}] Page ${pageNum}/${Math.ceil(totalEntries / 25)}: +${people.length} people (total: ${allPeople.length})`);
      }

      if (people.length === 0) break;
      if (pageNum >= (result.pagination?.total_pages || Infinity)) break;

      await sleep(800 + Math.random() * 500);
    }

    // Enrich with company funding data via organization/enrich API
    const domains = [...new Set(allPeople.map(p => p.company_domain).filter(Boolean))];
    console.log(`[${ts()}] Enriching ${domains.length} companies with funding data (org/enrich)...`);
    const orgData = {}; // domain -> { funding_stage, employees, country, ... }

    for (let i = 0; i < domains.length; i++) {
      const domain = domains[i];
      const result = await page.evaluate(async (d) => {
        try {
          const csrfMeta = document.querySelector('meta[name="csrf-token"]');
          const csrfToken = csrfMeta ? csrfMeta.content : '';
          const res = await fetch(`https://app.apollo.io/api/v1/organizations/enrich?domain=${encodeURIComponent(d)}`, {
            method: 'GET',
            headers: { 'X-Csrf-Token': csrfToken },
            credentials: 'include',
          });
          if (!res.ok) return { error: res.status };
          return await res.json();
        } catch (e) {
          return { error: e.message };
        }
      }, domain);

      if (!result.error && result.organization) {
        const org = result.organization;
        orgData[domain] = {
          funding_stage: org.latest_funding_stage || '',
          total_funding: org.total_funding || null,
          total_funding_printed: org.total_funding_printed || '',
          latest_funding_date: org.latest_funding_round_date || '',
          employees: org.estimated_num_employees || null,
          country: org.country || '',
          industry: org.industry || '',
          funding_events: org.funding_events || [],
        };
      }

      if ((i + 1) % 50 === 0) {
        const enriched = Object.keys(orgData).length;
        const withFunding = Object.values(orgData).filter(o => o.funding_stage).length;
        console.log(`[${ts()}]   ${i + 1}/${domains.length} done (${enriched} found, ${withFunding} with funding)`);
      }
      // Rate limit
      await sleep(200 + Math.random() * 200);
    }
    const enrichedCount = Object.keys(orgData).length;
    const withFundingCount = Object.values(orgData).filter(o => o.funding_stage).length;
    console.log(`[${ts()}] Enriched ${enrichedCount}/${domains.length} companies (${withFundingCount} with funding stage)`);

    // Merge enrichment into people
    for (const p of allPeople) {
      const d = (p.company_domain || '').toLowerCase().replace(/^www\./, '');
      const org = orgData[d];
      if (org) {
        p.company_funding_stage = org.funding_stage || p.company_funding_stage;
        p.company_total_funding = org.total_funding || p.company_total_funding;
        p.company_total_funding_printed = org.total_funding_printed || '';
        p.company_latest_funding_date = org.latest_funding_date || '';
        p.company_latest_funding_amount = null;
        p.company_employees = org.employees || p.company_employees;
        p.company_country = org.country || p.company_country;
        if (!p.company_industry && org.industry) p.company_industry = org.industry;
      }
    }

    // Clean email placeholder
    for (const p of allPeople) {
      if (p.email && p.email.includes('not_unlocked')) p.email = '';
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

    // Stats
    const withEmail = unique.filter(p => p.email).length;
    const withFunding = unique.filter(p => p.company_funding_stage).length;
    const companies = new Set(unique.map(p => p.company_domain)).size;

    console.log(`\n[${ts()}] DONE: ${unique.length} unique people from ${companies} companies`);
    console.log(`[${ts()}]   With email: ${withEmail}, With funding stage: ${withFunding}`);
    console.log(`[${ts()}] JSON: ${OUT_FILE}`);

    // Save CSV
    const CSV_FILE = OUT_FILE.replace('.json', '.csv');
    const csvHeader = 'funding_round,name,title,company,website,email,linkedin,company_country,employees';
    const csvRows = unique.map(p => {
      const esc = (s) => `"${(s || '').replace(/"/g, '""')}"`;
      return [
        esc(p.company_funding_stage),
        esc(p.name),
        esc(p.title),
        esc(p.company_name),
        esc(p.company_domain),
        esc(p.email),
        esc(p.linkedin_url),
        esc(p.company_country),
        p.company_employees || '',
      ].join(',');
    });
    fs.writeFileSync(CSV_FILE, csvHeader + '\n' + csvRows.join('\n'));
    console.log(`[${ts()}] CSV: ${CSV_FILE}`);

    // Print first 30
    console.log(`\n${'─'.repeat(140)}`);
    console.log(`${'Funding'.padEnd(12)} | ${'Name'.padEnd(25)} | ${'Title'.padEnd(28)} | ${'Company'.padEnd(22)} | ${'Domain'.padEnd(22)} | Email`);
    console.log(`${'─'.repeat(140)}`);
    for (const p of unique.slice(0, 30)) {
      console.log(
        `${(p.company_funding_stage || '?').padEnd(12)} | ` +
        `${(p.name || '').substring(0, 24).padEnd(25)} | ` +
        `${(p.title || '').substring(0, 27).padEnd(28)} | ` +
        `${(p.company_name || '').substring(0, 21).padEnd(22)} | ` +
        `${(p.company_domain || '').substring(0, 21).padEnd(22)} | ` +
        `${p.email || '-'}`
      );
    }
    if (unique.length > 30) console.log(`  ... and ${unique.length - 30} more`);

  } catch (e) {
    console.error(`[${ts()}] FATAL: ${e.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
