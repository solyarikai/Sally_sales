/**
 * Apollo Companies Tab — God Mode Scraper
 *
 * KPI: 20,000 companies
 * ICP: Small agencies / service businesses with remote workers in UAE
 *
 * Approach:
 * 1. Use industry tag IDs where known (IT, Marketing, Retail)
 * 2. Use keyword search for all other industries
 * 3. DOM scraping of Companies tab (shows ALL results, no credit limit)
 * 4. Paginate through ALL available pages (up to 100 per search)
 * 5. Log EVERYTHING
 *
 * Usage:
 *   node scripts/apollo_companies_god.js                         # run all
 *   node scripts/apollo_companies_god.js --max-pages 100         # default 100
 *   node scripts/apollo_companies_god.js --resume                # resume
 *   node scripts/apollo_companies_god.js --test "design"         # single test
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const OUT_DIR = path.join(__dirname, '..', 'easystaff-global', 'data');
const RESULTS_FILE = path.join(OUT_DIR, 'uae_20k_companies.json');
const PROGRESS_FILE = path.join(OUT_DIR, 'uae_20k_progress.json');
const LOG_FILE = path.join(OUT_DIR, 'uae_20k_search_log.jsonl');

if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// Append-only log — one JSON per line
function logEntry(entry) {
  const record = { ts: ts(), ...entry };
  fs.appendFileSync(LOG_FILE, JSON.stringify(record) + '\n');
  console.log(`[${record.ts}] ${entry.msg || JSON.stringify(entry)}`);
}

// ================================================================
//  KNOWN INDUSTRY TAG IDs (discovered via quick filters)
// ================================================================

const INDUSTRY_TAG_IDS = {
  'information technology & services': '5567cd4773696439b10b0000',
  'marketing & advertising': '5567cd467369644d39040000',
  'retail': '5567ced173696450cb580000',
};

// ================================================================
//  SEARCH CONFIGS — every ICP industry/keyword
// ================================================================

function buildUrl(params) {
  const parts = [];
  if (params.tagId) parts.push(`organizationIndustryTagIds[]=${params.tagId}`);
  for (const loc of (params.locations || ['United Arab Emirates'])) {
    parts.push(`organizationLocations[]=${encodeURIComponent(loc)}`);
  }
  for (const size of (params.sizes || ['1,10', '11,20', '21,50', '51,100', '101,200'])) {
    parts.push(`organizationNumEmployeesRanges[]=${encodeURIComponent(size)}`);
  }
  if (params.keyword) parts.push(`qKeywords=${encodeURIComponent(params.keyword)}`);
  parts.push('sortAscending=false');
  parts.push('sortByField=recommendations_score');
  if (params.page) parts.push(`page=${params.page}`);
  return 'https://app.apollo.io/#/companies?' + parts.join('&');
}

function generateConfigs(testKeyword) {
  const configs = [];

  if (testKeyword) {
    // Check if it's a tag ID test
    const tagId = INDUSTRY_TAG_IDS[testKeyword.toLowerCase()];
    if (tagId) {
      configs.push({
        id: `test_tag_${tagId}`,
        label: `TEST TAG: "${testKeyword}"`,
        url: buildUrl({ tagId }),
        filters: { industry_tag: testKeyword, tag_id: tagId, location: 'UAE', size: '1-200' },
      });
    } else {
      configs.push({
        id: `test_${testKeyword}`,
        label: `TEST KW: "${testKeyword}"`,
        url: buildUrl({ keyword: testKeyword }),
        filters: { keyword: testKeyword, location: 'UAE', size: '1-200' },
      });
    }
    return configs;
  }

  // STRATEGY: Break each industry tag by SIZE RANGE
  // Each size range gets its OWN pagination (100 pages each)
  // This gives 5× more coverage per industry tag
  const SIZE_BUCKETS = [
    { range: '1,10', label: '1-10 emp' },
    { range: '11,20', label: '11-20 emp' },
    { range: '21,50', label: '21-50 emp' },
    { range: '51,100', label: '51-100 emp' },
    { range: '101,200', label: '101-200 emp' },
  ];

  // Group 1: Industry tags × size ranges (HIGHEST YIELD)
  for (const [name, tagId] of Object.entries(INDUSTRY_TAG_IDS)) {
    if (name === 'retail') continue; // Not ICP
    for (const size of SIZE_BUCKETS) {
      configs.push({
        id: `tag_${tagId}_${size.range}`,
        label: `[TAG] ${name} × ${size.label}`,
        url: buildUrl({ tagId, sizes: [size.range] }),
        filters: { industry_tag: name, tag_id: tagId, size_range: size.range, location: 'UAE' },
      });
    }
  }

  // Group 2: Keyword search — ONLY use keywords that qKeywords actually filters
  // NOTE: qKeywords on Companies tab may not filter. These are fallback.
  const ICP_KEYWORDS = [
    'software company', 'web development', 'mobile app',
    'digital marketing', 'creative agency', 'design studio',
    'media production', 'video production', 'animation',
    'management consulting', 'recruitment agency', 'staffing',
    'outsourcing', 'fintech', 'edtech', 'ecommerce',
    'event management', 'translation services',
  ];

  for (const kw of ICP_KEYWORDS) {
    configs.push({
      id: `kw_${kw.replace(/\s+/g, '_')}`,
      label: `[KW] "${kw}"`,
      url: buildUrl({ keyword: kw }),
      filters: { keyword: kw, location: 'UAE', size: '1-200' },
    });
  }

  return configs;
}

// ================================================================
//  LOGIN
// ================================================================

async function login(page) {
  logEntry({ msg: 'LOGIN: Starting...' });
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);
  if (page.url().includes('/people') || page.url().includes('/home') || page.url().includes('/companies')) {
    logEntry({ msg: 'LOGIN: Already logged in' });
    return;
  }
  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 30 });
  await sleep(500);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 30 });
  await page.click('button[type="submit"]');
  await sleep(8000);
  logEntry({ msg: 'LOGIN: Success' });
}

// ================================================================
//  DOM SCRAPER
// ================================================================

async function scrapePage(page) {
  return page.evaluate(() => {
    const companies = [];
    const seen = new Set();

    // Find company links — works on Companies tab
    const links = document.querySelectorAll('a[href*="/companies/"], a[data-to*="/companies/"], a[href*="/organizations/"], a[data-to*="/organizations/"]');
    for (const link of links) {
      const name = link.textContent?.trim() || '';
      if (!name || name.length < 2 || seen.has(name.toLowerCase())) continue;
      seen.add(name.toLowerCase());

      const href = link.getAttribute('href') || link.getAttribute('data-to') || '';
      const idMatch = href.match(/(?:companies|organizations)\/([a-f0-9]+)/);
      const id = idMatch ? idMatch[1] : '';

      // Get row for additional data
      const row = link.closest('[role="row"], tr') || link.parentElement?.parentElement;
      let employees = null;
      let linkedinUrl = '';

      if (row) {
        // Find employee count (standalone number in a cell)
        const cells = row.querySelectorAll('[role="gridcell"], td, div');
        for (const cell of cells) {
          const text = cell.textContent?.trim() || '';
          if (/^\d{1,6}$/.test(text)) {
            const num = parseInt(text);
            if (num > 0 && num < 500000) employees = num;
          }
        }
        // Find LinkedIn
        const li = row.querySelector('a[href*="linkedin.com"]');
        if (li) linkedinUrl = li.href;
      }

      companies.push({ name, id, employees, linkedin_url: linkedinUrl });
    }

    // Get total results count ("1-25 of 2.7M")
    let total = null;
    const allText = document.querySelectorAll('span, div');
    for (const el of allText) {
      const t = el.textContent?.trim() || '';
      const m = t.match(/of\s+([\d,]+\.?\d*)\s*([KMB]?)/i);
      if (m) {
        let n = parseFloat(m[1].replace(/,/g, ''));
        if (m[2] === 'K') n *= 1000;
        if (m[2] === 'M') n *= 1000000;
        if (m[2] === 'B') n *= 1000000000;
        if (n > 0) { total = Math.round(n); break; }
      }
    }

    // Get current page number
    let currentPage = 1;
    const pageInputs = document.querySelectorAll('input[type="number"], input[aria-label*="page"]');
    for (const inp of pageInputs) {
      const v = parseInt(inp.value);
      if (v > 0) currentPage = v;
    }

    return { companies, total, currentPage };
  });
}

async function clickNext(page) {
  return page.evaluate(() => {
    // Method 1: ">" button
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      if (b.textContent?.trim() === '>' && !b.disabled) { b.click(); return true; }
    }
    // Method 2: aria-label next
    for (const b of btns) {
      const al = (b.getAttribute('aria-label') || '').toLowerCase();
      if (al.includes('next') && !b.disabled) { b.click(); return true; }
    }
    // Method 3: pagination after active
    let foundActive = false;
    for (const b of btns) {
      if (foundActive && !b.disabled && /^\d+$/.test(b.textContent?.trim())) {
        b.click();
        return true;
      }
      if (b.getAttribute('aria-current') === 'page') foundActive = true;
    }
    return false;
  });
}

// ================================================================
//  SEARCH & SCRAPE
// ================================================================

async function searchAndScrape(page, config, maxPages) {
  logEntry({
    msg: `SEARCH: ${config.label}`,
    type: 'search_start',
    ...config.filters,
    url: config.url,
  });

  await page.goto(config.url, { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(4000);

  const allCompanies = [];
  let totalAvailable = null;
  let pageNum = 1;
  let emptyStreak = 0;

  while (pageNum <= maxPages) {
    const { companies, total } = await scrapePage(page);
    if (total && !totalAvailable) totalAvailable = total;

    if (companies.length === 0) {
      emptyStreak++;
      if (emptyStreak >= 2) break;
      await sleep(3000);
      const retry = await scrapePage(page);
      if (retry.companies.length === 0) break;
      companies.push(...retry.companies);
      emptyStreak = 0;
    } else {
      emptyStreak = 0;
    }

    allCompanies.push(...companies);

    // Log every page
    logEntry({
      type: 'page',
      search: config.label,
      page: pageNum,
      found: companies.length,
      total_available: totalAvailable,
      cumulative: allCompanies.length,
    });

    // Don't break on short pages — try next anyway (Apollo may render fewer links)
    // Only break if we got 0 results
    if (companies.length === 0) break;

    const hasNext = await clickNext(page);
    if (!hasNext) break;

    pageNum++;
    await sleep(1500 + Math.random() * 1500);
  }

  logEntry({
    msg: `DONE: ${config.label} → ${allCompanies.length} companies from ${pageNum} pages (${totalAvailable || '?'} available)`,
    type: 'search_done',
    search: config.label,
    scraped: allCompanies.length,
    available: totalAvailable,
    pages: pageNum,
  });

  return allCompanies;
}

// ================================================================
//  DEDUP & PROGRESS
// ================================================================

function dedup(companies) {
  const map = new Map();
  for (const c of companies) {
    const key = c.id || c.name?.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!key) continue;
    if (!map.has(key)) {
      map.set(key, { ...c, _sources: [c._source || ''] });
    } else {
      const ex = map.get(key);
      if (!ex.employees && c.employees) ex.employees = c.employees;
      if (!ex.linkedin_url && c.linkedin_url) ex.linkedin_url = c.linkedin_url;
      if (!ex.domain && c.domain) ex.domain = c.domain;
      if (c._source) ex._sources.push(c._source);
    }
  }
  return [...map.values()];
}

function loadProgress() {
  try { return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8')); }
  catch { return { completed: [], allCompanies: [] }; }
}

function saveAll(progress) {
  const unique = dedup(progress.allCompanies);
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify({
    completed: progress.completed,
    stats: { raw: progress.allCompanies.length, unique: unique.length, updated: ts() },
  }, null, 2));
  fs.writeFileSync(RESULTS_FILE, JSON.stringify(unique, null, 2));

  logEntry({
    msg: `=== SAVED: ${unique.length} unique companies (${progress.allCompanies.length} raw) ===`,
    type: 'progress',
    raw: progress.allCompanies.length,
    unique: unique.length,
    completed_searches: progress.completed.length,
  });
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const args = process.argv.slice(2);
  const maxPages = args.includes('--max-pages') ? parseInt(args[args.indexOf('--max-pages') + 1]) : 100;
  const resume = args.includes('--resume');
  const testKw = args.includes('--test') ? args[args.indexOf('--test') + 1] : null;

  const configs = generateConfigs(testKw);

  logEntry({
    msg: `=== APOLLO COMPANIES GOD SEARCH ===`,
    type: 'init',
    kpi: 20000,
    max_pages: maxPages,
    total_configs: configs.length,
    industry_tag_ids: Object.keys(INDUSTRY_TAG_IDS).length,
    keyword_configs: configs.filter(c => c.id.startsWith('kw_')).length,
  });

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900',
           '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage',
           '--disable-gpu'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36');

  try {
    await login(page);

    const progress = resume ? loadProgress() : { completed: [], allCompanies: [] };
    const remaining = configs.filter(c => !progress.completed.includes(c.id));

    logEntry({ msg: `Remaining: ${remaining.length} searches (${progress.completed.length} done)` });

    let num = 0;
    for (const config of remaining) {
      num++;
      console.log(`\n[${num}/${remaining.length}]`);

      try {
        const companies = await searchAndScrape(page, config, maxPages);

        for (const c of companies) c._source = config.label;
        progress.allCompanies.push(...companies);
        progress.completed.push(config.id);

        if (num % 3 === 0 || num === remaining.length) {
          saveAll(progress);
        }

        await sleep(3000 + Math.random() * 3000);
      } catch (err) {
        logEntry({ msg: `ERROR: ${config.label}: ${err.message}`, type: 'error' });
        saveAll(progress);
        if (err.message.includes('timeout')) {
          await sleep(10000);
          try {
            await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
            await sleep(3000);
          } catch { break; }
        }
      }
    }

    // Final stats
    const unique = dedup(progress.allCompanies);
    const sizes = { '1-10': 0, '11-50': 0, '51-100': 0, '101-200': 0, '200+': 0, unknown: 0 };
    for (const c of unique) {
      const e = c.employees || 0;
      if (e === 0) sizes.unknown++;
      else if (e <= 10) sizes['1-10']++;
      else if (e <= 50) sizes['11-50']++;
      else if (e <= 100) sizes['51-100']++;
      else if (e <= 200) sizes['101-200']++;
      else sizes['200+']++;
    }

    logEntry({
      msg: `\n=== FINAL: ${unique.length} unique companies ===`,
      type: 'final',
      total: unique.length,
      with_employees: unique.filter(c => c.employees).length,
      with_linkedin: unique.filter(c => c.linkedin_url).length,
      sizes,
    });

    saveAll(progress);
  } catch (err) {
    logEntry({ msg: `FATAL: ${err.message}`, type: 'fatal' });
    await page.screenshot({ path: path.join(OUT_DIR, 'apollo_god_fatal.png'), fullPage: true });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
