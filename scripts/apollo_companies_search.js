/**
 * Apollo Companies Search — Internal API via Browser Session
 *
 * Uses Apollo's internal API (POST /api/v1/mixed_companies/search) from within
 * a Puppeteer browser session. Much faster and more reliable than DOM scraping.
 *
 * Key advantage over apollo_universal_search.js:
 *   - Uses internal API instead of UI grid scraping
 *   - q_organization_keyword_tags for precise keyword matching
 *   - Stealth plugin + saved profile (avoids CAPTCHA + email verify)
 *   - Structured JSON response (not fragile DOM selectors)
 *
 * Usage:
 *   # Search by keyword tags + locations (universal)
 *   node scripts/apollo_companies_search.js \
 *     --keywords "influencer marketing platform,creator analytics,UGC platform" \
 *     --locations "United Kingdom,India,France" \
 *     --sizes "5,50" --sizes "51,200" --sizes "201,500" --sizes "501,1000" --sizes "1001,5000" \
 *     --max-pages 25 \
 *     --output /tmp/companies.json
 *
 *   # Single keyword test
 *   node scripts/apollo_companies_search.js \
 *     --keywords "influencer marketing platform" \
 *     --locations "United Kingdom" \
 *     --max-pages 3 \
 *     --output /tmp/test.json
 *
 *   # With saved profile (skip login)
 *   node scripts/apollo_companies_search.js \
 *     --profile /tmp/puppeteer_dev_chrome_profile-lHTfSP \
 *     --keywords "creator economy" \
 *     --locations "India" \
 *     --output /tmp/test.json
 *
 *   # Resume interrupted search
 *   node scripts/apollo_companies_search.js \
 *     --keywords "..." --locations "..." \
 *     --output /tmp/companies.json --resume
 *
 *   # Config file (all params in JSON)
 *   node scripts/apollo_companies_search.js --config /tmp/search_config.json
 *
 * Config file format:
 *   {
 *     "keywords": ["influencer marketing platform", "creator analytics"],
 *     "locations": ["United Kingdom", "India"],
 *     "sizes": ["5,50", "51,200"],
 *     "max_pages": 25,
 *     "output": "/tmp/companies.json"
 *   }
 *
 * Output: JSON array of company objects with fields:
 *   id, name, domain, linkedin_url, phone, logo_url, industries,
 *   estimated_num_employees, keywords, city, state, country
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// ================================================================
//  PARSE ARGS
// ================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    keywords: [],
    locations: [],
    sizes: ['5,50', '51,200', '201,500', '501,1000', '1001,5000'],
    maxPages: 25,
    output: null,
    progressFile: null,
    profile: null,
    configFile: null,
    resume: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    if (arg === '--keywords' && next) {
      config.keywords.push(...next.split(',').map(k => k.trim()).filter(Boolean));
      i++;
    } else if (arg === '--locations' && next) {
      config.locations.push(...next.split(',').map(k => k.trim()).filter(Boolean));
      i++;
    } else if (arg === '--sizes' && next) {
      if (config.sizes[0] === '5,50' && config.sizes.length === 5) {
        config.sizes = []; // Reset default
      }
      config.sizes.push(next);
      i++;
    } else if (arg === '--max-pages' && next) {
      config.maxPages = parseInt(next) || 25;
      i++;
    } else if (arg === '--output' && next) {
      config.output = next;
      i++;
    } else if (arg === '--profile' && next) {
      config.profile = next;
      i++;
    } else if (arg === '--config' && next) {
      config.configFile = next;
      i++;
    } else if (arg === '--resume') {
      config.resume = true;
    }
  }

  // Load from config file if provided
  if (config.configFile && fs.existsSync(config.configFile)) {
    const fileConfig = JSON.parse(fs.readFileSync(config.configFile, 'utf8'));
    if (fileConfig.keywords) config.keywords = fileConfig.keywords;
    if (fileConfig.locations) config.locations = fileConfig.locations;
    if (fileConfig.sizes) config.sizes = fileConfig.sizes;
    if (fileConfig.max_pages) config.maxPages = fileConfig.max_pages;
    if (fileConfig.output) config.output = fileConfig.output;
    if (fileConfig.profile) config.profile = fileConfig.profile;
  }

  // Validate
  if (config.keywords.length === 0) {
    console.error('ERROR: At least one --keywords is required');
    console.error('  Example: --keywords "influencer marketing platform,creator analytics"');
    process.exit(1);
  }
  if (config.locations.length === 0) {
    console.error('ERROR: At least one --locations is required');
    console.error('  Example: --locations "United Kingdom,India,France"');
    process.exit(1);
  }

  // Default output path
  if (!config.output) {
    const kwSlug = config.keywords[0].replace(/[^a-z0-9]+/gi, '_').substring(0, 20).toLowerCase();
    const locSlug = config.locations[0].replace(/[^a-z0-9]+/gi, '_').substring(0, 15).toLowerCase();
    config.output = path.join(__dirname, '..', 'gathering-data', `apollo_${kwSlug}_${locSlug}.json`);
  }

  // Progress file next to output
  config.progressFile = config.output.replace(/\.json$/, '_progress.json');

  return config;
}

// ================================================================
//  LOGIN
// ================================================================

async function login(page) {
  console.log(`[${ts()}] LOGIN: Starting...`);
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies') || url.includes('/sequences')) {
    console.log(`[${ts()}] LOGIN: Already logged in`);
    return;
  }

  // React-compatible input: page.type() doesn't trigger React state updates
  async function typeReact(selector, value) {
    await page.click(selector, { clickCount: 3 });
    await sleep(200);
    await page.evaluate((sel, val) => {
      const el = document.querySelector(sel);
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, selector, value);
    await sleep(300);
  }

  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await typeReact('input[name="email"]', APOLLO_EMAIL);
  await typeReact('input[name="password"]', APOLLO_PASS);
  await page.click('button[type="submit"]');
  console.log(`[${ts()}] LOGIN: Submitted, waiting...`);
  await sleep(5000);

  // Take debug screenshot right after submit
  await page.screenshot({ path: '/tmp/apollo_after_submit.png', fullPage: true });
  console.log(`[${ts()}] LOGIN: Post-submit URL: ${page.url()}`);

  // Verify login — wait up to 60 seconds
  for (let i = 0; i < 30; i++) {
    const u = page.url();
    if (u.includes('/people') || u.includes('/home') || u.includes('/companies') || u.includes('/sequences')) {
      console.log(`[${ts()}] LOGIN: Success`);
      return;
    }
    if (u.includes('verify-email') || u.includes('ato/verify')) {
      await page.screenshot({ path: '/tmp/apollo_verify_email.png', fullPage: true });
      throw new Error('Apollo requires email verification from this IP. Use --profile with a pre-authenticated browser profile. Screenshot: /tmp/apollo_verify_email.png');
    }
    if (i % 5 === 0 && i > 0) {
      console.log(`[${ts()}] LOGIN: Still waiting... URL: ${u}`);
    }
    await sleep(2000);
  }

  // Take screenshot on failure
  const screenshotPath = '/tmp/apollo_login_fail.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  throw new Error(`Login failed (stuck at: ${page.url()}). Screenshot: ${screenshotPath}`);
}

// ================================================================
//  INTERNAL API CALLS
// ================================================================

async function apiSearchCompanies(page, params) {
  return page.evaluate(async (searchParams) => {
    try {
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
//  SEARCH — paginate through all results for one keyword
// ================================================================

async function searchKeyword(page, keyword, locations, sizes, maxPages) {
  const allAccounts = [];
  let pageNum = 1;
  let totalEntries = null;

  while (pageNum <= maxPages) {
    const sessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });

    const params = {
      q_organization_keyword_tags: [keyword],
      organization_locations: locations,
      organization_num_employees_ranges: sizes,
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
      ui_finder_random_seed: Math.random().toString(36).substring(2, 15),
      cacheKey: Date.now(),
    };

    const result = await apiSearchCompanies(page, params);

    if (result.error) {
      console.log(`    p${pageNum}: ERROR ${result.error}`);
      if (result.status === 422 || result.status === 429) break;
      await sleep(5000);
      pageNum++;
      continue;
    }

    const accounts = result.accounts || [];
    totalEntries = result.pagination?.total_entries || totalEntries;

    if (accounts.length === 0) break;

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

    // Enrich with snippets
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
    } catch (e) { /* snippets are bonus data */ }

    if (pageNum === 1) {
      console.log(`    p1: ${accounts.length} companies (total: ${totalEntries})`);
      const names = accounts.slice(0, 3).map(a => a.name || '?').join(', ');
      console.log(`    First 3: ${names}`);
    } else if (pageNum % 10 === 0) {
      console.log(`    p${pageNum}: +${accounts.length} companies`);
    }

    if (accounts.length < 25) break;
    if (pageNum >= (result.pagination?.total_pages || Infinity)) break;

    pageNum++;
    await sleep(800 + Math.random() * 500);
  }

  return { companies: allAccounts, totalEntries: totalEntries || 0, pages: pageNum };
}

// ================================================================
//  DEDUP
// ================================================================

function dedup(companies) {
  const seen = new Map();
  for (const c of companies) {
    const key = (c.domain || '').toLowerCase().replace(/^www\./, '').replace(/\/+$/, '');
    if (!key || !key.includes('.')) {
      // Fallback to org id
      const idKey = c.id || c.name?.toLowerCase().replace(/[^a-z0-9]/g, '') || '';
      if (idKey && !seen.has(idKey)) seen.set(idKey, c);
      continue;
    }
    if (!seen.has(key)) {
      seen.set(key, c);
    } else {
      // Merge missing fields
      const existing = seen.get(key);
      if (!existing.industry && c.industry) existing.industry = c.industry;
      if (!existing.estimated_num_employees && c.estimated_num_employees) existing.estimated_num_employees = c.estimated_num_employees;
      if (!existing.city && c.city) existing.city = c.city;
      if (!existing.linkedin_url && c.linkedin_url) existing.linkedin_url = c.linkedin_url;
    }
  }
  return [...seen.values()];
}

// ================================================================
//  PROGRESS
// ================================================================

function loadProgress(progressFile) {
  try { return JSON.parse(fs.readFileSync(progressFile, 'utf8')); }
  catch { return { completed: [], companies: [] }; }
}

function saveProgress(progressFile, outputFile, progress) {
  const unique = dedup(progress.companies);
  fs.writeFileSync(progressFile, JSON.stringify({
    completed: progress.completed,
    stats: {
      rawCount: progress.companies.length,
      uniqueCount: unique.length,
      lastUpdated: new Date().toISOString(),
    },
  }, null, 2));
  fs.writeFileSync(outputFile, JSON.stringify(unique, null, 2));
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const config = parseArgs();

  console.log(`\n[${ts()}] === APOLLO COMPANIES SEARCH (Internal API) ===`);
  console.log(`  Keywords: ${config.keywords.length}`);
  console.log(`  Locations: ${config.locations.join(', ')}`);
  console.log(`  Sizes: ${config.sizes.join(', ')}`);
  console.log(`  Max pages/keyword: ${config.maxPages}`);
  console.log(`  Output: ${config.output}`);
  if (config.profile) console.log(`  Profile: ${config.profile}`);
  console.log();

  // Ensure output directory exists
  const outDir = path.dirname(config.output);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  // Browser launch options
  const launchOptions = {
    headless: 'new',
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: [
      '--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900',
      '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
    defaultViewport: { width: 1440, height: 900 },
  };

  // Use saved profile if provided (skips login, avoids Cloudflare/email verify)
  if (config.profile && fs.existsSync(config.profile)) {
    launchOptions.userDataDir = config.profile;
    console.log(`  Using saved profile: ${config.profile}`);
  }

  const browser = await puppeteer.launch(launchOptions);
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36');

  try {
    await login(page);

    // Navigate to companies page to establish session context
    await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(3000);

    // Load progress if resuming
    const progress = config.resume ? loadProgress(config.progressFile) : { completed: [], companies: [] };
    const remaining = config.keywords.filter(kw => !progress.completed.includes(kw));

    console.log(`  Total keywords: ${config.keywords.length}, remaining: ${remaining.length}`);
    if (progress.completed.length > 0) {
      console.log(`  Resumed: ${progress.completed.length} keywords already done`);
    }
    console.log();

    let searchNum = 0;
    for (const keyword of remaining) {
      searchNum++;
      console.log(`[${searchNum}/${remaining.length}] "${keyword}"`);

      try {
        const { companies, totalEntries, pages } = await searchKeyword(
          page, keyword, config.locations, config.sizes, config.maxPages
        );

        console.log(`    -> ${companies.length} companies from ${pages} pages (${totalEntries} available)`);

        if (companies.length > 0) {
          progress.companies.push(...companies);
        }
        progress.completed.push(keyword);

        // Save every 3 keywords
        if (searchNum % 3 === 0 || searchNum === remaining.length) {
          saveProgress(config.progressFile, config.output, progress);
          const unique = dedup(progress.companies);
          console.log(`\n  === Progress: ${unique.length} unique companies ===\n`);
        }

        await sleep(2000 + Math.random() * 2000);

      } catch (err) {
        console.log(`  ERROR: ${err.message}`);
        saveProgress(config.progressFile, config.output, progress);
        if (err.message.includes('timeout')) {
          await sleep(10000);
          try {
            await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
            await sleep(3000);
          } catch { break; }
        }
      }
    }

    // Final save + stats
    saveProgress(config.progressFile, config.output, progress);
    const unique = dedup(progress.companies);

    console.log(`\n[${ts()}] === FINAL RESULTS ===`);
    console.log(`  Raw scraped: ${progress.companies.length}`);
    console.log(`  After dedup: ${unique.length}`);
    console.log(`  With domain: ${unique.filter(c => c.domain).length}`);

    // Country distribution
    const countries = {};
    for (const c of unique) {
      const country = c.country || '(unknown)';
      countries[country] = (countries[country] || 0) + 1;
    }
    console.log('\n  Country distribution:');
    for (const [country, count] of Object.entries(countries).sort((a, b) => b[1] - a[1]).slice(0, 20)) {
      console.log(`    ${country}: ${count}`);
    }

    console.log(`\n  Saved: ${config.output} (${unique.length} companies)`);

  } catch (err) {
    console.error(`[${ts()}] FATAL: ${err.message}`);
    const screenshotPath = config.output.replace(/\.json$/, '_error.png');
    try { await page.screenshot({ path: screenshotPath, fullPage: true }); } catch {}
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error(`FATAL: ${err.message}`);
  process.exit(1);
});
