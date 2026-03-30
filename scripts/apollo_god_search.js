/**
 * Apollo God-Mode UAE Agency Search
 *
 * KPI: 5,000 target companies across UAE
 *
 * Strategy A: Company name keywords (80+ queries × 3 UAE cities)
 * Strategy B: Broad seniority search — ALL founders/CEOs at small companies
 *             (no keyword/industry constraint → post-filter offline)
 *
 * Uses API response interception for structured data (domain, industry, employee count).
 * Falls back to DOM scraping if interception fails.
 *
 * Usage:
 *   node scripts/apollo_god_search.js                    # run all strategies
 *   node scripts/apollo_god_search.js --strategy A       # keywords only
 *   node scripts/apollo_god_search.js --strategy B       # broad seniority only
 *   node scripts/apollo_god_search.js --resume           # resume from progress file
 *   node scripts/apollo_god_search.js --max-pages 5      # limit pages per search (default 10)
 *   node scripts/apollo_god_search.js --city Dubai       # single city only
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const OUT_DIR = path.join(__dirname, '..', 'easystaff-global', 'data');
const RESULTS_FILE = path.join(OUT_DIR, 'uae_god_search_companies.json');
const PEOPLE_FILE = path.join(OUT_DIR, 'uae_god_search_people.json');
const PROGRESS_FILE = path.join(OUT_DIR, 'uae_god_search_progress.json');
const API_LOG_FILE = path.join(OUT_DIR, 'uae_god_search_api_log.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ================================================================
//  SEARCH CONFIGURATIONS
// ================================================================

const UAE_CITIES = [
  'Dubai, United Arab Emirates',
  'Abu Dhabi, United Arab Emirates',
  'Sharjah, United Arab Emirates',
];

// Strategy A: 80+ company name keywords
const KEYWORDS = [
  // --- Original 32 (proven) ---
  'marketing agency', 'digital agency', 'media production', 'staffing agency',
  'creative agency', 'advertising agency', 'event production', 'branding agency',
  'consulting firm', 'design agency', 'production house', 'film production',
  'video production', 'animation studio', 'PR agency', 'social media agency',
  'UX agency', 'content agency', 'post production', 'SEO agency',
  'web design', 'software development', 'IT services', 'game studio',
  'talent management', 'influencer agency', 'photography studio', 'SaaS',
  'tech startup', 'app development', 'e-commerce', 'motion graphics',
  'web development',

  // --- Professional services ---
  'recruitment agency', 'recruitment consultancy', 'HR consultancy',
  'HR outsourcing', 'management consulting', 'business consulting',
  'outsourcing', 'BPO', 'IT outsourcing', 'IT consulting',
  'accounting firm', 'bookkeeping services', 'translation services',
  'localization', 'architecture firm', 'interior design',
  'engineering consultancy', 'legal services',

  // --- Digital / tech (broader) ---
  'digital marketing', 'performance marketing', 'growth agency',
  'data analytics', 'AI consulting', 'cloud consulting',
  'cybersecurity', 'DevOps', 'mobile development', 'mobile app',
  'product design', 'UI design', 'web agency', 'ecommerce',
  'PPC agency', 'email marketing', 'automation agency',
  'CRM consulting', 'ERP consulting', 'software house',

  // --- Tech verticals ---
  'fintech', 'edtech', 'healthtech', 'proptech', 'martech',
  'insurtech', 'logistics tech', 'regtech', 'legaltech',

  // --- Media & entertainment ---
  'podcast production', 'music production', 'recording studio',
  'VFX studio', 'CGI', '3D studio', 'audio production',
  'content creation', 'live streaming', 'broadcast',

  // --- Broader service terms ---
  'digital solutions', 'tech solutions', 'creative studio',
  'innovation lab', 'digital transformation', 'development studio',
  'digital studio', 'media agency', 'communications agency',
  'integrated agency', 'strategy consulting', 'research firm',
  'market research', 'training company', 'coaching firm',
  'development company', 'technology company',
];

// Strategy B: Broad seniority × company size
const SENIORITIES = ['founder', 'c_suite', 'owner'];
const SIZE_RANGES = ['1,10', '11,20', '21,50', '51,100', '101,200'];

// Offline industry exclusion for Strategy B results
const EXCLUDE_KEYWORDS = [
  'restaurant', 'café', 'cafe', 'catering', 'food', 'bakery', 'kitchen',
  'hotel', 'hospitality', 'resort', 'spa', 'salon', 'beauty',
  'construction', 'contracting', 'building', 'real estate', 'property',
  'trading', 'import', 'export', 'wholesale', 'retail', 'supermarket',
  'shipping', 'freight', 'cargo', 'logistics', 'warehouse',
  'oil', 'gas', 'petroleum', 'mining', 'steel', 'metals',
  'medical', 'hospital', 'clinic', 'pharmacy', 'dental',
  'school', 'university', 'nursery', 'kindergarten',
  'laundry', 'cleaning', 'maintenance', 'plumbing', 'electrical',
  'car', 'auto', 'garage', 'vehicle', 'transport',
  'furniture', 'textile', 'garment', 'fabric',
  'jewelry', 'gold', 'diamond', 'watch',
  'travel', 'tourism', 'airline', 'cruise',
  'bank', 'insurance', 'exchange',
  'government', 'ministry', 'municipality', 'police', 'military',
  'church', 'mosque', 'temple',
];

// ================================================================
//  URL BUILDER
// ================================================================

function buildSearchUrl(params) {
  const base = 'https://app.apollo.io/#/people?';
  const parts = [];

  // Location
  for (const loc of (params.locations || [])) {
    parts.push(`personLocations[]=${encodeURIComponent(loc)}`);
  }

  // Company name keyword
  if (params.keyword) {
    parts.push(`qOrganizationName=${encodeURIComponent(params.keyword)}`);
  }

  // Seniority
  for (const sen of (params.seniorities || [])) {
    parts.push(`personSeniorities[]=${encodeURIComponent(sen)}`);
  }

  // Company size ranges
  for (const range of (params.sizeRanges || [])) {
    parts.push(`organizationNumEmployeesRanges[]=${encodeURIComponent(range)}`);
  }

  return base + parts.join('&');
}

// ================================================================
//  GENERATE ALL SEARCH CONFIGS
// ================================================================

function generateSearchConfigs(strategy, cityFilter) {
  const configs = [];
  const cities = cityFilter
    ? UAE_CITIES.filter(c => c.toLowerCase().includes(cityFilter.toLowerCase()))
    : UAE_CITIES;

  if (strategy === 'A' || strategy === 'all') {
    // Strategy A: keyword × city
    for (const city of cities) {
      for (const kw of KEYWORDS) {
        configs.push({
          id: `A_${city.split(',')[0]}_${kw}`,
          strategy: 'A',
          label: `[A] "${kw}" in ${city.split(',')[0]}`,
          url: buildSearchUrl({
            locations: [city],
            keyword: kw,
          }),
        });
      }
    }
  }

  if (strategy === 'B' || strategy === 'all') {
    // Strategy B: seniority × size × city (no keyword)
    for (const city of cities) {
      for (const size of SIZE_RANGES) {
        for (const sen of SENIORITIES) {
          configs.push({
            id: `B_${city.split(',')[0]}_${sen}_${size}`,
            strategy: 'B',
            label: `[B] ${sen} at ${size} emp in ${city.split(',')[0]}`,
            url: buildSearchUrl({
              locations: [city],
              seniorities: [sen],
              sizeRanges: [size],
            }),
          });
        }
      }
    }
  }

  return configs;
}

// ================================================================
//  LOGIN
// ================================================================

async function login(page) {
  console.log('[LOGIN] Logging into Apollo...');
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  if (page.url().includes('/people') || page.url().includes('/home')) {
    console.log('  Already logged in');
    return;
  }

  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 30 });
  await sleep(500);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 30 });
  await sleep(500);
  await page.click('button[type="submit"]');
  await sleep(5000);

  for (let i = 0; i < 30; i++) {
    if (page.url().includes('/people') || page.url().includes('/home') || page.url().includes('/sequences')) {
      console.log('  Login successful');
      return;
    }
    await sleep(2000);
  }
  throw new Error('Login failed — stuck at: ' + page.url());
}

// ================================================================
//  SCRAPE WITH API INTERCEPTION
// ================================================================

async function scrapeSearch(page, config, maxPages) {
  const allPeople = [];
  let interceptedData = [];

  // Set up API response interception
  const responseHandler = async (response) => {
    const url = response.url();
    if (url.includes('mixed_people/search') || url.includes('people/search')) {
      try {
        const data = await response.json();
        if (data.people && data.people.length > 0) {
          interceptedData.push(...data.people);
        }
      } catch (e) { /* ignore parse errors */ }
    }
  };
  page.on('response', responseHandler);

  try {
    // Navigate to search URL
    await page.goto(config.url, { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(3000);

    let pageNum = 1;

    while (pageNum <= maxPages) {
      // Wait for API response
      await sleep(2000 + Math.random() * 1000);

      // Check if we got API data
      const beforeCount = interceptedData.length;

      // Also try DOM scraping as fallback
      const domPeople = await scrapeDom(page);

      if (interceptedData.length > beforeCount) {
        // API interception worked — we have richer data
        const newPeople = interceptedData.slice(beforeCount);
        console.log(`  ${config.label} p${pageNum}: ${newPeople.length} people (API)`);
      } else if (domPeople.length > 0) {
        // Fallback to DOM data
        console.log(`  ${config.label} p${pageNum}: ${domPeople.length} people (DOM)`);
        // Convert DOM format to API-like format
        for (const p of domPeople) {
          interceptedData.push({
            name: p.name,
            title: p.title,
            organization: { name: p.company },
            organization_id: p.orgId,
            linkedin_url: p.linkedin,
            _source: 'dom',
          });
        }
      } else {
        console.log(`  ${config.label} p${pageNum}: 0 results — stopping`);
        break;
      }

      // Check for "no results" indicator
      const noResults = await page.evaluate(() => {
        const text = document.body.innerText || '';
        return text.includes('No people match') || text.includes('0 results') || text.includes('No results found');
      });
      if (noResults) break;

      // Try next page
      const hasNext = await clickNextPage(page);
      if (!hasNext) break;

      pageNum++;
      await sleep(2000 + Math.random() * 2000);
    }

  } finally {
    page.off('response', responseHandler);
  }

  return interceptedData;
}

// DOM scraper (fallback)
async function scrapeDom(page) {
  return page.evaluate(() => {
    const rows = [];
    const allCells = document.querySelectorAll('[role="gridcell"][aria-rowindex]');
    const rowIndices = new Set();
    for (const cell of allCells) rowIndices.add(cell.getAttribute('aria-rowindex'));

    for (const rowIndex of rowIndices) {
      const getCell = (col) => document.querySelector(`[role="gridcell"][aria-rowindex="${rowIndex}"][aria-colindex="${col}"]`);

      const nameCell = getCell(1);
      const nameLink = nameCell?.querySelector('a[data-to*="/people/"]');
      const name = nameLink?.textContent?.trim() || nameCell?.textContent?.trim() || '';
      if (!name || name.length < 2) continue;

      const titleCell = getCell(2);
      const title = titleCell?.textContent?.trim() || '';

      const companyCell = getCell(3);
      const companyLink = companyCell?.querySelector('a[data-to*="/organizations/"]');
      const company = companyLink?.textContent?.trim() || companyCell?.textContent?.trim() || '';
      const orgId = companyLink?.getAttribute('data-to')?.match(/organizations\/([a-f0-9]+)/)?.[1] || '';

      const linkedinCell = getCell(9);
      const linkedinLink = linkedinCell?.querySelector('a[href*="linkedin.com"]');
      const linkedin = linkedinLink?.href || '';

      if (title === 'Access email' || title === 'Access Mobile') continue;
      rows.push({ name, title, company, orgId, linkedin });
    }
    return rows;
  });
}

async function clickNextPage(page) {
  return page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
      if (ariaLabel.includes('next') || ariaLabel.includes('right-page')) {
        if (!btn.disabled) { btn.click(); return true; }
      }
    }
    const pageButtons = document.querySelectorAll('[class*="pagination"] button, [class*="Pagination"] button');
    let foundActive = false;
    for (const btn of pageButtons) {
      if (foundActive && !btn.disabled) { btn.click(); return true; }
      if (btn.getAttribute('aria-current') === 'page' || btn.classList.contains('active')) foundActive = true;
    }
    return false;
  });
}

// ================================================================
//  COMPANY EXTRACTION & DEDUP
// ================================================================

function extractCompanies(allPeople) {
  const companies = new Map();

  for (const person of allPeople) {
    const org = person.organization || {};
    const orgId = person.organization_id || org.id || '';
    const orgName = org.name || person._company || '';
    // Use orgId if available, otherwise fallback to normalized name
    const key = orgId || orgName.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!key) continue;

    if (!companies.has(key)) {
      companies.set(key, {
        id: orgId,
        name: orgName,
        domain: org.primary_domain || org.website_url || '',
        industry: org.industry || '',
        keywords: org.keywords || [],
        employees: org.estimated_num_employees || null,
        city: org.city || '',
        state: org.state || '',
        country: org.country || '',
        linkedin_url: org.linkedin_url || '',
        short_description: org.short_description || '',
        founded_year: org.founded_year || null,
        people: [],
        _sources: [],
      });
    }

    const comp = companies.get(key);
    // Enrich with any new data
    if (!comp.domain && (org.primary_domain || org.website_url)) {
      comp.domain = org.primary_domain || org.website_url;
    }
    if (!comp.industry && org.industry) comp.industry = org.industry;
    if (!comp.employees && org.estimated_num_employees) comp.employees = org.estimated_num_employees;

    comp.people.push({
      name: person.name || '',
      title: person.title || '',
      seniority: person.seniority || '',
      city: person.city || '',
      country: person.country || '',
      linkedin_url: person.linkedin_url || '',
      email: person.email || '',
    });
  }

  return companies;
}

function filterOfflineCompanies(companies) {
  const filtered = new Map();
  let excluded = 0;

  for (const [key, comp] of companies) {
    const nameLower = (comp.name || '').toLowerCase();
    const industryLower = (comp.industry || '').toLowerCase();
    const combined = nameLower + ' ' + industryLower;

    const isExcluded = EXCLUDE_KEYWORDS.some(kw => combined.includes(kw));
    if (isExcluded) {
      excluded++;
      continue;
    }
    filtered.set(key, comp);
  }

  console.log(`  Excluded ${excluded} offline companies (${EXCLUDE_KEYWORDS.length} filter keywords)`);
  return filtered;
}

// ================================================================
//  PROGRESS TRACKING
// ================================================================

function loadProgress() {
  try {
    return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));
  } catch {
    return { completed: [], allPeople: [] };
  }
}

function saveProgress(progress) {
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const args = process.argv.slice(2);
  const strategyArg = args.includes('--strategy') ? args[args.indexOf('--strategy') + 1] : 'all';
  const maxPages = args.includes('--max-pages') ? parseInt(args[args.indexOf('--max-pages') + 1]) : 10;
  const resume = args.includes('--resume');
  const cityFilter = args.includes('--city') ? args[args.indexOf('--city') + 1] : null;
  const dryRun = args.includes('--dry-run');

  const configs = generateSearchConfigs(strategyArg, cityFilter);
  console.log(`\n=== APOLLO GOD-MODE UAE SEARCH ===`);
  console.log(`Strategy: ${strategyArg}`);
  console.log(`Cities: ${cityFilter || 'all (Dubai, Abu Dhabi, Sharjah)'}`);
  console.log(`Max pages per search: ${maxPages}`);
  console.log(`Total search configs: ${configs.length}`);
  console.log(`  Strategy A (keywords): ${configs.filter(c => c.strategy === 'A').length}`);
  console.log(`  Strategy B (broad seniority): ${configs.filter(c => c.strategy === 'B').length}`);

  if (dryRun) {
    console.log('\n--- DRY RUN: Search URLs ---');
    for (const c of configs.slice(0, 20)) {
      console.log(`  ${c.label}`);
      console.log(`    ${c.url.substring(0, 120)}...`);
    }
    console.log(`  ... and ${Math.max(0, configs.length - 20)} more`);
    return;
  }

  // Load progress for resume
  const progress = resume ? loadProgress() : { completed: [], allPeople: [] };
  const remaining = configs.filter(c => !progress.completed.includes(c.id));
  console.log(`\nRemaining searches: ${remaining.length} (${progress.completed.length} already done)`);
  console.log(`People collected so far: ${progress.allPeople.length}`);

  // Launch browser
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

    let searchNum = 0;
    const totalSearches = remaining.length;
    let consecutiveEmpty = 0;

    for (const config of remaining) {
      searchNum++;
      console.log(`\n[${searchNum}/${totalSearches}] ${config.label}`);

      try {
        const people = await scrapeSearch(page, config, maxPages);

        if (people.length === 0) {
          consecutiveEmpty++;
          if (consecutiveEmpty > 10) {
            console.log('  WARNING: 10 consecutive empty results — possible rate limit or session issue');
            console.log('  Waiting 30s before continuing...');
            await sleep(30000);
            consecutiveEmpty = 0;
          }
        } else {
          consecutiveEmpty = 0;
          progress.allPeople.push(...people);
        }

        progress.completed.push(config.id);

        // Save progress every 5 searches
        if (searchNum % 5 === 0) {
          saveProgress(progress);
          // Also save intermediate company results
          const companies = extractCompanies(progress.allPeople);
          console.log(`\n  --- Progress: ${progress.allPeople.length} people → ${companies.size} unique companies ---\n`);
        }

        // Rate limiting between searches
        const delay = 3000 + Math.random() * 3000;
        await sleep(delay);

      } catch (err) {
        console.log(`  ERROR: ${err.message}`);
        // Save progress on error
        saveProgress(progress);

        // Try to recover
        if (err.message.includes('timeout') || err.message.includes('Navigation')) {
          console.log('  Attempting recovery...');
          await sleep(10000);
          try {
            await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
            await sleep(3000);
          } catch {
            console.log('  Recovery failed — stopping');
            break;
          }
        }
      }
    }

    // ==================== FINAL RESULTS ====================
    console.log('\n\n=== FINAL RESULTS ===');
    saveProgress(progress);

    const allCompanies = extractCompanies(progress.allPeople);
    console.log(`Total people scraped: ${progress.allPeople.length}`);
    console.log(`Total unique companies (raw): ${allCompanies.size}`);

    // Apply offline filter for Strategy B results
    const filteredCompanies = filterOfflineCompanies(allCompanies);
    console.log(`Total unique companies (filtered): ${filteredCompanies.size}`);

    // Stats
    const withDomain = [...filteredCompanies.values()].filter(c => c.domain).length;
    const withIndustry = [...filteredCompanies.values()].filter(c => c.industry).length;
    const withEmployees = [...filteredCompanies.values()].filter(c => c.employees).length;
    console.log(`  With domain: ${withDomain}`);
    console.log(`  With industry: ${withIndustry}`);
    console.log(`  With employee count: ${withEmployees}`);

    // City distribution
    const cityDist = {};
    for (const c of filteredCompanies.values()) {
      const city = c.city || '(unknown)';
      cityDist[city] = (cityDist[city] || 0) + 1;
    }
    console.log('\n  City distribution:');
    for (const [city, count] of Object.entries(cityDist).sort((a, b) => b[1] - a[1]).slice(0, 10)) {
      console.log(`    ${city}: ${count}`);
    }

    // Employee size distribution
    const sizeDist = { '1-10': 0, '11-50': 0, '51-100': 0, '101-200': 0, '200+': 0, 'unknown': 0 };
    for (const c of filteredCompanies.values()) {
      const emp = c.employees || 0;
      if (emp === 0) sizeDist['unknown']++;
      else if (emp <= 10) sizeDist['1-10']++;
      else if (emp <= 50) sizeDist['11-50']++;
      else if (emp <= 100) sizeDist['51-100']++;
      else if (emp <= 200) sizeDist['101-200']++;
      else sizeDist['200+']++;
    }
    console.log('\n  Company size distribution:');
    for (const [range, count] of Object.entries(sizeDist)) {
      console.log(`    ${range}: ${count}`);
    }

    // Save results
    const companiesArray = [...filteredCompanies.values()].sort((a, b) => (b.employees || 0) - (a.employees || 0));
    fs.writeFileSync(RESULTS_FILE, JSON.stringify(companiesArray, null, 2));
    console.log(`\nSaved ${companiesArray.length} companies to: ${RESULTS_FILE}`);

    // Save people too
    fs.writeFileSync(PEOPLE_FILE, JSON.stringify(progress.allPeople, null, 2));
    console.log(`Saved ${progress.allPeople.length} people to: ${PEOPLE_FILE}`);

  } catch (err) {
    console.error('\nFATAL ERROR:', err.message);
    saveProgress(progress);
    await page.screenshot({ path: path.join(OUT_DIR, 'apollo_god_error.png') });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
