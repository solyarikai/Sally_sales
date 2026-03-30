/**
 * Apollo Companies Search — Direct API
 *
 * Uses Apollo's internal API directly (POST /api/v1/mixed_companies/search)
 * instead of DOM scraping. Much faster, richer data.
 *
 * Discovered API format:
 *   - Endpoint: POST /api/v1/mixed_companies/search
 *   - Auth: Session cookies from browser login
 *   - Returns: accounts[] (25/page), pagination.total_entries
 *   - Supplementary: POST /api/v1/organizations/load_snippets for industry/location
 *
 * Usage:
 *   node scripts/apollo_companies_search.js                     # run all keywords
 *   node scripts/apollo_companies_search.js --broad             # no keyword, just UAE + size
 *   node scripts/apollo_companies_search.js --keyword "agency"  # single keyword test
 *   node scripts/apollo_companies_search.js --max-pages 100     # more pages (default 25)
 *   node scripts/apollo_companies_search.js --resume            # resume from progress
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const OUT_DIR = path.join(__dirname, '..', 'easystaff-global', 'data');
const RESULTS_FILE = path.join(OUT_DIR, 'uae_companies_api_results.json');
const PROGRESS_FILE = path.join(OUT_DIR, 'uae_companies_api_progress.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ================================================================
//  KEYWORDS — optimized for Companies search
// ================================================================

const KEYWORDS = [
  // Service businesses (core ICP)
  'agency', 'studio', 'consulting', 'consultancy', 'outsourcing',

  // Digital & tech
  'software', 'digital', 'technology', 'IT services', 'SaaS',
  'app development', 'web development', 'cloud', 'AI',
  'cybersecurity', 'automation', 'DevOps',

  // Marketing & creative
  'marketing', 'branding', 'advertising', 'creative',
  'design', 'media', 'content', 'SEO', 'social media',
  'PR', 'communications',

  // Production
  'production', 'animation', 'film', 'video', 'photography',
  'VFX', 'broadcast',

  // Professional services
  'recruitment', 'staffing', 'talent', 'HR services',
  'accounting', 'audit', 'legal', 'translation',
  'training', 'coaching', 'research',

  // Tech verticals
  'fintech', 'edtech', 'healthtech', 'proptech', 'ecommerce',
  'logistics', 'insurtech', 'martech',
];

const SIZE_RANGES = ['1,10', '11,20', '21,50', '51,100', '101,200'];

// ================================================================
//  LOGIN
// ================================================================

async function login(page) {
  console.log('[LOGIN] Logging into Apollo...');
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies')) {
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
    const u = page.url();
    if (u.includes('/people') || u.includes('/home') || u.includes('/companies') || u.includes('/sequences')) {
      console.log('  Login successful');
      return;
    }
    await sleep(2000);
  }
  throw new Error('Login failed — stuck at: ' + page.url());
}

// ================================================================
//  DIRECT API CALLS
// ================================================================

async function apiSearchCompanies(page, params) {
  return page.evaluate(async (searchParams) => {
    try {
      // Get CSRF token
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.content : '';

      const res = await fetch('https://app.apollo.io/api/v1/mixed_companies/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Csrf-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify(searchParams),
      });

      if (!res.ok) {
        return { error: `HTTP ${res.status}`, status: res.status };
      }
      return await res.json();
    } catch (e) {
      return { error: e.message };
    }
  }, params);
}

async function apiLoadSnippets(page, orgIds) {
  if (!orgIds.length) return {};
  return page.evaluate(async (ids) => {
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.content : '';

      const res = await fetch('https://app.apollo.io/api/v1/organizations/load_snippets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Csrf-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({ ids }),
      });
      if (!res.ok) return {};
      return await res.json();
    } catch (e) {
      return {};
    }
  }, orgIds);
}

// ================================================================
//  SEARCH ONE CONFIG — paginate through all results
// ================================================================

async function searchAllPages(page, config, maxPages) {
  const allAccounts = [];
  let pageNum = 1;
  let totalEntries = null;

  while (pageNum <= maxPages) {
    // Generate unique session IDs per search to avoid caching
    const sessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
    const randomSeed = Math.random().toString(36).substring(2, 15);

    const params = {
      organization_locations: ['United Arab Emirates'],
      organization_num_employees_ranges: config.sizeRanges || SIZE_RANGES,
      sort_by_field: '[none]',
      sort_ascending: false,
      page: pageNum,
      per_page: 25,
      display_mode: 'explorer_mode',
      context: 'companies-index-page',
      open_factor_names: [],
      num_fetch_result: 1,
      show_suggestions: false,
      include_account_engagement_stats: false,
      finder_version: 2,
      search_session_id: sessionId,
      ui_finder_random_seed: randomSeed,
      cacheKey: Date.now(),
    };

    if (config.keyword) {
      // Try both keyword params — Apollo uses different ones
      params.q_keywords = config.keyword;
      params.q_organization_name = config.keyword;
    }

    const result = await apiSearchCompanies(page, params);

    if (result.error) {
      console.log(`    p${pageNum}: ERROR ${result.error}`);
      // Log first error's full detail for debugging
      if (pageNum === 1) {
        console.log(`    Debug: params = ${JSON.stringify({q_keywords: params.q_keywords, q_organization_name: params.q_organization_name, organization_locations: params.organization_locations})}`);
      }
      if (result.status === 422 || result.status === 429) break;
      await sleep(5000);
      continue;
    }

    const accounts = result.accounts || [];
    totalEntries = result.pagination?.total_entries || totalEntries;

    if (accounts.length === 0) break;

    // Extract company data — fields come directly from the accounts response
    // (we requested specific fields in the API call)
    for (const acc of accounts) {
      allAccounts.push({
        id: acc.organization_id || acc.id || '',
        name: acc.name || '',
        domain: acc.domain || acc.website_url || '',
        linkedin_url: acc.linkedin_url || '',
        phone: acc.phone || acc.sanitized_phone || '',
        logo_url: acc.logo_url || '',
        industries: acc.industries || [],
        estimated_num_employees: acc.estimated_num_employees || null,
        keywords: acc.keywords || [],
        city: acc.city || '',
        state: acc.state || '',
        country: acc.country || '',
      });
    }

    // Also try loading snippets for extra data (industry, address)
    try {
      const orgIds = accounts.map(a => a.organization_id || a.id).filter(Boolean);
      if (orgIds.length > 0) {
        const snippets = await apiLoadSnippets(page, orgIds);
        if (snippets.organizations) {
          for (const org of snippets.organizations) {
            const existing = allAccounts.find(a => a.id === org.id);
            if (existing) {
              if (!existing.industry && org.industry) existing.industry = org.industry;
              if (!existing.estimated_num_employees && org.estimated_num_employees) existing.estimated_num_employees = org.estimated_num_employees;
              if (!existing.city && org.city) existing.city = org.city;
              if (!existing.country && org.country) existing.country = org.country;
              if (org.keywords?.length) existing.keywords = org.keywords;
            }
          }
        }
      }
    } catch (e) { /* snippets are bonus data, don't fail on them */ }

    if (pageNum === 1) {
      console.log(`    p${pageNum}: ${accounts.length} companies (total available: ${totalEntries})`);
      // Debug: show first 3 company names to verify keyword filtering
      const names = accounts.slice(0, 3).map(a => a.name || '?').join(', ');
      console.log(`    First 3: ${names}`);
    } else if (pageNum % 10 === 0) {
      console.log(`    p${pageNum}: ${accounts.length} companies`);
    }

    if (accounts.length < 25) break;
    if (pageNum >= (result.pagination?.total_pages || Infinity)) break;

    pageNum++;
    // Rate limit — gentle delay
    await sleep(800 + Math.random() * 500);
  }

  console.log(`    → ${allAccounts.length} companies from ${pageNum} pages (${totalEntries} available)`);
  return { companies: allAccounts, totalEntries };
}

// ================================================================
//  PROGRESS
// ================================================================

function loadProgress() {
  try { return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8')); }
  catch { return { completed: [], allCompanies: [] }; }
}

function saveProgress(progress) {
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify({
    completed: progress.completed,
    stats: {
      rawCount: progress.allCompanies.length,
      uniqueCount: dedup(progress.allCompanies).length,
      lastUpdated: new Date().toISOString(),
    },
    // Save companies separately to avoid huge progress file
  }, null, 2));

  // Save all companies
  fs.writeFileSync(RESULTS_FILE, JSON.stringify(dedup(progress.allCompanies), null, 2));
}

function dedup(companies) {
  const seen = new Map();
  for (const c of companies) {
    const key = c.id || c.name?.toLowerCase().replace(/[^a-z0-9]/g, '') || '';
    if (!key) continue;
    if (!seen.has(key)) {
      seen.set(key, c);
    } else {
      const existing = seen.get(key);
      // Merge missing fields
      if (!existing.domain && c.domain) existing.domain = c.domain;
      if (!existing.industry && c.industry) existing.industry = c.industry;
      if (!existing.estimated_num_employees && c.estimated_num_employees) existing.estimated_num_employees = c.estimated_num_employees;
      if (!existing.city && c.city) existing.city = c.city;
      if (!existing.linkedin_url && c.linkedin_url) existing.linkedin_url = c.linkedin_url;
    }
  }
  return [...seen.values()];
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const args = process.argv.slice(2);
  const maxPages = args.includes('--max-pages') ? parseInt(args[args.indexOf('--max-pages') + 1]) : 25;
  const resume = args.includes('--resume');
  const broadMode = args.includes('--broad');
  const singleKeyword = args.includes('--keyword') ? args[args.indexOf('--keyword') + 1] : null;

  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  // Generate search configs
  const configs = [];
  if (singleKeyword) {
    configs.push({ id: `kw_${singleKeyword}`, label: `"${singleKeyword}"`, keyword: singleKeyword });
  } else if (broadMode) {
    // No keyword — just UAE + size ranges, broken down by size for pagination
    for (const size of SIZE_RANGES) {
      configs.push({
        id: `broad_${size}`,
        label: `ALL UAE companies ${size} employees`,
        keyword: null,
        sizeRanges: [size],
      });
    }
  } else {
    // All keywords
    for (const kw of KEYWORDS) {
      configs.push({ id: `kw_${kw.trim()}`, label: `"${kw.trim()}"`, keyword: kw.trim() });
    }
    // Also run broad (no keyword) per size range
    for (const size of SIZE_RANGES) {
      configs.push({
        id: `broad_${size}`,
        label: `ALL UAE companies ${size} employees`,
        keyword: null,
        sizeRanges: [size],
      });
    }
  }

  console.log('\n=== APOLLO COMPANIES API SEARCH — UAE ===');
  console.log(`Search configs: ${configs.length}`);
  console.log(`Max pages per search: ${maxPages}`);
  console.log(`Max companies per search: ${maxPages * 25}`);

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

    // Need to navigate to a page first so page.evaluate has the right cookies/context
    await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(3000);

    const progress = resume ? loadProgress() : { completed: [], allCompanies: [] };
    const remaining = configs.filter(c => !progress.completed.includes(c.id));
    console.log(`Remaining: ${remaining.length} (${progress.completed.length} done)\n`);

    let searchNum = 0;
    for (const config of remaining) {
      searchNum++;
      console.log(`[${searchNum}/${remaining.length}] ${config.label}`);

      try {
        const { companies, totalEntries } = await searchAllPages(page, config, maxPages);

        if (companies.length > 0) {
          progress.allCompanies.push(...companies);
        }
        progress.completed.push(config.id);

        // Save every 3 searches
        if (searchNum % 3 === 0 || searchNum === remaining.length) {
          saveProgress(progress);
          const unique = dedup(progress.allCompanies);
          console.log(`\n  === Progress: ${unique.length} unique companies ===\n`);
        }

        await sleep(2000 + Math.random() * 2000);

      } catch (err) {
        console.log(`  ERROR: ${err.message}`);
        saveProgress(progress);
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
    console.log('\n\n=== FINAL RESULTS ===');
    const unique = dedup(progress.allCompanies);
    console.log(`Raw scraped: ${progress.allCompanies.length}`);
    console.log(`After dedup: ${unique.length}`);
    console.log(`With domain: ${unique.filter(c => c.domain).length}`);
    console.log(`With industry: ${unique.filter(c => c.industry).length}`);
    console.log(`With city: ${unique.filter(c => c.city).length}`);
    console.log(`With employees: ${unique.filter(c => c.estimated_num_employees).length}`);

    // City distribution
    const cities = {};
    for (const c of unique) {
      const city = c.city || '(unknown)';
      cities[city] = (cities[city] || 0) + 1;
    }
    console.log('\nCity distribution:');
    for (const [city, count] of Object.entries(cities).sort((a, b) => b[1] - a[1]).slice(0, 15)) {
      console.log(`  ${city}: ${count}`);
    }

    // Industry distribution
    const industries = {};
    for (const c of unique) {
      const ind = c.industry || '(unknown)';
      industries[ind] = (industries[ind] || 0) + 1;
    }
    console.log('\nTop industries:');
    for (const [ind, count] of Object.entries(industries).sort((a, b) => b[1] - a[1]).slice(0, 20)) {
      console.log(`  ${ind}: ${count}`);
    }

    // Size distribution
    const sizes = { '1-10': 0, '11-50': 0, '51-100': 0, '101-200': 0, '200+': 0, 'unknown': 0 };
    for (const c of unique) {
      const emp = c.estimated_num_employees || 0;
      if (emp === 0) sizes['unknown']++;
      else if (emp <= 10) sizes['1-10']++;
      else if (emp <= 50) sizes['11-50']++;
      else if (emp <= 100) sizes['51-100']++;
      else if (emp <= 200) sizes['101-200']++;
      else sizes['200+']++;
    }
    console.log('\nSize distribution:');
    for (const [range, count] of Object.entries(sizes)) {
      console.log(`  ${range}: ${count}`);
    }

    saveProgress(progress);
    console.log(`\nSaved ${unique.length} companies to ${RESULTS_FILE}`);

  } catch (err) {
    console.error('FATAL:', err.message);
    await page.screenshot({ path: path.join(OUT_DIR, 'apollo_api_error.png'), fullPage: true });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
